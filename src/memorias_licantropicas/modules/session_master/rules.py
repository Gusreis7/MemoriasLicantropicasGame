"""Consequências canônicas do diálogo: opinião não cria provas materiais."""
import re
from uuid import NAMESPACE_URL, uuid5
from memorias_licantropicas.contracts.investigation import CaseEvent, CaseTransition, Confrontation
from memorias_licantropicas.modules.session_master.service import direct_admission, normalize


def dialogue_transition(state, game, npc_id, conversation_id, incoming, outgoing, assessment, now):
    event_id = str(uuid5(NAMESPACE_URL, f'dialogue:{outgoing.id}'))
    if any(e.get('id') == event_id for e in state.dialogue_events):
        return CaseTransition(state=state)
    direct, surrendered = direct_admission(outgoing.content, incoming.content)
    member = next((m for m in game.characters if m.character_id == npc_id), None)
    victims = {normalize(c.victim_id.replace('_', ' ')) for c in state.crimes}
    specific = any(direct_admission(sentence, incoming.content)[0] and (
        re.search(r'\b(lobisomem|sou a fera|mortes|ataques|assassinatos)\b', normalize(sentence))
        or any(re.search(r'\b' + re.escape(victim) + r'\b', normalize(sentence)) for victim in victims))
        for sentence in re.split(r'[.!?;\n]+', outgoing.content))
    accepted = bool(member and member.role == 'werewolf' and member.alive and direct and specific and surrendered
        and assessment.kind == 'admission' and assessment.own_assertion and assessment.confidence >= .85)
    record = {'id': event_id, 'conversation_id': str(conversation_id), 'incoming_id': str(incoming.id),
        'outgoing_id': str(outgoing.id), 'npc_id': npc_id, 'day': state.day,
        'incoming': incoming.content, 'outgoing': outgoing.content,
        'assessment': assessment.model_dump(mode='json'), 'accepted_confession': accepted,
        'rule_version': 'natural-dialogue-v1', 'created_at': now.isoformat()}
    changes = {'dialogue_events': (*state.dialogue_events, record)}
    events = [CaseEvent(type='session.exchange_assessed', data={'id': event_id, 'npc_id': npc_id,
        'kind': assessment.kind, 'incoming_id': str(incoming.id), 'outgoing_id': str(outgoing.id)})]
    if assessment.kind == 'alibi' and assessment.day is not None and assessment.period:
        from memorias_licantropicas.modules.investigation.interrogation import make_interrogation
        day, period = assessment.day, assessment.period
        if day <= state.day and not (period == 'night' and day >= state.day) and not any(
                r.npc_id == npc_id and r.day == day and r.period == period for r in state.interrogations):
            names = {m.character_id: m.character_id for m in game.characters}
            declaration = make_interrogation(state, game, npc_id, day, period, names, now)
            changes['interrogations'] = (*state.interrogations, declaration.model_copy(update={'text': outgoing.content}))
            events.append(CaseEvent(type='character.interrogated', data={'interrogation_id': str(declaration.id),
                'npc_id': npc_id, 'day': day, 'period': period, 'source': 'dialogue'}))
    if accepted:
        confrontation = Confrontation(id=uuid5(NAMESPACE_URL, f'confession:{outgoing.id}'), npc_id=npc_id,
            day=state.day, confessed=True, text=outgoing.content, created_at=now)
        changes.update(status='won', phase='finished', ending_method='confession', detained_npc_id=npc_id,
            confrontations=(*state.confrontations, confrontation))
        events.extend((CaseEvent(type='werewolf.confessed', data={'character_id': npc_id, 'day': state.day,
            'source': 'dialogue', 'event_id': event_id}),
            CaseEvent(type='game.won', data={'werewolf_id': npc_id, 'method': 'confession', 'day': state.day})))
    return CaseTransition(state=state.model_copy(update=changes), events=tuple(events))
