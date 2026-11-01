from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from memorias_licantropicas.modules.investigation.schema import AccuseRequest, CasePublic, PresentRequest, SearchRequest
from memorias_licantropicas.modules.investigation.service import InvestigationService

router = APIRouter(prefix="/api/v1/games/{game_id}", tags=["investigation"])


async def get_investigation_service(request: Request) -> InvestigationService:
    return request.app.state.services.investigation


Service = Annotated[InvestigationService, Depends(get_investigation_service)]


@router.get("/investigation", response_model=CasePublic)
async def get_case(game_id: UUID, service: Service):
    return await service.get(game_id)


@router.post("/crime-scenes/{crime_id}/search", response_model=CasePublic)
async def search(game_id: UUID, crime_id: UUID, body: SearchRequest, service: Service):
    return await service.search(game_id, crime_id)


@router.post("/evidence/{evidence_id}/present", response_model=CasePublic)
async def present(game_id: UUID, evidence_id: UUID, body: PresentRequest, service: Service):
    return await service.present(game_id, evidence_id, body.npc_id)


@router.post("/accusations", response_model=CasePublic)
async def accuse(game_id: UUID, body: AccuseRequest, service: Service):
    return await service.accuse(game_id, body.suspect_id, body.evidence_ids, body.testimony_ids)
