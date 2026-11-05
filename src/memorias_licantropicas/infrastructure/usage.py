"""Medição por chamada: o ContextVar impede mistura entre partidas concorrentes."""

import asyncio
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import logging
from time import monotonic
from uuid import UUID, uuid4

from pydantic import ValidationError
from redis.exceptions import RedisError

from memorias_licantropicas.contracts.errors import LLM_PUBLIC_DETAILS, StorageUnavailableError
from memorias_licantropicas.contracts.usage import (
    UsageBreakdown, UsagePricing, UsageRecord, UsageSummary, UsageTotals,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageContext:
    game_id: UUID
    purpose: str
    npc_id: str | None = None


_usage_context: ContextVar[UsageContext | None] = ContextVar("llm_usage_context", default=None)


@contextmanager
def usage_scope(game_id: UUID, purpose: str, npc_id: str | None = None):
    """Registrar contexto antes da inferência; restore inclusive após exceções."""
    if not purpose or len(purpose) > 80 or (npc_id is not None and len(npc_id) > 80):
        raise ValueError("Contexto de consumo inválido.")
    context = UsageContext(UUID(str(game_id)), purpose, npc_id)
    token = _usage_context.set(context)
    try:
        yield context
    finally:
        _usage_context.reset(token)


def _totals(records):
    known_cost = Decimal("0")
    missing = unpriced = 0
    for record in records:
        price = record.pricing
        priced = (record.configured_model == price.model and
                  price.input_usd_per_million is not None and price.output_usd_per_million is not None)
        if record.input_tokens is None or record.output_tokens is None:
            missing += 1
        if not priced:
            unpriced += 1
        else:
            if record.input_tokens is not None:
                known_cost += Decimal(record.input_tokens) * price.input_usd_per_million / Decimal(1_000_000)
            if record.output_tokens is not None:
                known_cost += Decimal(record.output_tokens) * price.output_usd_per_million / Decimal(1_000_000)
    return UsageTotals(
        calls=len(records), completed_calls=sum(record.status == "completed" for record in records),
        failed_calls=sum(record.status == "failed" for record in records),
        cancelled_calls=sum(record.status == "cancelled" for record in records),
        known_input_tokens=sum(record.input_tokens or 0 for record in records),
        known_output_tokens=sum(record.output_tokens or 0 for record in records),
        calls_with_missing_tokens=missing, unpriced_calls=unpriced,
        known_estimated_cost_usd=known_cost,
        cost_complete=bool(records) and not missing and not unpriced,
        duration_ms=sum(record.duration_ms for record in records),
    )


class RedisUsageRepository:
    def __init__(self, client, prefix="ml:v1", *, pricing: UsagePricing | None = None):
        self._client = client
        self._prefix = prefix
        self.pricing = pricing or UsagePricing()

    def _key(self, game_id):
        return f"{self._prefix}:game:{{{game_id}}}:llm:usage"

    async def record(self, record: UsageRecord) -> bool:
        """Um ID de chamada só pode ser contabilizado uma vez."""
        try:
            return bool(await self._client.hsetnx(self._key(record.game_id), str(record.id), record.model_dump_json()))
        except RedisError:
            raise StorageUnavailableError("Medição de consumo indisponível.") from None

    async def summary(self, game_id: UUID) -> UsageSummary:
        try:
            raw = await self._client.hgetall(self._key(game_id))
            records = []
            for identifier, value in raw.items():
                record = UsageRecord.model_validate_json(value)
                identifier = identifier.decode() if isinstance(identifier, bytes) else identifier
                if record.game_id != game_id or str(record.id) != identifier:
                    raise ValueError("Identidade de medição inválida.")
                records.append(record)
            records.sort(key=lambda entry: (entry.started_at, str(entry.id)))
        except (RedisError, ValidationError, ValueError, TypeError):
            raise StorageUnavailableError("Medição de consumo indisponível.") from None
        by_purpose, by_model = defaultdict(list), defaultdict(list)
        snapshots = {}
        for record in records:
            by_purpose[record.purpose].append(record)
            by_model[record.configured_model].append(record)
            snapshots[record.pricing.model_dump_json()] = record.pricing
        return UsageSummary(
            game_id=game_id, coverage="recorded_calls_only" if records else "not_recorded",
            first_recorded_at=records[0].started_at if records else None,
            last_recorded_at=records[-1].started_at if records else None,
            totals=_totals(records),
            by_purpose=tuple(UsageBreakdown(key=key, **_totals(group).model_dump()) for key, group in sorted(by_purpose.items())),
            by_model=tuple(UsageBreakdown(key=key, **_totals(group).model_dump()) for key, group in sorted(by_model.items())),
            pricing_snapshots=tuple(snapshots.values()),
        )


class MeteredLLMClient:
    def __init__(self, client, repository: RedisUsageRepository, *, configured_model: str):
        self._client = client
        self._repository = repository
        self._configured_model = configured_model

    async def complete(self, messages, *, tools=(), tool_choice=None):
        native = {"tools": tools, "tool_choice": tool_choice} if tools or tool_choice is not None else {}
        context = _usage_context.get()
        if context is None:
            logger.warning("llm_usage code=usage_context_missing")
            return await self._client.complete(messages, **native)
        identifier, started_at, start = uuid4(), datetime.now(UTC), monotonic()
        response, status, error_code = None, "failed", None
        try:
            response = await self._client.complete(messages, **native)
            status = "completed"
            return response
        except asyncio.CancelledError:
            status, error_code = "cancelled", "cancelled"
            raise
        except Exception as error:
            # Somente o código estável; mensagens, URLs e credenciais não entram no registro.
            code = getattr(error, "code", None)
            error_code = code if isinstance(code, str) and code in LLM_PUBLIC_DETAILS else "llm_error"
            raise
        finally:
            record = UsageRecord(
                id=identifier, game_id=context.game_id, purpose=context.purpose, npc_id=context.npc_id,
                started_at=started_at, duration_ms=max(0, round((monotonic() - start) * 1000)),
                configured_model=self._configured_model, model=response.model if response is not None else self._configured_model,
                status=status, input_tokens=response.input_tokens if response is not None else None,
                output_tokens=response.output_tokens if response is not None else None,
                error_code=error_code, pricing=self._repository.pricing,
            )
            try:
                await self._repository.record(record)
            except StorageUnavailableError:
                # Telemetria indisponível não descarta uma resposta paga já recebida.
                logger.error("llm_usage code=usage_persistence_failed call_id=%s game_id=%s", identifier, context.game_id)

    async def aclose(self):
        await self._client.aclose()
