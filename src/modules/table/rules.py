"""Pure game-table rules. The model cannot create nights or change disclosures."""

from uuid import NAMESPACE_URL, uuid5

from src.contracts.errors import ConflictError, NotFoundError
from src.contracts.table import (
    NightEncounter, NightPresence, NightRecord, TableObservation, TableStatement, TableState,
)
from src.modules.world.catalog import LOCATIONS_BY_ID


def _id(game_id, *parts):
    return uuid5(NAMESPACE_URL, ":".join((str(game_id), "table-v2", *(str(part) for part in parts))))


def _place_name(location_id):
    location = LOCATIONS_BY_ID.get(location_id)
    return location.name if location else "local não registrado"


def make_night_record(game, world, day, now, *, crimes=(), excluded_ids=()):
    """Resolve one immutable night, including reciprocal continuous companionship.

    A sighting is an instant of visibility, not companionship. Its observer and
    companions stay at the same location, where the offender is briefly visible.
    """
    excluded = set(excluded_ids)
    living = {member.character_id for member in game.characters if member.alive and member.character_id not in excluded}
    positions = {npc.npc_id: npc.location_id for npc in world.npcs if npc.npc_id in living}
    # A travelling NPC has a real destination, not an invented location/alibi.
    for npc in world.npcs:
        if npc.npc_id in positions and npc.activity == "travelling" and getattr(npc, "destination_id", None):
            positions[npc.npc_id] = npc.destination_id
    participants = sorted(living & positions.keys())
    wolf = next((member.character_id for member in game.characters if member.role == "werewolf"), None)
    active_crimes = sorted((crime for crime in crimes if crime.day == day), key=lambda crime: str(crime.id))
    offenders = {crime.killer_id for crime in active_crimes}
    for crime in active_crimes:
        if crime.killer_id in living:
            positions[crime.killer_id] = crime.location_id
    eligible = sorted(set(participants) - {wolf} - offenders)
    partners = {}
    if {"bentinho", "capitu"} <= set(eligible):
        partners.update({"bentinho": "capitu", "capitu": "bentinho"})
    remaining = [person for person in eligible if person not in partners]
    if remaining:
        offset = (game.id.int + day) % len(remaining)
        remaining = remaining[offset:] + remaining[:offset]
    # Some innocents are alone too: lack of company never identifies the role.
    for index in range(0, max(0, len(remaining) - 2), 2):
        first, second = remaining[index:index + 2]
        partners.update({first: second, second: first})
    for first, second in sorted(partners.items()):
        if first < second:
            positions[second] = positions[first]
    observations = []
    wolf_crimes = [crime for crime in active_crimes if crime.killer_id == wolf and crime.cause == "werewolf"]
    observers = sorted(set(participants) - {wolf} - offenders)
    if wolf_crimes and wolf in positions and observers:
        observer = observers[(game.id.int + day) % len(observers)]
        location = positions[wolf]
        # The observer can actually see the offender at this location. Moving a
        # pair here is one night-resolution decision shared by both presences.
        positions[observer] = location
        if observer in partners:
            positions[partners[observer]] = location
        observations.append(TableObservation(
            id=_id(game.id, "sighting", day, observer, wolf), observer_id=observer,
            subject_id=wolf, day=day, location_id=location, kind="suspicious_presence",
        ))
    encounters = []
    encounter_by_person = {}
    for first, second in sorted(partners.items()):
        if first >= second:
            continue
        encounter = NightEncounter(
            id=_id(game.id, "encounter", day, first, second), day=day,
            location_id=positions[first], participant_ids=(first, second), coverage="full",
        )
        encounters.append(encounter)
        encounter_by_person[first] = encounter
        encounter_by_person[second] = encounter
    presences = []
    for person in sorted(living):
        encounter = encounter_by_person.get(person)
        location = positions.get(person)
        companions = tuple(other for other in encounter.participant_ids if other != person) if encounter else ()
        presences.append(NightPresence(
            id=_id(game.id, "presence", day, person), npc_id=person, day=day,
            location_id=location, encounter_id=encounter.id if encounter else None,
            companion_ids=companions, coverage="full" if location is not None else "unavailable",
        ))
        for companion in companions:
            observations.append(TableObservation(
                id=_id(game.id, "presence-observed", day, person, companion),
                observer_id=person, subject_id=companion, day=day,
                location_id=location, kind="presence",
            ))
    record = NightRecord(
        id=_id(game.id, "night", day), day=day, encounters=tuple(encounters),
        presences=tuple(presences), observations=tuple(sorted(observations, key=lambda item: str(item.id))), created_at=now,
    )
    validate_night_record(record)
    return record


