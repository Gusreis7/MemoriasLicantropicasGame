from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from memorias_licantropicas.contracts.errors import ConflictError
from memorias_licantropicas.contracts.model import GameState, GameCharacter
from memorias_licantropicas.contracts.investigation import Crime, Evidence, Testimony as Statement, Interrogation, ActivityClaim
from memorias_licantropicas.modules.investigation.catalog import (
    INVENTORIES, ITEMS_BY_ID, ITEMS, PERSONAL_EXTRAS, items_of_kind,
)
from memorias_licantropicas.modules.investigation.rules import (
    make_initial_investigation, make_crime, make_testimony, evaluate_accusation, inspect_evidence, choose_victim,
)
from memorias_licantropicas.modules.investigation.scoring import assess_dossier, dossier_strength
from memorias_licantropicas.modules.investigation.assembly import proof_strength

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def game_for(wolf):
    return GameState(id=UUID(int=12345), created_at=NOW, content_version='3', characters=tuple(
        GameCharacter(character_id=person, role='werewolf' if person == wolf else 'civil') for person in INVENTORIES))


def collected(crime):
    return crime.model_copy(update={'evidence':tuple(e.model_copy(update={'collected':True}) for e in crime.evidence)})


def dossier(wolf, *, after_night=False, examine=False):
    game=game_for(wolf)
    state=make_initial_investigation(game,NOW)
    initial=collected(state.crimes[0])
    state=state.model_copy(update={'crimes':(initial,)})
    names={person:person for person in INVENTORIES}
    statements=tuple(make_testimony(state,game,e,person,names,NOW)
        for e in initial.evidence for person in INVENTORIES if person != wolf)
    if after_night:
        victim=choose_victim(game)
        crime=collected(make_crime(game,1,victim,'cais_lanternas',NOW+timedelta(minutes=5)))
        game=game.model_copy(update={'characters':tuple(m.model_copy(update={'alive':False}) if m.character_id==victim else m for m in game.characters)})
        state=state.model_copy(update={'day':2,'crimes':(initial,crime)})
        statements+=tuple(make_testimony(state,game,e,m.character_id,names,NOW)
            for e in crime.evidence for m in game.characters if m.alive and m.character_id != wolf)
    state=state.model_copy(update={'testimonies':statements})
    if examine:
        for crime in state.crimes:
            for e in crime.evidence:
                state=inspect_evidence(state,e.id,NOW).state
    evidence_ids=tuple(e.id for c in state.crimes for e in c.evidence)
    testimony_ids=tuple(t.id for t in state.testimonies)
    return state,game,evidence_ids,testimony_ids


def test_personal_catalog_preserves_old_items_and_gives_each_person_three_exclusives():
    assert len(ITEMS_BY_ID)==len(ITEMS)==34
    all_personal=[]
    for person,inventory in INVENTORIES.items():
        assert len(inventory)==7 and len(set(inventory))==7
        assert len(items_of_kind(person,'unique'))==3
        assert len(items_of_kind(person,'singular'))==1
        assert len(items_of_kind(person,'common'))==3
        all_personal.extend(items_of_kind(person,'unique'))
        assert set(PERSONAL_EXTRAS[person]) <= set(inventory)
    assert len(all_personal)==len(set(all_personal))==21


@pytest.mark.parametrize('wolf',tuple(INVENTORIES))
def test_initial_common_and_singular_dossier_cannot_detain_anyone(wolf):
    state,game,ev,ts=dossier(wolf,examine=True)
    assessment=assess_dossier(state,wolf,ev,ts)
    assert not assessment.accepted
    assert assessment.material_points<=1.25
    assert 'examinar uma peça pessoal' in evaluate_accusation(state,wolf,ev,ts,NOW).reason
    assert proof_strength(state,wolf,ev,ts,NOW)<.35


@pytest.mark.parametrize('wolf',tuple(INVENTORIES))
def test_every_wolf_has_second_morning_path_with_one_dead_civil(wolf):
    state,game,ev,ts=dossier(wolf,after_night=True,examine=True)
    assert sum(not m.alive for m in game.characters)==1
    assessment=assess_dossier(state,wolf,ev,ts)
    assert assessment.accepted, (wolf,assessment)
    assert len(assessment.independent_witnesses)>=2
    assert assessment.examined_exclusive_ids
    assert evaluate_accusation(state,wolf,ev,ts,NOW).accepted


def test_exclusive_requires_examination_and_does_not_identify_the_owner_by_itself():
    state,game,ev,ts=dossier('escobar',after_night=True)
    assert not evaluate_accusation(state,'escobar',ev,ts,NOW).accepted
    exclusive=next(e for c in state.crimes for e in c.evidence if ITEMS_BY_ID[e.item_id].kind=='unique')
    result=inspect_evidence(state,exclusive.id,NOW)
    inspected=next(e for c in result.state.crimes for e in c.evidence if e.id==exclusive.id)
    assert inspected.examined and inspected.crime_link_verified
    assert 'Escobar' not in inspected.inspection_text
    assert len(result.events)==1
    assert inspect_evidence(result.state,exclusive.id,NOW).state==result.state
    assert inspect_evidence(result.state,exclusive.id,NOW).events==()
    assert evaluate_accusation(result.state,'escobar',ev,ts,NOW).accepted


