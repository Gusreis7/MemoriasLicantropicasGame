"""Apoios curtos e verificáveis para a conversa; não geram fatos novos."""

from src.textutils import (
    normalize,
    word_tokens,
    has_phrase,
    has_any_phrase,
    without_quotes,
    clauses,
    has_word_start,
)

NAMES = {
    "player": "Floriano",
    "bentinho": "Bentinho",
    "capitu": "Capitu",
    "escobar": "Escobar",
    "rubiao": "Rubião",
    "virgilia": "Virgília",
    "florenca": "Florença",
    "bacamarte": "Bacamarte",
}
STOP = {
    "para",
    "pelo",
    "pela",
    "como",
    "isso",
    "essa",
    "esse",
    "esta",
    "este",
    "voce",
    "floriano",
    "detetive",
    "sobre",
    "tenho",
    "posso",
    "dizer",
    "pessoa",
    "pessoas",
    "coisa",
    "coisas",
    "mais",
    "muito",
    "ainda",
    "apenas",
    "nada",
    "tudo",
    "aqui",
    "nao",
    "com",
    "que",
    "uma",
    "por",
    "dos",
    "das",
    "seu",
    "sua",
}


def normalized(text):
    return normalize(text)


def words(text):
    return {w for w in word_tokens(text) if len(w) > 2 and w not in STOP}


def is_greeting(question):
    text = normalized(question).strip()
    greetings = ("ola", "oi", "bom dia", "boa tarde", "boa noite", "salve")
    # Uma saudação pode ter vocativo, mas não embutir outra pergunta/frase.
    body = text.rstrip(".!? ")
    if "?" in body or "!" in body:
        return False
    return any(
        has_phrase(body, greeting)
        and word_tokens(body)[: len(word_tokens(greeting))] == word_tokens(greeting)
        for greeting in greetings
    )


def is_courtesy_reply(question, reply):
    """Vocabulário fechado para cortesia sem fatos, segredos ou confissões."""
    if not (is_greeting(question) or has_phrase(question, "fale comigo")):
        return False
    tokens = word_tokens(reply)
    allowed = set(
        (
            "ola oi bom boa dia tarde noite saudacoes salve floriano detetive senhor senhora sr meu minha caro cara homem "
            "que prazer muito ve lo la lhe te voce ver por aqui estar estou sou sim nao apenas e o a os as "
            "em com como vai seu sua hoje pode me chamar de capitu rubiao diga logo direto franca francamente "
            "fale falar aberto aberta voce deseja desejo quer quero saber pergunta perguntar saber conversar conversa "
            "o traz estas bandas lados util posso ajudar posso ajudo pois bem seja bem vindo obrigada obrigado "
            "tudo bem o que isso por favor falar comigo disposicao qual duvida tem deseja esclarecer"
        ).split()
    )
    return bool(tokens) and len(tokens) <= 35 and set(tokens) <= allowed


def dialogue_focus(question, observations):
    text = normalized(question)
    if is_greeting(question):
        return "A mensagem atual é apenas uma saudação. Cumprimente Floriano brevemente na sua voz, sem introduzir pistas, suspeitos ou acontecimentos."
    if has_phrase(text, "acredita") and has_word_start(text, ("lobisome",)):
        return "A pergunta atual é sobre sua crença em lobisomens. Diga se acredita, duvida ou não sabe, em primeira pessoa. Não invente conversas ou fontes para justificar sua opinião."
    if has_phrase(text, "fale comigo"):
        return "Floriano está pedindo uma conversa direta. Responda à impaciência dele e peça que esclareça o que deseja saber. Não repita seu objetivo pessoal ou pistas anteriores."
    if not (observations or {}).get("apoios_de_conversa") and has_phrase(
        text, "bras cubas"
    ):
        return "A pergunta atual é sobre Brás Cubas. Você não tem fatos autorizados sobre inimigos ou motivos contra ele. Diga francamente que não sabe apontar alguém; não invente dívidas, brigas ou suspeitos."
    return "Responda à última mensagem de Floriano. Seus objetivos influenciam seu tom, mas não substituem o assunto da pergunta. Não apresente as palavras dele como uma descoberta sua."


