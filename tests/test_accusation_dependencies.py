from uuid import UUID

import pytest

from src.contracts.investigation import InvestigationState
from src.modules.investigation.rules import make_testimony

pytestmark = pytest.mark.anyio


async def test_api_object_testimony_requires_its_item_not_a_synchronization_retry(api_client, storage):
    gid = (await api_client.post('/api/v1/games', json={})).json()['id']
    game = await storage.games.get(UUID(gid))
    key = f'{storage.prefix}:game:{{{gid}}}:investigation'
    state = InvestigationState.model_validate_json(await storage.client.get(key))
    crime = state.crimes[0]
    evidence = crime.evidence[0].model_copy(update={'collected': True})
    crime = crime.model_copy(update={'evidence': (evidence, *crime.evidence[1:])})
    statement = make_testimony(state, game, evidence, 'capitu', {}, game.created_at)
    state = state.model_copy(update={'crimes': (crime,), 'testimonies': (statement,)})
    await storage.client.set(key, state.model_dump_json())
    body = {'suspect_id': 'capitu', 'testimony_ids': [str(statement.id)]}
    missing = await api_client.post(f'/api/v1/games/{gid}/accusations/review', json=body)
    assert missing.status_code == 409
    assert missing.json()['detail'] == 'Um depoimento precisa acompanhar seu vestígio na acusação.'
    body['evidence_ids'] = [str(evidence.id)]
    valid = await api_client.post(f'/api/v1/games/{gid}/accusations/review', json=body)
    assert valid.status_code == 200
    after = InvestigationState.model_validate_json(await storage.client.get(key))
    assert after.accusations == () and after.revision == state.revision
