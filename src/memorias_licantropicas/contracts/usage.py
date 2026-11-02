"""Contadores conhecidos e estimativas de tabela, sem textos de inferência."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from memorias_licantropicas.contracts.model import Contract


class UsagePricing(Contract):
    model: str = "qwen.qwen3-32b"
    input_usd_per_million: Decimal | None = Field(default=None, ge=0)
    output_usd_per_million: Decimal | None = Field(default=None, ge=0)
    source: str = "https://aws.amazon.com/bedrock/pricing/"
    checked_at: str | None = None
    currency: Literal["USD"] = "USD"


class UsageRecord(Contract):
    id: UUID
    game_id: UUID
    purpose: str = Field(min_length=1, max_length=80)
    npc_id: str | None = Field(default=None, max_length=80)
    started_at: AwareDatetime
    duration_ms: int = Field(ge=0)
    configured_model: str
    model: str
    status: Literal["completed", "failed", "cancelled"]
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    pricing: UsagePricing


class UsageTotals(Contract):
    calls: int = 0
    completed_calls: int = 0
    failed_calls: int = 0
    cancelled_calls: int = 0
    known_input_tokens: int = 0
    known_output_tokens: int = 0
    calls_with_missing_tokens: int = 0
    unpriced_calls: int = 0
    known_estimated_cost_usd: Decimal = Decimal("0")
    cost_complete: bool = False
    duration_ms: int = 0


class UsageBreakdown(UsageTotals):
    key: str


class UsageSummary(Contract):
    game_id: UUID
    coverage: Literal["recorded_calls_only", "not_recorded"]
    first_recorded_at: AwareDatetime | None = None
    last_recorded_at: AwareDatetime | None = None
    totals: UsageTotals
    by_purpose: tuple[UsageBreakdown, ...] = ()
    by_model: tuple[UsageBreakdown, ...] = ()
    pricing_snapshots: tuple[UsagePricing, ...] = ()
    currency: Literal["USD"] = "USD"
    note: str = (
        "Estimativa dos tokens conhecidos nas chamadas registradas, sem créditos, impostos ou descontos. "
        "Chamadas anteriores à medição ou sem metadados não têm custo conhecido."
    )
