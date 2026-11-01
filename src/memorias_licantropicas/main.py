"""Ponto de entrada da API do jogo."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from memorias_licantropicas.composition import build_services
from memorias_licantropicas.contracts.errors import (
    AccessDeniedError,
    ConflictError,
    LLMUnavailableError,
    NotFoundError,
    StorageUnavailableError,
)
from memorias_licantropicas.modules.characters.router import (
    get_character_service,
    router as character_router,
)
from memorias_licantropicas.modules.games.router import (
    get_game_service,
    router as game_router,
)
from memorias_licantropicas.modules.characters.service import CharacterService
from memorias_licantropicas.modules.games.service import GameService
from memorias_licantropicas.modules.conversations.router import router as conversation_router, approach_router
from memorias_licantropicas.modules.world.router import router as world_router
from memorias_licantropicas.modules.admin.router import router as admin_router
from memorias_licantropicas.modules.investigation.router import router as investigation_router
from memorias_licantropicas.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    services = build_services(Settings())
    app.state.services = services
    try:
        yield
    finally:
        await services.aclose()


def character_service_dependency(request: Request) -> CharacterService:
    return request.app.state.services.characters


def game_service_dependency(request: Request) -> GameService:
    return request.app.state.services.games


def create_app() -> FastAPI:
    application = FastAPI(
        title="Memórias Licantropicas",
        description="API de um jogo de investigação e dedução social.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.dependency_overrides[get_character_service] = character_service_dependency
    application.dependency_overrides[get_game_service] = game_service_dependency
    application.include_router(character_router)
    application.include_router(game_router)
    application.include_router(conversation_router)
    application.include_router(approach_router)
    application.include_router(world_router)
    application.include_router(admin_router)
    application.include_router(investigation_router)

    async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
        errors = {
            NotFoundError: (404, "Recurso não encontrado."),
            AccessDeniedError: (403, "Acesso não permitido."),
            ConflictError: (409, "Conflito com o estado atual."),
            StorageUnavailableError: (503, "Persistência temporariamente indisponível."),
            LLMUnavailableError: (503, "Serviço de diálogo temporariamente indisponível."),
        }
        status_code, detail = errors[type(exc)]
        return JSONResponse(status_code=status_code, content={"detail": detail})

    for error_type in (
        NotFoundError, AccessDeniedError, ConflictError,
        StorageUnavailableError, LLMUnavailableError,
    ):
        application.add_exception_handler(error_type, domain_error_handler)

    application.add_api_route("/", index, methods=["GET"])
    application.add_api_route("/health", health, methods=["GET"])
    return application


def index() -> dict[str, str]:
    return {"name": "Memórias Licantropicas", "docs": "/docs"}


def health() -> dict[str, str]:
    return {"status": "ok"}


app = create_app()
