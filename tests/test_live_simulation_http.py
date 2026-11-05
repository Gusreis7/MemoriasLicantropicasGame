"""Transport contract tests; test doubles never run in the live product runner."""
import asyncio
import json

import httpx
import pytest

from src.simulation.session import LiveSession

pytestmark = pytest.mark.anyio


class PublicAPI:
    def __init__(self):
        self.requests = []
        self.case = {'status': 'active', 'day': 1, 'ending': None, 'inventory': [], 'crimes': [],
                     'testimonies': [], 'accusations': [], 'achievements': []}
        self.world = {'location': {'width': 960}, 'revision': 1,
                      'player': {'location_id': 'praca_verde', 'x': 160, 'movement_seq': 0}}
        self.movement_directions = []
        self.reject_move = False

    def handle(self, request):
        path = request.url.path
        self.requests.append((request.method, path))
        body = json.loads(request.content) if request.content else None
        if path == '/api/v1/world/locations':
            data = []
        elif request.method == 'POST' and path == '/api/v1/games':
            data = {'id': 'game-contract'}
        elif path.endswith('/investigation/skip-day'):
            self.case.update(status='lost', day=2, ending={'result': 'lost'})
            data = self.case
        elif path.endswith('/investigation'):
            data = self.case
        elif path.endswith('/world'):
            data = self.world
        elif path.endswith('/social/reports'):
            data = {'reports': []}
        elif path.endswith('/movement'):
            self.movement_directions.append(body['direction'])
            if self.reject_move and body['direction'] != 'idle':
                return httpx.Response(409, json={'detail': 'phase changed'})
            self.world['revision'] += 1
            self.world['player']['movement_seq'] = body['seq']
            data = self.world
        elif path.endswith('/games/game-contract'):
            data = {'id': 'game-contract', 'characters': []}
        else:
            return httpx.Response(404, json={'detail': 'Not found'})
        return httpx.Response(200, json=data)


class RecordingAgent:
    stats = {}

    def __init__(self, action):
        self.action = action
        self.observations = []

    async def decide(self, observation):
        self.observations.append(observation)
        return self.action


async def test_only_public_http_observations_and_real_terminal_response(tmp_path):
    api = PublicAPI()
    agent = RecordingAgent({'action': 'skip_day'})
    result = await LiveSession('http://game.test', agent, tmp_path,
                               max_steps=1, transport=httpx.MockTransport(api.handle)).run(1)
    assert result['status'] == 'completed' and result['result'] == 'lost'
    assert result['steps'] == 1
    assert len(agent.observations) == 1
    assert all('/admin' not in path for _, path in api.requests)
    assert set(agent.observations[0]) >= {'case', 'world', 'cast', 'locations', 'actions'}
    events = [json.loads(line) for line in (tmp_path / 'session-0001/events.jsonl').read_text().splitlines()]
    assert any(event['type'] == 'decision' for event in events)
    assert json.loads((tmp_path / 'session-0001/session.json').read_text())['status'] == 'completed'


async def test_step_limit_is_not_a_forced_game_defeat(tmp_path):
    api = PublicAPI()
    agent = RecordingAgent({'action': 'observe'})
    result = await LiveSession('http://game.test', agent, tmp_path, max_steps=1,
                               transport=httpx.MockTransport(api.handle)).run(1)
    assert result['status'] == 'stopped' and result['stop_reason'] == 'step_limit'
    assert result['result'] is None and api.case['status'] == 'active'
    assert all(method == 'GET' or path == '/api/v1/games' for method, path in api.requests)


async def test_timeout_preserves_partial_report_without_changing_motor(tmp_path):
    api = PublicAPI()
    agent = RecordingAgent({'action': 'wait', 'seconds': 30})
    result = await LiveSession('http://game.test', agent, tmp_path, max_seconds=.02,
                               transport=httpx.MockTransport(api.handle)).run(1)
    assert result['stop_reason'] == 'time_limit' and result['status'] == 'stopped'
    assert api.case['status'] == 'active'
    assert (tmp_path / 'session-0001/events.jsonl').exists()


async def test_cancel_preserves_report(tmp_path):
    api = PublicAPI()
    ready = asyncio.Event()

    class SlowAgent:
        async def decide(self, observation):
            ready.set()
            await asyncio.Event().wait()

    session = LiveSession('http://game.test', SlowAgent(), tmp_path, transport=httpx.MockTransport(api.handle))
    task = asyncio.create_task(session.run(1))
    await ready.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    report = json.loads((tmp_path / 'session-0001/session.json').read_text())
    assert report['status'] == 'stopped' and report['stop_reason'] == 'cancelled'
    assert report['result'] is None


async def test_movement_rejection_still_attempts_idle(tmp_path):
    api = PublicAPI()
    api.reject_move = True
    agent = RecordingAgent({'action': 'move', 'x': 400})
    result = await LiveSession('http://game.test', agent, tmp_path, max_steps=1,
                               transport=httpx.MockTransport(api.handle)).run(1)
    assert api.movement_directions == ['right', 'idle']
    assert result['status'] == 'stopped' and len(result['action_errors']) == 1


async def test_http_auth_error_does_not_fabricate_terminal_result(tmp_path):
    api = PublicAPI()

    def unavailable(request):
        if request.url.path.endswith('/approaches'):
            return httpx.Response(503, json={'code': 'llm_credentials_unavailable', 'detail': 'Login required'})
        return api.handle(request)

    agent = RecordingAgent({'action': 'dialogue', 'npc_id': 'capitu', 'content': 'O que sabe?'})
    result = await LiveSession('http://game.test', agent, tmp_path, max_steps=1,
                               transport=httpx.MockTransport(unavailable)).run(1)
    assert result['status'] == 'error' and result['result'] is None
    assert result['stop_reason'] == 'llm_credentials_unavailable'
    assert result['action_errors'][0]['error']['code'] == 'llm_credentials_unavailable'
    assert result['dialogue_turns'] == 0
