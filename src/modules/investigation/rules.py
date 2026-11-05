"""Regras sem I/O: evidência física, conhecimento limitado e decisão pública."""

from datetime import timedelta
from secrets import choice
from uuid import uuid4

from src.contracts.errors import ConflictError, NotFoundError
from src.contracts.investigation import (
    Accusation, Crime, Evidence, InvestigationState, JournalEdition, Testimony, CaseEvent, CaseTransition,
)
from src.modules.investigation.catalog import (
    INVENTORIES, ITEMS_BY_ID, OBSERVED_PEOPLE, PREFERRED_VICTIMS, INSPECTION_DETAILS, items_of_kind,
)


WEREWOLF_DEFEAT_THRESHOLD = 4


def werewolf_cast_victims(crimes, character_ids, werewolf_id):
    """Conta moradores do elenco mortos pela fera, sem incluir Brás Cubas ou crimes humanos."""
    return {crime.victim_id for crime in crimes
            if crime.victim_id in character_ids and crime.cause == "werewolf"
            and crime.killer_id == werewolf_id}


def choose_victim(game, detained_npc_id=None, excluded_ids=()) -> str | None:
    """Escolha de regras: civis vivos e livres; nunca o detetive ou o próprio lobo."""
    candidates = tuple(npc.character_id for npc in game.characters
                       if npc.alive and npc.character_id not in excluded_ids and npc.role == "civil" and npc.character_id != detained_npc_id)
    if not candidates:
        return None
    wolf = next(npc.character_id for npc in game.characters if npc.role == "werewolf")
    preferred = PREFERRED_VICTIMS.get(wolf)
    return preferred if preferred in candidates else choice(candidates)


def make_crime(game, day, victim_id, location_id, now, *, killer_id=None, cause="werewolf") -> Crime:
    wolf = killer_id or next(npc.character_id for npc in game.characters if npc.role == "werewolf")
    crime_id = uuid4()
    # Comuns são contexto. A peça individualizável só surge depois da primeira noite.
    common = items_of_kind(wolf, "common")
    singular = items_of_kind(wolf, "singular")
    personal = items_of_kind(wolf, "unique")
    distinctive = singular[day % len(singular)] if day == 0 else personal[(game.id.int + day - 1) % len(personal)]
    item_ids = (common[day % len(common)], distinctive)
    evidence = tuple(Evidence(
        id=uuid4(), crime_id=crime_id, item_id=item_id,
        description=f"Encontrado junto à cena: {ITEMS_BY_ID[item_id].description}",
        deposited_by=wolf,
    ) for item_id in item_ids)
    return Crime(id=crime_id, day=day, victim_id=victim_id, location_id=location_id,
                 occurred_at=now, killer_id=wolf, cause=cause, evidence=evidence)


def make_initial_investigation(game, now, day_seconds=300) -> InvestigationState:
    from src.modules.investigation.interrogation import record_activities
    from src.modules.world.catalog import make_initial_world
    initial = make_crime(game, 0, "bras_cubas", "praca_verde", now)
    from src.modules.investigation.night_story import make_night_story
    return InvestigationState(
        night_story=make_night_story(game), game_id=game.id, phase_ends_at=now + timedelta(seconds=day_seconds), crimes=(initial,),
        activity_records=record_activities(game, make_initial_world(game.id), 0, "night", now,
                                          source="initial_scenario", crime=initial),
        journal=(JournalEdition(day=1,
                    headline="Primeira morte suspeita de lobisomem: Brás Cubas encontrado morto",
                    body="A cidade amanhece sob o impacto da morte de Brás Cubas, a primeira morte suspeita atribuída a um lobisomem. "
                         "O detetive Floriano inicia a investigação na Praça Verde.",
                    victim_id="bras_cubas", suspicious_death_count=1, location_id="praca_verde"),),
    )


def find_evidence(state, evidence_id, *, collected=True) -> Evidence:
    evidence = next((item for crime in state.crimes for item in crime.evidence if item.id == evidence_id), None)
    if evidence is None:
        raise NotFoundError("Vestígio não encontrado nesta partida.")
    if collected and not evidence.collected:
        raise ConflictError("Recolha o vestígio antes de apresentá-lo.")
    return evidence


