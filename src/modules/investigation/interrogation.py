"""Atividades históricas, conhecimento acessível e confrontos sem inferência do LLM."""
from uuid import uuid4
from math import ceil

from src.contracts.errors import ConflictError, NotFoundError
from src.contracts.investigation import (
    ActivityClaim, ActivityRecord, Confrontation, Interrogation,
)
from src.modules.investigation.catalog import ITEMS_BY_ID
from src.modules.investigation.rules import evaluate_accusation, find_evidence

# Conteúdo versionado: os números afetam dificuldade, nunca aparecem no diálogo.
CONFESSION_DIFFICULTY = {"rubiao": 5, "bentinho": 6, "florenca": 7,
                        "virgilia": 7, "escobar": 8, "capitu": 9, "bacamarte": 10}
COOPERATION = {
    "bentinho": "Ajuda a descobrir o culpado, mas preserva a intimidade e desconfia de insinuações.",
    "capitu": "Ajuda com observações precisas, preservando clientes e autonomia.",
    "escobar": "Colabora para proteger a cidade e quem estima, sem divulgar sua intimidade.",
    "rubiao": "Procura ajudar e agradar, mas distingue o que viu de suas suposições.",
    "virgilia": "Troca informações para esclarecer o crime, atribuindo relatos a suas fontes.",
    "florenca": "Colabora com a investigação, exige respeito e não confunde crítica com culpa.",
    "bacamarte": "Coopera por observações que considera verificáveis e admite limites de memória.",
}
LOCATIONS = {"praca_verde": "Praça Verde", "cabana_capitu": "Cabana da Capitu",
             "casa_verde": "Casa Verde", "cafe_largo": "Café do Largo",
             "cais_lanternas": "Cais das Lanternas"}


def record_activities(game, world, day, period, now, *, source="world_snapshot", crime=None, crimes=(), excluded_ids=()):
    """Projeção do registro noturno único; de dia, retrato do mundo físico."""
    if period == "night":
        from src.modules.table.rules import make_night_record
        night = make_night_record(game, world, day, now,
            crimes=(*((crime,) if crime is not None else ()), *crimes), excluded_ids=excluded_ids)
        return tuple(ActivityRecord(
            id=presence.id, npc_id=presence.npc_id, day=day, period="night",
            location_id=presence.location_id,
            companion_ids=presence.companion_ids,
            observed_by=tuple(sorted({observation.observer_id for observation in night.observations
                                      if observation.subject_id == presence.npc_id})),
            activity=("Passou a noite com a companhia indicada." if presence.companion_ids
                      else "Passou a noite sem companhia que pudesse confirmar."),
            source=source, occurred_at=now,
        ) for presence in night.presences if presence.location_id is not None)
    places = {npc.npc_id: npc.location_id for npc in world.npcs if npc.activity != "travelling"}
    positions = {npc.npc_id: npc.x for npc in world.npcs}
    living = {npc.character_id for npc in game.characters if npc.alive and npc.character_id not in excluded_ids}
    for event in ((*((crime,) if crime is not None else ()), *crimes)):
        places[event.killer_id] = event.location_id
        positions[event.killer_id] = event.x
    result = []
    for npc_id, location in places.items():
        if npc_id not in living:
            continue
        companions = tuple(other for other in places if other != npc_id and other in living
                           and places[other] == location and abs(positions[other] - positions[npc_id]) <= 64)
        observers = tuple(other for other in places if other != npc_id and other in living
                          and places[other] == location)
        result.append(ActivityRecord(
            id=uuid4(), npc_id=npc_id, day=day, period=period, location_id=location,
            companion_ids=companions, observed_by=observers,
            activity="Tratava de seus afazeres no local no instante registrado.",
            source=source, occurred_at=now,
        ))
    return tuple(result)


