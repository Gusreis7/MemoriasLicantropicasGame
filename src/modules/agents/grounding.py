"""Âncoras literais de presença/fonte; ambiguidade é avaliada pelo mestre."""

from typing import Literal
from src.textutils import (
    normalize,
    word_tokens,
    has_phrase,
    has_any_phrase,
    clauses,
    without_quotes,
)

GroundingIssue = Literal["unsupported_presence", "unsupported_source"]
normalized = normalize


def grounding_issues(content, observations, names):
    if observations is None:
        return ()
    issues = []
    statements = clauses(without_quotes(normalize(content)))
    versions = observations.get("suas_versoes_de_interrogatorio", ())
    locations = {
        "praca_verde": "praca",
        "cabana_capitu": "cabana",
        "casa_verde": "casa verde",
        "cafe_largo": "cafe",
        "cais_lanternas": "cais",
    }
    own_locations = {
        locations.get(record.get("local_id"))
        for record in (*versions, *observations.get("suas_atividades", ()))
        if record.get("local_id")
    }
    for statement in statements:
        tokens = word_tokens(statement)
        if statement.endswith("?") or set(tokens) & {
            "nao",
            "nunca",
            "jamais",
            "talvez",
            "se",
        }:
            continue
        first_person = (
            bool(set(tokens) & {"estive", "passei", "encontrei", "fui", "andei"})
            or has_any_phrase(statement, ("eu estava", "eu andava"))
            or tokens[:1] == ("estava",)
        )
        if first_person and any(
            has_phrase(statement, place) and place not in own_locations
            for place in locations.values()
        ):
            issues.append("unsupported_presence")
            break
    memory = observations.get("memoria_social", {})
    known_sources = {
        entry.get("quem_falou") for entry in memory.get("memorias_relevantes", ())
    }
    known_sources.update(memory.get("fontes_conhecidas", ()))
    known_sources.update(
        entry.get("interlocutor_id")
        for entry in memory.get("encontros_anteriores", ())
        if entry.get("falas")
    )
    for identifier, name in names.items():
        if identifier in known_sources or identifier == "player":
            continue
        person = normalize(name.split()[0])
        for statement in statements:
            tokens = word_tokens(statement)
            if statement.endswith("?") or set(tokens) & {
                "nao",
                "nunca",
                "jamais",
                "talvez",
                "se",
            }:
                continue
            attributed = person in tokens and has_any_phrase(
                statement, ("me contou", "me disse", "me relatou", "me avisou")
            )
            prefixes = (
                "ouvi de",
                "ouvi dizer de",
                "ouvi da",
                "ouvi pela",
                "ouvi pelo",
                "ouvi dizer da",
                "ouvi dizer pela",
                "soube por",
                "por meio de",
                "me foi contado por",
                "me foi contada por",
                "me foi dito por",
                "me foi dita por",
                "me foi relatado por",
                "me foi relatada por",
            )
            attributed = attributed or any(
                has_phrase(statement, f"{prefix} {honorific}{person}")
                for prefix in prefixes
                for honorific in ("", "senhor ", "senhora ")
            )
            if attributed:
                issues.append("unsupported_source")
                return tuple(issues)
    return tuple(issues)
