"""Partidas completas: nenhuma fixture injeta vitória, pista ou voto no estado."""

import json
from types import SimpleNamespace
from uuid import uuid4

import fakeredis
import pytest

from memorias_licantropicas.simulation.session import (
    BudgetedSessionModel,
    OfflineSessionModel,
    SessionSimulation,
    public_ranking,
    run_sessions,
)
from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.contracts.model import ChatMessage

pytestmark = pytest.mark.anyio


async def test_complete_investigation_executes_dialogue_graph_and_persists_the_session():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    try:
        simulation = SessionSimulation(redis, "test:full-session", 20261105)
        result = await simulation.play("investigator")
        assert result["result"] == "won"
        assert result["ending_method"] == "detention"
        assert result["day"] >= 2
        for action in (
            "create_game",
            "walk",
            "travel",
            "dialogue",
            "search",
            "inspect",
            "present",
            "interrogate",
            "review",
            "accuse",
            "morning",
        ):
            assert result["actions"].get(action, 0) > 0, action
        assert result["persisted_player_messages"] >= 4
        assert result["graph_traces"] > 0, (
            "The runner must execute LangGraph, not just the pure rules"
        )
        assert result["npc_social_messages"] > 0
        assert result["knowledge_entries"] > 0
        for task in (
            "npc_dialogue",
            "session_assessment",
            "knowledge_extraction",
            "social_speech",
        ):
            assert result["llm_calls_by_task"].get(task, 0) > 0, task
        assert result["errors"] == []
        assert "deposited_by" not in json.dumps(result["trace"])
        assert "werewolf_audit_after_game" not in json.dumps(result["trace"])
    finally:
        await redis.aclose()


async def test_passive_player_loses_after_real_nights_and_still_has_conversations():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    try:
        result = await SessionSimulation(redis, "test:passive-session", 20261108).play(
            "passive"
        )
        assert result["result"] == "lost"
        assert result["actions"]["morning"] >= 4
        assert result["actions"]["dialogue"] > 0
        assert result["actions"].get("accuse", 0) == 0
        assert result["persisted_player_messages"] > 0
        assert result["graph_traces"] > 0
    finally:
        await redis.aclose()


async def test_invalid_provider_json_is_retried_inside_a_full_game():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    try:
        result = await SessionSimulation(
            redis, "test:repair-session", 20261105, fault="invalid_json_once"
        ).play("investigator")
        assert result["result"] in {"won", "lost"}
        assert result["injected_faults"] == 1
        assert result["actions"]["dialogue"] > 0
        assert result["graph_traces"] > 0
        assert result["errors"] == []
    finally:
        await redis.aclose()


async def test_authentication_failure_does_not_fabricate_an_npc_answer():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    try:
        result = await SessionSimulation(
            redis, "test:auth-session", 20261108, fault="authentication"
        ).play("passive")
        assert result["result"] == "lost"
        assert result["actions"]["dialogue_error"] > 0
        assert result["actions"].get("dialogue", 0) == 0
        assert result["persisted_player_messages"] == 0
        assert all(
            error["code"] == "llm_authentication_failed" for error in result["errors"]
        )
    finally:
        await redis.aclose()


async def test_run_uses_exclusive_redis_prefix_and_never_flushes_local_games(
    monkeypatch,
):
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    await redis.set("real-game:must-stay", "untouched")
    closed = []
    original_close = redis.aclose

    async def record_close():
        closed.append(True)

    monkeypatch.setattr(redis, "aclose", record_close)
    monkeypatch.setattr(
        "memorias_licantropicas.simulation.session.fakeredis.FakeAsyncRedis",
        lambda **kwargs: redis,
    )
    try:
        report = await run_sessions(count=1, seed=20261108, faults=False)
        assert report["summary"]["terminal_games"] == 1
        assert report["summary"]["real_aws_calls"] == 0
        assert report["summary"]["actual_aws_cost_usd"] == "0"
        assert await redis.get("real-game:must-stay") == "untouched"
        assert not [
            key async for key in redis.scan_iter(match="ml:session-simulation:*")
        ]
        assert closed
    finally:
        await original_close()


async def test_live_call_budget_is_shared_and_blocks_before_calling_provider():
    provider = OfflineSessionModel()
    client = BudgetedSessionModel(provider, 1)
    messages = (
        ChatMessage(role="system", content="[task:session_assessment]"),
        ChatMessage(role="user", content='{"personagem":"Bom dia"}'),
    )
    await client.complete(messages)
    with pytest.raises(LLMUnavailableError):
        await client.complete(messages)
    assert sum(provider.calls.values()) == 1
    assert client.exhausted


def test_public_policy_ignores_repeated_types_and_private_fields():
    first, repeated, personal = uuid4(), uuid4(), uuid4()
    case = SimpleNamespace(
        inventory=(
            SimpleNamespace(id=first, item_id="coin", kind="common"),
            SimpleNamespace(id=repeated, item_id="coin", kind="common"),
            SimpleNamespace(id=personal, item_id="ring", kind="unique"),
        ),
        testimonies=tuple(
            SimpleNamespace(
                evidence_id=identifier,
                witness_id=witness,
                recognition="recognizes",
                claimed_owner_id="capitu",
            )
            for identifier, witness in (
                (first, "bentinho"),
                (repeated, "bentinho"),
                (personal, "virgilia"),
            )
        ),
        accusations=(),
        journal=(),
        expelled_npc_ids=(),
    )
    result = public_ranking(case, {"capitu", "escobar"})
    assert result[0] == {"npc_id": "capitu", "score": 6, "types": 2, "sources": 2}