def make_interrogation(state, game, npc_id, day, period, names, now):
    if not any(member.character_id == npc_id for member in game.characters):
        raise NotFoundError("Morador não encontrado nesta partida.")
    if period == "night":
        from src.modules.table.rules import alibi_statement
        from uuid import NAMESPACE_URL, uuid5
        statement = alibi_statement(game.id, state.table, npc_id, day, names, now)
        night = next((night for night in state.table.nights if night.day == day), None)
        seen = tuple(observation for observation in night.observations if observation.observer_id == npc_id) if night else ()
        observations = tuple(ActivityClaim(
            npc_id=item.subject_id, location_id=item.location_id, companion_ids=(),
            activity="Presença observada brevemente; isso não comprova toda a noite.",
        ) for item in seen)
        return Interrogation(
            id=uuid5(NAMESPACE_URL, f"{game.id}:table-interrogation:{npc_id}:{day}:night"),
            npc_id=npc_id, day=day, period="night", location_id=statement.location_id,
            companion_ids=statement.companion_ids, activity="Registro da mesa sobre o período noturno.",
            text=statement.text, observations=observations, truthful=True,
            source_record_ids=statement.source_ids, created_at=now,
        )
    records = tuple(record for record in state.activity_records
                    if record.day == day and record.period == period)
    own = next((record for record in records if record.npc_id == npc_id), None)
    if own is None:
        return Interrogation(id=uuid4(), npc_id=npc_id, day=day, period=period,
            location_id=None, activity="Sem registro acessível desse período.",
            text="Não consigo reconstituir esse período com segurança, detetive. Prefiro admitir a lacuna.",
            truthful=True, created_at=now)
    location = own.location_id
    companions = own.companion_ids
    activity = own.activity
    # Limite de conhecimento e disposição: cada um recorda apenas encontros observados.
    limit = 2 if npc_id in {"capitu", "virgilia", "florenca"} else 1
    # Recordações sobre terceiros referem-se a outros instantes do período. A
    # própria companhia não é revelada por via indireta no relato sobre terceiro.
    observed = tuple(record for record in records if npc_id in record.observed_by)[:limit]
    observations = tuple(ActivityClaim(npc_id=record.npc_id, location_id=record.location_id,
        companion_ids=tuple(other for other in record.companion_ids if other != npc_id),
        activity=record.activity) for record in observed)
    company = ", ".join(names.get(other, other) for other in companions) if companions else "sem companhia que possa confirmar"
    text = (f"Naquele período, estava em {LOCATIONS.get(location, location)}, {company}. {activity} "
            "Estou falando do instante de que me recordo; isso não comprova toda a noite.")
    if observations:
        text += " Vi " + "; ".join(f"{names.get(record.npc_id, record.npc_id)} em "
            f"{LOCATIONS.get(record.location_id, record.location_id)}" for record in observed) + "."
    return Interrogation(id=uuid4(), npc_id=npc_id, day=day, period=period,
        location_id=location, companion_ids=companions, activity=activity, text=text,
        observations=observations, truthful=True,
        source_record_ids=(own.id, *(record.id for record in observed)), created_at=now)


def npc_interrogation_context(state, npc_id):
    """Projeção epistêmica reutilizada por diálogo com jogador e encontros sociais."""
    versions = tuple(record for record in state.interrogations if record.npc_id == npc_id)
    observations = tuple(record for record in state.activity_records if record.period == "day" and npc_id in record.observed_by)
    night_observations = tuple(item for night in state.table.nights for item in night.observations if item.observer_id == npc_id)
    return {
        "cooperacao_com_investigacao": COOPERATION.get(npc_id, "Ajude a esclarecer o crime com o que sabe."),
        "suas_versoes_de_interrogatorio": [{"dia": record.day, "periodo": record.period,
            "local_id": record.location_id, "companhias": record.companion_ids, "fala": record.text,
            "observacoes": [claim.model_dump() for claim in record.observations]} for record in versions],
        "observacoes_pessoais_de_presenca": [{"dia": record.day, "periodo": record.period,
            "personagem_id": record.npc_id, "local_id": record.location_id,
            "atividade": record.activity, "limite": "Observação em um instante; não cobre toda a noite."}
            for record in observations] + [{"dia": item.day, "periodo": "night",
                "personagem_id": item.subject_id, "local_id": item.location_id,
                "atividade": "Presença observada brevemente.", "limite": "Avistamento não equivale a companhia durante toda a noite."}
                for item in night_observations],
        "seus_confrontos": [{"fala": record.text, "dia": record.day}
                            for record in state.confrontations if record.npc_id == npc_id],
        "limite_das_versoes": "Preserve o conteúdo das versões que você prestou. Uma alegação alheia "
                              "não vira fato; não receba nem invente álibis privados de terceiros.",
    }