def _next_witness_hint(game, npc_id, item, names):
    # Um encaminhamento por ofício/tipo visível, nunca por identidade do culpado.
    textile = any(word in item.name.casefold() for word in ("fio", "fita", "tecido", "lenço", "leque", "dedal"))
    candidates = ("capitu", "virgilia", "florenca", "escobar", "bacamarte", "bentinho", "rubiao") if textile else (
        "escobar", "bacamarte", "virgilia", "capitu", "bentinho", "florenca", "rubiao")
    available = {m.character_id for m in game.characters if m.alive and m.character_id != npc_id}
    other = next((person for person in candidates if person in available), None)
    return (f" Mostre também a {names.get(other, other)} e pergunte onde viu algo parecido." if other else
            " Compare as marcas da peça com os relatos que já recolheu.")


def make_testimony(state, game, evidence, npc_id, names, now) -> Testimony:
    """Observações pessoais não identificam quem efetivamente deixou um objeto comum."""
    item = ITEMS_BY_ID[evidence.item_id]
    npc = next(member for member in game.characters if member.character_id == npc_id)
    own = evidence.item_id in INVENTORIES[npc_id]
    observers = tuple(person for person in OBSERVED_PEOPLE[npc_id]
                      if evidence.item_id in INVENTORIES[person])
    recognition, owner, truthful = "unknown", None, True
    if own and (npc.role == "werewolf" or (state.night_story and state.night_story.plot
            and state.night_story.plot.planner_id==npc_id and state.night_story.plot.status=="succeeded"
            and evidence.deposited_by==npc_id)):
        recognition, truthful = "denies", False
        text = f"Não reconheço {item.name.lower()} como meu, detetive." + _next_witness_hint(game, npc_id, item, names)
    elif observers:
        recognition, owner = "recognizes", observers[0]
        if item.kind == "common":
            text = (f"Já vi {names.get(owner, owner)} com um objeto igual. É comum na cidade; "
                    "isso não prova que este seja daquela pessoa.")
        elif item.kind == "singular":
            text = (f"Já vi {names.get(owner, owner)} usar um desses. É pouco comum, "
                    "mas conheço outras pessoas que poderiam ter um parecido.")
        else:
            text = f"Reconheço esta peça: já a vi com {names.get(owner, owner)}. {INSPECTION_DETAILS[item.id]}"
    elif own:
        recognition, owner = "recognizes", npc_id
        if item.kind == "common":
            text = "Tenho um objeto desse tipo, como outras pessoas da cidade. Não sei dizer de quem é este."
        elif item.kind == "singular":
            text = "Uso uma peça desse tipo. Não sou a única pessoa do bairro a possuí-la."
        else:
            text = "Reconheço essa peça como minha, detetive. Não sei como foi parar aí."
    else:
        text = "Não sei de quem é essa peça." + _next_witness_hint(game, npc_id, item, names)
    return Testimony(id=uuid4(), day=state.day, evidence_id=evidence.id, witness_id=npc_id,
                     recognition=recognition, claimed_owner_id=owner, text=text, truthful=truthful, created_at=now)


def inspect_evidence(state, evidence_id, now):
    """Um exame canônico da peça recolhida; a identidade do dono continua investigável."""
    evidence = find_evidence(state, evidence_id)
    if getattr(evidence, "examined", False):
        return CaseTransition(state=state)
    item = ITEMS_BY_ID[evidence.item_id]
    if item.kind == "unique":
        text = (INSPECTION_DETAILS[evidence.item_id] +
                " Na borda recém-rompida há resíduos compatíveis com as marcas da luta desta cena. "
                "A peça tem uma ligação material com o ataque; isso não identifica, por si, quem a deixou.")
    elif item.kind == "singular":
        text = ("O acabamento é pouco habitual, mas não há assinatura, reparo ou marca que individualize este exemplar. "
                "Um parecido pode pertencer a mais de uma pessoa; procure uma peça pessoal e compare os relatos.")
    else:
        text = ("É um objeto de fabricação corrente. As marcas de uso são genéricas e não individualizam seu dono. "
                "Pode ajudar a reconstruir a cena, mas não sustenta uma prisão por si só.")
    inspected = evidence.model_copy(update={"examined": True, "inspection_text": text,
                                           "crime_link_verified": item.kind == "unique"})
    crimes = tuple(crime.model_copy(update={"evidence": tuple(inspected if e.id == evidence.id else e
                       for e in crime.evidence)}) if crime.id == evidence.crime_id else crime for crime in state.crimes)
    return CaseTransition(state=state.model_copy(update={"crimes": crimes}), events=(CaseEvent(
        type="evidence.examined", data={"evidence_id": str(evidence.id), "item_id": evidence.item_id,
                                       "crime_id": str(evidence.crime_id), "day": state.day}),))


