import re
import secrets
from fastapi import APIRouter, Request, Response
from src.modules.telemetry.service import SESSION_SECONDS

router = APIRouter(tags=["telemetry"])
COOKIE = "ml_visit"


@router.post("/api/v1/visits", status_code=204)
async def visit(request: Request):
    token = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32}", token):
        token = secrets.token_urlsafe(24)
    await request.app.state.services.telemetry.record(token)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, path="/api/v1/visits",
                        httponly=True, samesite="strict",
                        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https")
    return response
