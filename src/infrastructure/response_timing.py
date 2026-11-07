"""Expose application response time without recording visitors or request data."""

from time import perf_counter


class ResponseTimingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/"):
            return await self.app(scope, receive, send)
        started = perf_counter()

        async def timed_send(message):
            if message["type"] == "http.response.start":
                duration = (perf_counter() - started) * 1000
                message = {**message, "headers": [*message.get("headers", []),
                    (b"server-timing", f"app;dur={duration:.2f}".encode("ascii"))]}
            await send(message)

        await self.app(scope, receive, timed_send)