def review_accusation(state, suspect_id, evidence_ids, testimony_ids):
    """Diagnóstico público sem consumir ação ou ler a identidade do culpado."""
    from src.modules.investigation.scoring import assess_dossier
    assessment = assess_dossier(state, suspect_id, evidence_ids, testimony_ids)
    missing = []
    if len(assessment.linked_item_ids) < 2:
        missing.append("Relacionar pelo menos dois tipos distintos de vestígio à pessoa acusada.")
    if not assessment.examined_exclusive_ids and len(assessment.corroborated_personal_ids) < 2:
        missing.append("É preciso examinar uma peça pessoal e relacionar sua marca ao suspeito por depoimento, "
                       "ou reunir dois objetos exclusivos diferentes, cada um reconhecido por duas testemunhas externas.")
    if len(assessment.independent_witnesses) < 2 and not (assessment.independent_witnesses and assessment.alibi_conflict):
        missing.append("Ouvir duas fontes independentes, ou uma fonte e uma contradição de álibis já registrada.")
    if assessment.total < 5:
        missing.append("Reunir indícios mais específicos; objetos comuns têm peso muito baixo.")
    if assessment.accepted:
        if assessment.custody_route == 'corroborated_personal_marks':
            reason = ("Duas peças pessoais diferentes tiveram suas marcas reconhecidas por duas testemunhas externas cada. "
                      "O conjunto justifica a custódia, mesmo sem exame adicional. A noite esclarecerá a hipótese de licantropia.")
        else:
            reason = ("A marca individualizada, o exame da ligação com a cena e a corroboração registrada justificam a custódia. "
                      "Isso ainda não confirma que a pessoa seja o lobisomem; a noite esclarecerá a hipótese.")
        missing = []
    else:
        reason = "Ainda falta: " + " ".join(missing) + " Você pode completar o dossiê e reapresentá-lo hoje."
    return assessment, tuple(missing), reason


def dossier_fingerprint(state, suspect_id, evidence_ids, testimony_ids):
    """Duplicatas de exemplar/relato não fabricam um dossiê novo; um exame novo sim."""
    import json
    from hashlib import sha256
    from src.modules.investigation.scoring import public_alibi_conflict
    selected={find_evidence(state,identifier).item_id for identifier in evidence_ids}
    exam={e.item_id for c in state.crimes for e in c.evidence if e.collected and e.examined and e.item_id in selected}
    records={t.id:t for t in state.testimonies}
    claims=sorted({(records[identifier].witness_id,find_evidence(state,records[identifier].evidence_id).item_id,
                   records[identifier].recognition,records[identifier].claimed_owner_id or '') for identifier in testimony_ids})
    payload=('custody-v5',suspect_id,sorted(selected),sorted(exam),claims,public_alibi_conflict(state,suspect_id))
    return sha256(json.dumps(payload).encode()).hexdigest()


def evaluate_accusation(state, suspect_id, evidence_ids, testimony_ids, now) -> Accusation:
    assessment, _, reason = review_accusation(state,suspect_id,evidence_ids,testimony_ids)
    return Accusation(id=uuid4(), day=state.day, suspect_id=suspect_id,
        evidence_ids=tuple(dict.fromkeys(evidence_ids)), testimony_ids=tuple(dict.fromkeys(testimony_ids)),
        accepted=assessment.accepted, reason=reason, created_at=now,
        dossier_fingerprint=dossier_fingerprint(state,suspect_id,evidence_ids,testimony_ids))
