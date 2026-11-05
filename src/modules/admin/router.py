from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from src.modules.admin.auth import AdminAuth, COOKIE_NAME, COOKIE_PATH
from src.modules.admin.schema import (
    AdminConversation, AdminMessage, AdminState, EventPublic, GameListItem, Interactions,
    LoginRequest, Page, SessionPublic,
)
from src.modules.admin.service import AdminService
from src.contracts.social import SocialState
from src.contracts.usage import UsageSummary


async def no_cache(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/admin/api/v1", tags=["admin"], dependencies=[Depends(no_cache)])


def get_auth(request: Request) -> AdminAuth:
    return request.app.state.services.admin_auth


def get_service(request: Request) -> AdminService:
    return request.app.state.services.admin


async def require_admin(request: Request, auth: Annotated[AdminAuth, Depends(get_auth)]) -> str:
    return await auth.session(request.cookies.get(COOKIE_NAME))


Auth = Annotated[AdminAuth, Depends(get_auth)]
Service = Annotated[AdminService, Depends(get_service)]
User = Annotated[str, Depends(require_admin)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=200)]


@router.post("/auth/login", response_model=SessionPublic)
async def login(body: LoginRequest, request: Request, response: Response, auth: Auth):
    auth.check_origin(request.headers.get("origin"))
    remote_ip = request.client.host if request.client else "unknown"
    token = await auth.login(body.username, body.password.get_secret_value(), remote_ip)
    response.set_cookie(COOKIE_NAME, token, max_age=auth.session_seconds, path=COOKIE_PATH,
                        httponly=True, secure=auth.cookie_secure, samesite="strict")
    return SessionPublic(username=auth.username)


@router.get("/auth/session", response_model=SessionPublic)
async def session(user: User):
    return SessionPublic(username=user)


@router.post("/auth/logout")
async def logout(request: Request, response: Response, auth: Auth, user: User):
    auth.check_origin(request.headers.get("origin"))
    await auth.logout(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, secure=auth.cookie_secure,
                           httponly=True, samesite="strict")
    return {"ok": True}


@router.get("/games", response_model=Page[GameListItem])
async def games(user: User, service: Service, offset: Offset = 0, limit: Limit = 20):
    return await service.list_games(offset, limit)


@router.get("/games/{game_id}/state", response_model=AdminState)
async def state(game_id: UUID, user: User, service: Service):
    return await service.state(game_id)


@router.get("/games/{game_id}/events", response_model=Page[EventPublic])
async def events(game_id: UUID, user: User, service: Service, offset: Offset = 0, limit: Limit = 50):
    return await service.events(game_id, offset, limit)


@router.get("/games/{game_id}/conversations", response_model=Page[AdminConversation])
async def conversations(game_id: UUID, user: User, service: Service, offset: Offset = 0, limit: Limit = 50):
    return await service.conversations(game_id, offset, limit)


@router.get("/games/{game_id}/conversations/{conversation_id}/messages", response_model=Page[AdminMessage])
async def messages(game_id: UUID, conversation_id: UUID, user: User, service: Service,
                   offset: Offset = 0, limit: Limit = 100):
    return await service.messages(game_id, conversation_id, offset, limit)


@router.get("/games/{game_id}/interactions", response_model=Interactions)
async def interactions(game_id: UUID, user: User, service: Service):
    return await service.interactions(game_id)


@router.get("/games/{game_id}/social", response_model=SocialState)
async def social(game_id: UUID, user: User, service: Service):
    return await service.social(game_id)


@router.get("/games/{game_id}/usage", response_model=UsageSummary)
async def usage(game_id: UUID, user: User, service: Service):
    return await service.usage(game_id)


@router.get("/health")
async def health(user: User, service: Service):
    return await service.health()
