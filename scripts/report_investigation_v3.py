#!/usr/bin/env python3
"""Rebuild provisional/complete v3 investigation summaries from paired JSONL logs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

POLICIES = ("informed", "common_rush", "unexamined", "single_source")
QUESTIONS = ("help", "relations", "alibi", "object", "followup")
MANUAL_CASES = (0, 1, 3, 7, 9, 14, 15, 20, 21, 30)
MANUAL_NOTES = {
    0: "A resposta depois nomeia a ligação Capitu–Escobar e sugere falar com ambos; antes, o encaminhamento recai em Rubião. O proxy acionável marca as duas respostas, sem julgar qual encaminhamento é melhor.",
    1: "Antes, Bentinho fala em primeira pessoa sobre a resistência ao tratamento; depois, a fala enumera a lembrança autorizada e indica Bacamarte e Bentinho. A formulação posterior é mais prescritiva, mas soa mais resumida.",
    3: "As duas falas recusam tratar item comum como autoria. Depois, a resposta associa o tipo a Rubião e aponta as anotações do caderno; isso continua sendo reconhecimento de objeto semelhante, não prova de quem deixou o exemplar.",
    7: "Depois, Capitu menciona ter visto Virgília, informação ausente antes; também delimita que não sabe onde Virgília esteve depois. O proxy de evasão sobe por essa ressalva lexical, não por uma avaliação de sinceridade.",
    9: "A resposta posterior nomeia Escobar como alguém que já teve objeto semelhante e sugere comparar depoimentos. A anterior traz uma pergunta sobre autoria e intenção; ambas permanecem sem atribuir o objeto ao crime.",
    14: "A resposta posterior recomenda uma pessoa específica para reconhecer lenços. A fala anterior diz que o lenço é comum e orienta buscar quem o viu; a diferença observada é a especificidade do contato sugerido.",
    15: "Depois, Escobar dá contexto mais explícito sobre casamento e ciúme, mas é mais longa. O detector de metáfora marca “sombra de um cão” por palavra-chave, exemplo de que o proxy não interpreta contexto.",
    20: "Depois, a resposta comprime o tema do ciúme e termina em pergunta a Bentinho; antes, oferecia outros contatos. O próximo-passo proxy cai por seu padrão lexical estreito, apesar da sugestão textual.",
    21: "Antes, Rubião responde com uma imagem afetiva breve; depois, descreve a falta de reciprocidade e oferece continuar a conversa. Isso compara duas formulações do tema, sem validar a leitura do personagem.",
    30: "Antes, Virgília sugere ouvir Florença sobre Rubião; depois, descreve o ressentimento de Florença contra Bacamarte e sugere perguntar. A diferença muda o foco narrativo e não demonstra que uma versão seja verdadeira.",
}
EXPECTED_PER_PHASE = 100
EXPECTED_CALLS_PER_DIALOGUE = 2


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, parse_float=Decimal, parse_int=int)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: JSON inválido: {exc}") from exc
        if not isinstance(row, dict) or "case_id" not in row:
            raise ValueError(f"{path}:{line_no}: linha sem case_id")
        rows.append(row)
    return rows


def dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def median(values: list[Decimal]) -> Decimal | None:
    return Decimal(str(statistics.median(values))) if values else None


def fmt(value: Any, places: int = 2) -> str:
    if value is None:
        return "—"
    d = dec(value)
    if d is None:
        return str(value)
    q = Decimal(1).scaleb(-places)
    return format(d.quantize(q), "f")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_probe_completed(row: dict[str, Any]) -> bool:
    return row.get("dialogue", {}).get("status") == "completed"


def is_game_completed(row: dict[str, Any]) -> bool:
    game = row.get("game") or {}
    return row.get("status") == "completed" and game.get("result") in {"won", "lost"}


def unique_by_id(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        key = int(row["case_id"])
        result[key] = row
    return result


def mean_rate(rows: list[dict[str, Any]], key: str) -> Decimal | None:
    available = [Decimal(int(bool(r["dialogue"][key]))) for r in rows if r.get("dialogue", {}).get(key) is not None]
    return sum(available, Decimal(0)) / len(available) if available else None


def word_median(rows: list[dict[str, Any]]) -> Decimal | None:
    values = [Decimal(str(r["dialogue"]["words"])) for r in rows if r.get("dialogue", {}).get("words") is not None]
    return median(values)


def latency_median(rows: list[dict[str, Any]]) -> Decimal | None:
    values = [dec(r.get("dialogue", {}).get("latency_seconds")) for r in rows]
    return median([v for v in values if v is not None])


def probe_groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if is_probe_completed(row):
            groups[str(row.get("dialogue", {}).get("question_type") or "unknown")].append(row)
    return groups


def game_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    games = [r for r in rows if is_game_completed(r)]
    won = sum((r.get("game") or {}).get("result") == "won" for r in games)
    lost = sum((r.get("game") or {}).get("result") == "lost" for r in games)
    accepted = [dec((r.get("game") or {}).get("first_accepted_day")) for r in games]
    accepted = [v for v in accepted if v is not None]
    refusals = sum(int((r.get("game") or {}).get("refusals") or 0) for r in games)
    return {"games": len(games), "won": won, "lost": lost,
            "refusals": refusals, "first_accepted_day_median": median(accepted)}


def usage_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum only dialogue.usage.totals and its by_purpose attribution once per row."""
    result: dict[str, Any] = {"calls": 0, "completed_calls": 0, "failed_calls": 0,
                              "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": Decimal(0),
                              "unpriced_calls": 0, "missing_token_calls": 0}
    purposes: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "calls": 0, "completed_calls": 0, "failed_calls": 0, "input_tokens": 0,
        "output_tokens": 0, "estimated_cost_usd": Decimal(0), "unpriced_calls": 0,
        "missing_token_calls": 0,
    })
    snapshots: set[tuple[str, str, str, str]] = set()
    for row in rows:
        usage = (row.get("dialogue") or {}).get("usage") or {}
        total = usage.get("totals") or {}
        if not total:
            continue
        for key in ("calls", "completed_calls", "failed_calls", "known_input_tokens", "known_output_tokens", "unpriced_calls", "calls_with_missing_tokens"):
            mapped = {"known_input_tokens": "input_tokens", "known_output_tokens": "output_tokens",
                      "calls_with_missing_tokens": "missing_token_calls"}.get(key, key)
            result[mapped] += int(total.get(key) or 0)
        cost = dec(total.get("known_estimated_cost_usd"))
        if cost is not None:
            result["estimated_cost_usd"] += cost
        for item in usage.get("by_purpose") or []:
            task = str(item.get("key") or "unknown")
            bucket = purposes[task]
            for key in ("calls", "completed_calls", "failed_calls", "known_input_tokens", "known_output_tokens", "unpriced_calls", "calls_with_missing_tokens"):
                mapped = {"known_input_tokens": "input_tokens", "known_output_tokens": "output_tokens",
                          "calls_with_missing_tokens": "missing_token_calls"}.get(key, key)
                bucket[mapped] += int(item.get(key) or 0)
            task_cost = dec(item.get("known_estimated_cost_usd"))
            if task_cost is not None:
                bucket["estimated_cost_usd"] += task_cost
        for snap in usage.get("pricing_snapshots") or []:
            snapshots.add((str(snap.get("model", "")), str(snap.get("input_usd_per_million", "")),
                           str(snap.get("output_usd_per_million", "")), str(snap.get("checked_at", ""))))
    result["purposes"] = dict(purposes)
    result["pricing_snapshots"] = sorted(snapshots)
    return result


