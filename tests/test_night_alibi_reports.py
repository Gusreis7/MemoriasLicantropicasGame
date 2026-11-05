from uuid import uuid4

import pytest

from src.contracts.errors import NotFoundError
from src.modules.investigation.interrogation import record_activities
from src.modules.investigation.scoring import assess_dossier
from src.modules.world.catalog import make_initial_world


def test_night_partners_are_reciprocal_and_wolf_has_witness(game):
    world = make_initial_world(game.id)
    records = record_activities(game, world, 0, "night", game.created_at)
    by_person = {record.npc_id: record for record in records}
    wolf = next(member.character_id for member in game.characters if member.role == "werewolf")
    assert not by_person[wolf].companion_ids
    assert by_person[wolf].observed_by
    for record in records:
        for partner in record.companion_ids:
            assert record.npc_id in by_person[partner].companion_ids
            assert record.location_id == by_person[partner].location_id
            assert wolf not in (record.npc_id, partner)


def test_only_selected_useful_reports_affect_dossier(game):
    from src.modules.investigation.rules import make_initial_investigation
    state = make_initial_investigation(game, game.created_at)
    first, second, third = uuid4(), uuid4(), uuid4()
    reports = (
        {"outgoing_id": str(first), "npc_id": "bentinho", "outgoing": "Desconfio de Escobar, ele pode ser o lobisomem.",
         "narrative_authorized": True, "useful": True, "assessment": {"kind": "suspicion"}},
        {"outgoing_id": str(second), "npc_id": "escobar", "outgoing": "Passei a noite sozinho.",
         "narrative_authorized": True, "useful": True, "assessment": {"kind": "alibi"}},
        {"outgoing_id": str(third), "npc_id": "capitu", "outgoing": "Suspeito de Escobar.",
         "narrative_authorized": True, "useful": True, "assessment": {"kind": "suspicion"}},
    )
    state = state.model_copy(update={"dialogue_events": reports})
    baseline = assess_dossier(state, "escobar", (), ())
    selected = assess_dossier(state, "escobar", (), (), (first, second))
    assert selected.total == baseline.total + 4
    assert not selected.accepted
    assert assess_dossier(state, "escobar", (), (), (first, second, third)).custody_route == "witness_reports"
    assert assess_dossier(state, "capitu", (), (), (first, second)).total == baseline.total
    ambiguous = dict(reports[1], outgoing="Estou sozinha nisso, a não ser pela companhia de Bentinho.")
    state = state.model_copy(update={"dialogue_events": (reports[0], ambiguous, reports[2])})
    assert assess_dossier(state, "escobar", (), (), (second,)).total == 0
    with pytest.raises(NotFoundError):
        assess_dossier(state, "escobar", (), (), (uuid4(),))
