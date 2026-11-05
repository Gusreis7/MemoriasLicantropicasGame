"""Conquistas de informação efetivamente ouvida, com causa e IDs estáveis."""

from src.textutils import (
    normalize as normalized_text,
    word_tokens,
    has_phrase,
    has_any_phrase,
    without_quotes,
    clauses,
    has_word_start,
)
from src.contracts.investigation import Achievement

DEFINITIONS = {
    "marriage_triangle": (
        "Três versões de um casamento",
        "Descobriu o casamento de Capitu e Bentinho e a amizade de Capitu com Escobar.",
    ),
    "seminary_bond": (
        "Amigos do seminário",
        "Ouviu a história da ligação de Bentinho e Escobar no seminário.",
    ),
    "treatment_bentinho": (
        "Consultas e resistências",
        "Descobriu o acompanhamento de Bentinho por Bacamarte e sua resistência ao tratamento.",
    ),
    "florenca_father": (
        "A causa de Florença",
        "Soube da internação do pai de Florença e de sua oposição a Bacamarte.",
    ),
    "capitu_separation": (
        "Uma confidência de Capitu",
        "Capitu lhe confiou o desejo de separar-se de Bentinho.",
    ),
    "escobar_affection": (
        "Além da amizade",
        "Escobar lhe confiou seus sentimentos por Bentinho.",
    ),
    "personal_trace": (
        "Uma marca pessoal",
        "Examinou um vestígio pessoal e identificou sua marca distintiva.",
    ),
}
TOPIC_DISCOVERIES = {
    "casamento": "marriage_triangle",
    "amizade-capitu-escobar": "marriage_triangle",
    "seminario": "seminary_bond",
    "tratamento": "treatment_bentinho",
    "causa-florenca": "florenca_father",
    "separacao": "capitu_separation",
    "afeto-escobar": "escobar_affection",
}


def normalize(text):
    return normalized_text(text)


def award(state, achievement_id, now, *, source_message_id=None, source_npc_id=None):
    if achievement_id not in DEFINITIONS or any(
        a.id == achievement_id for a in state.achievements
    ):
        return state
    title, description = DEFINITIONS[achievement_id]
    record = Achievement(
        id=achievement_id,
        title=title,
        description=description,
        unlocked_at=now,
        source_message_id=source_message_id,
        source_npc_id=source_npc_id,
    )
    return state.model_copy(update={"achievements": (*state.achievements, record)})


def _assertion_clauses(content):
    result = []
    for statement in clauses(without_quotes(normalize(content))):
        if statement.endswith("?"):
            continue
        tokens = list(word_tokens(statement))
        # Resistência à medicação é afirmativa; negar o acompanhamento continua negação.
        adjusted = []
        index = 0
        while index < len(tokens):
            if tokens[index : index + 2] == ["nao", "toma"]:
                adjusted.extend(("resiste", "a", "tomar"))
                index += 2
            else:
                adjusted.append(tokens[index])
                index += 1
        text = " ".join(adjusted)
        if has_any_phrase(
            text, ("nao", "nunca", "jamais", "talvez", "se", "dizem que", "ouvi dizer")
        ):
            continue
        result.append(text)
    return result


def discovery_assertions(npc_id, content):
    name = {
        "bentinho": "bentinho",
        "escobar": "escobar",
        "capitu": "capitu",
        "florenca": "florenca",
        "rubiao": "rubiao",
        "virgilia": "virgilia",
        "bacamarte": "bacamarte",
    }.get(npc_id)
    result = []
    for statement in _assertion_clauses(content):
        tokens = word_tokens(statement)
        resolved = []
        index = 0
        while index < len(tokens):
            if name and tokens[index : index + 2] == ("meu", "pai"):
                resolved.extend(("pai", "de", name))
                index += 2
            else:
                resolved.append(
                    name if name and tokens[index] == "eu" else tokens[index]
                )
                index += 1
        result.append(" ".join(resolved))
    return " ".join(result)


def discoveries_in_reply(npc_id, content, allowed_ids):
    """IDs autorizados vêm da projeção privada, nunca da pergunta do jogador."""
    plain = discovery_assertions(npc_id, content)
    original = " ".join(_assertion_clauses(content))
    names = set(word_tokens(plain))
    # Conceitos usam vocabulário explícito e radicais simples de palavras portuguesas.
    checks = {
        "marriage_triangle": {"capitu", "bentinho", "escobar"} <= names
        and has_word_start(plain, ("casad", "casamento", "marido"))
        and has_word_start(plain, ("amig", "amizade")),
        "seminary_bond": {"bentinho", "escobar", "seminario"} <= names
        and has_word_start(plain, ("estud", "amig", "ligacao", "juntos")),
        "treatment_bentinho": {"bentinho", "bacamarte"} <= names
        and has_word_start(plain, ("tratamento", "medicacao", "remedio", "consult"))
        and has_word_start(plain, ("resist", "evita", "falta", "recusa")),
        "florenca_father": {"florenca", "pai", "bacamarte"} <= names
        and (has_word_start(plain, ("intern",)) or has_phrase(plain, "casa verde")),
        "capitu_separation": npc_id == "capitu"
        and bool(
            set(word_tokens(original))
            & {"quero", "desejo", "penso", "pretendo", "decidi", "vou"}
        )
        and (
            has_word_start(original, ("separ",))
            or has_any_phrase(original, ("deixar meu marido", "deixar bentinho"))
        ),
        "escobar_affection": npc_id == "escobar"
        and has_phrase(original, "bentinho")
        and (
            has_word_start(original, ("amo", "apaixon"))
            or has_any_phrase(
                original,
                ("sinto por", "meu amor", "alem da amizade", "mais que amizade"),
            )
        ),
    }
    return tuple(
        identifier
        for identifier, accepted in checks.items()
        if identifier in set(allowed_ids) and accepted
    )
