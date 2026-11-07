import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from src.modules.telemetry.router import router
from src.modules.telemetry.service import TelemetryService

pytestmark = pytest.mark.anyio


async def test_visits_are_sessions_not_requests_and_expire_from_active(storage):
    now = [datetime(2026, 11, 7, tzinfo=UTC)]
    service = TelemetryService(storage.client, storage.prefix, clock=lambda: now[0])
    token = str(uuid4())
    await asyncio.gather(*(service.record(token) for _ in range(3)))
    await service.record(str(uuid4()))
    summary = await service.summary()
    assert summary['connections'] == 2 and summary['active_connections'] == 2
    now[0] += timedelta(seconds=91)
    assert (await service.summary())['active_connections'] == 0
    await service.record(token)
    assert (await service.summary())['connections'] == 2
    assert (await service.summary())['active_connections'] == 1
    # Cookie/session expiry represents a new visit, without losing the total.
    from hashlib import sha256
    await storage.client.delete(f'{service.base}:session:{sha256(token.encode()).hexdigest()}')
    await service.record(token)
    assert (await service.summary())['connections'] == 3
    assert (await service.summary())['connections_since'] == summary['connections_since']


async def test_visit_api_uses_private_cookie_and_never_exposes_metrics(storage):
    app = FastAPI()
    service = TelemetryService(storage.client, storage.prefix)
    app.state.services = SimpleNamespace(telemetry=service)
    app.include_router(router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://game.test') as client:
        for _ in range(2):
            response = await client.post('/api/v1/visits')
            assert response.status_code == 204 and response.content == b''
            assert response.headers['cache-control'] == 'no-store'
            assert 'HttpOnly' in response.headers['set-cookie']
            assert 'Secure' in response.headers['set-cookie']
        assert (await service.summary())['connections'] == 1
        assert (await client.get('/api/v1/visits')).status_code == 405
        assert (await client.get('/admin/api/v1/metrics')).status_code == 404
