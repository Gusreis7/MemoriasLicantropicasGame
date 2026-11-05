"""Partidas completas por services reais e grafo de diálogo.

Offline: uv run python scripts/run_session_simulations.py --games 100
Real: uv run python scripts/run_session_simulations.py --live --games 1 --aws-profile terraform --max-live-calls 100
O modo real pode gerar cobrança; exige --live, perfil explícito e cota positiva.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from src.simulation.session import BudgetedSessionModel, run_sessions


async def execute(args):
    model = pricing = None
    if args.live:
        if not args.aws_profile or not args.max_live_calls or args.max_live_calls < 1:
            raise ValueError("--live exige --aws-profile e --max-live-calls positivo")
        # Nothing in this block is imported or initialized by the offline/test path.
        from src.infrastructure.llm.aws_credentials import (
            ProfileTokenProvider,
        )
        from src.infrastructure.llm.bedrock_mantle import (
            BedrockMantleClient,
        )
        from src.infrastructure.usage import UsagePricing
        from src.settings import Settings

        settings = Settings()
        model = BudgetedSessionModel(
            BedrockMantleClient(
                base_url=settings.mantle_base_url,
                api_key=None,
                model=settings.bedrock_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_tokens=max(1200, settings.llm_max_tokens),
                token_provider=ProfileTokenProvider(
                    args.aws_profile, settings.aws_region
                ),
            ),
            args.max_live_calls,
        )
        same_price = (
            settings.bedrock_model == settings.llm_pricing_model
            and settings.aws_region == settings.llm_pricing_region
        )
        pricing = UsagePricing(
            model=settings.bedrock_model,
            input_usd_per_million=settings.llm_input_usd_per_million
            if same_price
            else None,
            output_usd_per_million=settings.llm_output_usd_per_million
            if same_price
            else None,
            source=settings.llm_pricing_source,
            checked_at=settings.llm_pricing_checked_at,
        )
    try:
        return await run_sessions(
            args.games,
            args.seed,
            args.redis_url,
            faults=not args.no_faults and not args.live,
            live_model=model,
            pricing=pricing,
            progress=lambda completed, total, result: print(
                f"{completed}/{total}: {result['policy']} seed={result['seed']} "
                f"result={result['result']} day={result['day']}",
                file=sys.stderr,
                flush=True,
            ),
        )
    finally:
        if model is not None:
            await model.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261105)
    parser.add_argument(
        "--redis-url",
        default=None,
        help="Opcional: Redis real; limpa somente prefixo exclusivo da execução.",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/simulations/sessions.json")
    )
    parser.add_argument(
        "--no-faults",
        action="store_true",
        help="Desabilita erros injetados no modelo offline.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Habilita chamadas AWS potencialmente cobradas.",
    )
    parser.add_argument("--aws-profile", default=None)
    parser.add_argument("--max-live-calls", type=int, default=None)
    args = parser.parse_args()
    report = asyncio.run(execute(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
