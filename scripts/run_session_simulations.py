"""Execute N partidas reais por HTTP, com Floriano controlado por LLM.

A aplicação deve estar em execução com NPCs/Bedrock configurados. Não há provedor
offline nem política fixa. --max-live-calls limita SOMENTE as chamadas de Floriano;
inferências de NPCs/mestre/convivência feitas pelo servidor são adicionais.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from time import perf_counter
from uuid import uuid4

# Permite executar diretamente do checkout sem depender de instalação do wheel.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from src.infrastructure.llm.aws_credentials import ProfileTokenProvider
from src.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from src.settings import Settings
from src.simulation.model import BudgetedSessionModel, FlorianoAgent
from src.simulation.session import LiveSession


def positive_int(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("deve ser inteiro positivo")
    return result


def positive_float(value):
    result = float(value)
    if not 0 < result < float('inf'):
        raise argparse.ArgumentTypeError("deve ser número positivo e finito")
    return result


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def make_report(results, agent, started, status, args):
    completed = [item for item in results if item.get('status') == 'completed']
    won = sum(item.get('result') == 'won' for item in completed)
    action_counts = Counter()
    for item in results:
        action_counts.update(item.get('action_counts', {}))
    audits = [item['server_statistics'] for item in results if item.get('server_statistics', {}).get('available')]
    return {
        'mode': 'live_http_llm', 'status': status,
        'created_at': datetime.now(UTC).isoformat(), 'api_url': args.api_url,
        'requested_games': args.games, 'sessions': results,
        'summary': {
            'recorded_sessions': len(results), 'completed_games': len(completed),
            'won': won, 'lost': sum(item.get('result') == 'lost' for item in completed),
            'win_rate_completed': won / len(completed) if completed else None,
            'status_counts': dict(Counter(item.get('status', 'unknown') for item in results)),
            'stop_reasons': dict(Counter(item.get('stop_reason') or 'none' for item in results)),
            'duration_seconds': perf_counter() - started,
            'agent_usage': agent.stats,
            'action_counts': dict(action_counts),
            'completed_day_distribution': dict(Counter(str(item.get('day')) for item in completed)),
            'server_audits_available': len(audits),
            'server_usage': aggregate_server_usage(audits),
        },
        'limits': {
            'max_agent_provider_calls': args.max_live_calls,
            'max_steps_per_session': args.max_steps, 'max_seconds_per_session': args.max_seconds,
            'server_calls_included_in_agent_budget': False,
        },
        'limitations': [
            'O limite de chamadas cobre apenas Floriano, incluindo novas tentativas de contrato.',
            'NPCs, mestre e convivência usam o LLM configurado no servidor e geram consumo adicional.',
            'Interromper o runner não pausa nem apaga partidas: relógio e worker do servidor continuam.',
            'Sessões interrompidas ou com erro não são contabilizadas como derrotas nem partidas concluídas.',
            'Custos são estimativas dos tokens conhecidos, conforme a tabela configurada, não fatura AWS.',
        ],
    }


def aggregate_server_usage(audits):
    # Audit documents preserve their source; do not invent totals when unavailable.
    totals = Counter()
    for audit in audits:
        usage = audit.get('usage', {})
        if isinstance(usage, dict):
            source = usage.get('totals', usage)
            for key, value in source.items():
                if type(value) in (int, float):
                    totals[key] += value
                elif key == 'known_estimated_cost_usd' and value is not None:
                    totals[key] += float(value)
    return {'available': bool(audits), 'totals': dict(totals),
            'scope': 'Somente sessões com auditoria Redis disponível; o worker pode continuar depois da coleta.'}


async def execute(args):
    settings = Settings()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError('A pasta já contém arquivos; escolha outra para preservar a execução anterior.')
    args.output.mkdir(parents=True, exist_ok=True)
    profile = args.aws_profile or settings.aws_profile
    token = settings.bedrock_api_key.get_secret_value().strip() if settings.bedrock_api_key else ''
    provider = ProfileTokenProvider(profile, settings.aws_region,
        refresh_source_dir=settings.aws_profile_source_dir) if profile or settings.aws_use_default_credentials else None
    if not token and provider is None:
        raise ValueError('Configure AWS_BEARER_TOKEN_BEDROCK ou --aws-profile antes de executar.')
    client = BedrockMantleClient(
        base_url=settings.mantle_base_url, api_key=token or None,
        model=settings.bedrock_model, timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=max(1200, settings.llm_max_tokens), token_provider=provider,
    )
    prices_match = settings.bedrock_model == settings.llm_pricing_model and settings.aws_region == settings.llm_pricing_region
    budget = BudgetedSessionModel(client, args.max_live_calls,
        input_price=settings.llm_input_usd_per_million if prices_match else None,
        output_price=settings.llm_output_usd_per_million if prices_match else None)
    agent = FlorianoAgent(budget)
    results, started, status = [], perf_counter(), 'preflight'
    try:
        async with asyncio.timeout(args.request_timeout):
            async with httpx.AsyncClient(timeout=args.request_timeout, follow_redirects=False) as http:
                response = await http.get(args.api_url.rstrip('/') + '/health')
                response.raise_for_status()
            if not token and provider is not None:
                await provider.get_token()  # Valida credencial sem imprimir nem realizar inferência.
        if args.preflight_only:
            status = 'preflight_passed'
            return make_report(results, agent, started, status, args)
        print('Execução real: limite de chamadas cobre apenas Floriano; consumo do servidor é adicional.', file=sys.stderr, flush=True)
        status = 'running'
        write_json(args.output / 'summary.json', make_report(results, agent, started, status, args))
        for index in range(1, args.games + 1):
            if budget.stats['calls'] >= budget.max_calls:
                status = 'agent_budget_exhausted'
                break
            session = LiveSession(args.api_url, agent, args.output,
                max_steps=args.max_steps, max_seconds=args.max_seconds,
                request_timeout=args.request_timeout)
            try:
                result = await session.run(index)
            except Exception as error:
                # Detalhes de transporte podem carregar contexto; registrar só classe segura.
                result = {'index': index, 'status': 'error', 'result': None,
                          'stop_reason': type(error).__name__, 'game_id': None}
            if args.redis_url and result.get('game_id'):
                from src.simulation.audit import collect_server_statistics
                try:
                    result['server_statistics'] = await collect_server_statistics(
                        args.redis_url, args.redis_prefix or settings.redis_prefix, result['game_id'])
                except Exception as error:
                    result['server_statistics'] = {'available': False, 'error': type(error).__name__}
            else:
                result['server_statistics'] = {
                    'available': False, 'reason': 'Configure --redis-url para coletar consumo e auditoria do servidor.',
                }
            write_json(args.output / f'session-{index:04d}' / 'session.json', result)
            results.append(result)
            write_json(args.output / 'summary.json', make_report(results, agent, started, status, args))
            print(f"{index}/{args.games}: game={result.get('game_id')} status={result.get('status')} result={result.get('result')} steps={result.get('steps')}", file=sys.stderr, flush=True)
            if result.get('stop_reason') in ('CallBudgetExceeded', 'agent_budget_exhausted'):
                status = 'agent_budget_exhausted'
                break
        if status == 'running':
            status = 'finished' if all(item.get('status') == 'completed' for item in results) else 'finished_with_incomplete_sessions'
        return make_report(results, agent, started, status, args)
    except asyncio.CancelledError:
        status = 'interrupted'
        recorded_indices = {item.get('index') for item in results}
        for partial in sorted(args.output.glob('session-*/session.json')):
            try:
                item = json.loads(partial.read_text(encoding='utf-8'))
                if item.get('index') not in recorded_indices:
                    results.append(item)
            except (OSError, ValueError):
                pass
        raise
    except Exception as error:
        status = 'error'
        # Não persistir mensagens de erro do provedor: podem conter dados de requisição.
        write_json(args.output / 'error.json', {'error': type(error).__name__})
        raise
    finally:
        write_json(args.output / 'summary.json', make_report(results, agent, started, status, args))
        await budget.aclose()


def parser():
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument('--games', type=positive_int, required=True)
    argument_parser.add_argument('--max-live-calls', type=positive_int, required=True,
        help='Teto global de chamadas do LLM de Floriano; chamadas do servidor são adicionais.')
    argument_parser.add_argument('--api-url', default='http://localhost:7079')
    argument_parser.add_argument('--aws-profile', default=None)
    argument_parser.add_argument('--output', type=Path, default=Path('artifacts/simulations') / (
        'live-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]))
    argument_parser.add_argument('--max-steps', type=positive_int, default=200)
    argument_parser.add_argument('--max-seconds', type=positive_float, default=1800)
    argument_parser.add_argument('--request-timeout', type=positive_float, default=120)
    argument_parser.add_argument('--redis-url', default=None,
        help='Redis da aplicação para auditoria posterior; não é fornecido ao agente.')
    argument_parser.add_argument('--redis-prefix', default=None)
    argument_parser.add_argument('--preflight-only', action='store_true',
        help='Verifica HTTP e credencial sem criar partida nem chamar inferência.')
    return argument_parser


def main():
    args = parser().parse_args()
    try:
        report = asyncio.run(execute(args))
    except KeyboardInterrupt:
        print('Execução interrompida; consulte os registros incrementais.', file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Execução falhou: {type(error).__name__}. Verifique configuração e relatórios locais.', file=sys.stderr)
        return 1
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    return 0 if report['status'] in ('finished', 'preflight_passed') else 2


if __name__ == '__main__':
    raise SystemExit(main())
