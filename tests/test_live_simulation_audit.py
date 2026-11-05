import json
from uuid import uuid4

import fakeredis
import pytest

from src.simulation.audit import collect_server_statistics

pytestmark = pytest.mark.anyio


async def test_audit_reads_only_named_game_and_separates_fallbacks():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    game_id, conversation_id = uuid4(), uuid4()
    base = f'test:audit:game:{{{game_id}}}'
    try:
        await redis.set(f'{base}:state', json.dumps({'id': str(game_id), 'status': 'active'}))
        await redis.set('unrelated', 'preserved')
        await redis.zadd(f'{base}:conversations', {str(conversation_id): 1})
        key = f'{base}:conversation:{conversation_id}'
        await redis.rpush(f'{key}:order', 'one', 'two')
        await redis.hset(f'{key}:messages', mapping={
            'one': json.dumps({'sender_id': 'player', 'content': 'O que viu?'}),
            'two': json.dumps({'sender_id': 'capitu', 'content': 'Falha técnica', 'generation_status': 'fallback'}),
        })
        before = {key: await redis.dump(key) async for key in redis.scan_iter()}
        audit = await collect_server_statistics(None, 'test:audit', game_id, client=redis)
        assert audit['npc_generation_status_counts'] == {'fallback': 1}
        assert audit['usage']['totals']['calls'] == 0
        assert audit['ongoing_game'] is True
        assert {key: await redis.dump(key) async for key in redis.scan_iter()} == before
        assert not (await collect_server_statistics(None, 'wrong', game_id, client=redis))['available']
    finally:
        await redis.aclose()
