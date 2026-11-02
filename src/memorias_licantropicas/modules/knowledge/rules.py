"""Regras puras de relações e transmissão; discurso não altera fatos do caso."""

import unicodedata
from uuid import NAMESPACE_URL, uuid5

from memorias_licantropicas.contracts.errors import AccessDeniedError
from memorias_licantropicas.contracts.social import KnowledgeEntry, Relationship


def initial_relationships(character_ids):
    seeds = {
        ("bentinho", "capitu"): (15, -15, 25),
        ("bentinho", "escobar"): (-25, -35, 30),
        ("capitu", "bentinho"): (-20, -20, 25),
        ("escobar", "bentinho"): (65, 35, 0),
        ("virgilia", "florenca"): (55, 40, 0),
        ("florenca", "rubiao"): (-25, -15, 30),
        ("rubiao", "florenca"): (60, 25, 0),
        ("florenca", "bacamarte"): (-45, -35, 45),
        ("bacamarte", "player"): (-5, -25, 5),
    }
    seeds.update({
        ("capitu", "escobar"): (50, 45, 0),
        ("escobar", "capitu"): (30, 25, 5),
        ("capitu", "bacamarte"): (15, 25, 0),
        ("bacamarte", "bentinho"): (10, 10, 0),
        ("bentinho", "bacamarte"): (-15, -20, 15),
        ("florenca", "virgilia"): (55, 45, 0),
    })
    loyalties = {("escobar", "bentinho"): 80, ("capitu", "escobar"): 40,
                 ("virgilia", "florenca"): 65, ("florenca", "virgilia"): 55}
    suspicions = {("bentinho", "escobar"): 50, ("bentinho", "capitu"): 30,
                  ("florenca", "bacamarte"): 30}
    ids = tuple(character_ids)
    return tuple(Relationship(actor_id=actor, target_id=target,
                              affinity=seeds.get((actor, target), (0, 0, 0))[0],
                              trust=seeds.get((actor, target), (0, 0, 0))[1],
                              resentment=seeds.get((actor, target), (0, 0, 0))[2],
                              suspicion=suspicions.get((actor,target),0),
                              loyalty=loyalties.get((actor,target),0))
                 for actor in ids for target in (*ids, "player") if actor != target)


def relationship_for(state, actor_id, target_id):
    return next((relation for relation in state.relationships
                 if relation.actor_id == actor_id and relation.target_id == target_id),
                Relationship(actor_id=actor_id, target_id=target_id))


def apply_relationship(state, actor_id, target_id, cause_id, *, affinity=0, trust=0, resentment=0, suspicion=0, loyalty=0):
    relation = relationship_for(state, actor_id, target_id)
    if cause_id in relation.causes:
        return state
    def bounded(value, change, floor=-100):
        return min(100, max(floor, value + min(5, max(-5, change))))
    updated = relation.model_copy(update={
        "affinity": bounded(relation.affinity, affinity),
        "trust": bounded(relation.trust, trust),
        "resentment": bounded(relation.resentment, resentment, 0),
        "suspicion": bounded(relation.suspicion, suspicion, 0),
        "loyalty": bounded(relation.loyalty, loyalty, 0),
        "causes": (*relation.causes, cause_id),
    })
    others = tuple(item for item in state.relationships if (item.actor_id, item.target_id) != (actor_id, target_id))
    return state.model_copy(update={"relationships": (*others, updated)})


