import json
import traceback

import httpx
import pytest

from src.contracts.errors import LLMUnavailableError
from src.contracts.model import ChatMessage
from src.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from unittest.mock import AsyncMock

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def mantle_factory():
    clients = []

    async def create(handler, api_key="fake-test-key"):
        client = BedrockMantleClient(
            base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
            api_key=api_key,
            model="qwen.qwen3-32b",
            timeout_seconds=1,
            max_tokens=64,
        )
        await client._client.aclose()
        client._client = httpx.AsyncClient(
            base_url="https://bedrock-mantle.us-east-1.api.aws/v1/",
            transport=httpx.MockTransport(handler),
        )
        clients.append(client)
        return client

    yield create
    for client in clients:
        await client.aclose()


def completion(content="Bom dia", finish_reason="stop"):
    return {
        "model": "qwen.qwen3-32b",
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }


async def test_mantle_request_and_response_contract(mantle_factory):
    def handle(request):
        assert (
            str(request.url)
            == "https://bedrock-mantle.us-east-1.api.aws/v1/chat/completions"
        )
        assert request.headers["authorization"] == "Bearer fake-test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "qwen.qwen3-32b"
        assert payload["messages"] == [{"role": "user", "content": "Olá"}]
        assert payload["max_tokens"] == 64
        assert payload["stream"] is False
        return httpx.Response(200, json=completion())

    client = await mantle_factory(handle)
    reply = await client.complete((ChatMessage(role="user", content="Olá"),))
    assert reply.content == "Bom dia"
    assert (reply.input_tokens, reply.output_tokens) == (12, 4)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "llm_authentication_failed"),
        (403, "llm_authentication_failed"),
        (404, "llm_model_unavailable"),
        (429, "llm_rate_limited"),
        (500, "llm_unavailable"),
        (502, "llm_unavailable"),
    ],
)
async def test_provider_errors_are_sanitized(mantle_factory, status, code):
    client = await mantle_factory(
        lambda request: httpx.Response(status, text="provider-private-detail")
    )
    prompt = (ChatMessage(role="user", content="PRIVATE_PROMPT_123"),)
    with pytest.raises(LLMUnavailableError) as error:
        await client.complete(prompt)
    assert error.value.code == code
    assert "provider-private-detail" not in str(error.value)
    assert "fake-test-key" not in str(error.value)
    formatted = "".join(traceback.format_exception(error.value))
    assert all(
        secret not in formatted
        for secret in ("provider-private-detail", "fake-test-key", "PRIVATE_PROMPT_123")
    )


@pytest.mark.parametrize(
    "payload,code",
    [
        (completion(""), "llm_invalid_response"),
        (completion(finish_reason="length"), "llm_response_truncated"),
        ({"choices": []}, "llm_invalid_response"),
    ],
)
async def test_invalid_completions_are_rejected(mantle_factory, payload, code):
    client = await mantle_factory(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(LLMUnavailableError) as error:
        await client.complete((ChatMessage(role="user", content="Olá"),))
    assert error.value.code == code


async def test_missing_credentials_never_sends_request(mantle_factory):
    def forbidden(request):
        pytest.fail("Credencial ausente não pode disparar HTTP")

    client = await mantle_factory(forbidden, api_key=None)
    with pytest.raises(LLMUnavailableError, match="Credencial") as error:
        await client.complete((ChatMessage(role="user", content="Olá"),))
    assert error.value.code == "llm_credentials_missing"


@pytest.mark.parametrize(
    "failure,code",
    [
        (httpx.ReadTimeout, "llm_timeout"),
        (httpx.ConnectError, "llm_unavailable"),
    ],
)
async def test_transport_diagnostics_exclude_raw_exception_and_prompt(
    mantle_factory, failure, code
):
    def handle(request):
        raise failure(
            "private-network-detail fake-test-key PRIVATE_PROMPT_123", request=request
        )

    client = await mantle_factory(handle)
    prompt = (ChatMessage(role="user", content="PRIVATE_PROMPT_123"),)
    with pytest.raises(LLMUnavailableError) as error:
        await client.complete(prompt)
    assert error.value.code == code
    formatted = "".join(traceback.format_exception(error.value))
    assert all(
        secret not in formatted
        for secret in ("private-network-detail", "fake-test-key", "PRIVATE_PROMPT_123")
    )


async def test_invalid_json_has_safe_diagnostic(mantle_factory):
    client = await mantle_factory(
        lambda request: httpx.Response(200, text="private-provider-payload")
    )
    with pytest.raises(LLMUnavailableError) as error:
        await client.complete((ChatMessage(role="user", content="Olá"),))
    assert error.value.code == "llm_invalid_response"
    assert "private-provider-payload" not in "".join(
        traceback.format_exception(error.value)
    )


async def test_profile_failure_never_reaches_provider_http(mantle_factory):
    def forbidden(request):
        pytest.fail("Falha de credencial não pode disparar HTTP")

    client = await mantle_factory(forbidden, api_key=None)
    provider = AsyncMock()
    provider.get_token.side_effect = LLMUnavailableError(
        "Falha sanitizada.", code="llm_credentials_unavailable"
    )
    client._token_provider = provider
    with pytest.raises(LLMUnavailableError) as error:
        await client.complete((ChatMessage(role="user", content="Olá"),))
    assert error.value.code == "llm_credentials_unavailable"
    provider.get_token.assert_awaited_once()


async def test_profile_token_is_requested_per_call(mantle_factory):
    def handle(request):
        assert request.headers["authorization"] == "Bearer profile-token"
        return httpx.Response(200, json=completion())

    client = await mantle_factory(handle, api_key=None)
    provider = AsyncMock()
    provider.get_token.return_value = "profile-token"
    client._token_provider = provider
    for _ in range(2):
        await client.complete((ChatMessage(role="user", content="Olá"),))
    assert provider.get_token.await_count == 2


async def test_explicit_api_key_takes_precedence_over_profile(mantle_factory):
    client = await mantle_factory(
        lambda request: httpx.Response(200, json=completion())
    )
    provider = AsyncMock()
    client._token_provider = provider
    await client.complete((ChatMessage(role="user", content="Olá"),))
    provider.get_token.assert_not_awaited()
