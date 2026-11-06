"""Authoritative night facts, truthful disclosures and deterministic confirmation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.contracts.errors import ConflictError, NotFoundError
from src.contracts.model import GameCharacter, GameState
from src.contracts.table import TableState
from src.modules.characters.catalog import CHARACTERS
from src.modules.investigation.interrogation import make_interrogation, record_activities
from src.modules.investigation.rules import make_crime
from src.modules.table.rules import (
    alibi_statement, append_night, disclose_statements, make_night_record,
    sighting_statements, statement_status,
)
from src.modules.world.catalog import make_initial_world

NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)
IDS = tuple(person.id for person in CHARACTERS)
NAMES = {person.id: person.name for person in CHARACTERS}


def scenario(wolf="rubiao", game_id=UUID("09f6e69c-fbc0-44a7-9d02-cb3ce0d1c918")):
    game = GameState(id=game_id, created_at=NOW, content_version="3", characters=tuple(
        GameCharacter(character_id=person, role="werewolf" if person == wolf else "civil") for person in IDS))
    world = make_initial_world(game.id)
    crime = make_crime(game, 0, "bras_cubas", "praca_verde", NOW)
    night = make_night_record(game, world, 0, NOW, crimes=(crime,))
    return game, world, crime, night


@pytest.mark.parametrize("wolf", IDS)
def test_each_role_has_consistent_reciprocal_night_and_real_witness(wolf):
    game, world, crime, night = scenario(wolf)
    by_person = {presence.npc_id: presence for presence in night.presences}
    assert set(by_person) == set(IDS)
    assert not by_person[wolf].companion_ids
    assert any(not presence.companion_ids for person, presence in by_person.items() if person != wolf)
    witnesses = [observation for observation in night.observations if observation.kind == "suspicious_presence"]
    assert len(witnesses) == 1 and witnesses[0].subject_id == wolf
    assert witnesses[0].observer_id != wolf
    for observation in night.observations:
        assert by_person[observation.observer_id].location_id == observation.location_id
        assert by_person[observation.subject_id].location_id == observation.location_id
    for presence in night.presences:
        for companion in presence.companion_ids:
            other = by_person[companion]
            assert presence.npc_id in other.companion_ids
            assert presence.encounter_id == other.encounter_id
            assert presence.location_id == other.location_id
            assert wolf != companion
    if wolf not in ("bentinho", "capitu"):
        assert by_person["bentinho"].companion_ids == ("capitu",)
        assert by_person["capitu"].companion_ids == ("bentinho",)


def test_night_ids_and_content_are_stable_under_order_and_retry():
    game, world, crime, night = scenario()
    reordered = world.model_copy(update={"npcs": tuple(reversed(world.npcs))})
    replay = make_night_record(game, reordered, 0, NOW + timedelta(seconds=3), crimes=(crime,))
    assert replay.model_dump(exclude={"created_at"}) == night.model_dump(exclude={"created_at"})
    table = append_night(TableState(), night)
    assert append_night(table, replay) == table
    changed = night.model_copy(update={"presences": tuple(
        presence.model_copy(update={"location_id": "casa_verde"}) if presence.npc_id == "rubiao" else presence
        for presence in night.presences)})
    with pytest.raises(ConflictError):
        append_night(table, changed)


@pytest.mark.parametrize("order", [("bentinho", "capitu"), ("capitu", "bentinho")])
def test_confirmation_requires_both_real_disclosures_in_either_order(order):
    game, _, _, night = scenario()
    table = append_night(TableState(), night)
    first = alibi_statement(game.id, table, order[0], 0, NAMES, NOW)
    second = alibi_statement(game.id, table, order[1], 0, NAMES, NOW)
    assert first.root_id == second.root_id
    assert first.location_id == second.location_id
    assert first.companion_ids == (order[1],)
    assert second.companion_ids == (order[0],)
    table = disclose_statements(table, (first,))
    assert statement_status(table, first) == "awaiting_confirmation"
    assert statement_status(table, second) == "awaiting_confirmation"
    table = disclose_statements(table, (second,))
    assert statement_status(table, first) == statement_status(table, second) == "confirmed"
    replay = alibi_statement(game.id, table, order[0], 0, NAMES, NOW + timedelta(seconds=4))
    assert disclose_statements(table, (replay,)) == table


def test_confirmation_does_not_cross_recipients_or_periods():
    game, _, _, night = scenario()
    table = append_night(TableState(), night)
    first = alibi_statement(game.id, table, "bentinho", 0, NAMES, NOW)
    other_listener = alibi_statement(game.id, table, "capitu", 0, NAMES, NOW, recipient_id="virgilia")
    table = disclose_statements(table, (first, other_listener))
    assert statement_status(table, first) == "awaiting_confirmation"


def test_alone_and_unavailable_are_distinct_and_never_invent_company():
    game, _, _, night = scenario()
    table = append_night(TableState(), night)
    lone = alibi_statement(game.id, table, "rubiao", 0, NAMES, NOW)
    missing = alibi_statement(game.id, table, "rubiao", 12, NAMES, NOW)
    assert lone.alibi_status == "alone" and not lone.companion_ids
    assert missing.alibi_status == "unavailable" and missing.location_id is None
    assert lone.id != missing.id and lone.root_id != missing.root_id
    with pytest.raises(ConflictError):
        disclose_statements(table, (lone.model_copy(update={"companion_ids": ("capitu",)}),))


def test_sighting_belongs_only_to_observer_and_does_not_reveal_role_as_fact():
    game, _, _, night = scenario()
    table = append_night(TableState(), night)
    observation = next(item for item in night.observations if item.kind == "suspicious_presence")
    statements = sighting_statements(game.id, table, observation.observer_id, NAMES, NOW)
    assert len(statements) == 1
    statement = statements[0]
    assert statement.subject_id == observation.subject_id
    assert statement.source_ids == (observation.id,)
    assert "suspeitar" in statement.text and "não presenciei" in statement.text
    uninformed = next(person for person in IDS if person not in (observation.observer_id, observation.subject_id))
    assert not sighting_statements(game.id, table, uninformed, NAMES, NOW)
    with pytest.raises(NotFoundError):
        disclose_statements(table, (statement.model_copy(update={"speaker_id": uninformed}),))


def test_activity_snapshot_projects_exact_same_night_sources():
    game, world, crime, night = scenario()
    records = record_activities(game, world, 0, "night", NOW, crime=crime, source="initial_scenario")
    by_person = {item.npc_id: item for item in night.presences}
    for record in records:
        presence = by_person[record.npc_id]
        assert record.id == presence.id
        assert record.companion_ids == presence.companion_ids
        assert record.location_id == presence.location_id


@pytest.mark.parametrize("person", ("rubiao", "bacamarte", "bentinho", "capitu"))
def test_interrogation_reads_canonical_night_without_false_alibi_or_memory_lapse(person):
    from types import SimpleNamespace
    game, _, _, night = scenario()
    table = append_night(TableState(), night)
    state = SimpleNamespace(table=table)
    canonical = alibi_statement(game.id, table, person, 0, NAMES, NOW)
    result = make_interrogation(state, game, person, 0, "night", NAMES, NOW)
    assert result.truthful is True
    assert result.location_id == canonical.location_id
    assert result.companion_ids == canonical.companion_ids
    assert result.text == canonical.text
