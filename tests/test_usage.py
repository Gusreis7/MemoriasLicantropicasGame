import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from memorias_licantropicas.contracts.errors import (
    LLMUnavailableError,
    StorageUnavailableError,
)
from memorias_licantropicas.contracts.model import ChatMessage, LLMResponse
from memorias_licantropicas.contracts.usage import UsagePricing, UsageRecord
from memorias_licantropicas.infrastructure.usage import (
    MeteredLLMClient,
    RedisUsageRepository,
    usage_scope,
)

pytestmark = pytest.mark.anyio
PRICING = UsagePricing(
    input_usd_per_million=Decimal("0.15"),
    output_usd_per_million=Decimal("0.60"),
    checked_at="2026-11-01",
)
MESSAGES = (ChatMessage(role="user", content="O que sabe?"),)


def record(game_id, **updates):
    return UsageRecord(
        id=uuid4(),
        game_id=game_id,
        purpose="player_dialogue",
        configured_model="qwen.qwen3-32b",
        model="qwen.qwen3-32b",
        started_at=datetime.now(UTC),
        duration_ms=10,
        status="completed",
        input_tokens=1_000_000,
        output_tokens=100_000,
        pricing=PRICING,
    ).model_copy(update=updates)


class PaidLLM:
    async def complete(self, messages, *, tools=(), tool_choice=None):
        await asyncio.sleep(0)
        return LLMResponse(
            model="qwen.qwen3-32b",
            content="Uma fala que o parser poderá rejeitar.",
            input_tokens=1_000_000,
            output_tokens=100_000,
        )

    async def aclose(self):
        pass


async def test_exact_decimal_prices_idempotency_and_frozen_tariff(storage, game):
    repository = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    entry = record(game.id)
    assert await repository.record(entry)
    assert not await repository.record(entry)
    repository.pricing = PRICING.model_copy(
        update={"input_usd_per_million": Decimal("999")}
    )
    summary = await repository.summary(game.id)
    assert summary.totals.calls == 1
    assert summary.totals.known_input_tokens == 1_000_000
    assert summary.totals.known_output_tokens == 100_000
    assert summary.totals.known_estimated_cost_usd == Decimal("0.21")
    assert summary.totals.cost_complete
    assert summary.pricing_snapshots == (PRICING,)


async def test_parallel_games_and_nested_scopes_do_not_mix(storage):
    repository = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    client = MeteredLLMClient(PaidLLM(), repository, configured_model=PRICING.model)
    game_a, game_b = uuid4(), uuid4()

    async def call(game_id, purpose):
        with usage_scope(game_id, purpose):
            await client.complete(MESSAGES)
            if game_id == game_a:
                with usage_scope(game_b, "evaluation"):
                    await client.complete(MESSAGES)
                await client.complete(MESSAGES)

    await asyncio.gather(call(game_a, "player_dialogue"), call(game_b, "social_speech"))
    a, b = await repository.summary(game_a), await repository.summary(game_b)
    assert a.totals.calls == b.totals.calls == 2
    assert {entry.key for entry in a.by_purpose} == {"player_dialogue"}
    assert {entry.key for entry in b.by_purpose} == {"social_speech", "evaluation"}
    await client.complete(MESSAGES)  # previous scopes have been restored to None
    assert (await repository.summary(game_a)).totals.calls == 2


async def test_usage_is_saved_before_application_rejects_model_text(storage, game):
    repository = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    client = MeteredLLMClient(PaidLLM(), repository, configured_model=PRICING.model)
    with pytest.raises(ValueError):
        with usage_scope(game.id, "social_speech", "capitu"):
            await client.complete(MESSAGES)
            raise ValueError("parser rejected content")
    result = await repository.summary(game.id)
    assert result.totals.completed_calls == 1
    assert result.totals.known_estimated_cost_usd == Decimal("0.21")
    raw = await storage.client.hgetall(repository._key(game.id))
    assert "Uma fala" not in str(raw) and "O que sabe" not in str(raw)


async def test_provider_failure_is_unknown_cost_not_free(storage, game):
    class FailedLLM(PaidLLM):
        async def complete(self, messages, *, tools=(), tool_choice=None):
            raise LLMUnavailableError(
                "Do not persist this raw error", code="llm_timeout"
            )

    repository = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    client = MeteredLLMClient(FailedLLM(), repository, configured_model=PRICING.model)
    with pytest.raises(LLMUnavailableError):
        with usage_scope(game.id, "player_dialogue"):
            await client.complete(MESSAGES)
    result = await repository.summary(game.id)
    assert result.totals.failed_calls == result.totals.calls_with_missing_tokens == 1
    assert result.totals.known_estimated_cost_usd == 0
    assert not result.totals.cost_complete
    raw = await storage.client.hgetall(repository._key(game.id))
    assert "llm_timeout" in str(raw) and "Do not persist" not in str(raw)


async def test_cancellation_records_uncertain_usage(storage, game):
    class CancelledLLM(PaidLLM):
        async def complete(self, messages, *, tools=(), tool_choice=None):
            raise asyncio.CancelledError()

    repository = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    client = MeteredLLMClient(
        CancelledLLM(), repository, configured_model=PRICING.model
    )
    with pytest.raises(asyncio.CancelledError):
        with usage_scope(game.id, "knowledge_extraction"):
            await client.complete(MESSAGES)
    totals = (await repository.summary(game.id)).totals
    assert totals.cancelled_calls == totals.calls_with_missing_tokens == 1
    assert not totals.cost_complete


