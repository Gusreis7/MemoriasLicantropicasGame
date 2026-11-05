"""Projeção de deslocamentos reais persistidos; não altera posições históricas."""
from src.modules.world.catalog import LOCATIONS_BY_ID


def project_npc(npc, now):
    if npc.activity != "travelling" or not npc.travel_started_at or not npc.travel_arrives_at or not npc.travel_route:
        return npc.location_id, npc.x
    duration = (npc.travel_arrives_at - npc.travel_started_at).total_seconds()
    fraction = min(1., max(0., (now - npc.travel_started_at).total_seconds() / max(.01, duration)))
    route = npc.travel_route
    origin = npc.travel_origin_x if npc.travel_origin_x is not None else npc.x
    target = npc.travel_target_x if npc.travel_target_x is not None else 160
    if len(route) == 1:
        return route[0], origin + (target - origin) * fraction
    # Cada trecho aparece na rua correspondente; entrada e saída pelas bordas.
    stage = min(len(route) - 1, int(fraction * len(route)))
    local = min(1., fraction * len(route) - stage)
    previous_exit = next((e for e in LOCATIONS_BY_ID[route[stage-1]].exits if e.target_location_id == route[stage]), None) if stage else None
    next_exit = next((e for e in LOCATIONS_BY_ID[route[stage]].exits if e.target_location_id == route[stage+1]), None) if stage < len(route)-1 else None
    start = origin if stage == 0 else (928 if previous_exit and previous_exit.arrival_side == "right" else 32)
    end = target if stage == len(route) - 1 else (32 if next_exit and next_exit.side == "left" else 928)
    return route[stage], start + (end - start) * local
