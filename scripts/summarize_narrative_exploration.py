"""Resume artefatos existentes; não cria jogos, não chama LLM e não consulta preços.

Exemplo: python scripts/summarize_narrative_exploration.py --root /caminho/repo
Use --output-dir para gerar a documentação em outro checkout.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import hashlib
import importlib
import json
from pathlib import Path
import statistics
import sys

D = Decimal
COUNTS = ('calls', 'completed_calls', 'failed_calls', 'cancelled_calls', 'known_input_tokens',
          'known_output_tokens', 'calls_with_missing_tokens', 'unpriced_calls', 'duration_ms')


def read_rows(path):
    if not path.exists():
        return [], []
    rows, warnings = [], []
    lines = path.read_text().splitlines()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if number != len(lines):
                raise ValueError(f'{path}:{number}: JSON inválido no meio do arquivo')
            warnings.append(f'{path.name}: última linha incompleta ignorada; executar novamente após conclusão')
    return rows, warnings


def bucket():
    return {**{k: 0 for k in COUNTS}, 'known_estimated_cost_usd': D(0),
            'records_without_usage': 0, 'cost_complete': True}


def add_usage(total, values):
    if not values:
        total['records_without_usage'] += 1
        total['cost_complete'] = False
        return
    for key in COUNTS:
        value = values.get(key)
        if value is not None:
            total[key] += int(value)
        elif key in ('calls', 'known_input_tokens', 'known_output_tokens'):
            total['cost_complete'] = False
    cost = values.get('known_estimated_cost_usd')
    if cost is not None:
        total['known_estimated_cost_usd'] += D(str(cost))
    total['cost_complete'] &= bool(values.get('cost_complete', False))


def outcomes(rows):
    result = []
    for policy in sorted({r.get('policy', 'unknown') for r in rows}):
        selected = [r for r in rows if r.get('policy', 'unknown') == policy]
        wins = sum(r.get('result') == 'won' for r in selected)
        result.append({'policy': policy, 'games': len(selected), 'wins': wins,
                       'losses': sum(r.get('result') == 'lost' for r in selected),
                       'errors': sum(r.get('result') == 'error' for r in selected),
                       'win_rate': wins / len(selected),
                       'methods': dict(Counter(r.get('method') or r.get('result') for r in selected)),
                       'mean_day': statistics.mean(r['day'] for r in selected if 'day' in r)
                           if any('day' in r for r in selected) else None})
    return result


def algebra(root):
    """Avaliações pontuais das fórmulas, sem partidas ou amostragem aleatória."""
    sys.path.insert(0, str(root / 'src'))
    math = importlib.import_module('memorias_licantropicas.modules.knowledge.mechanics')
    contracts = importlib.import_module('memorias_licantropicas.contracts.social')
    assembly = importlib.import_module('memorias_licantropicas.modules.investigation.assembly')
    R = contracts.Relationship
    friend = (R(actor_id='capitu', target_id='escobar', affinity=70, trust=60, loyalty=70),)
    enemy = (R(actor_id='capitu', target_id='escobar', affinity=-70, trust=-60, resentment=90, suspicion=90),)
    hostile_player = (R(actor_id='capitu', target_id='player', affinity=-80, trust=-90, resentment=90, suspicion=80),)
    examples = [('neutro, argumento fraco', (), .4, 0),
                ('neutro, argumento forte', (), .4, 1),
                ('amigo protegido, prova moderada', friend, .65, .7),
                ('inimigo, mesma prova moderada', enemy, .65, .7),
                ('hostilidade a Floriano, prova fraca', hostile_player, .1, .1),
                ('amigo protegido, prova forte', friend, 1, .8),
                ('neutro, eloquência sem prova', (), 0, 1)]
    output = []
    for label, relations, proof, argument in examples:
        scores = math.vote_scores('capitu', 'escobar', relations, proof, argument)
        ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
        target, score = ordered[0]
        choice = target if score >= assembly.VOTE_THRESHOLD and score - ordered[1][1] >= assembly.VOTE_MARGIN else None
        output.append({'case': label, 'proof': proof, 'argument': argument,
                       'scores': scores, 'vote': choice})
    return {'vote_threshold': assembly.VOTE_THRESHOLD, 'vote_margin': assembly.VOTE_MARGIN,
            'formula_source_sha256': hashlib.sha256(Path(math.__file__).read_bytes()).hexdigest(),
            'examples': output}


def jsonable(value):
    if isinstance(value, D):
        return str(value)
    raise TypeError(type(value).__name__)


def money(value):
    return format(D(value).quantize(D("0.00000001")), "f")


def table(rows):
    result = ['| Política | Partidas | Vitórias | Derrotas | Erros | Métodos |',
              '| --- | ---: | ---: | ---: | ---: | --- |']
    for row in rows:
        methods = ', '.join(f'{k}: {v}' for k, v in row['methods'].items())
        result.append(f"| {row['policy']} | {row['games']} | {row['wins']} | {row['losses']} | {row['errors']} | {methods} |")
    return '\n'.join(result)


def build_report(summary):
    count, real = summary['scenario_accounting'], summary['real_usage']
    lines = ['# Exploração das mecânicas narrativas: resultados e custo', '',
        'Relatório gerado de arquivos JSONL existentes. Este comando não executa partidas, não faz inferências e não consulta preços.', '',
        '## Escopo e contabilização', '',
        f"Foram contabilizados **{count['total_scenarios']} cenários/tentativas**: {count['failed_setup_attempts']} inicializações com erro, "
        f"{count['completed_rule_games']} partidas completas de regras e {count['distinct_live_encounters']} encontros reais com Qwen. "
        'Continuações dos mesmos encontros não contam como novas partidas; seus custos entram integralmente em fases separadas.', '',
        'As 21 primeiras tentativas falharam no setup porque o método `seed` colidia com um atributo inteiro. '
        'Os registros foram preservados e não entram no denominador de vitórias das partidas completas. '
        'Das 72 partidas posteriores, as primeiras 21 são calibragem; as 51 restantes são o conjunto posterior à correção da extração de “matou”. '
        'As fases foram separadas cronologicamente, sem excluir as derrotas anteriores.', '',
        '## Regras: calibragem de 21 partidas completas', '', table(summary['policies']['calibration']), '',
        '## Regras: conjunto posterior de 51 partidas completas', '', table(summary['policies']['holdout']), '',
        '## O que os resultados demonstram', '',
        f"- As partidas completas registraram {summary['rule_metrics']['reported_transition_errors']} ocorrências de erro em ações e "
        f"{summary['rule_metrics']['false_confession_wins']} vitórias atribuídas a confissões de inocentes. Essa contagem cobre somente as transições realmente exercitadas.",
        '- A política informada coleta objetos e consulta todas as testemunhas acessíveis; seu alto aproveitamento mostra que o conjunto de pistas resolve esses cenários. '
        'Não mede a dificuldade para uma pessoa que conversa livremente nem prova equilíbrio humano.',
        '- A confissão natural foi alimentada por uma persona programada que sabe o próprio papel e devolve uma frase de confissão/rendição para o culpado. '
        'Isso verifica a ligação chat → mestre → resolução, mas não mede a probabilidade de convencer um Qwen real a confessar.',
        '- A política `hostile_rash` aplica previamente 12 eventos hostis fortes a todos os NPCs. Ela verifica a possibilidade de expulsar Floriano sob relações deterioradas; '
        'não estima a frequência dessa derrota em conversa cotidiana.',
        '- A política `rash` faz uma primeira acusação precipitada, depois passa a coletar pistas e usar a política informada de prisão. '
        'Suas vitórias não demonstram sucesso de acusações aleatórias durante toda a partida.',
        '- A semeadura produziu assuntos autorais e raízes de fofoca. Essas partidas não executam uma longa rede autônoma de conversas; '
        'propagação, confidências e reputação precisam também dos testes específicos e de observação de partidas humanas.', '',
        '## Qwen real: custo por fase e qualidade', '',
        '| Fase | Respostas concluídas / registros | Chamadas | Entrada | Saída | Tokens desconhecidos (chamadas) | Custo conhecido USD |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for phase in real['phases']:
        u = phase['usage']
        lines.append(f"| {phase['file']} | {phase['completed']}/{phase['records']} | {u['calls']} | {u['known_input_tokens']} | {u['known_output_tokens']} | {u['calls_with_missing_tokens']} | {u['known_estimated_cost_usd']} |")
    lines += ['', '| Tarefa (todas as fases reais) | Chamadas | Entrada | Saída | USD conhecido |',
              '| --- | ---: | ---: | ---: | ---: |']
    for task, u in sorted(real['by_purpose'].items()):
        lines.append(f"| {task} | {u['calls']} | {u['known_input_tokens']} | {u['known_output_tokens']} | {u['known_estimated_cost_usd']} |")
    total = real['totals']
    lines += ['', f"Total registrado: **{total['calls']} chamadas**, **{total['known_input_tokens']} tokens de entrada**, "
              f"**{total['known_output_tokens']} de saída**, **USD {total['known_estimated_cost_usd']}** de custo conhecido estimado. "
              f"Resumos sem uso registrado: {total['records_without_usage']}; chamadas sem tarifa: {total['unpriced_calls']}. "
              'Custo é estimativa dos tokens observados, não extrato da fatura, crédito ou gratuidade.', '',
              'As fases usam repositórios de medição separados e carregam somente as falas anteriores para continuar o mesmo encontro; '
              'seus contadores são incrementais por fase, não totais cumulativos que devam ser deduplicados.', '',
              'Leitura qualitativa das primeiras fases: as respostas iniciais foram extensas, incluíram narração de gestos e locais não autorizados '
              '(por exemplo, a escultura da Cachoeira). A continuação encurtou as falas, mas preservou deriva narrativa: Capitu ainda chamou '
              'Floriano de “delegado”, Escobar revelou afeto íntimo e surgiram locais/fontes inventados. '
              'Uma resposta concluída tecnicamente não equivale a resposta aprovada em naturalidade ou fidelidade.', '']
    quality = next((p for p in real['phases'] if p['file'] == 'live_quality.jsonl'), None)
    if quality:
        lines += [f"A terceira fase contém {quality['records']}/7 registros após a revisão de qualidade. "
                  'Os sinais automáticos abaixo são triagem; exigem leitura das respostas e não certificam ausência de alucinação.',
                  f"Palavras por resposta concluída: média {quality['mean_reply_words']:.1f}; "
                  f"máximo {quality['max_reply_words']}. Referências a delegado: {quality['delegate_mentions']}. "
                  f"Respostas acima de 120 palavras: {quality['long_replies']}. ",
                  f"O mestre propôs reparo em {quality['corrected_replies']}/7 respostas; problemas identificados: {quality['quality_issues']}.",
                  'A leitura manual ainda encontrou alegações não sustentadas no reparo de Florença (Capitu copiando seus versos) '
                  'e na resposta de Bacamarte (visitas noturnas e associação com escuridão). O reparo melhorou concisão e tratamento, '
                  'mas não aprovou o grounding narrativo: uma correção do LLM pode introduzir nova invenção.', '']
    else:
        lines += ['A terceira fase `live_quality.jsonl` ainda não estava disponível nesta geração do relatório. '
                  'O script deve ser executado novamente quando ela terminar; não se presume aprovação de qualidade.', '']
    lines += ['## Influência algébrica de argumentos e vínculos', '',
              f"Avaliações pontuais da função real `vote_scores`; não são novas simulações. Limiar {summary['algebra']['vote_threshold']:.2f}, "
              f"margem mínima {summary['algebra']['vote_margin']:.2f}.", '',
              '| Condição | Prova | Argumento | Score acusado | Score Floriano | Voto |',
              '| --- | ---: | ---: | ---: | ---: | --- |']
    for r in summary['algebra']['examples']:
        lines.append(f"| {r['case']} | {r['proof']:.2f} | {r['argument']:.2f} | {r['scores']['escobar']:.4f} | {r['scores']['player']:.4f} | {r['vote'] or 'abstenção'} |")
    lines += ['', 'Uma fala coerente pode alterar voto na fronteira; simpatia protege e ressentimento favorece acusação. '
              'Prova forte supera amizade moderada, enquanto hostilidade a Floriano pode inverter o alvo. '
              'Sem prova, eloquência isolada não ultrapassa o limiar no caso neutro. Isso é propriedade das fórmulas, não resultado de um teste humano.', '',
              '## Projeção de custo por partida', '']
    estimate = summary['cost_projection']
    if estimate:
        lines += [f"Base observada: {estimate['sample_completed_exchanges']} trocas concluídas de `{estimate['sample_phase']}`; "
                  f"média USD {money(estimate['observed_mean_exchange_usd'])} por troca, incluindo tarefas medidas do mestre/reparo. "
                  f"Vinte trocas com a mesma distribuição custariam aproximadamente USD {money(estimate['twenty_exchanges_usd'])}.", '',
                  '| Hipótese adicional | Chamadas | Entrada/chamada | Saída/chamada | USD estimado |',
                  '| --- | ---: | ---: | ---: | ---: |']
        for extra in estimate['assumed_extras']:
            lines.append(f"| {extra['purpose']} | {extra['calls']} | {extra['input_tokens_per_call']} | {extra['output_tokens_per_call']} | {extra['cost_usd']} |")
        lines += ['', f"Total ilustrativo: **USD {money(estimate['illustrative_total_usd'])}**. "
                  'Os extras são hipóteses de tamanho de contexto, não tokens medidos: 16 falas sociais, 8 extrações e uma chamada de assembleia. '
                  'O total não é limite de cobrança: contexto crescente, retries, falhas e reparos mudam o custo. '
                  'Não foi cobrada inferência nos 72 jogos programados; o custo conhecido do provedor nesta exploração vem dos encontros reais.', '',
                  f"Snapshot usado: `{estimate['pricing']['model']}`, entrada USD {estimate['pricing']['input_usd_per_million']}/milhão, "
                  f"saída USD {estimate['pricing']['output_usd_per_million']}/milhão; consulta registrada {estimate['pricing'].get('checked_at', 'desconhecida')}. "
                  f"Fonte registrada: {estimate['pricing'].get('source', 'não informada')}. Não houve nova consulta de tarifa.", '']
    else:
        lines += ['Não foi possível produzir uma projeção monetária completa com os snapshots e resumos disponíveis.', '']
    lines += ['## Critérios de aceite e pontos ainda abertos', '',
              '- **Passou nos cenários exercitados:** fechamento por assembleia/prisão/confissão programada, derrota por sobrevivência e expulsão de Floriano; sem promoção de confissão de inocente registrada nessas partidas.',
              '- **Falhou e foi corrigido:** colisão do método `seed` no setup; reconhecimento de “matou” na admissão natural. As falhas anteriores permanecem nos artefatos.',
              '- **Não aprovado como equilíbrio humano:** políticas informadas muito eficientes, hostilidade forte concentrada em 12 eventos programados e pequenas amostras por personagem. O holdout usa código corrigido, mas a distribuição de políticas e cenários é conhecida pelo autor da exploração.',
              '- **Qualidade narrativa inicialmente falhou:** excesso de narração, intimidade prematura e detalhes inventados nas amostras reais. A terceira fase precisa de leitura manual; custo/latência não bastam como aceite.',
              '- **Próxima avaliação recomendada:** sessões humanas sem acesso ao papel secreto, mistura gradual de cordialidade e hostilidade, fofocas transmitidas ao longo do dia, confidências abertas por ações concretas e argumentos livres na assembleia. Não foram iniciadas novas partidas para ampliar esta exploração.', '']
    lines += ['## Reprodução do relatório', '',
              '`uv run python scripts/summarize_narrative_exploration.py --root .` lê os artefatos e regrava relatório, resumo JSON e CSV. '
              'Não executa o runner de partidas. O resumo registra SHA-256 dos arquivos de entrada e da função de votação usada na análise algébrica.', '']
    if summary['warnings']:
        lines += ['## Avisos de geração', '', *['- ' + warning for warning in summary['warnings']], '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    data = args.data_dir or root / 'docs/exploracao_narrativa'
    output = args.output_dir or root / 'docs/exploracao_narrativa'
    output.mkdir(parents=True, exist_ok=True)
    setup, warnings = read_rows(data / 'calibration.jsonl')
    games, notes = read_rows(data / 'validation.jsonl'); warnings += notes
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob('*.jsonl')}
    phases, total, all_csv, prices = [], bucket(), [], []
    all_purposes = defaultdict(bucket)
    for name, rows in [('setup_failed', setup), ('rules_calibration', games[:21]), ('rules_holdout', games[21:])]:
        for row in rows:
            all_csv.append({'phase': name, 'seed': row.get('seed'), 'policy': row.get('policy'),
                'wolf': row.get('wolf'), 'result': row.get('result'), 'method': row.get('method'),
                'error_type': row.get('error'), 'error_detail': row.get('detail'),
                'day': row.get('day'), 'errors': len(row.get('errors', [])) + int(row.get('result') == 'error'),
                'calls': row.get('provider_calls', 0), 'input_tokens': row.get('measured_input_tokens', 0),
                'output_tokens': row.get('measured_output_tokens', 0), 'cost_usd': '0' if row.get('provider_calls', 0) == 0 else None})
    files = sorted(data.glob('live*.jsonl'), key=lambda p: ({'live.jsonl': 0, 'live_followup.jsonl': 1, 'live_quality.jsonl': 2}.get(p.name, 3), p.name))
    latest_rows, latest_phase = [], None
    for path in files:
        rows, notes = read_rows(path); warnings += notes
        usage, purposes = bucket(), defaultdict(bucket)
        for row in rows:
            raw = row.get('usage') or {}
            totals = raw.get('totals')
            add_usage(usage, totals); add_usage(total, totals)
            for item in raw.get('by_purpose', []):
                add_usage(purposes[item['key']], item)
                add_usage(all_purposes[item['key']], item)
            for price in raw.get('pricing_snapshots', []):
                if price not in prices:
                    prices.append(price)
            all_csv.append({'phase': path.stem, 'npc_id': row.get('npc_id'),
                'game_id': row.get('game_id') or raw.get('game_id'), 'result': row.get('status'),
                'errors': int(row.get('status') != 'completed'), 'calls': (totals or {}).get('calls'),
                'input_tokens': (totals or {}).get('known_input_tokens'), 'output_tokens': (totals or {}).get('known_output_tokens'),
                'cost_usd': (totals or {}).get('known_estimated_cost_usd')})
        complete = [r for r in rows if r.get('status') == 'completed']
        words = [len(r.get('reply', '').split()) for r in complete]
        phases.append({'file': path.name, 'records': len(rows), 'completed': len(complete),
            'usage': usage, 'by_purpose': dict(purposes), 'mean_reply_words': statistics.mean(words) if words else 0,
            'max_reply_words': max(words, default=0), 'long_replies': sum(w > 120 for w in words),
            'delegate_mentions': sum('delegado' in r.get('reply', '').lower() for r in complete),
            'quality_issues': dict(Counter(issue for r in rows for a in r.get('assessments', []) for issue in a.get('issues', []))),
            'corrected_replies': sum(any(a.get('corrected_reply') for a in r.get('assessments', [])) for r in rows)})
        if complete:
            latest_rows, latest_phase = complete, path.name
    first_live, _ = read_rows(data / 'live.jsonl')
    distinct = {r.get('game_id') or (r.get('usage') or {}).get('game_id') or r.get('npc_id') for r in first_live}
    projection = None
    if latest_rows:
        priced_rows = [r for r in latest_rows if (r.get('usage') or {}).get('totals', {}).get('cost_complete')]
        if priced_rows:
            snapshot = next((p for r in reversed(priced_rows) for p in (r['usage'].get('pricing_snapshots') or []) if p.get('input_usd_per_million') is not None and p.get('output_usd_per_million') is not None), None)
            if snapshot:
                cost = sum((D(str(r['usage']['totals']['known_estimated_cost_usd'])) for r in priced_rows), D(0)) / len(priced_rows)
                extras = []
                for purpose, calls, inp, out in [('social_speech', 16, 1500, 100), ('knowledge_extraction', 8, 2000, 250), ('assembly_debate', 1, 3000, 700)]:
                    value = D(calls) * (D(inp) * D(snapshot['input_usd_per_million']) + D(out) * D(snapshot['output_usd_per_million'])) / D(1_000_000)
                    extras.append({'purpose': purpose, 'calls': calls, 'input_tokens_per_call': inp, 'output_tokens_per_call': out, 'cost_usd': value})
                projection = {'sample_phase': latest_phase, 'sample_completed_exchanges': len(priced_rows),
                    'observed_mean_exchange_usd': cost, 'twenty_exchanges_usd': 20 * cost,
                    'assumed_extras': extras, 'illustrative_total_usd': 20 * cost + sum((e['cost_usd'] for e in extras), D(0)), 'pricing': snapshot}
    summary = {'scenario_accounting': {'failed_setup_attempts': len(setup), 'completed_rule_games': len(games),
                    'distinct_live_encounters': len(distinct), 'total_scenarios': len(setup) + len(games) + len(distinct),
                    'live_utterance_records': sum(p['records'] for p in phases)},
        'policies': {'setup': outcomes(setup), 'calibration': outcomes(games[:21]), 'holdout': outcomes(games[21:]), 'all_rules': outcomes(games)},
        'rule_metrics': {'reported_transition_errors': sum(len(r.get('errors', [])) for r in games),
                         'false_confession_wins': sum(r.get('factual_false_confession_wins', 0) for r in games)},
        'real_usage': {'totals': total, 'phases': phases, 'by_purpose': dict(all_purposes), 'pricing_snapshots': prices},
        'algebra': algebra(root), 'cost_projection': projection, 'source_sha256': sources, 'warnings': warnings}
    (output / 'resumo.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=jsonable) + '\n')
    (output / 'relatorio.md').write_text(build_report(summary))
    fields = ['phase', 'seed', 'policy', 'wolf', 'npc_id', 'game_id', 'result', 'method', 'day', 'errors', 'error_type', 'error_detail', 'calls', 'input_tokens', 'output_tokens', 'cost_usd']
    with (output / 'resultados.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(all_csv)
    print(json.dumps({'scenarios': summary['scenario_accounting'], 'known_real_cost_usd': total['known_estimated_cost_usd'], 'output': str(output)}, default=jsonable))


if __name__ == '__main__':
    main()
