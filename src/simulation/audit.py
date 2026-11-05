"""Auditoria administrativa posterior; nunca entra no contexto de Floriano."""
from collections import Counter
from datetime import UTC, datetime
import json
from uuid import UUID

from redis.asyncio import Redis

from src.infrastructure.usage import RedisUsageRepository


async def collect_server_statistics(redis_url, prefix, game_id, *, client=None):
    """Lê exclusivamente a partida indicada; não altera saves nem índices."""
    identifier = UUID(str(game_id))
    owned = client is None
    redis = client or Redis.from_url(redis_url, decode_responses=True,
                                     socket_connect_timeout=3, socket_timeout=5)
    base = f'{prefix}:game:{{{identifier}}}'
    try:
        raw_game = await redis.get(f'{base}:state')
        if raw_game is None:
            return {'available': False, 'reason': 'game_not_found_in_configured_redis'}
        game = json.loads(raw_game)
        if str(game['id']) != str(identifier):
            raise ValueError('Identidade da partida inconsistente')
        usage = await RedisUsageRepository(redis, prefix).summary(identifier)
        events = [json.loads(raw) for raw in await redis.lrange(f'{base}:events', 0, -1)]
        conversations = []
        statuses = Counter()
        speakers = Counter()
        for conversation_id in await redis.zrange(f'{base}:conversations', 0, -1):
            conversation_id = str(UUID(str(conversation_id)))
            key = f'{base}:conversation:{conversation_id}'
            order = await redis.lrange(f'{key}:order', 0, -1)
            raw_messages = await redis.hmget(f'{key}:messages', order) if order else []
            messages = [json.loads(raw) for raw in raw_messages if raw is not None]
            for message in messages:
                speakers[message['sender_id']] += 1
                if message['sender_id'] != 'player':
                    statuses[message.get('generation_status', 'unknown')] += 1
            conversations.append({'conversation_id': conversation_id, 'messages': messages})
        return {
            'available': True,
            'sampled_at': datetime.now(UTC).isoformat(),
            'game_status_at_sampling': game['status'],
            'coverage': 'recorded_server_calls_at_sampling_time',
            'usage': usage.model_dump(mode='json'),
            'message_counts_by_speaker': dict(speakers),
            'npc_generation_status_counts': dict(statuses),
            'event_counts': dict(Counter(event['type'] for event in events)),
            'events': events,
            'conversations': conversations,
            'ongoing_game': game['status'] == 'active',
        }
    finally:
        if owned:
            await redis.aclose()
