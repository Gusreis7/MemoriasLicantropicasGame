from datetime import UTC, datetime
from hashlib import sha256
from redis.exceptions import RedisError, WatchError
from src.contracts.errors import StorageUnavailableError

SESSION_SECONDS = 1800
ACTIVE_SECONDS = 90


class TelemetryService:
    def __init__(self, client, prefix, clock=None):
        self.client = client
        self.base = f"{prefix}:metrics:{{visits}}"
        self.clock = clock or (lambda: datetime.now(UTC))

    async def record(self, token):
        now = self.clock()
        identifier = sha256(token.encode()).hexdigest()
        session = f"{self.base}:session:{identifier}"
        try:
            for _ in range(5):
                try:
                    async with self.client.pipeline() as pipe:
                        await pipe.watch(session)
                        exists = await pipe.exists(session)
                        pipe.multi()
                        pipe.set(session, "1", ex=SESSION_SECONDS)
                        if not exists:
                            pipe.hincrby(self.base, "total", 1)
                        pipe.hsetnx(self.base, "since", now.isoformat())
                        pipe.zremrangebyscore(f"{self.base}:active", "-inf", now.timestamp() - ACTIVE_SECONDS)
                        pipe.zadd(f"{self.base}:active", {identifier: now.timestamp()})
                        await pipe.execute()
                        return
                except WatchError:
                    continue
        except RedisError:
            pass
        raise StorageUnavailableError("Contagem de visitas indisponível.")

    async def summary(self):
        now = self.clock()
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.hmget(self.base, "total", "since")
            pipe.zcount(f"{self.base}:active", f"({now.timestamp() - ACTIVE_SECONDS}", "+inf")
            (total, since), active = await pipe.execute()
        return {"connections": int(total or 0), "active_connections": active, "connections_since": since}
