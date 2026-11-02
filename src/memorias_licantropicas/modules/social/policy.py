"""Decisões sociais puras: não consultam papéis secretos ou o provedor de LLM."""

from collections import deque
from datetime import timedelta

from memorias_licantropicas.contracts.social import SocialDay
from memorias_licantropicas.modules.knowledge.rules import relationship_for
from memorias_licantropicas.modules.world.catalog import LOCATIONS_BY_ID

SLOT_SECONDS = (60, 120, 180, 240)
SLOT_WINDOW_SECONDS = 15
MAX_ENCOUNTERS_PER_NPC = 2
PAIR_COOLDOWN_SECONDS = 60


def day_record(state, day):
    return next((item for item in state.days if item.day == day), SocialDay(day=day))


def replace_day(state, record):
    return state.model_copy(update={"days": (*tuple(item for item in state.days if item.day != record.day), record)})


def route_between(origin, destination):
    """Caminho explícito entre os locais; inclui origem e destino."""
    if origin not in LOCATIONS_BY_ID or destination not in LOCATIONS_BY_ID:
        return ()
    paths = deque([(origin,)])
    visited = {origin}
    while paths:
        path = paths.popleft()
        if path[-1] == destination:
            return path
        for exit in LOCATIONS_BY_ID[path[-1]].exits:
            if exit.target_location_id not in visited:
                visited.add(exit.target_location_id)
                paths.append((*path, exit.target_location_id))
    return ()


def social_tone(state, actor_id, other_id):
    relation = relationship_for(state, actor_id, other_id)
    if relation.resentment >= 25 or relation.affinity <= -20:
        return "hostil"
    if relation.affinity >= 25 and relation.trust >= 0:
        return "amigável"
    return "reservado"


def select_pair(state, eligible_ids, world, day, slot, now):
    """Pontua novidade, assunto, relações e participação sem ler o papel do elenco."""
    positions = {npc.npc_id: npc for npc in world.npcs}
    encounters = [item for item in state.encounters if item.day == day]
    counts = {identifier: sum(identifier in item.participant_ids for item in encounters)
              for identifier in eligible_ids}
    last_seen = {identifier: max((item.started_at for item in state.encounters
                                 if identifier in item.participant_ids), default=None)
                 for identifier in eligible_ids}
    candidates = []
    for actor in sorted(eligible_ids):
        if counts[actor] >= MAX_ENCOUNTERS_PER_NPC or actor not in positions:
            continue
        owned = [entry for entry in state.knowledge if entry.owner_id == actor and entry.kind != "literal"]
        for recipient in sorted(eligible_ids):
            if actor == recipient or counts[recipient] >= MAX_ENCOUNTERS_PER_NPC or recipient not in positions:
                continue
            pair = {actor, recipient}
            if any(set(item.participant_ids) == pair and
                   now - item.started_at < timedelta(seconds=PAIR_COOLDOWN_SECONDS) for item in encounters):
                continue
            route = route_between(positions[actor].location_id, positions[recipient].location_id)
            if not route:
                continue
            known_roots = {entry.root_id for entry in state.knowledge if entry.owner_id == recipient}
            topics = sorted(owned, key=lambda entry: (
                recipient in entry.subject_ids or recipient == entry.claimed_source_id,
                entry.root_id not in known_roots,
                entry.created_at,
            ), reverse=True)[:2]
            relation = relationship_for(state, actor, recipient)
            score = -15 * (counts[actor] + counts[recipient])
            score += sum(20 if last_seen[identifier] is None else
                         min(20, max(0, int((now - last_seen[identifier]).total_seconds() / 60)))
                         for identifier in (actor, recipient))
            score += 5 if len(route) == 1 else 0
            score += sum(15 for entry in topics if entry.root_id not in known_roots)
            score += sum(30 for entry in topics if recipient in entry.subject_ids or recipient == entry.claimed_source_id)
            score += min(10, abs(relation.affinity) // 10 + relation.resentment // 10)
            # Empates variam de forma estável por slot, sem novo sorteio em retry.
            tie = sum(ord(letter) for letter in f"{day}:{slot}:{actor}:{recipient}") % 17
            candidates.append((score, tie, actor, recipient, tuple(entry.id for entry in topics), route))
    return max(candidates, default=None)


def should_refuse(state, actor_id, recipient_id, topic_ids):
    relation = relationship_for(state, recipient_id, actor_id)
    relevant = any(entry.id in topic_ids and recipient_id in entry.subject_ids for entry in state.knowledge)
    return relation.trust <= -70 and relation.resentment >= 85 and not relevant
