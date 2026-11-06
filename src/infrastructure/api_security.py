"""Bounded per-process admission control; never inspect narrative text as code."""

import asyncio
import ipaddress
import time
from dataclasses import dataclass, field
from urllib.parse import unquote

from starlette.responses import JSONResponse


@dataclass
class Client:
    seen: float
    buckets: dict = field(default_factory=dict)
    strikes: int = 0
    blocked_until: float = 0


class ApiSecurityMiddleware:
    def __init__(self, app, trusted_proxies="", clock=time.monotonic,
                 max_clients=10000, body_limit=16384):
        self.app, self.clock = app, clock
        self.max_clients, self.body_limit = max_clients, body_limit
        self.clients = {}
        self.trusted = [ipaddress.ip_network(x.strip()) for x in trusted_proxies.split(',') if x.strip()]

    def identity(self, scope):
        peer = (scope.get('client') or ('unknown', 0))[0]
        try:
            if any(ipaddress.ip_address(peer) in network for network in self.trusted):
                values = [v for k, v in scope['headers'] if k.lower() == b'x-forwarded-for']
                if len(values) == 1:
                    return str(ipaddress.ip_address(values[0].decode('ascii')))
        except (ValueError, UnicodeError):
            pass
        return peer

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def reject(status, code, retry=None):
            headers = {'Retry-After': str(retry)} if retry else {}
            await JSONResponse({'detail': 'Requisição bloqueada pela proteção da API.', 'code': code},
                               status_code=status, headers=headers)(scope, receive, send)

        now = self.clock()
        # Bounded memory, including under scans from many different addresses.
        if len(self.clients) >= self.max_clients:
            self.clients = {k: v for k, v in self.clients.items()
                            if now - v.seen < 600 or v.blocked_until > now}
        key = self.identity(scope)
        client = self.clients.get(key)
        if client is None:
            if len(self.clients) >= self.max_clients:
                return await reject(503, 'security_capacity', 60)
            client = self.clients[key] = Client(now)
        client.seen = now
        if client.blocked_until > now:
            return await reject(429, 'client_temporarily_blocked', max(1, int(client.blocked_until-now)+1))

        async def strike(status, code):
            client.strikes += 1
            if client.strikes >= 3:
                client.blocked_until = now + 600
                client.strikes = 0
            return await reject(status, code)

        path = scope['path'].lower()
        for _ in range(3):
            path = unquote(path)
        parts = path.replace('\\', '/').split('/')
        if any(p in ('.git', '.env', '..', 'wp-admin', 'wp-login.php') for p in parts):
            return await strike(403, 'malicious_path')

        # Movement and polling need a higher budget than expensive LLM calls.
        policies = [('all', 40, 20)]
        if scope['method'] == 'POST' and path.rstrip('/') == '/api/v1/games':
            policies.append(('creation', 6, .1))
        if scope['method'] == 'POST' and path.endswith('/messages'):
            policies.append(('dialogue', 5, .5))
        for name, capacity, refill in policies:
            tokens, previous = client.buckets.get(name, (capacity, now))
            tokens = min(capacity, tokens + (now-previous)*refill)
            if tokens < 1:
                return await reject(429, 'rate_limited', max(1, int((1-tokens)/refill)+1))
            client.buckets[name] = (tokens-1, now)

        chunks, size = [], 0
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    size += len(message.get('body', b''))
                    if size > self.body_limit:
                        return await strike(413, 'body_too_large')
                    chunks.append(message)
                    if not message.get('more_body', False):
                        break
        except TimeoutError:
            return await strike(408, 'body_timeout')

        async def buffered_receive():
            if chunks:
                return chunks.pop(0)
            return await receive()

        await self.app(scope, buffered_receive, send)
