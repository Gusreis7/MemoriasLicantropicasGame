"""Incentivos sociais reais: papéis não entram nas fórmulas."""
from datetime import UTC, datetime
from uuid import uuid4
import pytest

from src.contracts.errors import AccessDeniedError
from src.contracts.social import Relationship, SocialMessage, SocialState
from src.modules.knowledge.mechanics import can_share, closeness, vote_scores
from src.modules.knowledge.rules import apply_relationship, initial_relationships, relationship_for, transmit
from src.modules.knowledge.seeds import seed_social_state

IDS=('bentinho','capitu','escobar','bacamarte','virgilia','florenca','rubiao')
NOW=datetime(2026,11,2,tzinfo=UTC)


def seeded():
    return seed_social_state(SocialState(game_id=uuid4()), IDS, NOW)


def test_author_topics_seed_once_preserve_existing_memory_and_relationships():
    state=seeded()
    assert seed_social_state(state,IDS,NOW)==state
    assert state.topics_initialized
    assert len(state.relationships)==(len(IDS)+1)*(len(IDS)+2)
    assert relationship_for(state,'escobar','bentinho').loyalty>=50
    assert relationship_for(state,'bentinho','escobar').suspicion>=50
    assert relationship_for(state,'capitu','escobar').affinity>0
    secret=[e for e in state.knowledge if 'vai além' in e.proposition]
    assert len(secret)==1 and secret[0].owner_id=='escobar' and secret[0].visibility=='private'
    rumors=[e for e in state.knowledge if 'impressão minha' in e.proposition]
    assert {e.owner_id for e in rumors}=={'virgilia','capitu'}
    assert all(e.kind=='interpretation' for e in rumors)


def test_confidence_cannot_leak_until_trust_and_affinity_are_earned():
    state=seeded()
    secret=next(e for e in state.knowledge if e.visibility=='private' and e.owner_id=='escobar')
    message=SocialMessage(id=uuid4(),sender_id='escobar',content=secret.proposition,
                          claim_ids=(secret.id,),intent='confide',created_at=NOW)
    assert not can_share(secret,state.relationships,'escobar','player')
    with pytest.raises(AccessDeniedError): transmit(state,message,'player',1)
    relations=(*state.relationships,)
    relations=tuple(r.model_copy(update={'trust':100,'affinity':100,'loyalty':100})
                    if r.actor_id=='escobar' and r.target_id=='player' else r for r in relations)
    state=state.model_copy(update={'relationships':relations})
    assert closeness(relationship_for(state,'escobar','player'))==100
    result=transmit(state,message,'player',1)
    assert result.knowledge[-1].root_id==secret.root_id
    assert result.knowledge[-1].visibility=='trusted'


def test_repeated_rumor_never_adds_independent_sources_or_farms_suspicion():
    state=seeded()
    topic=next(e for e in state.knowledge if e.owner_id=='bentinho' and e.kind=='interpretation')
    message=SocialMessage(id=uuid4(),sender_id='bentinho',content=topic.proposition,
                          claim_ids=(topic.id,),intent='accuse',created_at=NOW)
    first=transmit(state,message,'rubiao',1)
    score=relationship_for(first,'rubiao','escobar').suspicion
    again=transmit(first,message.model_copy(update={'id':uuid4()}),'rubiao',1)
    assert again==first and score>0
    assert len({e.root_id for e in first.knowledge if e.proposition==topic.proposition})==1


def test_relationship_changes_have_limits_and_causal_idempotency():
    state=seeded(); cause=uuid4()
    new=apply_relationship(state,'rubiao','player',cause,trust=-500,suspicion=500,loyalty=500)
    r=relationship_for(new,'rubiao','player')
    assert (r.trust,r.suspicion,r.loyalty)==(-5,5,5)
    assert apply_relationship(new,'rubiao','player',cause,suspicion=5)==new


def test_votes_are_bounded_proof_sensitive_and_can_target_floriano():
    relationships=initial_relationships(IDS)
    weak=vote_scores('capitu','escobar',relationships,0,.1)
    strong=vote_scores('capitu','escobar',relationships,1,.8)
    assert 0<=weak['escobar']<strong['escobar']<=1
    hostile=(Relationship(actor_id='capitu',target_id='player',trust=-90,affinity=-80,resentment=90,suspicion=80),)
    reaction=vote_scores('capitu','escobar',hostile,.1,.1)
    assert reaction['player']>.5 and reaction['player']>reaction['escobar']
    assert vote_scores('escobar','escobar',relationships,1,1)['escobar']==0
    for proof in (-10,0,.5,1,10):
        for argument in (-10,0,.5,1,10):
            assert all(0<=v<=1 for v in vote_scores('capitu','escobar',hostile,proof,argument).values())


def test_friendship_can_protect_and_resentment_can_accuse_without_proof():
    friendly=(Relationship(actor_id='capitu',target_id='escobar',affinity=70,trust=60,loyalty=70),)
    hostile=(Relationship(actor_id='capitu',target_id='escobar',affinity=-70,trust=-60,resentment=90,suspicion=90),)
    assert vote_scores('capitu','escobar',hostile,.35,.4)['escobar'] > vote_scores('capitu','escobar',friendly,.35,.4)['escobar']
