"""Contratos do jogador LLM; transporte dublê exclusivo da suíte, sem AWS."""
import asyncio
import importlib.util
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.contracts.model import LLMResponse
from src.simulation.model import (
    AgentDecisionError, BudgetedSessionModel, CallBudgetExceeded, FlorianoAction,
    FlorianoAgent,
)

pytestmark = pytest.mark.anyio


class NativeClient:
    def __init__(self, invalid_before=0):
        self.calls = 0
        self.invalid_before = invalid_before
        self.messages = []

    async def complete(self, messages, *, tools=(), tool_choice=None):
        self.calls += 1
        self.messages.append(messages)
        assert len(tools) == 1 and tool_choice == 'required'
        if self.calls <= self.invalid_before:
            return LLMResponse(content='{"action":"skip_day"}', model='test', input_tokens=10, output_tokens=4)
        return LLMResponse(tool_calls=({'name': tools[0]['function']['name'],
            'args': {'action': 'dialogue', 'npc_id': 'capitu', 'content': 'Onde estava ontem?'},
            'id': str(self.calls), 'type': 'tool_call'},), model='test', input_tokens=10, output_tokens=4)

    async def aclose(self):
        pass


@pytest.mark.parametrize('arguments', [
    {'action': 'move'}, {'action': 'dialogue', 'npc_id': 'capitu'},
    {'action': 'accuse'}, {'action': 'skip_day', 'killer_id': 'capitu'},
    {'action': 'wait', 'seconds': '4'}, {'action': 'travel', 'target_location_id': ''},
])
def test_action_contract_rejects_missing_arguments_and_extra_secrets(arguments):
    with pytest.raises(ValidationError):
        FlorianoAction.model_validate(arguments)


async def test_native_retry_uses_budget_and_preserves_observation():
    client = NativeClient(invalid_before=1)
    budget = BudgetedSessionModel(client, 2, input_price=0.15, output_price=0.6)
    agent = FlorianoAgent(budget)
    observation = {'case': {'day': 1}, 'heard': ['Capitu disse estar no cais.']}
    action = await agent.decide(observation)
    assert action['action'] == 'dialogue' and action['npc_id'] == 'capitu'
    assert budget.stats['calls'] == budget.stats['completed'] == 2
    assert budget.stats['input_tokens'] == 20
    assert budget.stats['output_tokens'] == 8
    assert budget.stats['estimated_cost_usd'] > 0
    assert 'heard' in client.messages[0][-1].content
    with pytest.raises(CallBudgetExceeded):
        await agent.decide(observation)
    assert client.calls == 2


async def test_no_static_decision_when_provider_returns_text_instead_of_tool():
    budget = BudgetedSessionModel(NativeClient(invalid_before=5), 3)
    with pytest.raises(AgentDecisionError):
        await FlorianoAgent(budget).decide({'case': {'day': 1}})
    assert budget.stats['calls'] == 2


async def test_budget_counts_failed_transport_and_is_global_across_agents():
    class FailedClient(NativeClient):
        async def complete(self, *args, **kwargs):
            raise RuntimeError('test transport failed')
    budget = BudgetedSessionModel(FailedClient(), 1)
    with pytest.raises(RuntimeError):
        await FlorianoAgent(budget).decide({})
    with pytest.raises(CallBudgetExceeded):
        await FlorianoAgent(budget).decide({})
    assert budget.stats['failed'] == 1 and budget.stats['calls'] == 1
    assert budget.stats['cost_complete'] is False
    assert budget.stats['missing_tokens'] == 2


def load_runner():
    path = Path(__file__).resolve().parents[1] / 'scripts/run_session_simulations.py'
    spec = importlib.util.spec_from_file_location('live_session_runner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batch_report_distinguishes_incomplete_games_and_aggregates_known_usage(tmp_path):
    runner = load_runner()
    args = SimpleNamespace(api_url='http://localhost:7079', games=3, max_live_calls=10,
                           max_steps=5, max_seconds=30)
    results = [
        {'status': 'completed', 'result': 'won', 'day': 3, 'action_counts': {'dialogue': 2},
         'server_statistics': {'available': True, 'usage': {'totals': {'calls': 8,
             'known_input_tokens': 200, 'known_estimated_cost_usd': '0.01'}}}},
        {'status': 'stopped', 'result': None, 'stop_reason': 'max_steps', 'action_counts': {'dialogue': 1}},
    ]
    report = runner.make_report(results, SimpleNamespace(stats={'calls': 3}), perf_counter(), 'interrupted', args)
    assert report['summary']['completed_games'] == 1
    assert report['summary']['lost'] == 0
    assert report['summary']['win_rate_completed'] == 1
    assert report['summary']['action_counts'] == {'dialogue': 3}
    assert report['summary']['server_usage']['totals']['calls'] == 8
    runner.write_json(tmp_path / 'summary.json', report)
    assert (tmp_path / 'summary.json').is_file()
    assert not (tmp_path / 'summary.json.tmp').exists()


def test_cli_rejects_zero_budget_and_offline_flag():
    runner = load_runner()
    for arguments in (['--games', '1', '--max-live-calls', '0'],
                      ['--games', '1', '--max-live-calls', '1', '--no-faults']):
        with pytest.raises(SystemExit):
            runner.parser().parse_args(arguments)