def make_confrontation(state, game, npc_id, evidence_ids, testimony_ids, interrogation_ids, now):
    if any(record.npc_id == npc_id and record.day == state.day for record in state.confrontations):
        raise ConflictError("Já houve um confronto com esta pessoa hoje. Reúna novos elementos para outro dia.")
    by_interrogation = {record.id: record for record in state.interrogations}
    if any(identifier not in by_interrogation for identifier in interrogation_ids):
        raise NotFoundError("Interrogatório não encontrado nesta partida.")
    selected_interrogations = tuple(by_interrogation[identifier] for identifier in interrogation_ids)
    if not any(record.npc_id == npc_id for record in selected_interrogations):
        raise ConflictError("Inclua uma versão registrada do próprio interrogado para confrontá-lo.")
    # Esta regra recebe apenas a seleção pública: não consulta o papel para pontuar.
    assessment = evaluate_accusation(state, npc_id, evidence_ids, testimony_ids, now)
    by_testimony = {record.id: record for record in state.testimonies}
    statements = tuple(by_testimony[identifier] for identifier in testimony_ids)
    selected_item_ids = {find_evidence(state, identifier).item_id for identifier in evidence_ids}
    linked_statements = tuple(record for record in statements
        if find_evidence(state, record.evidence_id).item_id in selected_item_ids
        and record.recognition == "recognizes" and record.claimed_owner_id == npc_id)
    items = {find_evidence(state, record.evidence_id).item_id for record in linked_statements}
    from src.modules.investigation.scoring import assess_dossier
    dossier = assess_dossier(state, npc_id, evidence_ids, testimony_ids)
    pressure = ceil(dossier.material_points)
    pressure += int(bool(linked_statements))
    witnesses = {record.witness_id for record in linked_statements if record.witness_id != npc_id}
    pressure += min(2, max(0, len(witnesses) - 1))
    denial_conflict = any(record.witness_id == npc_id and record.recognition == "denies"
                          and find_evidence(state, record.evidence_id).item_id in selected_item_ids
                          for record in statements)
    pressure += 2 if denial_conflict else 0
    alibi_conflict = any(
        own.npc_id == npc_id and own.location_id is not None
        and witness.npc_id != npc_id and witness.day == own.day and witness.period == own.period
        and any(observation.npc_id == npc_id and observation.location_id != own.location_id
                for observation in witness.observations)
        for own in selected_interrogations for witness in selected_interrogations
    )
    pressure += 2 if alibi_conflict else 0
    member = next(member for member in game.characters if member.character_id == npc_id)
    confessed = bool(assessment.accepted and (denial_conflict or alibi_conflict)
                     and pressure >= CONFESSION_DIFFICULTY.get(npc_id, 10)
                     and member.role == "werewolf")
    text = ("Não sustentarei mais essa versão. Sou o lobisomem; os ataques foram obra minha. "
            "Entrego-me ao delegado." if confessed else
            "Contestei os elementos que me apresentou, detetive. Minha versão fica registrada; "
            "não farei a declaração que procura.")
    if confessed and npc_id == "bacamarte":
        text = ("Chamei de delírio o que os vestígios demonstram. Sou eu quem se transforma; "
                "sou o lobisomem. Aceito a custódia para impedir novos ataques.")
    return Confrontation(id=uuid4(), npc_id=npc_id, day=state.day, evidence_ids=evidence_ids,
        testimony_ids=testimony_ids, interrogation_ids=interrogation_ids, confessed=confessed,
        pressure=pressure, text=text, created_at=now)