def validate_night_record(record):
    presences = {presence.npc_id: presence for presence in record.presences}
    if len(presences) != len(record.presences):
        raise ConflictError("Uma noite não pode registrar a mesma pessoa duas vezes.")
    encounters = {encounter.id: encounter for encounter in record.encounters}
    if len(encounters) != len(record.encounters):
        raise ConflictError("Encontro noturno duplicado.")
    for encounter in record.encounters:
        if (encounter.day != record.day or len(encounter.participant_ids) < 2
                or len(set(encounter.participant_ids)) != len(encounter.participant_ids)
                or not set(encounter.participant_ids) <= presences.keys()):
            raise ConflictError("Encontro noturno exige participantes válidos e distintos.")
    for presence in record.presences:
        if presence.day != record.day or presence.npc_id in presence.companion_ids:
            raise ConflictError("Presença noturna inconsistente.")
        if presence.encounter_id is None:
            if presence.companion_ids:
                raise ConflictError("Companhia exige um encontro compartilhado.")
            continue
        encounter = encounters.get(presence.encounter_id)
        if (encounter is None or encounter.day != record.day or encounter.location_id != presence.location_id
                or encounter.coverage != presence.coverage):
            raise ConflictError("Encontro não corresponde à presença.")
        expected = set(encounter.participant_ids) - {presence.npc_id}
        if presence.npc_id not in encounter.participant_ids or expected != set(presence.companion_ids):
            raise ConflictError("Participantes não correspondem ao encontro.")
        for other in expected:
            peer = presences.get(other)
            if peer is None or peer.encounter_id != encounter.id or presence.npc_id not in peer.companion_ids or peer.location_id != presence.location_id:
                raise ConflictError("Companhia noturna deve ser recíproca.")
    for observation in record.observations:
        observer, subject = presences.get(observation.observer_id), presences.get(observation.subject_id)
        if observer is None or subject is None or observer.npc_id == subject.npc_id or observation.day != record.day:
            raise ConflictError("Observação noturna inválida.")
        if observer.location_id != observation.location_id or subject.location_id != observation.location_id:
            raise ConflictError("Observação exige visibilidade no mesmo local.")


def append_night(table, record):
    validate_night_record(record)
    existing = next((night for night in table.nights if night.day == record.day), None)
    if existing:
        # Clock values are metadata; a replay cannot alter any nightly fact.
        if existing.model_dump(exclude={"created_at"}) != record.model_dump(exclude={"created_at"}):
            raise ConflictError("Esta noite já foi resolvida com outros fatos.")
        return table
    return table.model_copy(update={"nights": tuple(sorted((*table.nights, record), key=lambda night: night.day))})


def alibi_statement(game_id, table, npc_id, day, names, now, recipient_id="player"):
    night = next((night for night in table.nights if night.day == day), None)
    presence = next((item for item in night.presences if item.npc_id == npc_id), None) if night else None
    source_ids = ()
    location = None
    companions = ()
    if presence is None or presence.coverage == "unavailable":
        status = "unavailable"
        text = f"Não tenho um registro seguro de onde estava na noite {day}; não posso inventar uma companhia para confirmá-lo."
        root = _id(game_id, "unavailable-alibi", day, npc_id)
    else:
        location, companions = presence.location_id, presence.companion_ids
        source_ids = (presence.id, *((presence.encounter_id,) if presence.encounter_id else ()))
        root = presence.encounter_id or presence.id
        status = "partial" if presence.coverage == "partial" else "accompanied" if companions else "alone"
        if companions:
            company = ", ".join(names.get(person, person) for person in companions)
            coverage = "parte da noite" if status == "partial" else "a noite"
            text = f"Na noite {day}, passei {coverage} em {_place_name(location)} com {company}. Essa companhia pode confirmar minha presença nesse período."
        else:
            text = f"Na noite {day}, estava em {_place_name(location)}, sem companhia. Não tenho outra pessoa que confirme minha presença nesse período."
    return TableStatement(
        id=_id(game_id, "alibi-statement", root, npc_id, recipient_id), kind="alibi",
        speaker_id=npc_id, recipient_id=recipient_id, subject_id=npc_id,
        day=day, period="night", source_ids=source_ids, root_id=root,
        location_id=location, companion_ids=companions, alibi_status=status,
        text=text, created_at=now,
    )


