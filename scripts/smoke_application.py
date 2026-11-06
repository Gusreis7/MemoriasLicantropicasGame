"""Three deployment checks: syntax, application startup and public/admin routes.

Run in the runtime image with SOCIAL_ENABLED=false and API_DOCS_ENABLED=false.
No game sessions, Redis requests or model calls are needed.
"""
import asyncio
from pathlib import Path

import httpx

from src.main import create_app


async def main():
    for path in (Path(__file__).resolve().parents[1] / 'src').rglob('*.py'):
        compile(path.read_bytes(), str(path), 'exec')
    print('OK: Python syntax (no bytecode writes)')
    app = create_app()
    async with app.router.lifespan_context(app):
        # No background polling of Redis during this offline deployment check.
        if app.state.services.social_worker is not None:
            await app.state.services.social_worker.stop()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://localhost') as client:
            health = await client.get('/health')
            assert health.status_code == 200 and health.json()['status'] == 'ok'
            catalog = await client.get('/api/v1/characters')
            assert catalog.status_code == 200 and len(catalog.json()) == 7
            print('OK: startup, health and character catalog')
            assert (await client.get('/admin/api/v1/auth/session')).status_code == 401
            assert (await client.get('/docs')).status_code == 404
            print('OK: admin requires authentication and production docs are disabled')


if __name__ == '__main__':
    asyncio.run(main())