def _lead(statement, npc_id):
    text = normalized(statement)
    if "seminario" in text:
        other = (
            "Escobar"
            if npc_id == "bentinho"
            else "Bentinho"
            if npc_id == "escobar"
            else "Bentinho ou Escobar"
        )
        return f"Pergunte também a {other} como foi essa amizade no seminário."
    if "medicacao" in text or "consultas" in text:
        if npc_id == "bacamarte":
            return "Converse com Bentinho sobre as consultas."
        if npc_id == "bentinho":
            return "Converse com Bacamarte sobre o acompanhamento."
        return "Converse com Bacamarte sobre o acompanhamento e com Bentinho sobre as consultas."
    if "internado" in text or "internou" in text:
        if npc_id == "florenca":
            return "Pergunte a Bacamarte por que decidiu internar meu pai."
        return "Florença pode lhe contar por que contesta a internação do pai."
    if "casad" in text or "ciume" in text:
        if npc_id == "bentinho":
            return "Ouça também Capitu sobre essas discussões."
        if npc_id == "capitu":
            return "Ouça também Bentinho sobre essas discussões."
        return "Ouça Capitu e Bentinho separadamente sobre essas discussões."
    if "amizade" in text or "amigos" in text:
        others = [
            name
            for identifier, name in NAMES.items()
            if identifier not in (npc_id, "player") and normalized(name) in text
        ]
        if others:
            return f"Pergunte também a {' ou '.join(others[:2])} pela versão dessa amizade."
        return "Compare essa amizade com os relatos que já anotou no caderno."
    if "objeto" in text or "peca" in text:
        return "Compare esta informação com o que outra testemunha reconhece."
    return "Compare esse relato com os que já anotou no caderno."


def is_alibi_question(question):
    tokens = set(word_tokens(question))
    whereabouts = {"estava", "esteve", "ficou", "passou", "andou", "jantou", "saiu"}
    if "alibi" in tokens and tokens & {"qual", "seu"}:
        return True
    if tokens & {"onde", "aonde"} and tokens & whereabouts:
        return True
    if has_phrase(question, "com quem") and tokens & whereabouts:
        return True
    return ("que" in tokens and bool(tokens & {"fazia", "fez"})) or has_phrase(
        question, "estava fazendo"
    )


def dialogue_supports(profile, observations, question):
    """Lista somente o que a persona pode compartilhar agora, com origem estável."""
    if observations is None:
        return ()
    if is_greeting(question):
        return ()
    # O nome usado como vocativo não torna todos os fatos do próprio NPC
    # relevantes: "acredita em lobisomens, Rubião?" não pede seu namoro.
    query = words(question) - words(profile.name)
    candidates = []
    for index, record in enumerate(
        observations.get("seus_depoimentos_registrados", ())
    ):
        statement = record.get("fala", "")
        if record.get("nome"):
            statement = f"Sobre {record['nome']}: {statement}"
        if statement:
            candidates.append(
                {
                    "id": f"testimony:{record.get('evidence_id', index)}",
                    "statement": statement,
                    "lead": "Compare este objeto com os depoimentos já anotados no caderno.",
                    "kind": "testimony",
                    "priority": 5,
                }
            )
    for index, record in enumerate(observations.get("suas_atividades", ())):
        statement = record.get("lembranca") or record.get("fala", "")
        if statement:
            candidates.append(
                {
                    "id": f"activity:{record.get('dia', index)}:{record.get('periodo', '')}",
                    "statement": statement,
                    "lead": "Confronte essa lembrança com a versão de quem estava por perto.",
                    "kind": "activity",
                    "priority": 4 if is_alibi_question(question) else 0,
                }
            )
    active = observations.get("ultimo_objeto_apresentado") or {}
    if active.get("fala_registrada"):
        candidates.append(
            {
                "id": f"active-item:{active.get('evidence_id', active.get('item_id', ''))}",
                "statement": f"Sobre {active.get('nome', 'essa peça')}: {active['fala_registrada']}",
                "lead": "Compare este objeto com os depoimentos já anotados no caderno.",
                "kind": "testimony",
                "priority": 8,
            }
        )
    social = observations.get("memoria_social", {})
    for index, entry in enumerate(social.get("memorias_relevantes", ())):
        if entry.get("compartilhavel", True) is False:
            continue
        # Private entries are projected only after authorization by KnowledgeService.
        if entry.get("visibilidade") == "private" and not entry.get(
            "compartilhavel", False
        ):
            continue
        statement = entry.get("conteudo", "")
        if not statement or entry.get("tipo") == "literal":
            continue
        if entry.get("origem") != "authored" and "mostro-lhe" in normalized(statement):
            # A apresentação de um objeto pelo jogador não é descoberta nova.
            continue
        speaker = entry.get("quem_falou")
        if entry.get("origem") != "authored" and speaker and speaker != profile.id:
            statement = f"Ouvi de {NAMES.get(speaker, speaker)}: {statement}"
        candidates.append(
            {
                "id": str(entry.get("claim_id", f"memory:{index}")),
                "statement": statement,
                "lead": _lead(statement, profile.id),
                "kind": "social",
                "authored": entry.get("origem") == "authored",
                "priority": 2
                if entry.get("origem") == "authored"
                else (9 if not asks_for_guidance(question) else 0),
            }
        )
    # Do not fall back to an unrelated inventory or private biography.
    for candidate in candidates:
        candidate["relevance"] = len(query & words(candidate["statement"]))
    # Uma pergunta específica não autoriza trocar de assunto só porque há
    # testemunhos ou rumores disponíveis. Saudações não pedem pistas.
    subjects = [
        normalized(name)
        for identifier, name in {**NAMES, "bras_cubas": "Brás Cubas"}.items()
        if identifier not in ("player", profile.id)
        and normalized(name) in normalized(question)
    ]
    candidates = [
        candidate
        for candidate in candidates
        if (candidate["relevance"] > 0 or asks_for_guidance(question))
        and (
            not subjects
            or any(
                subject in normalized(candidate["statement"]) for subject in subjects
            )
        )
    ]
    candidates.sort(key=lambda c: (c["relevance"], c["priority"]), reverse=True)
    selected = []
    seen = set()
    for candidate in candidates:
        if candidate["statement"] in seen:
            continue
        seen.add(candidate["statement"])
        selected.append(candidate)
        if len(selected) == 3:
            break
    return tuple(selected)


