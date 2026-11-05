"""Autoria e âncoras literais conservadoras; parecer semântico pertence ao mestre."""

from src.contracts.assessment import DialogueAssessment
from src.textutils import (
    normalize,
    word_tokens,
    has_phrase,
    has_any_phrase,
    without_quotes,
    clauses,
)

_REPETITION = (
    "repita",
    "repete",
    "diga exatamente",
    "pronuncie",
    "traduza",
    "cite",
    "recite",
    "repeat",
    "say exactly",
)
_UNCERTAIN = (
    "nao",
    "nunca",
    "jamais",
    "se",
    "talvez",
    "hipotese",
    "imagina",
    "imagine",
    "disse que",
    "diga que",
    "quer que",
    "quer ouvir",
    "brincadeira",
)
_INDIRECT = (
    "ouvi",
    "disseram",
    "contaram",
    "ele disse",
    "ela disse",
    "voce diz",
    "voce disse",
    "o senhor diz",
    "segundo",
    "inocente",
    "acusado",
    "acusada",
    "dizem",
    "pensam",
    "culpam",
)
_FIRST_PERSON = frozenset(
    "eu meu minha minhas meus mim sou fui tirei fiz cometi causei ceifei matei ataquei transformei pratiquei".split()
)
_ADMISSION = (
    "eu sou o lobisomem",
    "sou o lobisomem",
    "fui eu quem matou",
    "fui eu que matou",
    "eu matei",
    "eu ataquei",
    "fui eu quem atacou",
    "sou a fera",
    "fui eu quem causou esses ataques",
    "fui eu quem causou os ataques",
    "fui eu quem causou estes ataques",
)
_SURRENDER = (
    "entrego me",
    "me entrego",
    "vou me entregar",
    "me entregarei",
    "entregar me",
    "aceito a prisao",
    "aceito a custodia",
    "aceito ser preso",
    "aceito ser presa",
    "aceito que me levem a delegacia",
    "leve me ao delegado",
    "pode me prender",
    "entrego minhas armas",
    "leve me",
    "levem me",
    "conduza me",
    "me levar",
    "me algemar",
    "me prender",
)


def _assertions(content, incoming="", *, exclude_indirect=False):
    if has_any_phrase(incoming, _REPETITION):
        return ()
    result = []
    for clause in clauses(without_quotes(normalize(content))):
        if clause.rstrip().endswith("?") or has_any_phrase(clause, _UNCERTAIN):
            continue
        if exclude_indirect and has_any_phrase(clause, _INDIRECT):
            continue
        result.append(clause)
    return tuple(result)


def _admits(clause):
    if has_any_phrase(clause, _ADMISSION):
        return True
    tokens = set(word_tokens(clause))
    return (
        has_any_phrase(
            clause,
            (
                "fui o responsavel",
                "fui a responsavel",
                "fui eu o responsavel",
                "fui eu a responsavel",
            ),
        )
        and bool(tokens & {"por", "pelas", "pelos", "pela", "pelo"})
        and bool(tokens & {"mortes", "ataques", "assassinatos"})
    )


def direct_admission(content, incoming=""):
    assertions = _assertions(content, incoming)
    return any(_admits(clause) for clause in assertions), any(
        has_any_phrase(clause, _SURRENDER) for clause in assertions
    )


def own_assertion_clauses(content, incoming=""):
    return tuple(
        clause
        for clause in _assertions(content, incoming, exclude_indirect=True)
        if set(word_tokens(clause)) & _FIRST_PERSON
    )


def admission_evidence(content, incoming, assessment):
    direct, surrendered = direct_admission(content, incoming)
    semantic = (
        assessment.kind == "admission"
        and assessment.confidence >= 0.9
        and assessment.own_assertion
        and bool(assessment.quote)
        and assessment.quote in content
        and bool(own_assertion_clauses(assessment.quote, incoming))
    )
    for clause in clauses(without_quotes(normalize(content))):
        if clause.endswith("?"):
            continue
        custody = (
            has_any_phrase(clause, _SURRENDER)
            or has_phrase(clause, "nao resistirei")
            or (
                "permitirei" in word_tokens(clause)
                and any(
                    word.startswith(("algem", "prend")) for word in word_tokens(clause)
                )
            )
        )
        negated = bool(
            set(word_tokens(clause)) & {"nao", "nunca", "jamais"}
        ) and not has_phrase(clause, "nao resistirei")
        if semantic and assessment.surrender and custody and not negated:
            surrendered = True
    return direct or semantic, surrendered


