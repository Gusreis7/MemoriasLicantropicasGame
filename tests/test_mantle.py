import json

import httpx
import pytest

from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.contracts.model import ChatMessage
from memorias_licantropicas.infrastructure.llm.bedrock_mantle import BedrockMantleClient

pytestmark = pytest.mark.anyio


@pytest.fixture
async def mantle_factory():
    clients = []

    async def create(handler, api_key="fake-test-key"):
        client = BedrockMantleClient(base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
                                    api_key=api_key, model="qwen.qwen3-32b", timeout_seconds=1, max_tokens=64)
        await client._client.aclose()
        client._client = httpx.AsyncClient(base_url="https://bedrock-mantle.us-east-1.api.aws/v1/",
                                          transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    yield create
    for client in clients:
        await client.aclose()


def completion(content="Bom dia", finish_reason="stop"):
    return {"model": "qwen.qwen3-32b", "choices": [{"finish_reason": finish_reason,
            "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4}}


async def test_mantle_request_and_response_contract(mantle_factory):
    def handle(request):
        assert str(request.url) == "https://bedrock-mantle.us-east-1.api.aws/v1/chat/completions"
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


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_provider_errors_are_sanitized(mantle_factory, status):
    client = await mantle_factory(lambda request: httpx.Response(status, text="provider-private-detail"))
    with pytest.raises(LLMUnavailableError) as error:
        await client.complete((ChatMessage(role="user", content="Olá"),))
    assert "provider-private-detail" not in str(error.value)
    assert "fake-test-key" not in str(error.value)


@pytest.mark.parametrize("payload", [completion(""), completion(finish_reason="length"), {"choices": []}])
async def test_invalid_completions_are_rejected(mantle_factory, payload):
    client = await mantle_factory(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(LLMUnavailableError):
        await client.complete((ChatMessage(role="user", content="Olá"),))


async def test_missing_credentials_never_sends_request(mantle_factory):
    def forbidden(request):
        pytest.fail("Credencial ausente não pode disparar HTTP")
    client = await mantle_factory(forbidden, api_key=None)
    with pytest.raises(LLMUnavailableError, match="Credencial"):
        await client.complete((ChatMessage(role="user", content="Olá"),))
