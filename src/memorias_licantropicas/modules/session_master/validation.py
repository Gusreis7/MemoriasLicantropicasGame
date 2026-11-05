"""Regras semânticas locais: autoria, citações e limites do parecer do modelo."""

import re
import unicodedata

from memorias_licantropicas.contracts.assessment import DialogueAssessment


def normalize(value):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(c)
    )


def direct_admission(content, incoming=""):
    """Critério conservador: verbo próprio e entrega, sem citação/negação/ordem de repetir."""
    text = normalize(content)
    if re.search(
        r"\b(repita|repete|diga exatamente|pronuncie|traduza|cite|recite|repeat|say exactly)\b",
        normalize(incoming),
    ):
        return False, False
    # Aspas são discurso citado; frases hipotéticas e negativas não são admissões.
    text = re.sub(r'[«“"].*?[»”"]', "", text, flags=re.S)
    assertions = []
    for sentence in re.split(r"[.!?;\n]+", text):
        if re.search(
            r"\b(nao|nunca|jamais|se|talvez|hipotese|imagina|imagine|disse que|diga que|quer que|quer ouvir|brincadeira)\b",
            sentence,
        ):
            continue
        assertions.append(sentence)
    direct = any(
        re.search(
            r"\b(eu sou o lobisomem|sou o lobisomem|fui eu quem matou|fui eu que matou|eu matei|eu ataquei|fui eu quem atacou|sou a fera|fui (?:eu )?(?:o |a )?responsavel (?:por|pel[oa]s?) (?:essas |estas |as |os )?(?:mortes|ataques|assassinatos)|fui eu quem causou (?:esses |os |estes )?ataques)\b",
            part,
        )
        for part in assertions
    )
    surrender = any(
        re.search(
            r"\b(entrego-me|me entrego|vou me entregar|aceito a prisao|aceito ser pres[oa]|aceito a custodia|aceito que me levem a delegacia|leve-me ao delegado|pode me prender|entrego minhas armas)\b",
            part,
        )
        for part in assertions
    )
    return direct, surrender


def own_assertion_clauses(content, incoming=""):
    text = normalize(content)
    if re.search(
        r"\b(repita|repete|diga exatamente|pronuncie|traduza|cite|recite|repeat|say exactly)\b",
        normalize(incoming),
    ):
        return ()
    text = re.sub(r'[«“"].*?[»”"]', "", text, flags=re.S)
    result = []
    for sentence in re.split(r"[.!?;\n]+", text):
        if re.search(
            r"\b(nao|nunca|jamais|se|talvez|hipotese|imagine|ouvi|disseram|contaram|ele disse|ela disse|voce diz|voce disse|o senhor diz|quer que|quer ouvir|brincadeira|segundo|inocente|acusado|acusada|dizem|pensam|culpam)\b",
            sentence,
        ):
            continue
        if re.search(
            r"\b(eu|meu|minha|minhas|meus|mim|sou|fui|tirei|fiz|cometi|causei|ceifei|matei|ataquei|transformei|pratiquei)\b",
            sentence,
        ):
            result.append(sentence)
    return tuple(result)


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
    # A proposta do modelo precisa de um compromisso textual real do falante.
    text = normalize(content)
    surrender_anchor = re.search(
        r"\b(entrego-me|me entrego|vou me entregar|me entregarei|entregar-me|aceito (?:a |ser )?(?:custodia|prisao|pres[oa])|leve-me|levem-me|conduza-me|me (?:levar|algemar|prender)|permitirei.{0,35}(?:algem|prend)|nao resistirei)\b",
        text,
    )
    surrender_negated = re.search(
        r"\b(nao|nunca|jamais)\b.{0,30}\b(entregar|entrego|pres[oa]|prisao|custodia|leve-me|algemar)\b",
        text,
    )
    if semantic and assessment.surrender and surrender_anchor and not surrender_negated:
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
    text = normalize(incoming)
    from memorias_licantropicas.modules.agents.support import is_alibi_question

    if is_alibi_question(incoming):
        period = (
            "night" if re.search(r"\b(noite|anoitecer|madrugada)\b", text) else "day"
        )
        match = re.search(r"\bdia\s+(\d+)\b", text)
        target_day = (
            int(match.group(1))
            if match
            else max(0, day - 1)
            if ("ontem" in text or period == "night")
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
    return DialogueAssessment()


def validate_assessment(proposal, base, incoming, outgoing, day):
    issues = list(proposal.issues)
    # Estes dois problemas possuem marcadores textuais verificáveis.
    # Uma opinião ou um vocativo cortês não pode disparar uma troca de fala.
    if "wrong_address" in issues and not re.search(
        r"\b(?:senhor[a]? delegado|delegado[,!]|delegada[,!])",
        normalize(outgoing.content),
    ):
        issues.remove("wrong_address")
    if "narrator_style" in issues and not re.search(
        r"\b(?:ele|ela|capitu|bentinho|escobar|rubiao|virgilia|florenca|bacamarte)\s+(?:baixou|olhou|suspirou|ergueu|virou|sorriu|caminhou|disse|pensou)\b|^\s*[*\[]",
        normalize(outgoing.content),
    ):
        issues.remove("narrator_style")
    from memorias_licantropicas.modules.agents.support import is_greeting

    if (
        "off_topic" in issues
        and is_greeting(incoming.content)
        and len(outgoing.content.split()) <= 30
        and re.search(
            r"\b(?:ola|oi|bom dia|boa tarde|boa noite|saudacoes)\b",
            normalize(outgoing.content),
        )
        and not re.search(
            r"\b(?:bentinho|escobar|florenca|bacamarte|virgilia|lobisomem|lobo|remedio|medicacao)\b",
            normalize(outgoing.content),
        )
    ):
        issues.remove("off_topic")
    proposal = proposal.model_copy(update={"issues": tuple(issues)})
    from memorias_licantropicas.modules.agents.support import is_alibi_question

    if proposal.kind == "alibi" and not is_alibi_question(incoming.content):
        proposal = proposal.model_copy(
            update={"kind": "conversation", "period": None, "day": None}
        )
    if proposal.issues:
        # Review proposes issues; only the graph may regenerate in the persona's voice.
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