def local_assessment(incoming, outgoing, day):
    direct, surrender = direct_admission(outgoing, incoming)
    if direct:
        return DialogueAssessment(
            kind="admission",
            quote=outgoing[:2400],
            confidence=1,
            own_assertion=True,
            surrender=surrender,
        )
    from src.modules.agents.support import is_alibi_question

    if not is_alibi_question(incoming):
        return DialogueAssessment()
    tokens = word_tokens(incoming)
    period = "night" if set(tokens) & {"noite", "anoitecer", "madrugada"} else "day"
    explicit_day = next(
        (
            int(tokens[index + 1])
            for index, token in enumerate(tokens[:-1])
            if token == "dia" and tokens[index + 1].isdecimal()
        ),
        None,
    )
    target_day = (
        explicit_day
        if explicit_day is not None
        else max(0, day - 1)
        if "ontem" in tokens or period == "night"
        else day
    )
    return DialogueAssessment(
        kind="alibi",
        quote=outgoing[:2400],
        confidence=0.75,
        own_assertion=True,
        period=period,
        day=target_day,
    )


def validate_assessment(proposal, base, incoming, outgoing, day):
    """Valida referências literais; o classificador decide os demais significados."""
    issues = list(proposal.issues)
    text = normalize(outgoing.content)
    tokens = word_tokens(text)
    if "wrong_address" in issues and not (
        has_any_phrase(text, ("senhor delegado", "senhora delegado"))
        or any(
            marker in text
            for marker in ("delegado,", "delegado!", "delegada,", "delegada!")
        )
    ):
        issues.remove("wrong_address")
    actors = {
        "ele",
        "ela",
        "capitu",
        "bentinho",
        "escobar",
        "rubiao",
        "virgilia",
        "florenca",
        "bacamarte",
    }
    gestures = {
        "baixou",
        "olhou",
        "suspirou",
        "ergueu",
        "virou",
        "sorriu",
        "caminhou",
        "disse",
        "pensou",
    }
    narrator = outgoing.content.lstrip().startswith(("*", "[")) or any(
        a in actors and b in gestures for a, b in zip(tokens, tokens[1:])
    )
    if "narrator_style" in issues and not narrator:
        issues.remove("narrator_style")
    from src.modules.agents.support import (
        is_greeting,
        is_alibi_question,
    )

    if (
        "off_topic" in issues
        and is_greeting(incoming.content)
        and len(tokens) <= 30
        and has_any_phrase(
            text, ("ola", "oi", "bom dia", "boa tarde", "boa noite", "saudacoes")
        )
        and not set(tokens)
        & {
            "bentinho",
            "escobar",
            "florenca",
            "bacamarte",
            "virgilia",
            "lobisomem",
            "lobo",
            "remedio",
            "medicacao",
        }
    ):
        issues.remove("off_topic")
    proposal = proposal.model_copy(update={"issues": tuple(issues)})
    if proposal.kind == "alibi" and not is_alibi_question(incoming.content):
        proposal = proposal.model_copy(
            update={"kind": "conversation", "period": None, "day": None}
        )
    if proposal.issues:
        return proposal
    if proposal.useful and (
        not proposal.useful_quote or proposal.useful_quote not in outgoing.content
    ):
        proposal = proposal.model_copy(update={"useful": False, "useful_quote": ""})
    meta = {
        "source": "model",
        "attempts": proposal.attempts,
        "useful": proposal.useful,
        "useful_quote": proposal.useful_quote,
    }
    if proposal.quote and proposal.quote not in outgoing.content:
        return base.model_copy(update=meta)
    if proposal.kind == "admission":
        if base.kind == "admission":
            return base.model_copy(update=meta)
        own, _ = admission_evidence(outgoing.content, incoming.content, proposal)
        return (
            proposal
            if own
            else proposal.model_copy(
                update={"kind": "partial_admission", "surrender": False}
            )
        )
    return (
        base.model_copy(update=meta)
        if base.kind in {"admission", "alibi"}
        else proposal
    )
