"""Protocolo Mantle nativo + ChatModel.with_structured_output, sem chamada AWS."""

import asyncio
import json
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

from memorias_licantropicas.contracts.generation import Extraction, SpeechProposal
from memorias_licantropicas.contracts.model import ChatMessage, LLMResponse
from memorias_licantropicas.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from memorias_licantropicas.infrastructure.llm.structured import (
    MantleChatModel,
    generate_structured,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Speech(BaseModel):
    """Resposta falada do personagem."""

    model_config = ConfigDict(extra="forbid", strict=True)
    fala: str = Field(min_length=1)


MESSAGES = (
    ChatMessage(role="system", content="Seja Capitu."),
    ChatMessage(role="user", content="Bom dia."),
)


def completion(
    arguments='{"fala":"Bom dia, Floriano."}', *, name="Speech", content=None
):
    return {
        "model": "qwen.qwen3-32b",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }


async def client_with(handler, token_provider=None):
    client = BedrockMantleClient(
        base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
        api_key=None if token_provider else "fake",
        model="qwen.qwen3-32b",
        timeout_seconds=1,
        max_tokens=512,
        token_provider=token_provider,
    )
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://bedrock-mantle.us-east-1.api.aws/v1/",
        transport=httpx.MockTransport(handler),
    )
    return client


@pytest.mark.anyio
async def test_native_request_sends_schema_in_tools_and_keeps_prompt_unmodified():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=completion())

    client = await client_with(handler)
    try:
        assert isinstance(MantleChatModel(port=client), BaseChatModel)
        result = await generate_structured(client, MESSAGES, Speech)
        assert result.ok and result.value.fala == "Bom dia, Floriano."
        assert (result.response.input_tokens, result.response.output_tokens) == (12, 4)
        payload = seen[0]
        assert payload["messages"] == [m.model_dump() for m in MESSAGES]
        assert payload["tools"][0]["function"]["name"] == "Speech"
        assert (
            payload["tools"][0]["function"]["parameters"]["additionalProperties"]
            is False
        )
        assert payload["tool_choice"] == "auto"
        assert "response_format" not in payload
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_native_arguments_are_parsed_by_framework_while_content_is_ignored():
    client = await client_with(
        lambda request: httpx.Response(
            200, json=completion(content="PRIVATE_REASONING_NOT_PUBLIC")
        )
    )
    try:
        result = await generate_structured(client, MESSAGES, Speech)
        assert result.ok and result.value.fala == "Bom dia, Floriano."
        assert "PRIVATE_REASONING_NOT_PUBLIC" not in repr(result)
        assert "PRIVATE_REASONING_NOT_PUBLIC" not in repr(result.response)
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_missing_tool_is_not_recovered_from_valid_json_content():
    payload = {
        "model": "qwen.qwen3-32b",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"fala":"Bom dia"}'},
            }
        ],
    }
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    client = await client_with(handler)
    try:
        result = await generate_structured(client, MESSAGES, Speech)
        assert not result.ok and result.error_code == "invalid_tool_response"
        assert result.attempts == 2 and len(calls) == 2
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_malformed_native_arguments_are_retained_only_as_invalid_tool_call():
    client = await client_with(
        lambda request: httpx.Response(
            200, json=completion(arguments='{"fala":"PRIVATE_TRUNCATED')
        )
    )
    try:
        result = await generate_structured(client, MESSAGES, Speech, max_attempts=1)
        assert not result.ok and result.error_code == "invalid_tool_arguments"
        assert result.response.invalid_tool_calls and not result.response.tool_calls
        assert "PRIVATE_TRUNCATED" not in repr(result.response)
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fresh_bearer_token_is_resolved_for_each_bounded_attempt():
    provider = AsyncMock()
    provider.get_token.side_effect = ["token-one", "token-two"]
    authorizations = []

    def handler(request):
        authorizations.append(request.headers["authorization"])
        return httpx.Response(
            200,
            json=completion(
                arguments='{"fala":7}'
                if len(authorizations) == 1
                else '{"fala":"Bom dia"}'
            ),
        )

    client = await client_with(handler, provider)
    try:
        result = await generate_structured(client, MESSAGES, Speech)
        assert result.ok and result.attempts == 2
        assert authorizations == ["Bearer token-one", "Bearer token-two"]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_natural_wire_arrays_and_uuid_strings_are_accepted_by_pydantic_tools():
    message_id = "12345678-1234-1234-1234-123456789012"
    payload = {
        "claims": [
            {
                "message_id": message_id,
                "source_span": "Vi Capitu no cais.",
                "proposition": "Capitu esteve no cais.",
                "subject_ids": ["capitu"],
                "parent_claim_ids": [],
            }
        ]
    }
    client = await client_with(
        lambda request: httpx.Response(
            200, json=completion(name="Extraction", arguments=json.dumps(payload))
        )
    )
    try:
        result = await generate_structured(client, MESSAGES, Extraction)
        assert result.ok and result.value.claims[0].message_id == UUID(message_id)
        assert result.value.claims[0].subject_ids == ("capitu",)
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_false_forcing_and_unimplemented_modes_fail_before_transport():
    fake = AsyncMock()
    model = MantleChatModel(port=fake)
    with pytest.raises(ValueError):
        model.bind_tools([Speech], tool_choice="required")
    with pytest.raises(ValueError):
        model.with_structured_output(Speech, method="json_mode")
    assert fake.complete.await_count == 0
