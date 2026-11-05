"""Consequências canônicas do diálogo: opinião não cria provas materiais."""

import re
from uuid import NAMESPACE_URL, uuid5
from memorias_licantropicas.contracts.investigation import (
    CaseEvent,
    CaseTransition,
    Confrontation,
)
from memorias_licantropicas.modules.session_master.validation import (
    normalize,
    admission_evidence,
    own_assertion_clauses,
)


def dialogue_transition(
    state, game, npc_id, conversation_id, incoming, outgoing, assessment, now
):
    event_id = str(uuid5(NAMESPACE_URL, f"dialogue:{outgoing.id}"))
    if any(e.get("id") == event_id for e in state.dialogue_events):
        return CaseTransition(state=state)
    direct, surrendered = admission_evidence(
        outgoing.content, incoming.content, assessment
    )
    member = next((m for m in game.characters if m.character_id == npc_id), None)
    victims = {
        normalize(c.victim_id.replace("_", " "))
        for c in state.crimes
        if c.killer_id == npc_id and c.cause == "werewolf"
    }
    # A fala própria precisa apontar à fera, aos ataques ou a uma vítima real do caso.
    specific = any(
        (
            re.search(r"\b(lobisomem|fera|mortes|ataques|assassinatos)\b", clause)
            or (
                re.search(
                    r"\b(matei|matou|ataquei|atacou|assassinei|tirei|ceifei|arranquei|causei|cometi)\b",
                    clause,
                )
                and any(
                    re.search(r"\b" + re.escape(victim) + r"\b", clause)
                    for victim in victims
                )
            )
        )
        for clause in own_assertion_clauses(outgoing.content, incoming.content)
    )
    accepted = bool(
        member
        and member.role == "werewolf"
        and member.alive
        and direct
        and specific
        and surrendered
        and assessment.kind == "admission"
        and assessment.own_assertion
        and assessment.confidence >= 0.85
    )
    civil_admission = bool(
        member
        and member.role == "civil"
        and direct
        and any(
            c.killer_id == npc_id
            and c.cause == "civil"
            and any(
                normalize(c.victim_id.replace("_", " ")) in clause
                and re.search(r"\b(matei|ataquei|assassinei|tirei|ceifei)\b", clause)
                for clause in own_assertion_clauses(outgoing.content, incoming.content)
            )
            for c in state.crimes
        )
    )
    record = {
        "id": event_id,
        "conversation_id": str(conversation_id),
        "incoming_id": str(incoming.id),
        "outgoing_id": str(outgoing.id),
        "npc_id": npc_id,
        "day": state.day,
        "incoming": incoming.content,
        "outgoing": outgoing.content,
        "narrative_authorized": outgoing.narrative_authorized,
        "useful": outgoing.useful,
        "assessment": assessment.model_dump(mode="json"),
        "accepted_confession": accepted,
        "civil_admission": civil_admission,
        "rule_version": "natural-dialogue-v1",
        "created_at": now.isoformat(),
    }
    from memorias_licantropicas.modules.achievements.rules import (
        award,
        discoveries_in_reply,
        discovery_assertions,
    )

    discovered = (
        discoveries_in_reply(npc_id, outgoing.content, assessment.discovery_ids)
        if outgoing.narrative_authorized
        else ()
    )
    # Public fragments may be heard in different conversations; private disclosures require the owner's current voice.
    public_ids = {
        "marriage_triangle",
        "seminary_bond",
        "treatment_bentinho",
        "florenca_father",
    }
    if outgoing.narrative_authorized:
        for topic in public_ids:
            passages = [
                discovery_assertions(event["npc_id"], event["outgoing"])
                for event in state.dialogue_events
                if event.get("narrative_authorized", False)
                and topic
                in event.get("assessment", {}).get("eligible_discovery_ids", ())
            ]
            if topic in assessment.eligible_discovery_ids:
                passages.append(discovery_assertions(npc_id, outgoing.content))
            if passages:
                discovered = tuple(
                    dict.fromkeys(
                        (
                            *discovered,
                            *discoveries_in_reply("", ". ".join(passages), (topic,)),
                        )
                    )
                )
    discovered_state = state
    for achievement_id in discovered:
        discovered_state = award(
            discovered_state,
            achievement_id,
            now,
            source_message_id=outgoing.id,
            source_npc_id=npc_id,
        )
    changes = {
        "dialogue_events": (*state.dialogue_events, record),
        "achievements": discovered_state.achievements,
    }
    events = [
        CaseEvent(
            type="session.exchange_assessed",
            data={
                "id": event_id,
                "npc_id": npc_id,
                "kind": assessment.kind,
                "incoming_id": str(incoming.id),
                "outgoing_id": str(outgoing.id),
            },
        )
    ]
    if civil_admission:
        events.append(
            CaseEvent(
                type="civil_crime.admitted",
                data={
                    "character_id": npc_id,
                    "day": state.day,
                    "message_id": str(outgoing.id),
                },
            )
        )
    if (
        assessment.kind == "alibi"
        and assessment.own_assertion
        and assessment.quote
        and assessment.quote in outgoing.content
        and assessment.day is not None
        and assessment.period
    ):
        from memorias_licantropicas.modules.investigation.interrogation import (
            make_interrogation,
        )

        day, period = assessment.day, assessment.period
        if (
            day <= state.day
            and not (period == "night" and day >= state.day)
            and not any(
                r.npc_id == npc_id and r.day == day and r.period == period
                for r in state.interrogations
            )
        ):
            names = {m.character_id: m.character_id for m in game.characters}
            declaration = make_interrogation(
                state, game, npc_id, day, period, names, now
            )
            # Only what was actually said enters the public notebook, not all private observations.
            text = normalize(outgoing.content)
            places = {
                "praca_verde": "praca",
                "cabana_capitu": "cabana",
                "casa_verde": "casa verde",
                "cafe_largo": "cafe",
                "cais_lanternas": "cais",
            }
            mentioned = {
                key
                for key, alias in places.items()
                if re.search(r"\b" + alias + r"\b", text)
            }
            observations = tuple(
                claim
                for claim in declaration.observations
                if normalize(claim.npc_id.replace("_", " ")) in text
                and claim.location_id in mentioned
            )
            companions = tuple(
                person
                for person in declaration.companion_ids
                if normalize(person.replace("_", " ")) in text
            )
            changes["interrogations"] = (
                *state.interrogations,
                declaration.model_copy(
                    update={
                        "text": outgoing.content,
                        "location_id": declaration.location_id
                        if declaration.location_id in mentioned
                        else None,
                        "companion_ids": companions,
                        "observations": observations,
                    }
                ),
            )
            events.append(
                CaseEvent(
                    type="character.interrogated",
                    data={
                        "interrogation_id": str(declaration.id),
                        "npc_id": npc_id,
                        "day": day,
                        "period": period,
                        "source": "dialogue",
                    },
                )
            )
    if accepted:
        confrontation = Confrontation(
            id=uuid5(NAMESPACE_URL, f"confession:{outgoing.id}"),
            npc_id=npc_id,
            day=state.day,
            confessed=True,
            text=outgoing.content,
            created_at=now,
        )
        changes.update(
            status="won",
            phase="finished",
            ending_method="confession",
            detained_npc_id=npc_id,
            confrontations=(*state.confrontations, confrontation),
        )
        events.extend(
            (
                CaseEvent(
                    type="werewolf.confessed",
                    data={
                        "character_id": npc_id,
                        "day": state.day,
                        "source": "dialogue",
                        "event_id": event_id,
                    },
                ),
                CaseEvent(
                    type="game.won",
                    data={
                        "werewolf_id": npc_id,
                        "method": "confession",
                        "day": state.day,
                    },
                ),
            )
        )
    return CaseTransition(state=state.model_copy(update=changes), events=tuple(events))
