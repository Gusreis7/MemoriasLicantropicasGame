"""O mestre publica opinião assinada a partir do desfecho e autoria reais."""
import json
from datetime import UTC, datetime

import pytest

from memorias_licantropicas.contracts.model import LLMResponse
from memorias_licantropicas.modules.investigation.rules import make_initial_investigation, make_crime
from memorias_licantropicas.modules.session_master.editorial import final_edition, SIGNATURE
from memorias_licantropicas.modules.session_master.service import SessionMasterService

pytestmark = pytest.mark.anyio
NOW = datetime(2026, 11, 4, tzinfo=UTC)


@pytest.mark.parametrize('method', ['detention', 'confession', 'assembly'])
@pytest.mark.parametrize('unavailable', [False, True])
async def test_signed_editorial_uses_actual_deaths_and_method(game, method, unavailable):
    names = {'bentinho': 'Bentinho', 'capitu': 'Capitu', 'escobar': 'Escobar'}
    state = make_initial_investigation(game, NOW)
    wolf_crime = make_crime(game, 1, 'capitu', 'praca_verde', NOW,
                           killer_id='bentinho', cause='werewolf')
    human_crime = make_crime(game, 1, 'escobar', 'praca_verde', NOW,
                            killer_id='capitu', cause='civil')
    state = state.model_copy(update={'status': 'won', 'phase': 'finished',
        'ending_method': method, 'crimes': (wolf_crime, human_crime)})
    state = state.model_copy(update={'journal': (*state.journal,
        final_edition(state, names, werewolf_id='bentinho'))})
    calls = []
    class LLM:
        async def complete(self, prompt):
            calls.append(prompt)
            if unavailable:
                raise RuntimeError('offline')
            return LLMResponse(content='A persistência de Floriano merece o reconhecimento desta cidade. Que o alívio de hoje nos ensine a preservar a memória das vítimas e a exigir justiça.', model='fake')
    master = SessionMasterService(None, None, None, LLM())
    result = await master.publish_victory(state, game)
    body = result.journal[-1].body
    assert 'Bentinho era o lobisomem' in body
    assert 'Capitu (1)' in body
    assert 'Escobar' not in body
    assert body.endswith(SIGNATURE)
    assert len(result.journal) == len(state.journal)
    assert result.status == 'won'
    payload = json.loads(calls[0][1].content)
    assert 'Capitu' in payload['fatos_confirmados']
    assert 'Escobar' not in payload['fatos_confirmados']
    assert ('persistência de Floriano' in body) != unavailable
