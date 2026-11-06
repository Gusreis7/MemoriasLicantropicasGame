"""The activity projection and the table refer to the same original night."""

from src.modules.investigation.interrogation import record_activities
from src.modules.investigation.rules import make_initial_investigation
from src.modules.world.catalog import make_initial_world


def test_night_partners_are_reciprocal_and_wolf_has_witness(game):
    world = make_initial_world(game.id)
    state = make_initial_investigation(game, game.created_at)
    records = record_activities(game, world, 0, "night", game.created_at,
                                crimes=state.crimes, source="initial_scenario")
    by_person = {record.npc_id: record for record in records}
    wolf = next(member.character_id for member in game.characters if member.role == "werewolf")
    assert not by_person[wolf].companion_ids
    assert by_person[wolf].observed_by
    presences = {item.npc_id: item for item in state.table.nights[0].presences}
    for record in records:
        assert record.id == presences[record.npc_id].id
        for partner in record.companion_ids:
            assert record.npc_id in by_person[partner].companion_ids
            assert record.location_id == by_person[partner].location_id
            assert wolf not in (record.npc_id, partner)