def test_inspection_requires_collecting_real_object():
    state=make_initial_investigation(game_for('bentinho'),NOW)
    with pytest.raises(ConflictError): inspect_evidence(state,state.crimes[0].evidence[0].id,NOW)


def test_one_witness_repeated_under_new_ids_is_still_one_source():
    state,game,ev,ts=dossier('capitu',after_night=True,examine=True)
    statements=tuple(t.model_copy(update={'witness_id':'escobar'}) for t in state.testimonies)
    state=state.model_copy(update={'testimonies':statements})
    assert not evaluate_accusation(state,'capitu',ev,ts*20,NOW).accepted
    assert len(assess_dossier(state,'capitu',ev,ts).independent_witnesses)==1


def test_private_killer_and_truth_flags_do_not_affect_score():
    state,game,ev,ts=dossier('rubiao',after_night=True,examine=True)
    base=assess_dossier(state,'rubiao',ev,ts)
    changed=state.model_copy(update={
        'crimes':tuple(c.model_copy(update={'killer_id':'capitu','evidence':tuple(e.model_copy(update={'deposited_by':'capitu'}) for e in c.evidence)}) for c in state.crimes),
        'testimonies':tuple(t.model_copy(update={'truthful':not t.truthful}) for t in state.testimonies)})
    assert assess_dossier(changed,'rubiao',ev,ts)==base


def test_common_spam_cannot_gain_custody_or_large_assembly_weight():
    game=game_for('capitu');state=make_initial_investigation(game,NOW)
    common=tuple(i.id for i in ITEMS if i.kind=='common')
    crime=state.crimes[0].model_copy(update={'evidence':tuple(Evidence(id=uuid4(),crime_id=state.crimes[0].id,item_id=i,description='Vestígio.',collected=True,deposited_by='capitu') for i in common)})
    statements=tuple(Statement(id=uuid4(),day=1,evidence_id=e.id,witness_id=w,
        recognition='recognizes',claimed_owner_id='capitu',text='Já vi um desses.',truthful=True,created_at=NOW)
        for e in crime.evidence for w in ('bentinho','escobar','virgilia'))
    state=state.model_copy(update={'crimes':(crime,),'testimonies':statements})
    ev=tuple(e.id for e in crime.evidence);ts=tuple(t.id for t in statements)
    result=assess_dossier(state,'capitu',ev*20,ts*20)
    assert result.material_points==.5 and not result.accepted
    assert dossier_strength(result)<=.15


def test_personal_variants_cycle_without_magic_inventory_positions():
    game=game_for('bacamarte')
    seen=set()
    for day in (1,2,3):
        crime=make_crime(game,day,'rubiao','cafe_largo',NOW)
        seen.update(e.item_id for e in crime.evidence if ITEMS_BY_ID[e.item_id].kind=='unique')
    assert seen==set(items_of_kind('bacamarte','unique'))


def test_examination_of_any_collected_copy_supports_the_same_item_stack():
    state,game,ev,ts=dossier('bentinho',after_night=True,examine=True)
    personal=next(e for c in state.crimes for e in c.evidence if ITEMS_BY_ID[e.item_id].kind=='unique')
    copy=personal.model_copy(update={'id':uuid4(),'examined':False,'inspection_text':None,'crime_link_verified':False})
    crime=state.crimes[-1].model_copy(update={'evidence':(*state.crimes[-1].evidence,copy)})
    state=state.model_copy(update={'crimes':(*state.crimes[:-1],crime)})
    selected=tuple(copy.id if i==personal.id else i for i in ev)
    assert evaluate_accusation(state,'bentinho',selected,ts,NOW).accepted


def test_one_source_can_be_corroborated_by_a_registered_contradiction_not_private_truth():
    state,game,ev,ts=dossier('capitu',after_night=True,examine=True)
    statements=tuple(t.model_copy(update={'witness_id':'escobar'}) for t in state.testimonies)
    state=state.model_copy(update={'testimonies':statements})
    own=Interrogation(id=uuid4(),npc_id='capitu',day=0,period='night',location_id='cabana_capitu',
        activity='Alega ter ficado em casa.',text='Fiquei em casa.',truthful=False,created_at=NOW)
    witness=Interrogation(id=uuid4(),npc_id='escobar',day=0,period='night',location_id='cais_lanternas',
        activity='Passou pelo cais.',text='Vi Capitu no cais.',truthful=True,created_at=NOW,
        observations=(ActivityClaim(npc_id='capitu',location_id='cais_lanternas',activity='No cais.',source='observed'),))
    state=state.model_copy(update={'interrogations':(own,witness)})
    assert evaluate_accusation(state,'capitu',ev,ts,NOW).accepted
    hearsay=witness.model_copy(update={'observations':tuple(o.model_copy(update={'source':'heard'}) for o in witness.observations)})
    assert not evaluate_accusation(state.model_copy(update={'interrogations':(own,hearsay)}),'capitu',ev,ts,NOW).accepted
