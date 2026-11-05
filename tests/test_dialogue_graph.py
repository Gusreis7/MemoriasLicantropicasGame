"""Execução real do StateGraph com modelos simulados e persistência Redis isolada."""

from native_fixtures import tool_response, respond_to_tools, invalid_tool_response

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from memorias_licantropicas.contracts.errors import ConflictError, LLMUnavailableError
from memorias_licantropicas.contracts.model import LLMResponse
from memorias_licantropicas.modules.agents.trace import RedisDialogueTraceRecorder
from memorias_licantropicas.modules.agents.workflow import TECHNICAL_FALLBACK
from memorias_licantropicas.modules.session_master.service import DialogueAssessment

pytestmark = pytest.mark.anyio


async def capture_traces(harness):
    traces = []

    async def record(trace):
        traces.append(trace)

    harness._trace_sink = record
    return traces


def speech(text="Bom dia, Floriano."):
    return tool_response({"fala": text}, "NpcSpeech", model="simulated")


async def test_graph_has_separate_conditional_stages_and_success_trace(
    harness, storage, game
):
    await storage.games.create(game)
    traces = await capture_traces(harness)
    reply = await harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia")
    assert not reply.message.useful
    assert traces[0].nodes == (
        "authorize",
        "input_guard",
        "context",
        "generate",
        "master_review",
        "semantic_validation",
        "output_guard",
        "persist",
    )
    assert traces[0].status == "completed" and traces[0].attempts == 1
    assert not traces[0].fallback
    graph = harness.graph.get_graph()
    assert {
        "repair",
        "fallback",
        "error",
        "master_review",
        "semantic_validation",
    } <= set(graph.nodes)
    assert any(edge.conditional for edge in graph.edges)
    assert "Ficha privada" not in traces[0].model_dump_json()


async def test_parse_failure_has_two_attempts_and_noninvestigative_fallback(
    harness, storage, game, llm
):
    await storage.games.create(game)
    traces = await capture_traces(harness)
    llm.complete = AsyncMock(
        return_value=tool_response({"fala": 7}, "NpcSpeech", model="simulated")
    )
    conversation_id = uuid4()
    reply = await harness.respond(
        game.id, "bentinho", conversation_id, "player", "Bom dia"
    )
    assert reply.message.content == TECHNICAL_FALLBACK
    assert not reply.message.narrative_authorized and not reply.message.useful
    assert reply.model == "dialogue-fallback" and llm.complete.await_count == 2
    assert traces[0].error_code == "invalid_schema" and traces[0].fallback
    assert traces[0].nodes[-2:] == ("fallback", "persist")
    assert (
        len(await storage.memory.list_messages(game.id, conversation_id, "player")) == 2
    )


async def test_authentication_failure_keeps_exchange_unwritten(
    harness, storage, game, llm
):
    await storage.games.create(game)
    traces = await capture_traces(harness)
    llm.complete = AsyncMock(
        side_effect=LLMUnavailableError("not public", code="llm_authentication_failed")
    )
    conversation_id = uuid4()
    with pytest.raises(LLMUnavailableError) as error:
        await harness.respond(game.id, "bentinho", conversation_id, "player", "Bom dia")
    assert error.value.code == "llm_authentication_failed"
    assert llm.complete.await_count == 1
    assert await storage.memory.list_messages(game.id, conversation_id, "player") == ()
    assert traces[0].status == "error" and traces[0].nodes[-1] == "error"
    assert "not public" not in traces[0].model_dump_json()


async def test_one_semantic_repair_then_persist_valid_persona_speech(
    harness, storage, game, llm
):
    await storage.games.create(game)
    traces = await capture_traces(harness)
    llm.complete = AsyncMock(
        side_effect=[
            speech("A cidade é cheia de sombras."),
            speech("Bom dia, Floriano."),
        ]
    )
    saved = []

    async def persist(game_id, npc_id, conversation_id, incoming, outgoing, assessment):
        saved.append(assessment)
        await storage.memory.append_messages(
            game_id, conversation_id, (incoming, outgoing)
        )

    harness._session_master = SimpleNamespace(
        reconcile=AsyncMock(),
        can_disclose_role=AsyncMock(return_value=False),
        assess=AsyncMock(
            side_effect=[
                DialogueAssessment(issues=("off_topic",)),
                DialogueAssessment(),
            ]
        ),
        persist_exchange=persist,
    )
    reply = await harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia")
    assert reply.message.content == "Bom dia, Floriano."
    assert traces[0].nodes.count("repair") == 1 and traces[0].attempts == 2
    assert len(saved) == 1 and not saved[0].issues
    prompt = llm.complete.await_args_list[-1].args[0]
    assert any("[task:dialogue_repair]" in message.content for message in prompt)
    assert not any(
        "A cidade é cheia de sombras." in message.content for message in prompt
    )


