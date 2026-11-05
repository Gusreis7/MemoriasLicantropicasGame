"""Utilidade não certifica verdade: uma fofoca atribuída também pode ajudar."""

from memorias_licantropicas.modules.agents.support import words, normalized, NAMES
from memorias_licantropicas.textutils import word_tokens, has_phrase, has_any_phrase


def useful_report(
    content, observations, *, kind="conversation", quote="", suggested=False
):
    if not observations or not content.strip():
        return False
    text = normalized(content)
    tokens = word_tokens(text)
    if tokens in {
        ("ola",),
        ("oi",),
        ("bom", "dia"),
        ("boa", "tarde"),
        ("boa", "noite"),
        ("obrigado",),
        ("obrigada",),
    }:
        return False
    if has_any_phrase(
        text, ("nao sei", "nao reconheco", "nada a declarar")
    ) and not set(tokens) & {"vi", "ouvi", "pergunte", "procure", "converse"}:
        return False
    from memorias_licantropicas.modules.session_master.validation import (
        own_assertion_clauses,
    )

    plot = observations.get("seu_conflito_privado") or {}
    if plot.get("estado") == "succeeded" and any(
        set(word_tokens(clause)) & {"matei", "assassinei"}
        and has_phrase(clause, plot.get("alvo", ""))
        for clause in own_assertion_clauses(content)
    ):
        return True
    actual = words(content) - {normalized(name) for name in NAMES.values()}
    for support in observations.get("apoios_de_conversa", ()):
        expected = words(support.get("statement", "")) - {
            normalized(name) for name in NAMES.values()
        }
        if len(actual & expected) >= min(4, max(2, len(expected) // 3)):
            return True
    return bool(
        suggested
        and quote
        and quote in content
        and kind in ("alibi", "admission")
        and (
            set(tokens) & {"estava", "estive", "vi", "matei", "ataquei"}
            or has_phrase(text, "sou o lobisomem")
        )
    )
