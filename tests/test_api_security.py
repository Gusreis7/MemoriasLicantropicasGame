import httpx
import pytest
from starlette.responses import JSONResponse

from src.infrastructure.api_security import ApiSecurityMiddleware

pytestmark = pytest.mark.anyio


async def endpoint(scope, receive, send):
    body = await receive()
    await JSONResponse({'size': len(body.get('body', b''))})(scope, receive, send)


async def test_rate_limit_refills_and_ips_are_isolated():
    now = [0.0]
    app = ApiSecurityMiddleware(endpoint, clock=lambda: now[0])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
        for _ in range(6):
            assert (await client.post('/api/v1/games')).status_code == 200
        response = await client.post('/api/v1/games', headers={'X-Forwarded-For': '8.8.8.8'})
        assert response.status_code == 429  # untrusted headers cannot evade the budget
        assert int(response.headers['Retry-After']) > 0
        now[0] = 11
        assert (await client.post('/api/v1/games')).status_code == 200
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app, client=('10.0.0.2', 42)), base_url='http://test') as other:
        assert (await other.post('/api/v1/games')).status_code == 200


async def test_scans_block_temporarily_and_narrative_text_is_allowed():
    now = [0.0]
    app = ApiSecurityMiddleware(endpoint, clock=lambda: now[0])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
        assert (await client.post('/messages', json={'content': "Você viu .env ou uma ameaça?"})).status_code == 200
        for path in ('/.env', '/.git/config', '/%252eenv'):
            assert (await client.get(path)).status_code == 403
        assert (await client.get('/api/v1/characters')).status_code == 429
        now[0] = 601
        assert (await client.get('/api/v1/characters')).status_code == 200


async def test_streamed_body_limit_and_capacity_are_bounded():
    app = ApiSecurityMiddleware(endpoint, body_limit=8, max_clients=1)
    async def body():
        yield b'12345'
        yield b'67890'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
        assert (await client.post('/messages', content=body())).status_code == 413
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app, client=('10.0.0.2', 42)), base_url='http://test') as other:
        assert (await other.get('/')).status_code == 503


async def test_proxy_trust_requires_explicit_peer_network():
    app = ApiSecurityMiddleware(endpoint, trusted_proxies='172.30.253.0/28')
    scope = {'client': ('172.30.253.3', 42), 'headers': [(b'x-forwarded-for', b'203.0.113.8')]}
    assert app.identity(scope) == '203.0.113.8'
    scope['client'] = ('198.51.100.1', 42)
    assert app.identity(scope) == '198.51.100.1'