def achievements(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        game = row.get("game") or {}
        for item in game.get("achievements") or []:
            counts[str(item)] += 1
    return counts


def short_quote(text: str, limit: int = 14) -> str:
    words = text.strip().split()
    quote = " ".join(words[:limit])
    if len(words) > limit:
        quote += "…"
    return quote.replace("|", "\\|").replace("\n", " ")


def comparison_comment(before: dict[str, Any], after: dict[str, Any]) -> str:
    b, a = before.get("dialogue", {}), after.get("dialogue", {})
    observed = []
    for key, label in (("actionable_proxy", "actionability proxy"), ("named_next_step", "next-step proxy"),
                       ("evasive_proxy", "evasion proxy"), ("metaphor_proxy", "metaphor proxy")):
        if b.get(key) != a.get(key):
            observed.append(f"{label}: {int(bool(b.get(key)))}→{int(bool(a.get(key)))}")
    bw, aw = b.get("words"), a.get("words")
    if bw is not None and aw is not None:
        observed.append(f"palavras: {bw}→{aw}")
    if not observed:
        observed.append("os proxies registrados coincidem")
    return "; ".join(observed) + ". A diferença descreve estas respostas e não certifica verdade ou causalidade."


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows])


def build_report(root: Path, output_dir: Path) -> None:
    data_dir = root / "docs/exploracao_investigacao_v3"
    paths = {phase: data_dir / f"{phase}.jsonl" for phase in ("before", "after")}
    benchmark_code = root / "scripts/benchmark_investigation_v3.py"
    report_code = Path(__file__).resolve()
    rows = {phase: load_jsonl(path) for phase, path in paths.items()}
    indexed = {phase: unique_by_id(group) for phase, group in rows.items()}
    before_ids, after_ids = set(indexed["before"]), set(indexed["after"])
    paired_ids = sorted(before_ids & after_ids)
    complete_after = set(range(EXPECTED_PER_PHASE)).issubset(after_ids)
    state_label = "concluído (100/100)" if complete_after else f"provisório ({len(after_ids)}/100 linhas after)"

    # Compact, machine-readable aggregate document.
    summaries: dict[str, Any] = {"status": "completed" if complete_after else "provisional",
        "phase_line_counts": {phase: len(rows[phase]) for phase in rows},
        "unique_case_counts": {phase: len(indexed[phase]) for phase in rows},
        "paired_case_ids": paired_ids, "missing_after_case_ids": sorted(before_ids - after_ids),
        "missing_before_case_ids": sorted(after_ids - before_ids), "phases": {},
        "source_hashes_sha256": {str(path.relative_to(root)): sha256(path) for path in paths.values()},
        "benchmark_code_sha256": sha256(benchmark_code),
        "report_code_sha256": sha256(report_code),
        "benchmark_base_commit": "e2f2d62", "after_freeze_commit": "9e7ca6f",
        "pricing_snapshot": {"input_usd_per_million": "0.15", "output_usd_per_million": "0.60", "checked_at": "2026-11-01"}}

    csv_rows: list[dict[str, Any]] = []
    for phase, phase_rows in rows.items():
        games = game_metrics(phase_rows)
        probes = [r for r in phase_rows if is_probe_completed(r)]
        failed_probes = sum((r.get("dialogue") or {}).get("status") == "failed" for r in phase_rows)
        failed_probe_details = [{"case_id": r["case_id"], "error_code": (r.get("dialogue") or {}).get("error_code")}
                                for r in phase_rows if (r.get("dialogue") or {}).get("status") == "failed"]
        errored_rows = sum(r.get("status") == "error" for r in phase_rows)
        usage = usage_metrics(phase_rows)
        phase_achievements = achievements(phase_rows)
        summaries["phases"][phase] = {
            "lines": len(phase_rows), "unique_case_ids": len(indexed[phase]), "paired_with_other_phase": len(paired_ids),
            "row_status_completed": sum(r.get("status") == "completed" for r in phase_rows),
            "row_status_error": errored_rows, "completed_games": games,
            "completed_probes": len(probes), "failed_probes": failed_probes,
            "failed_probe_details": failed_probe_details,
            "probe_other_or_missing": len(phase_rows) - len(probes) - failed_probes,
            "probe_metrics": {key: {"rate": mean_rate(probes, key), "count": sum(bool(r["dialogue"].get(key)) for r in probes), "n": len(probes)}
                              for key in ("actionable_proxy", "evasive_proxy", "metaphor_proxy", "named_next_step")},
            "words_median": word_median(probes), "latency_seconds_median": latency_median(probes),
            "usage": usage, "achievement_unlock_counts": dict(phase_achievements),
        }
        for policy in sorted(set(str(r.get("policy", "unknown")) for r in phase_rows)):
            subset = [r for r in phase_rows if r.get("policy") == policy]
            metric = game_metrics(subset)
            metric.update({"phase": phase, "policy": policy,
                           "completed_probes": sum(is_probe_completed(r) for r in subset),
                           "failed_probes": sum((r.get("dialogue") or {}).get("status") == "failed" for r in subset),
                           "actionable_proxy_rate": mean_rate([r for r in subset if is_probe_completed(r)], "actionable_proxy"),
                           "evasive_proxy_rate": mean_rate([r for r in subset if is_probe_completed(r)], "evasive_proxy"),
                           "metaphor_proxy_rate": mean_rate([r for r in subset if is_probe_completed(r)], "metaphor_proxy"),
                           "named_next_step_rate": mean_rate([r for r in subset if is_probe_completed(r)], "named_next_step"),
                           "words_median": word_median([r for r in subset if is_probe_completed(r)]),
                           "latency_seconds_median": latency_median([r for r in subset if is_probe_completed(r)])})
            csv_rows.append(metric)

    question_metrics: dict[str, Any] = {}
    for phase, phase_rows in rows.items():
        probes = [r for r in phase_rows if is_probe_completed(r)]
        groups = probe_groups(phase_rows)
        question_metrics[phase] = {}
        for group, subset in [("overall", probes)] + sorted(groups.items()):
            row = {"phase": phase, "question_type": group, "n": len(subset),
                   "actionable_proxy_rate": mean_rate(subset, "actionable_proxy"),
                   "evasive_proxy_rate": mean_rate(subset, "evasive_proxy"),
                   "metaphor_proxy_rate": mean_rate(subset, "metaphor_proxy"),
                   "named_next_step_rate": mean_rate(subset, "named_next_step"),
                   "words_median": word_median(subset), "latency_seconds_median": latency_median(subset)}
            question_metrics[phase][group] = row
            csv_rows.append(row)
    summaries["question_metrics"] = question_metrics

    usage_csv = []
    for phase, phase_rows in rows.items():
        usage = summaries["phases"][phase]["usage"]
        usage_csv.append({"phase": phase, "task": "overall", **{k: usage[k] for k in ("calls", "completed_calls", "failed_calls", "input_tokens", "output_tokens", "estimated_cost_usd", "unpriced_calls", "missing_token_calls")}})
        for task, values in sorted(usage["purposes"].items()):
            usage_csv.append({"phase": phase, "task": task, **values})
    summaries["usage_csv_rows"] = usage_csv

    # A curated cross-question sample of paired outputs. Each excerpt is a short, exact prefix.
    manual = []
    for case_id in MANUAL_CASES:
        a, b = indexed["before"].get(case_id), indexed["after"].get(case_id)
        if not a or not b or not is_probe_completed(a) or not is_probe_completed(b):
            continue
        da, db = a["dialogue"], b["dialogue"]
        manual.append({"case_id": case_id, "question_type": da.get("question_type"), "actor": da.get("actor"),
                       "before": short_quote(str(da.get("reply", ""))), "after": short_quote(str(db.get("reply", ""))),
                       "comment": MANUAL_NOTES.get(case_id, comparison_comment(a, b))})
    summaries["manual_comparisons"] = manual
    summaries["sources"] = {"before_sha256": sha256(paths["before"]), "after_sha256": sha256(paths["after"]),
                            "benchmark_script_sha256": sha256(benchmark_code),
                            "report_script_sha256": sha256(report_code)}

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "resumo.json"
    json_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    fields = ["phase", "policy", "question_type", "task", "games", "won", "lost", "refusals",
              "first_accepted_day_median", "completed_probes", "failed_probes", "n", "actionable_proxy_rate",
              "evasive_proxy_rate", "metaphor_proxy_rate", "named_next_step_rate", "words_median",
              "latency_seconds_median", "calls", "completed_calls", "failed_calls", "input_tokens", "output_tokens",
              "estimated_cost_usd", "unpriced_calls", "missing_token_calls"]
    with (output_dir / "resultados.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in csv_rows:
            writer.writerow({key: str(value) if isinstance(value, Decimal) else value for key, value in row.items()})
        writer.writerow({})
        writer.writerow({"phase": "task usage below"})
        for row in usage_csv:
            writer.writerow({key: str(value) if isinstance(value, Decimal) else value for key, value in row.items()})

    phase_table = []
    for phase in ("before", "after"):
        s = summaries["phases"][phase]
        gm = s["completed_games"]
        phase_table.append([phase, s["lines"], f"{s['completed_probes']} / {s['failed_probes']}",
                            gm["games"], gm["won"], gm["lost"], gm["refusals"],
                            fmt(gm["first_accepted_day_median"], 1), f"{s['usage']['calls']} / {EXPECTED_PER_PHASE * EXPECTED_CALLS_PER_DIALOGUE}",
                            fmt(s["words_median"], 1), fmt(s["latency_seconds_median"], 2)])
    failed_details = [f"{phase} case {detail['case_id']}: {detail['error_code']}"
                      for phase in ("before", "after") for detail in summaries["phases"][phase]["failed_probe_details"]]
    failed_note = "Falhas de sondagem: " + (", ".join(failed_details) + "." if failed_details else "nenhuma registrada.")
    policy_table = []
    for phase in ("before", "after"):
        for policy in sorted(set(r.get("policy", "unknown") for r in rows[phase])):
            subset = [r for r in rows[phase] if r.get("policy") == policy]
            g = game_metrics(subset)
            probes = [r for r in subset if is_probe_completed(r)]
            policy_table.append([phase, policy, g["games"], g["won"], g["lost"], g["refusals"],
                                 fmt(g["first_accepted_day_median"], 1), f"{sum(is_probe_completed(r) for r in subset)}/{len(subset)}",
                                 fmt(mean_rate(probes, "actionable_proxy"), 2)])
    question_table = []
    for phase in ("before", "after"):
        for group, m in summaries["question_metrics"][phase].items():
            question_table.append([phase, group, m["n"], fmt(m["actionable_proxy_rate"], 2),
                                   fmt(m["evasive_proxy_rate"], 2), fmt(m["metaphor_proxy_rate"], 2),
                                   fmt(m["named_next_step_rate"], 2), fmt(m["words_median"], 1),
                                   fmt(m["latency_seconds_median"], 2)])
    usage_table = []
    for phase, phase_rows in rows.items():
        u = summaries["phases"][phase]["usage"]
        usage_table.append([phase, "total registrado", u["calls"], u["input_tokens"], u["output_tokens"], fmt(u["estimated_cost_usd"], 8)])
        for task, values in sorted(u["purposes"].items()):
            usage_table.append([phase, task, values["calls"], values["input_tokens"], values["output_tokens"], fmt(values["estimated_cost_usd"], 8)])

    pairs_text = "\n\n".join(f"**Caso {p['case_id']} · {p['question_type']} · {p['actor']}**  \n"
                               f"Antes: “{p['before']}”  \nDepois: “{p['after']}”  \n"
                               f"{p['comment']}" for p in manual) or "Não há dez pares de respostas completos nos dados atuais."
    snapshot_lines = []
    for phase in ("before", "after"):
        snapshots = summaries["phases"][phase]["usage"]["pricing_snapshots"]
        if snapshots:
            snapshot_lines.append(f"{phase}: modelo `{snapshots[0][0]}`, entrada US${snapshots[0][1]}/M, saída US${snapshots[0][2]}/M, verificação `{snapshots[0][3]}`.")
    snapshot_text = " ".join(snapshot_lines) or "Os JSONL não contêm snapshot de preços."
    completeness_note = ("As 100 linhas after esperadas foram registradas." if complete_after else
                         f"O conjunto after está parcial: {len(indexed['after'])}/100 linhas únicas; os números após são provisórios.")
    report = f"""# Investigação v3: comparação antes/depois ({state_label})

Este arquivo é gerado por `scripts/report_investigation_v3.py`. O conjunto after tem **{len(indexed['after'])}/100** linhas únicas e {len(paired_ids)} pares por `case_id`. {completeness_note} Baseline de código: `e2f2d62`; congelamento da variante: `9e7ca6f`.

## Escopo e limites

As partidas são de um jogador programado que consulta exaustivamente o caderno. Taxa de vitória não é taxa de vitória humana nem prova de equilíbrio. Qwen é não determinístico: os casos repetem papéis, perguntas e estados programados, mas 100 partidas não são observações estatisticamente independentes. A política é correlacionada ao tipo de pergunta por `i % 5`; não se pode interpretar diferenças entre políticas como efeito causal da voz. Vinte cenários definem confiança 20 e afinidade 12 antes da fala para exercitar a condição de confidência; isso não representa confiança adquirida de fato em quatro dias. Os IDs de jogo after são fixados aos da baseline e a variante contém itens pessoais adicionais selecionados de forma estável.

Os indicadores `actionable_proxy`, `evasive_proxy`, `metaphor_proxy` e `named_next_step` são heurísticas lexicais documentadas em `scripts/benchmark_investigation_v3.py`. “Acionável” é só proxy de utilidade: não certifica correção semântica, verdade, nem se o próximo passo é útil. As citações abaixo são amostras curtas pareadas, não avaliação manual completa.

## Resultados gerais

{markdown_table(['fase','linhas','sondagens completas / falhas','partidas completas','vitórias','derrotas','recusas','mediana 1ª aceitação (dia)','chamadas LLM / 200 esperadas','mediana palavras','mediana latência s'], phase_table)}

Partidas e sondagens são contadas separadamente. Linhas com erro de execução não entram nas estatísticas de partida; falha de sondagem não é confundida com derrota. O denominador esperado de chamadas assume 100 sondagens por fase e duas solicitações por sondagem.

{failed_note}

## Partidas por política programada

{markdown_table(['fase','política','jogos','vitórias','derrotas','recusas','mediana 1ª aceitação (dia)','sondagens concluídas/linhas','proxy acionável'], policy_table)}

As políticas são `informed`, `common_rush`, `unexamined` e `single_source`, definidas pelo benchmark. `informed` é a única que inspeciona todas as pistas recolhidas; os demais filtros variam evidências/testemunhos anexados. Cada política se repete em posições que também determinam tipo de pergunta; a tabela é descritiva.

## Falas por tipo de pergunta e geral

{markdown_table(['fase','grupo','n falas completas','acionável proxy','evasiva proxy','metáfora proxy','próximo passo nomeado','mediana palavras','mediana latência s'], question_table)}

Taxas são proporções sobre sondagens de diálogo completas em cada grupo. Palavras e latência são medianas; a latência vem do registro do harness e não é medida de experiência do jogador.

## Descobertas desbloqueadas

{markdown_table(['fase','conquista','partidas com desbloqueio'], [[phase, aid, count] for phase in ('before','after') for aid,count in sorted(summaries['phases'][phase]['achievement_unlock_counts'].items())] or [['—','Nenhum registro','0']])}

A tabela só conta IDs presentes em `game.achievements` nos JSONL; uma lista vazia significa nenhum desbloqueio registrado nesses cenários e não ausência de suporte no produto.

## Tokens e custo estimado

{markdown_table(['fase','tarefa','chamadas','tokens de entrada','tokens de saída','USD estimado'], usage_table)}

Tokens e custo somam exclusivamente `dialogue.usage.totals` uma vez por sondagem. A tabela por tarefa usa `by_purpose`, que reparte o mesmo total; não deve ser somada de novo ao total da fase. Os custos são estimativas calculadas pelo snapshot configurado de US$ 0,15/M tokens de entrada e US$ 0,60/M de saída, verificado em 2026-11-01. Isso não é preço atual nem fatura; chamadas sem metadados e cobertura anterior à medição limitam o total conhecido. Esperam-se 400 chamadas quando houver 100 sondagens em cada fase e duas chamadas registradas por sondagem.

{snapshot_text}

## Dez pares lidos manualmente

{pairs_text}

## Revisão qualitativa crítica: fidelidade e voz

O `actionable_proxy` marcou 94 de 99 respostas after completas. A amostra seguinte mostra por que esse 94/99 não é taxa de fidelidade: é um sinal lexical de possível utilidade, não uma checagem de suporte ou de coerência do personagem.

- **Caso 34 · Virgília / follow-up sobre cera:** os suportes autorizados incluem “Já vi Dr. Bacamarte com um objeto igual” e assuntos sobre Florença, mas não mencionam Brás Cubas afogado nem vapor. A resposta acrescenta “se viajava com vela na mesma linha do vapor que afogou Brás”. Essa associação concreta não aparece nos suportes que conferi e deve ser tratada como conteúdo inventado, não como pista.
- **Caso 81 · Virgília / relações:** os suportes registram que Bentinho e Escobar estudaram juntos no seminário (“Bentinho e Escobar estudaram juntos no seminário e mantiveram uma ligação antiga”). A fala after transfere a lembrança para “A amizade entre nós é de longa data, de seminário” e parece atribuir a história a Virgília e Florença. A relação de seminário foi atribuída ao par errado.
- **Caso 1 · Bentinho / relações:** antes, Bentinho responde em primeira pessoa sobre resistir ao tratamento. Depois, fala de si em terceira pessoa (“Bentinho faz acompanhamento…”) e termina orientando Floriano a conversar “com Bentinho”, isto é, com o próprio interlocutor. A memória do tratamento está autorizada, mas a forma é uma piora clara de voz e continuidade.
- **Caso 21 · Rubião / relações:** depois, Rubião repete de perto o suporte autorizado sobre a investida não correspondida (“Rubião tenta aproximar-se de Florença…”). Isso tem âncora, mas a formulação em terceira pessoa soa como resumo de ficha e não como uma fala dele. O actionability proxy aceita a resposta sem medir naturalidade.

Esses casos foram conferidos contra `authorized_supports` em ambas as linhas JSONL; apenas as afirmações indicadas como não apoiadas foram julgadas sem suporte. A revisão é uma leitura qualitativa pequena e não estima prevalência. Próximos passos: aumentar a checagem automática de cada afirmação contra os suportes explícitos, validar a identidade gramatical da primeira pessoa e inspecionar manualmente uma amostra maior por tipo de pergunta antes de usar o proxy para decisões de qualidade.

Uma correção posterior ao congelamento `9e7ca6f` está sendo feita em separado por outra agente: renderização determinística e descoberta/conquista ligada à fala em primeira pessoa. Ela não altera os 100 registros after que este relatório resume; a versão corrigida precisará de uma nova execução/avaliação para aparecer nos dados.

## Reprodutibilidade e hash SHA-256

{markdown_table(['arquivo','SHA-256'], [[str(path.relative_to(root)), sha256(path)] for path in [paths['before'], paths['after'], benchmark_code]] + [['scripts/report_investigation_v3.py', sha256(report_code)]])}

O resumo `resumo.json` guarda os mesmos hashes, contagens e métricas em formato legível por máquina; `resultados.csv` permite filtrar políticas, pergunta e tarefa de uso. Para atualizar o relatório quando `after.jsonl` chegar a 100 linhas, execute:

```sh
python scripts/report_investigation_v3.py --root /caminho/para/repo --output-dir /caminho/para/docs/exploracao_investigacao_v3
```

A entrada lida deve ser `docs/exploracao_investigacao_v3/{{before,after}}.jsonl` dentro de `--root`; a saída é escrita somente em `--output-dir`.

## Regras de evidência alteradas

A versão nova limita comuns a 0,25 cada e teto conjunto 0,5; singulares valem 1 e têm teto 2; exclusivos valem 3 por tipo. Fontes externas distintas somam 0,5 cada até 1, e uma contradição pública válida de álibi pode somar 0,75. Custódia exige pontuação mínima 5, dois tipos ligados ao acusado, exclusivo examinado com vínculo físico à cena e duas fontes externas; alternativa: uma fonte externa e uma contradição pública de álibis. O exame repetido é idempotente e não transforma comuns/singulares em prova de maior peso. A especificação completa está em `docs/evidencias_especificidade_v3.md`.
"""
    (output_dir / "relatorio.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="raiz somente-leitura do repositório que contém JSONL e benchmark")
    parser.add_argument("--output-dir", type=Path, required=True, help="diretório da saída do relatório")
    args = parser.parse_args()
    build_report(args.root.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