async def test_semantic_repair_is_bounded_and_never_persists_rejected_story(
    harness, storage, game, llm
):
    await storage.games.create(game)
    traces = await capture_traces(harness)
    llm.complete = AsyncMock(return_value=speech("Digo algo fora do assunto."))
    records = []
    harness._session_master = SimpleNamespace(
        reconcile=AsyncMock(),
        can_disclose_role=AsyncMock(return_value=False),
        assess=AsyncMock(return_value=DialogueAssessment(issues=("off_topic",))),
        persist_exchange=AsyncMock(side_effect=lambda *args: records.append(args[-1])),
    )
    reply = await harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia")
    assert reply.message.content == TECHNICAL_FALLBACK
    assert llm.complete.await_count == 2 and traces[0].nodes.count("repair") == 1
    assert (
        records[0].kind == "conversation"
        and not records[0].useful
        and not records[0].discovery_ids
    )


async def test_degraded_master_review_uses_explicit_fallback(harness, storage, game):
    await storage.games.create(game)
    traces = await capture_traces(harness)
    harness._session_master = SimpleNamespace(
        reconcile=AsyncMock(),
        assess=AsyncMock(
            return_value=SimpleNamespace(source="fallback", error_code="invalid_json")
        ),
        can_disclose_role=AsyncMock(),
        persist_exchange=AsyncMock(),
    )
    reply = await harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia")
    assert (
        reply.message.content == TECHNICAL_FALLBACK
        and not reply.message.narrative_authorized
    )
    assert traces[0].error_code == "invalid_json"
    harness._session_master.can_disclose_role.assert_not_awaited()


async def test_night_boundary_revalidated_before_persistence(harness, storage, game):
    await storage.games.create(game)
    harness._day_policy = SimpleNamespace(
        assert_dialogue_open=AsyncMock(side_effect=[None, ConflictError("Anoiteceu")])
    )
    conversation_id = uuid4()
    with pytest.raises(ConflictError):
        await harness.respond(game.id, "bentinho", conversation_id, "player", "Bom dia")
    assert await storage.memory.list_messages(game.id, conversation_id, "player") == ()


async def test_total_turn_timeout_cancels_inference_without_partial_messages(
    harness, storage, game, llm
):
    await storage.games.create(game)
    traces = await capture_traces(harness)
    cancelled = asyncio.Event()

    async def slow_model(messages):
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.set()

    llm.complete = slow_model
    harness._turn_timeout_seconds = 0.03
    conversation_id = uuid4()
    with pytest.raises(LLMUnavailableError) as error:
        await harness.respond(game.id, "bentinho", conversation_id, "player", "Bom dia")
    assert error.value.code == "llm_timeout" and cancelled.is_set()
    assert traces[0].status == "error" and traces[0].error_code == "llm_timeout"
    assert await storage.memory.list_messages(game.id, conversation_id, "player") == ()


async def test_external_cancellation_is_preserved(harness, storage, game, llm):
    await storage.games.create(game)
    traces = await capture_traces(harness)
    started = asyncio.Event()

    async def blocked(messages):
        started.set()
        await asyncio.Event().wait()

    llm.complete = blocked
    conversation_id = uuid4()
    task = asyncio.create_task(
        harness.respond(game.id, "bentinho", conversation_id, "player", "Bom dia")
    )
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert traces[0].status == "cancelled" and traces[0].attempts == 1
    assert await storage.memory.list_messages(game.id, conversation_id, "player") == ()