def sighting_statements(game_id, table, npc_id, names, now, recipient_id="player", day=None):
    result = []
    for night in table.nights:
        if day is not None and night.day != day:
            continue
        for observation in night.observations:
            if observation.observer_id != npc_id or observation.kind != "suspicious_presence":
                continue
            person = names.get(observation.subject_id, observation.subject_id)
            text = (f"Na noite {night.day}, vi {person} nas proximidades de {_place_name(observation.location_id)}. "
                    "Essa presença me faz suspeitar fortemente que seja o lobisomem; não presenciei o ataque e isso continua sendo uma suspeita.")
            result.append(TableStatement(
                id=_id(game_id, "sighting-statement", observation.id, recipient_id), kind="sighting",
                speaker_id=npc_id, recipient_id=recipient_id, subject_id=observation.subject_id,
                day=night.day, period="night", source_ids=(observation.id,), root_id=observation.id,
                location_id=observation.location_id, text=text, created_at=now,
            ))
    return tuple(result)


def disclose_statements(table, statements):
    known = {statement.id: statement for statement in table.statements}
    additions = []
    for statement in statements:
        existing = known.get(statement.id)
        if existing:
            if existing.model_dump(exclude={"created_at"}) != statement.model_dump(exclude={"created_at"}):
                raise ConflictError("Uma declaração registrada não pode ser reescrita.")
            continue
        _validate_statement_sources(table, statement)
        known[statement.id] = statement
        additions.append(statement)
    return table.model_copy(update={"statements": (*table.statements, *additions)}) if additions else table


def _validate_statement_sources(table, statement):
    if statement.kind == "alibi":
        if statement.subject_id != statement.speaker_id or statement.period != "night":
            raise ConflictError("Álibi precisa se referir à própria presença noturna.")
        night = next((night for night in table.nights if night.day == statement.day), None)
        presence = next((item for item in night.presences if item.npc_id == statement.speaker_id), None) if night else None
        if presence is None:
            if statement.alibi_status != "unavailable" or statement.source_ids or statement.companion_ids or statement.location_id is not None:
                raise NotFoundError("Não há fatos noturnos que autorizem este álibi.")
            return
        expected_status = "unavailable" if presence.coverage == "unavailable" else "partial" if presence.coverage == "partial" else "accompanied" if presence.companion_ids else "alone"
        expected_sources = (presence.id, *((presence.encounter_id,) if presence.encounter_id else ())) if expected_status != "unavailable" else ()
        if (statement.subject_id != statement.speaker_id or statement.location_id != presence.location_id
                or statement.companion_ids != presence.companion_ids or statement.alibi_status != expected_status
                or statement.source_ids != expected_sources
                or (expected_status != "unavailable" and statement.root_id != (presence.encounter_id or presence.id))):
            raise ConflictError("Declaração não corresponde ao álibi verdadeiro do personagem.")
    elif statement.kind == "sighting":
        observations = {item.id: item for night in table.nights for item in night.observations}
        if len(statement.source_ids) != 1 or statement.period != "night":
            raise NotFoundError("Avistamento sem observação própria.")
        for source_id in statement.source_ids:
            observation = observations.get(source_id)
            if (observation is None or observation.observer_id != statement.speaker_id or observation.subject_id != statement.subject_id
                    or observation.kind != "suspicious_presence" or observation.day != statement.day
                    or observation.location_id != statement.location_id or statement.root_id != observation.id):
                raise NotFoundError("Avistamento não pertence a este personagem.")


def statement_status(table, statement):
    if statement.kind != "alibi":
        return "reported"
    if statement.alibi_status != "accompanied":
        return statement.alibi_status or "unavailable"
    if not any(disclosed.id == statement.id for disclosed in table.statements):
        return "awaiting_confirmation"
    for companion in statement.companion_ids:
        if not any(
            other.kind == "alibi" and other.speaker_id == companion
            and other.recipient_id == statement.recipient_id and other.day == statement.day
            and other.root_id == statement.root_id and other.alibi_status == "accompanied"
            and statement.speaker_id in other.companion_ids and other.location_id == statement.location_id
            for other in table.statements
        ):
            return "awaiting_confirmation"
    return "confirmed"
