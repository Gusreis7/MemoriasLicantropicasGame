"""A política da simulação decide a partir dos mesmos dados do navegador."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

spec = importlib.util.spec_from_file_location("ml_gameplay_simulations",
    Path(__file__).resolve().parents[1] / "scripts" / "simulate_gameplay.py")
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)
Simulation, rank_suspects = runner.Simulation, runner.rank_suspects


def test_public_ranking_deduplicates_item_types_and_ignores_denials_without_attribution():
    one, duplicate, rare = uuid4(), uuid4(), uuid4()
    case = SimpleNamespace(
        inventory=(SimpleNamespace(id=one, item_id="coin", kind="common"),
                   SimpleNamespace(id=duplicate, item_id="coin", kind="common"),
                   SimpleNamespace(id=rare, item_id="ring", kind="singular")),
        testimonies=(SimpleNamespace(evidence_id=one, recognition="recognizes", claimed_owner_id="a"),
                     SimpleNamespace(evidence_id=duplicate, recognition="recognizes", claimed_owner_id="a"),
                     SimpleNamespace(evidence_id=rare, recognition="recognizes", claimed_owner_id="a"),
                     SimpleNamespace(evidence_id=rare, recognition="denies", claimed_owner_id=None)),
    )
    ranked = rank_suspects(case, {"a", "b"})
    assert ranked == [{"npc_id": "a", "score": 4, "types": 2}, {"npc_id": "b", "score": 0, "types": 0}]


@pytest.mark.anyio
async def test_simulated_walk_uses_movement_and_elapsed_clock(storage):
    simulation = Simulation(storage.client, storage.prefix, 10)
    await simulation.create("bentinho")
    started = simulation.clock()
    snapshot = await simulation.walk_to("praca_verde", 600)
    assert abs(snapshot.player.x - 600) <= 5
    assert snapshot.player.movement_seq > 2
    assert (simulation.clock() - started).total_seconds() >= (600 - 160 - 5) / 210
    assert (await simulation.investigation.get(simulation.game_id)).day == 1


@pytest.mark.anyio
async def test_public_policy_can_win_by_confession_without_private_decision_data(storage, single_wolf_attack):
    simulation = Simulation(storage.client, storage.prefix, 11)
    result = await simulation.play("rubiao", "confession")
    assert result["result"] == "won" and result["ending"]["method"] == "confession"
    assert result["actions"]["interrogate"] > 0 and result["actions"]["present"] > 0
    assert result["errors"] == []


@pytest.mark.anyio
async def test_unsupported_accusation_never_grants_a_free_victory(storage, single_wolf_attack):
    simulation = Simulation(storage.client, storage.prefix, 12)
    result = await simulation.play("capitu", "unsupported")
    assert result["result"] == "lost" and result["day"] == 5
    assert len(result["accusations"]) == 4
    assert not any(item["accepted"] for item in result["accusations"])


@pytest.mark.anyio
async def test_premature_public_tiebreak_is_refused_before_distinctive_evidence(storage, single_wolf_attack):
    simulation = Simulation(storage.client, storage.prefix, 13)
    result = await simulation.play("escobar", "rash")
    assert result["accusations"][0]["suspect_id"] == "bentinho"
    assert not result["accusations"][0]["accepted"]
    assert result["accusations"][0]["day"] == 1
    assert result["wrong_detentions"] == 0
    assert any(item["accepted"] and item["day"] >= 2 for item in result["accusations"])
    assert result["actions"]["inspect"] > 0
    assert result["ending"]["werewolf_id"] == "escobar"