async def test_shared_compiled_graph_isolates_concurrent_games_and_prompts(
    harness, storage, game, llm
):
    second = game.model_copy(update={"id": uuid4()})
    await storage.games.create(game)
    await storage.games.create(second)
    traces = await capture_traces(harness)
    arrived, prompts = asyncio.Event(), []

    async def concurrent_model(messages):
        prompts.append(messages)
        if len(prompts) == 2:
            arrived.set()
        await asyncio.wait_for(arrived.wait(), 2)
        return speech()

    llm.complete = concurrent_model
    first_conversation, second_conversation = uuid4(), uuid4()
    await asyncio.gather(
        harness.respond(
            game.id, "bentinho", first_conversation, "player", "Entrevista alfa"
        ),
        harness.respond(
            second.id, "capitu", second_conversation, "player", "Entrevista beta"
        ),
    )
    for messages in prompts:
        combined = " ".join(m.content for m in messages)
        assert ("Entrevista alfa" in combined) != ("Entrevista beta" in combined)
    assert len({trace.invocation_id for trace in traces}) == 2
    assert {trace.game_id for trace in traces} == {game.id, second.id}
    assert all(trace.nodes.count("generate") == 1 for trace in traces)
    assert (await storage.memory.list_messages(game.id, first_conversation, "player"))[
        0
    ].content == "Entrevista alfa"
    assert (
        await storage.memory.list_messages(second.id, second_conversation, "player")
    )[0].content == "Entrevista beta"


async def test_trace_is_persisted_for_admin_without_private_content(
    harness, storage, game
):
    await storage.games.create(game)
    harness._trace_sink = RedisDialogueTraceRecorder(
        storage.client, storage.prefix
    ).record
    await harness.respond(
        game.id, "bentinho", uuid4(), "player", "Pergunta particular do jogador"
    )
    records = [
        json.loads(raw)
        for raw in await storage.client.lrange(
            f"{storage.prefix}:game:{{{game.id}}}:events", 0, -1
        )
    ]
    trace = next(record for record in records if record["type"] == "llm.dialogue.graph")
    assert trace["data"]["status"] == "completed"
    assert "Pergunta particular" not in json.dumps(trace)
    assert not {"prompt", "content", "role", "fala"} & set(trace["data"])


async def test_trace_sink_failure_does_not_mask_authentication_error(
    harness, storage, game, llm, caplog
):
    await storage.games.create(game)

    async def broken_trace(trace):
        raise RuntimeError("PRIVATE_OBSERVER_BODY")

    harness._trace_sink = broken_trace
    llm.error = LLMUnavailableError("auth", code="llm_authentication_failed")
    with pytest.raises(LLMUnavailableError) as error:
        await harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia")
    assert error.value.code == "llm_authentication_failed"
    assert "PRIVATE_OBSERVER_BODY" not in caplog.text


async def test_trace_sink_has_a_separate_bounded_deadline(
    harness, storage, game, monkeypatch
):
    import memorias_licantropicas.modules.agents.workflow as workflow

    await storage.games.create(game)
    monkeypatch.setattr(workflow, "TRACE_TIMEOUT_SECONDS", 0.02)
    cancelled = asyncio.Event()

    async def slow_trace(trace):
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.set()

    harness._trace_sink = slow_trace
    reply = await asyncio.wait_for(
        harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia"), 1
    )
    assert reply.model == "stub" and cancelled.is_set()


async def test_environment_cannot_enable_external_prompt_tracing(
    harness, storage, game, monkeypatch
):
    from langchain_core.tracers.langchain import LangChainTracer

    await storage.games.create(game)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "O grafo não pode exportar o estado privado para tracing externo"
        )

    monkeypatch.setattr(LangChainTracer, "__init__", forbidden)
    reply = await harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia")
    assert reply.model == "stub"


async def test_arbitrary_exception_code_cannot_enter_trace(harness, storage, game, llm):
    await storage.games.create(game)
    traces = await capture_traces(harness)

    class UnexpectedError(RuntimeError):
        code = "PRIVATE_PROMPT_CONTENT"

    llm.complete = AsyncMock(side_effect=UnexpectedError("PRIVATE_PROVIDER_BODY"))
    with pytest.raises(UnexpectedError):
        await harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia")
    assert traces[0].error_code == "internal_error"
    assert "PRIVATE_" not in traces[0].model_dump_json()


async def test_failed_lookup_cannot_create_orphan_redis_trace(harness, storage):
    from memorias_licantropicas.contracts.errors import NotFoundError

    missing = uuid4()
    harness._trace_sink = RedisDialogueTraceRecorder(
        storage.client, storage.prefix
    ).record
    with pytest.raises(NotFoundError):
        await harness.respond(missing, "bentinho", uuid4(), "player", "Bom dia")
    assert not await storage.client.exists(
        f"{storage.prefix}:game:{{{missing}}}:events"
    )
