from uuid import uuid4
from datetime import timedelta
import pytest
from test_evidence_specificity_v3 import dossier,NOW,game_for,collected
from test_interrogations import inquiry,near
from memorias_licantropicas.modules.investigation.catalog import items_of_kind,INVENTORIES
from memorias_licantropicas.modules.investigation.rules import make_crime,make_testimony,evaluate_accusation
from memorias_licantropicas.modules.investigation.scoring import assess_dossier


def personal_dossier(person='bentinho'):
 state,game,_,_=dossier(person,after_night=True)
 crime=collected(make_crime(game,2,'bras_cubas','cafe_largo',NOW))
 old_unique=next(e.item_id for e in state.crimes[-1].evidence if e.item_id in items_of_kind(person,'unique'))
 other=next(i for i in items_of_kind(person,'unique') if i!=old_unique)
 crime=crime.model_copy(update={'evidence':tuple(e.model_copy(update={'item_id':other}) if e.item_id in items_of_kind(person,'unique') else e for e in crime.evidence)})
 state=state.model_copy(update={'day':3,'crimes':(*state.crimes,crime)})
 statements=tuple(make_testimony(state,game,e,m.character_id,{p:p for p in INVENTORIES},NOW)
     for c in state.crimes for e in c.evidence for m in game.characters if m.alive)
 state=state.model_copy(update={'testimonies':statements})
 return state,game,tuple(e.id for c in state.crimes for e in c.evidence),tuple(t.id for t in statements)

@pytest.mark.parametrize('person',('bentinho','capitu','escobar','rubiao','florenca','virgilia','bacamarte'))
def test_two_personal_marks_corroborated_per_item_allow_custody_without_examination(person):
 state,game,ev,ts=personal_dossier(person)
 result=assess_dossier(state,person,ev,ts)
 assert result.accepted and result.custody_route=='corroborated_personal_marks'
 assert len(result.corroborated_personal_ids)==2 and not result.examined_exclusive_ids


def test_repeated_copies_of_one_personal_item_do_not_replace_distinct_marks():
 state,game,ev,ts=personal_dossier()
 first=items_of_kind('bentinho','unique')[1]
 crimes=tuple(c.model_copy(update={'evidence':tuple(e.model_copy(update={'item_id':first}) if e.item_id in items_of_kind('bentinho','unique') else e for e in c.evidence)}) for c in state.crimes)
 state=state.model_copy(update={'crimes':crimes})
 assert not assess_dossier(state,'bentinho',ev,ts).accepted


def test_two_sources_on_common_items_do_not_corroborate_unique_marks():
 state,game,ev,ts=personal_dossier()
 statements=tuple(t for t in state.testimonies if t.witness_id!='florenca')
 state=state.model_copy(update={'testimonies':statements})
 # Force every exclusive recognition onto one real witness, retaining common witnesses.
 personal_ids={e.id for c in state.crimes for e in c.evidence if e.item_id in items_of_kind('bentinho','unique')}
 state=state.model_copy(update={'testimonies':tuple(t.model_copy(update={'witness_id':'bacamarte'}) if t.evidence_id in personal_ids else t for t in statements)})
 assert not assess_dossier(state,'bentinho',ev,tuple(t.id for t in state.testimonies)).accepted


def test_private_truth_and_killer_fields_do_not_change_review():
 state,_,ev,ts=personal_dossier();before=assess_dossier(state,'bentinho',ev,ts)
 changed=state.model_copy(update={'crimes':tuple(c.model_copy(update={'killer_id':'capitu','cause':'civil','evidence':tuple(e.model_copy(update={'deposited_by':'capitu'}) for e in c.evidence)}) for c in state.crimes),'testimonies':tuple(t.model_copy(update={'truthful':False}) for t in state.testimonies)})
 assert assess_dossier(changed,'bentinho',ev,ts)==before

@pytest.mark.anyio
async def test_rejection_does_not_burn_day_and_identical_retry_is_idempotent(inquiry):
 from test_interrogations import dossier as ready_dossier
 state,game,ev,ts=await ready_dossier(inquiry)
 await inquiry.storage.client.set(inquiry.key+':investigation',state.model_dump_json())
 rejected=await inquiry.service.accuse(game.id,'capitu',(),())
 assert not rejected.accusations[-1].accepted
 repeated=await inquiry.service.accuse(game.id,'capitu',(),())
 assert repeated.revision==rejected.revision and repeated.accusations==rejected.accusations
 approved=await inquiry.service.accuse(game.id,'capitu',ev,ts)
 assert approved.day==rejected.day and approved.phase=='night' and approved.accusations[-1].accepted

@pytest.mark.anyio
async def test_read_only_review_has_no_accusation_or_clock_cost(inquiry):
 state,game,ev,ts=personal_dossier('capitu')
 # Use the persisted fixture's game identity for the transactional service.
 state=state.model_copy(update={'game_id':inquiry.game.id,'phase_ends_at':inquiry.clock[0]+timedelta(minutes=5)})
 await inquiry.turns.sync(inquiry.game.id)
 await inquiry.storage.client.set(inquiry.key+':investigation',state.model_dump_json())
 before=await inquiry.turns.sync(inquiry.game.id)
 review=await inquiry.service.review_accusation(inquiry.game.id,'capitu',ev,ts)
 assert review.ready and review.route=='corroborated_personal_marks'
 assert (await inquiry.turns.sync(inquiry.game.id))==before