def transmit(state, message, recipient_id, day):
    owned = {entry.id: entry for entry in state.knowledge if entry.owner_id == message.sender_id}
    if any(identifier not in owned for identifier in message.claim_ids):
        raise AccessDeniedError("A fala cita um relato que o emissor não conhece.")
    from memorias_licantropicas.modules.knowledge.mechanics import can_share, gossip_weight
    for identifier in message.claim_ids:
        if not can_share(owned[identifier], state.relationships, message.sender_id, recipient_id):
            raise AccessDeniedError("A confidência exige um vínculo de confiança maior.")
    entries = list(state.knowledge)
    new_suspicions = []
    contested_player_roots = set()
    for identifier in dict.fromkeys(message.claim_ids):
        parent = owned[identifier]
        if parent.kind == "literal":
            continue
        known_root = any(entry.owner_id == recipient_id and entry.root_id == parent.root_id for entry in entries)
        # Repetição e recirculação não representam nova fonte independente.
        kind = {"deny": "denial", "correct": "correction", "interpret": "interpretation"}.get(message.intent, parent.kind)
        proposition = message.content if message.intent in ("deny", "correct", "interpret") else parent.proposition
        normalized = "".join(character for character in unicodedata.normalize("NFKD", message.content.casefold())
                             if not unicodedata.combining(character))
        aliases = ("floriano", "detetive") if parent.speaker_id == "player" else (parent.speaker_id,)
        claimed_source = parent.speaker_id if any(alias in normalized for alias in aliases) else None
        effective_parent = parent
        if message.intent in ("deny", "correct", "interpret"):
            own_variant = next((entry for entry in entries if entry.owner_id == message.sender_id
                                and entry.root_id == parent.root_id and entry.kind == kind
                                and entry.proposition == proposition), None)
            if own_variant is None:
                own_variant = KnowledgeEntry(
                    id=uuid5(NAMESPACE_URL, f"{message.id}:{message.sender_id}:{parent.id}:own"),
                    owner_id=message.sender_id, root_id=parent.root_id,
                    source_message_id=message.id, speaker_id=message.sender_id,
                    claimed_source_id=claimed_source, source_span=message.content,
                    proposition=proposition, subject_ids=parent.subject_ids,
                    parent_ids=(parent.id,), kind=kind, day=day, created_at=message.created_at,
                )
                entries.append(own_variant)
            effective_parent = own_variant
        if any(entry.owner_id == recipient_id and entry.root_id == parent.root_id
               and entry.kind == kind and entry.proposition == proposition for entry in entries):
            continue
        entry_id = uuid5(NAMESPACE_URL, f"{message.id}:{recipient_id}:{parent.id}")
        entries.append(KnowledgeEntry(
            id=entry_id, owner_id=recipient_id, root_id=parent.root_id,
            source_message_id=message.id, speaker_id=message.sender_id,
            claimed_source_id=claimed_source, source_span=message.content,
            proposition=proposition, subject_ids=parent.subject_ids,
            parent_ids=(effective_parent.id,), kind=kind, confidence="low", stance="undecided",
            visibility="trusted" if parent.visibility == "private" else parent.visibility,
            disclosure_threshold=max(45, parent.disclosure_threshold) if parent.visibility == "private" else parent.disclosure_threshold,
            day=day, created_at=message.created_at,
        ))
        if message.intent in ("accuse", "defend") and (not known_root or message.intent == "defend"):
            for target in parent.subject_ids:
                if target not in (message.sender_id, recipient_id):
                    source_relation = relationship_for(state, recipient_id, message.sender_id)
                    target_relation = relationship_for(state, recipient_id, target)
                    new_suspicions.append((target, parent.root_id, max(1, round(5 * gossip_weight(source_relation, target_relation, kind))) * (-1 if message.intent == "defend" else 1), message.intent))
        if kind in ("denial", "correction") and any(
            entry.owner_id == recipient_id and entry.root_id == parent.root_id
            and entry.speaker_id == "player" and entry.kind == "report" for entry in state.knowledge
        ):
            contested_player_roots.add(parent.root_id)
    # Contestar uma versão recebida do detetive justifica dúvida, sem concluir que ele mentiu.
    if contested_player_roots:
        entries = [entry.model_copy(update={"stance": "doubts"})
                   if entry.owner_id == recipient_id and entry.speaker_id == "player"
                   and entry.root_id in contested_player_roots and entry.kind == "report" else entry
                   for entry in entries]
    updated = state.model_copy(update={"knowledge": tuple(entries)})
    for target, root, weight, intent in new_suspicions:
        cause = uuid5(NAMESPACE_URL, f"{root}:{recipient_id}:{target}:gossip_suspicion:{intent}")
        updated = apply_relationship(updated, recipient_id, target, cause, suspicion=weight)
    for root_id in contested_player_roots:
        cause = uuid5(NAMESPACE_URL, f"{root_id}:{recipient_id}:contested_player")
        updated = apply_relationship(updated, recipient_id, "player", cause, trust=-1)
    return updated
