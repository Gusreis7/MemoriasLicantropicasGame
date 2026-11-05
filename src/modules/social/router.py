from uuid import UUID

from fastapi import APIRouter, Request

from src.modules.social.views import HeardReports

router = APIRouter(prefix="/api/v1/games", tags=["convivência"])


@router.get("/{game_id}/social/reports", response_model=HeardReports)
async def reports(game_id: UUID, request: Request):
    services = request.app.state.services
    if services.social_reads is None:
        # Serviços antigos/test doubles continuam suportados sem dados sociais.
        await services.games.get(game_id)
        return HeardReports()
    return await services.social_reads.reports(game_id)
