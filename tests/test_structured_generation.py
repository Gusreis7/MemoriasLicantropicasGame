"""Contratos novos não reparam JSON inválido nem escondem falhas de transporte."""

import asyncio
import json
import traceback
from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict, Field

from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.contracts.model import ChatMessage, LLMResponse
from memorias_licantropicas.infrastructure.llm.structured import (
    StructuredOutputError,
    format_instructions,
    generate_structured,
    parse_model_output,
)


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    quote: str
    score: int


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    useful: bool
    day: int = Field(ge=0)
    entries: tuple[Entry, ...]
    message_id: UUID | None = None


GOOD = '{"useful":true,"day":1,"entries":[{"quote":"Vi Capitu no cais.","score":2}]}'
MESSAGES = (
    ChatMessage(role="system", content='Ficha privada:\n{"id":"capitu"}'),
    ChatMessage(role="user", content='{"fala":"Quem estava no cais?"}'),
)


def test_langchain_parser_handles_json_native_tuple_and_uuid_without_coercion():
    identifier = "12345678-1234-1234-1234-123456789012"
    data = json.loads(GOOD) | {"message_id": identifier}
    result = parse_model_output(json.dumps(data), Evaluation)
    assert isinstance(result.entries, tuple)
    assert result.entries[0].score == 2
    assert result.message_id == UUID(identifier)

    assert "entries" in format_instructions(Evaluation)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " ",
        "Segue: " + GOOD,
        "```json\n" + GOOD + "\n```",
        GOOD + " lixo",
        GOOD[:-1],
        "[]",
        "null",
        "true",
        GOOD + GOOD,
        '{"useful":true,"useful":false,"day":1,"entries":[]}',
        '{"useful":true,"day":NaN,"entries":[]}',
        '{"useful":true,"day":Infinity,"entries":[]}',
        '{"useful":true,"day":1,"entries":[{"quote":"a","quote":"b","score":2}]}',
    ],
)
def test_rejects_entire_malformed_or_ambiguous_document(raw):
    with pytest.raises(StructuredOutputError) as error:
        parse_model_output(raw, Evaluation)
    assert error.value.code == "invalid_json"


@pytest.mark.parametrize(
    "change",
    [
        {"useful": "true"},
        {"useful": 1},
        {"day": "1"},
        {"day": True},
        {"day": -1},
        {"entries": [{"quote": "PRIVATE_RAW_SECRET", "score": "2"}]},
        {"entries": [{"quote": "PRIVATE_RAW_SECRET", "score": 2, "admin": True}]},
        {"entries": [{"score": 2}]},
        {"admin": True},
    ],
)
def test_rejects_wrong_types_unknown_fields_and_nested_contract_errors(change):
    raw = json.dumps(json.loads(GOOD) | change)
    with pytest.raises(StructuredOutputError) as error:
        parse_model_output(raw, Evaluation)
    assert error.value.code == "invalid_schema"
    assert "PRIVATE_RAW_SECRET" not in "".join(traceback.format_exception(error.value))


class ScriptedClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        result = next(self.responses)
        if isinstance(result, BaseException):
            raise result
        return LLMResponse(
            content=result, model="offline-fixture", input_tokens=20, output_tokens=5
        )


@pytest.mark.anyio
async def test_invalid_response_gets_one_bounded_retry_without_echoing_raw_output():
    client = ScriptedClient(["PRIVATE_RAW_SECRET", GOOD])
    result = await generate_structured(client, MESSAGES, Evaluation)
    assert result.ok and result.attempts == 2 and result.error_code is None
    assert result.value.day == 1 and result.response.output_tokens == 5
    assert len(client.calls) == 2
    for prompt in client.calls:
        assert prompt[0] == MESSAGES[0] and prompt[-1] == MESSAGES[-1]
        assert prompt[-2].role == "system" and "entries" in prompt[-2].content
        assert "PRIVATE_RAW_SECRET" not in str(prompt)
    assert "tentativa anterior" in client.calls[1][-2].content
    assert "PRIVATE_RAW_SECRET" not in repr(result)


@pytest.mark.anyio
async def test_exhausted_parser_returns_failure_and_never_fabricates_value():
    client = ScriptedClient(["PRIVATE_RAW_SECRET", '{"useful":true}'])
    result = await generate_structured(client, MESSAGES, Evaluation)
    assert not result.ok and result.value is None and result.attempts == 2
    assert result.error_code == "invalid_schema" and len(client.calls) == 2
    assert "PRIVATE_RAW_SECRET" not in repr(result)


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
async def test_auth_quota_timeout_and_network_failures_do_not_retry_or_leak(code):
    client = ScriptedClient([LLMUnavailableError("PRIVATE_PROVIDER_SECRET", code=code)])
    result = await generate_structured(client, MESSAGES, Evaluation)
    assert not result.ok and result.attempts == 1 and result.error_code == code
    assert len(client.calls) == 1 and "PRIVATE_PROVIDER_SECRET" not in repr(result)


@pytest.mark.anyio
@pytest.mark.parametrize("code", ["llm_invalid_response", "llm_response_truncated"])
async def test_invalid_transport_document_can_be_retried_without_repair(code):
    client = ScriptedClient([LLMUnavailableError("PRIVATE", code=code), GOOD])
    result = await generate_structured(client, MESSAGES, Evaluation)
    assert result.ok and result.attempts == 2


@pytest.mark.anyio
async def test_cancellation_propagates_instead_of_returning_fallback():
    client = ScriptedClient([asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        await generate_structured(client, MESSAGES, Evaluation)
    assert len(client.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("attempts", [0, 4, True, "2"])
async def test_invalid_retry_budget_fails_before_calling_provider(attempts):
    client = ScriptedClient([])
    with pytest.raises(ValueError):
        await generate_structured(client, MESSAGES, Evaluation, max_attempts=attempts)
    assert client.calls == []


@pytest.mark.anyio
async def test_both_paid_attempts_remain_visible_to_usage_meter(storage):
    from uuid import uuid4
    from memorias_licantropicas.infrastructure.usage import (
        MeteredLLMClient,
        RedisUsageRepository,
        usage_scope,
    )

    game_id = uuid4()
    repository = RedisUsageRepository(storage.client, storage.prefix)
    client = MeteredLLMClient(
        ScriptedClient(["invalid document", GOOD]),
        repository,
        configured_model="offline-fixture",
    )
    with usage_scope(game_id, "structured-contract-test", "capitu"):
        result = await generate_structured(client, MESSAGES, Evaluation)
    summary = await repository.summary(game_id)
    assert result.ok and summary.totals.calls == 2
    assert summary.totals.known_input_tokens == 40
    assert summary.totals.known_output_tokens == 10