async def test_unknown_exception_code_is_not_persisted(storage, game):
    class UntrustedError(Exception):
        code = "PRIVATE_MODEL_METADATA"

    class BrokenLLM(PaidLLM):
        async def complete(self, messages, *, tools=(), tool_choice=None):
            raise UntrustedError("PRIVATE_MODEL_MESSAGE")

    repository = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    client = MeteredLLMClient(BrokenLLM(), repository, configured_model=PRICING.model)
    with pytest.raises(UntrustedError):
        with usage_scope(game.id, "player_dialogue"):
            await client.complete(MESSAGES)
    raw = str(await storage.client.hgetall(repository._key(game.id)))
    assert "llm_error" in raw
    assert "PRIVATE_MODEL" not in raw


async def test_missing_price_and_tokens_are_explicit(storage, game):
    repository = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    await repository.record(record(game.id, configured_model="other-model"))
    await repository.record(record(game.id, output_tokens=None))
    totals = (await repository.summary(game.id)).totals
    assert (
        totals.calls == 2
        and totals.unpriced_calls == totals.calls_with_missing_tokens == 1
    )
    assert totals.known_estimated_cost_usd == Decimal("0.15")
    assert not totals.cost_complete
    empty = await repository.summary(uuid4())
    assert empty.coverage == "not_recorded"
    assert empty.first_recorded_at is None and not empty.totals.cost_complete


async def test_corrupt_cross_game_data_fails_closed(storage, game):
    repository = RedisUsageRepository(storage.client, storage.prefix)
    entry = record(uuid4())
    await storage.client.hset(
        repository._key(game.id), str(entry.id), entry.model_dump_json()
    )
    with pytest.raises(StorageUnavailableError):
        await repository.summary(game.id)


async def test_metering_failure_preserves_paid_response(storage, game, caplog):
    class BrokenRepository(RedisUsageRepository):
        async def record(self, entry):
            raise StorageUnavailableError("private Redis failure")

    client = MeteredLLMClient(
        PaidLLM(),
        BrokenRepository(storage.client, storage.prefix),
        configured_model=PRICING.model,
    )
    with usage_scope(game.id, "player_dialogue"):
        response = await client.complete(MESSAGES)
    assert response.input_tokens == 1_000_000
    assert "usage_persistence_failed" in caplog.text
    assert "private Redis failure" not in caplog.text


@pytest.mark.parametrize(
    "region,model,expected",
    [
        ("us-east-1", "qwen.qwen3-32b", Decimal("0.15")),
        ("eu-west-1", "qwen.qwen3-32b", None),
        ("us-east-1", "another-model", None),
    ],
)
async def test_default_rates_apply_only_to_verified_region_and_model(
    region, model, expected
):
    from memorias_licantropicas.composition import build_services
    from memorias_licantropicas.settings import Settings

    services = build_services(
        Settings(_env_file=None, aws_region=region, bedrock_model=model)
    )
    try:
        assert services.usage.pricing.input_usd_per_million == expected
        assert isinstance(services.llm, MeteredLLMClient)
        assert all(
            isinstance(client, MeteredLLMClient) for client in services.social_clients
        )
    finally:
        await services.aclose()


async def test_usage_admin_endpoint_requires_session_and_returns_measured_game(
    api_client, storage, game
):
    url = f"/admin/api/v1/games/{game.id}/usage"
    assert (await api_client.get(url)).status_code == 401
    await storage.games.create(game)
    repository = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    await repository.record(record(game.id))
    login = await api_client.post(
        "/admin/api/v1/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    assert login.status_code == 200
    response = await api_client.get(url)
    assert (
        response.status_code == 200 and response.headers["cache-control"] == "no-store"
    )
    payload = response.json()
    assert payload["totals"]["known_input_tokens"] == 1_000_000
    assert Decimal(payload["totals"]["known_estimated_cost_usd"]) == Decimal("0.21")
    assert payload["coverage"] == "recorded_calls_only"
    assert (
        await api_client.get(f"/admin/api/v1/games/{uuid4()}/usage")
    ).status_code == 404


async def test_metered_client_preserves_native_tools_and_output(storage, game):
    from native_fixtures import respond_to_tools

    tools = (
        {
            "type": "function",
            "function": {
                "name": "NpcSpeech",
                "parameters": {
                    "type": "object",
                    "properties": {"fala": {"type": "string"}},
                },
            },
        },
    )
    seen = []

    class NativeProvider:
        async def complete(self, messages, *, tools=(), tool_choice=None):
            seen.append((tools, tool_choice))
            return respond_to_tools(
                {"fala": "Boa noite."},
                tools,
                tool_choice,
                input_tokens=12,
                output_tokens=4,
            )

    usage = RedisUsageRepository(storage.client, storage.prefix, pricing=PRICING)
    client = MeteredLLMClient(NativeProvider(), usage, configured_model=PRICING.model)
    with usage_scope(game.id, "player_dialogue"):
        response = await client.complete(MESSAGES, tools=tools, tool_choice="auto")
    assert seen == [(tools, "auto")]
    assert response.tool_calls[0].name == "NpcSpeech"
    assert response.tool_calls[0].args == {"fala": "Boa noite."}
    assert response.content == ""
    assert (await usage.summary(game.id)).totals.completed_calls == 1
