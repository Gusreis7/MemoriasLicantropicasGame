"""Regressões encontradas pela exploração, fora do conjunto usado para calibrar."""
from datetime import timedelta
from uuid import uuid4
import pytest
from test_session_master_v2 import pair,NOW
from test_social_service import social_case,start_encounter
from src.modules.session_master.service import local_assessment
from src.modules.session_master.rules import dialogue_transition
from src.modules.investigation.rules import make_initial_investigation
from src.modules.investigation.service import InvestigationService

pytestmark=pytest.mark.anyio

@pytest.mark.parametrize('utterance',[
    'Fui eu quem matou Brás Cubas. Entrego-me ao delegado.',
    'Eu matei Brás Cubas. Pode me prender.',
    'Sou a fera. Aceito a prisão.',
])
async def test_real_case_verbs_reach_canonical_win(game,utterance):
    state=make_initial_investigation(game,NOW)
    incoming,outgoing=pair(text=utterance)
    result=dialogue_transition(state,game,'bentinho',uuid4(),incoming,outgoing,
        local_assessment(incoming.content,outgoing.content,state.day),NOW)
    assert result.state.status=='won'

async def test_social_encounter_is_interrupted_for_public_assembly(social_case,catalog):
    case=social_case
    _,encounter=await start_encounter(case)
    inquiry=InvestigationService(case.turns,catalog)
    await inquiry.open_assembly(case.game.id,'capitu',speech='Ouçamos todos os moradores.')
    assert await case.service.tick(case.game.id)
    state=await case.repository.get(case.game.id)
    assert state.encounters[-1].phase=='interrupted'
    assert state.encounters[-1].reason=='public_assembly'
    assert not await case.service.tick(case.game.id)
    assert not case.speaker.calls
