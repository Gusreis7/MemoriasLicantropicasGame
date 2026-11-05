"""Validação conservadora de presenças/fontes; nunca reescreve uma fala."""

import re
import unicodedata
from typing import Literal

GroundingIssue = Literal["unsupported_presence", "unsupported_source"]


def normalized(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c)
    )


def grounding_issues(
    content: str, observations: dict | None, names: dict[str, str]
) -> tuple[GroundingIssue, ...]:
    if observations is None:
        return ()
    issues: list[GroundingIssue] = []
    text = normalized(content)
    versions = observations.get("suas_versoes_de_interrogatorio", ())
    locations = {
        "praca_verde": "praca",
        "cabana_capitu": "cabana",
        "casa_verde": "casa verde",
        "cafe_largo": "cafe",
        "cais_lanternas": "cais",
    }
    # First-person assertions only: reporting "Bentinho estava no cais" is not
    # an assertion that the speaker was there. Semantic review handles ambiguity.
    has_presence = re.search(
        r"\b(?:estive|passei|encontrei|fui|andei)\b|\beu\s+(?:estava|andava)\b|^\s*estava\b",
        text,
    )
    own_locations = {
        locations.get(record.get("local_id"))
        for record in (*versions, *observations.get("suas_atividades", ()))
        if record.get("local_id")
    }
    if has_presence and any(
        place in text and place not in own_locations for place in locations.values()
    ):
        issues.append("unsupported_presence")
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
        person = re.escape(normalized(name.split()[0]))
        direct_source = (
            rf"\b{person}\b.{{0,16}}\bme (?:contou|disse|relatou|avisou)\b|"
            rf"\b(?:ouvi(?: dizer)?[ ,]*(?:de|pela?|da)|soube por|por meio de)\s+(?:senhora?\s+)?{person}\b|"
            rf"\b(?:me foi (?:contad[ao]|dit[ao]|relatad[ao]) por)\s+{person}\b"
        )
        if re.search(direct_source, text):
            issues.append("unsupported_source")
            break
    return tuple(issues)
