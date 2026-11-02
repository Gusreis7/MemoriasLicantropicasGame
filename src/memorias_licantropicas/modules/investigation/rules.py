"""Regras sem I/O: evidência física, conhecimento limitado e decisão pública."""

from datetime import timedelta
from secrets import choice
from uuid import uuid4

from memorias_licantropicas.contracts.errors import ConflictError, NotFoundError
from memorias_licantropicas.contracts.investigation import (
    Accusation, Crime, Evidence, InvestigationState, JournalEdition, Testimony,
)
from memorias_licantropicas.modules.investigation.catalog import (
    INVENTORIES, ITEMS_BY_ID, OBSERVED_PEOPLE, PREFERRED_VICTIMS,
)


def choose_victim(game, detained_npc_id=None, excluded_ids=()) -> str | None:
    """Escolha de regras: civis vivos e livres; nunca o detetive ou o próprio lobo."""
    candidates = tuple(npc.character_id for npc in game.characters
                       if npc.alive and npc.character_id not in excluded_ids and npc.role == "civil" and npc.character_id != detained_npc_id)
    if not candidates:
        return None
    wolf = next(npc.character_id for npc in game.characters if npc.role == "werewolf")
    preferred = PREFERRED_VICTIMS.get(wolf)
    return preferred if preferred in candidates else choice(candidates)


def make_crime(game, day, victim_id, location_id, now) -> Crime:
    wolf = next(npc.character_id for npc in game.characters if npc.role == "werewolf")
    inventory = INVENTORIES[wolf]
    crime_id = uuid4()
    # Nenhuma pista falsa física: o objeto comum é ambíguo, mas a origem é factual.
    item_ids = (inventory[2 + day % 3], inventory[0] if day >= 3 else inventory[1])
    evidence = tuple(Evidence(
        id=uuid4(), crime_id=crime_id, item_id=item_id,
        description=f"Encontrado junto à cena: {ITEMS_BY_ID[item_id].description}",
        deposited_by=wolf,
    ) for item_id in item_ids)
    return Crime(id=crime_id, day=day, victim_id=victim_id, location_id=location_id,
                 occurred_at=now, killer_id=wolf, evidence=evidence)


def make_initial_investigation(game, now, day_seconds=300) -> InvestigationState:
    from memorias_licantropicas.modules.investigation.interrogation import record_activities
    from memorias_licantropicas.modules.world.catalog import make_initial_world
    initial = make_crime(game, 0, "bras_cubas", "praca_verde", now)
    return InvestigationState(
        game_id=game.id, phase_ends_at=now + timedelta(seconds=day_seconds), crimes=(initial,),
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


def make_testimony(state, game, evidence, npc_id, names, now) -> Testimony:
    """Observações pessoais não identificam quem efetivamente deixou um objeto comum."""
    item = ITEMS_BY_ID[evidence.item_id]
    npc = next(member for member in game.characters if member.character_id == npc_id)
    own = evidence.item_id in INVENTORIES[npc_id]
    observers = tuple(person for person in OBSERVED_PEOPLE[npc_id]
                      if evidence.item_id in INVENTORIES[person])
    recognition, owner, truthful = "unknown", None, True
    if own and npc.role == "werewolf":
        recognition, truthful = "denies", False
        text = "Não reconheço esse objeto, detetive. Não posso dizer a quem pertence."
    elif observers:
        recognition, owner = "recognizes", observers[0]
        if item.kind == "common":
            text = (f"Já vi {names.get(owner, owner)} com um objeto igual. É comum na cidade; "
                    "isso não prova que este seja daquela pessoa.")
        elif item.kind == "singular":
            text = (f"Já vi {names.get(owner, owner)} usar um desses. É pouco comum, "
                    "mas conheço outras pessoas que poderiam ter um parecido.")
        else:
            text = f"Reconheço esta peça: já a vi com {names.get(owner, owner)}. Guarde bem esse detalhe."
    elif own:
        recognition, owner = "recognizes", npc_id
        if item.kind == "common":
            text = "Tenho um objeto desse tipo, como outras pessoas da cidade. Não sei dizer de quem é este."
        elif item.kind == "singular":
            text = "Uso uma peça desse tipo. Não sou a única pessoa do bairro a possuí-la."
        else:
            text = "Reconheço essa peça como minha, detetive. Não sei como foi parar aí."
    else:
        text = "Não conheço a procedência desse objeto. Prefiro não inventar uma resposta."
    return Testimony(id=uuid4(), day=state.day, evidence_id=evidence.id, witness_id=npc_id,
                     recognition=recognition, claimed_owner_id=owner, text=text, truthful=truthful, created_at=now)


def evaluate_accusation(state, suspect_id, evidence_ids, testimony_ids, now) -> Accusation:
    """Não recebe GameState nem papéis: só analisa o conjunto de provas apresentado."""
    selected = tuple(find_evidence(state, identifier) for identifier in evidence_ids)
    by_id = {testimony.id: testimony for testimony in state.testimonies}
    if any(identifier not in by_id for identifier in testimony_ids):
        raise NotFoundError("Depoimento não encontrado nesta partida.")
    statements = tuple(by_id[identifier] for identifier in testimony_ids)
    if any(statement.evidence_id not in evidence_ids for statement in statements):
        raise ConflictError("Um depoimento precisa acompanhar seu vestígio na acusação.")
    linked = {statement.evidence_id for statement in statements
              if statement.recognition == "recognizes" and statement.claimed_owner_id == suspect_id}
    # Uma mesma espécie de objeto vale uma vez, mesmo encontrada em cenas distintas.
    item_ids = {evidence.item_id for evidence in selected if evidence.id in linked}
    points = sum({"unique": 3, "singular": 2, "common": 1}[ITEMS_BY_ID[item_id].kind]
                 for item_id in item_ids)
    if linked:
        points += 1
    accepted = len(item_ids) >= 2 and points >= 4
    if accepted:
        reason = ("Há ao menos dois tipos de vestígio ligados à pessoa acusada por depoimentos registrados. "
                  "A corroboração justifica a custódia desta noite; ainda não é uma confirmação de culpa.")
    elif len(item_ids) < 2:
        reason = ("São necessários ao menos dois tipos de vestígio ligados à pessoa acusada por depoimentos. "
                  "Repetir o mesmo objeto ou apresentar apenas uma suspeita não basta.")
    else:
        reason = ("Os objetos apresentados são comuns demais para justificar a custódia. "
                  "Reúna um vestígio mais distintivo e corroboração registrada.")
    return Accusation(id=uuid4(), day=state.day, suspect_id=suspect_id,
                      evidence_ids=tuple(dict.fromkeys(evidence_ids)), testimony_ids=tuple(dict.fromkeys(testimony_ids)),
                      accepted=accepted, reason=reason, created_at=now)
