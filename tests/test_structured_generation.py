"""Contratos nativos não fazem downgrade para parsing de conteúdo textual."""

import asyncio
from unittest.mock import patch
from uuid import uuid4

import fakeredis
import pytest
from langchain_core.tracers.langchain import LangChainTracer
from pydantic import BaseModel, ConfigDict, Field

from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.contracts.model import ChatMessage, LLMResponse
from memorias_licantropicas.infrastructure.llm.structured import generate_structured


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    useful: bool
    day: int = Field(ge=0)


GOOD = {"useful": True, "day": 1}
MESSAGES = (
    ChatMessage(role="system", content="PRIVATE_CONTEXT"),
    ChatMessage(role="user", content="Pergunta"),
)


def native(args=GOOD, name="Evaluation", **kwargs):
    return LLMResponse(
        model="offline-fixture",
        tool_calls=({"name": name, "args": args, "id": "call-1"},),
        input_tokens=20,
        output_tokens=5,
        **kwargs,
    )


class ScriptedClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def complete(self, messages, *, tools=(), tool_choice=None):
        self.calls.append((messages, tools, tool_choice))
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response


@pytest.mark.anyio
@pytest.mark.parametrize(
    "args",
    [
        {"useful": "true", "day": 1},
        {"useful": 1, "day": 1},
        {"useful": True, "day": "1"},
        {"useful": True, "day": True},
        {"useful": True, "day": -1},
        {"useful": True, "day": 1, "admin": True},
        {},
    ],
)
async def test_native_wrong_types_and_unknown_fields_are_rejected(args):
    result = await generate_structured(
        ScriptedClient([native(args)]), MESSAGES, Evaluation, max_attempts=1
    )
    assert not result.ok and result.error_code == "invalid_schema"


@pytest.mark.anyio
async def test_bounded_retry_preserves_prompt_and_uses_native_schema_each_time():
    client = ScriptedClient([native({"useful": True, "day": "1"}), native()])
    result = await generate_structured(client, MESSAGES, Evaluation)
    assert result.ok and result.attempts == 2 and result.value.day == 1
    for prompt, tools, choice in client.calls:
        assert prompt == MESSAGES and choice == "auto"
        assert tools[0]["function"]["name"] == "Evaluation"
    assert "PRIVATE_CONTEXT" not in repr(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        LLMResponse(model="fake", content='{"useful":true,"day":1}'),
        native(name="Unexpected"),
        LLMResponse(
            model="fake",
            tool_calls=(
                {"name": "Evaluation", "args": GOOD, "id": "a"},
                {"name": "Evaluation", "args": GOOD, "id": "b"},
            ),
        ),
    ],
)
async def test_absent_unknown_or_multiple_calls_fail_without_content_recovery(response):
    result = await generate_structured(
        ScriptedClient([response]), MESSAGES, Evaluation, max_attempts=1
    )
    assert not result.ok and result.error_code == "invalid_tool_response"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "code",
    [
        "llm_credentials_missing",
        "llm_credentials_unavailable",
        "llm_authentication_failed",
        "llm_rate_limited",
        "llm_timeout",
        "llm_unavailable",
        "llm_model_unavailable",
    ],
)
async def test_auth_quota_timeout_and_network_errors_do_not_retry(code):
    client = ScriptedClient([LLMUnavailableError("PRIVATE_PROVIDER_SECRET", code=code)])
    result = await generate_structured(client, MESSAGES, Evaluation)
    assert not result.ok and result.attempts == 1 and result.error_code == code
    assert len(client.calls) == 1 and "PRIVATE_PROVIDER_SECRET" not in repr(result)


@pytest.mark.anyio
async def test_cancellation_propagates():
    client = ScriptedClient([asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        await generate_structured(client, MESSAGES, Evaluation)
    assert len(client.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("attempts", [0, 4, True, "2"])
async def test_invalid_budget_never_calls_provider(attempts):
    client = ScriptedClient([])
    with pytest.raises(ValueError):
        await generate_structured(client, MESSAGES, Evaluation, max_attempts=attempts)
    assert client.calls == []


@pytest.mark.anyio
async def test_native_attempts_keep_usage_records_and_forward_tool_kwargs():
    from memorias_licantropicas.infrastructure.usage import (
        MeteredLLMClient,
        RedisUsageRepository,
        usage_scope,
    )

    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    try:
        repository = RedisUsageRepository(redis, "native-contract-test")
        raw = ScriptedClient([native({"useful": True, "day": "1"}), native()])
        client = MeteredLLMClient(raw, repository, configured_model="offline-fixture")
        game_id = uuid4()
        with usage_scope(game_id, "native-contract-test", "capitu"):
            result = await generate_structured(client, MESSAGES, Evaluation)
        summary = await repository.summary(game_id)
        assert result.ok and summary.totals.calls == 2
        assert (
            summary.totals.known_input_tokens == 40
            and summary.totals.known_output_tokens == 10
        )
        assert all(call[1] and call[2] == "auto" for call in raw.calls)
    finally:
        await redis.aclose()


@pytest.mark.anyio
async def test_incidental_langsmith_environment_cannot_export_private_inputs(
    monkeypatch,
):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "fake-test-only")
    with patch.object(
        LangChainTracer,
        "__init__",
        side_effect=AssertionError("external tracer created"),
    ) as constructor:
        result = await generate_structured(
            ScriptedClient([native()]), MESSAGES, Evaluation
        )
    assert result.ok and constructor.call_count == 0


@pytest.mark.anyio
async def test_actual_task_cancellation_reaches_transport_and_never_returns_fallback():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class SlowClient:
        async def complete(self, messages, *, tools=(), tool_choice=None):
            started.set()
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.set()

    task = asyncio.create_task(generate_structured(SlowClient(), MESSAGES, Evaluation))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(cancelled.wait(), 1)