def compact_observations(profile, observations, question):
    if observations is None:
        return None
    supports = dialogue_supports(profile, observations, question)
    result = {
        key: observations[key]
        for key in (
            "dia",
            "fase",
            "seu_conflito_privado",
            "ultimo_objeto_apresentado",
            "suas_atividades",
            "seus_depoimentos_registrados",
            "suas_versoes_de_interrogatorio",
            "seus_confrontos",
        )
        if key in observations
    }
    # A memória também explica emoções e reações, mesmo sem ser uma pista
    # lexicalmente ligada à pergunta. A projeção já pertence apenas a este NPC.
    social = observations.get("memoria_social", {})
    result["memoria_social"] = {
        key: social.get(key, [])
        for key in (
            "confidencias_autorizadas",
            "descobertas_autorizadas",
            "relacao_com_interlocutor",
            "sentimentos_proprios",
        )
    }
    result["apoios_de_conversa"] = supports
    result["memoria_social"]["memorias_relevantes"] = [
        entry
        for entry in social.get("memorias_relevantes", ())
        if entry.get("compartilhavel", True)
        and (
            entry.get("visibilidade") != "private"
            or entry.get("compartilhavel") is True
        )
    ][:12]
    result["memoria_social"]["encontros_anteriores"] = social.get(
        "encontros_anteriores", ()
    )[-3:]
    result["memoria_social"]["fontes_conhecidas"] = sorted(
        {
            entry.get("quem_falou")
            for entry in social.get("memorias_relevantes", ())
            if entry.get("quem_falou")
        }
        | {
            entry.get("interlocutor_id")
            for entry in social.get("encontros_anteriores", ())
            if entry.get("interlocutor_id") and entry.get("falas")
        }
    )
    return result


def unauthorized_personal_disclosure(npc_id, content, observations):
    """Só sinais explícitos de confidências próprias; ambiguidade cabe ao mestre."""
    allowed = set(
        (observations or {})
        .get("memoria_social", {})
        .get("descobertas_autorizadas", ())
    )
    for clause in clauses(without_quotes(normalized(content))):
        if clause.endswith("?") or has_any_phrase(
            clause,
            (
                "nao sou",
                "nao sinto",
                "nao amo",
                "nao quero",
                "nao pretendo",
                "nunca quis",
                "dizem que",
                "ouvi dizer",
                "segundo",
            ),
        ):
            continue
        if npc_id == "escobar" and "escobar_affection" not in allowed:
            own_love = has_any_phrase(
                clause,
                ("amo", "sinto por", "alem da amizade", "meu amor", "mais que amizade"),
            ) or has_word_start(clause, ("apaixon",))
            if "bentinho" in word_tokens(clause) and own_love:
                return True
            if has_phrase(clause, "sou um amigo que o ama"):
                return True
        if npc_id == "capitu" and "capitu_separation" not in allowed:
            tokens = word_tokens(clause)
            intention = {"quero", "desejo", "penso", "pretendo", "decidi", "vou"}
            for position, token in enumerate(tokens):
                if token not in intention:
                    continue
                remainder = " ".join(tokens[position + 1 :])
                if has_word_start(remainder, ("separ",)) or has_any_phrase(
                    remainder, ("deixar meu marido", "deixar bentinho")
                ):
                    return True
    return False


def asks_for_guidance(question):
    return bool(
        has_any_phrase(
            question,
            (
                "por onde comeco",
                "por onde comecar",
                "como comeco",
                "como comecar",
                "onde investigar",
                "onde procuro",
                "onde procurar",
                "alguma pista",
                "uma pista",
                "tem pista",
                "teria pista",
                "alguma sugestao",
                "uma sugestao",
                "alguma informacao",
                "uma informacao",
                "me ajudar",
                "me orientar",
                "o que sabe",
                "que voce sabe",
                "que o senhor sabe",
                "que a senhora sabe",
                "o que conhece",
                "pode me contar",
            ),
        )
        or (
            set(word_tokens(question)) & {"conte", "contar", "fale"}
            and bool(
                set(word_tokens(question))
                & {"sabe", "amizade", "investigacao", "pistas"}
            )
        )
    )
