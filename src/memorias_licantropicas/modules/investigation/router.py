from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from memorias_licantropicas.modules.investigation.schema import (
    AccusationReviewPublic, AssemblyOpenRequest, AssemblyResolveRequest, AssemblyRequest, AccuseRequest, CasePublic, PresentRequest, SearchRequest, InterrogateRequest, ConfrontRequest,
)
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


@router.post("/accusations/review", response_model=AccusationReviewPublic)
async def review(game_id: UUID, body: AccuseRequest, service: Service):
    return await service.review_accusation(game_id, body.suspect_id, body.evidence_ids, body.testimony_ids)


@router.post("/accusations", response_model=CasePublic)
async def accuse(game_id: UUID, body: AccuseRequest, service: Service):
    return await service.accuse(game_id, body.suspect_id, body.evidence_ids, body.testimony_ids)


@router.post("/interrogations", response_model=CasePublic)
async def interrogate(game_id: UUID, body: InterrogateRequest, service: Service):
    return await service.interrogate(game_id, body.npc_id, body.day, body.period)


@router.post("/confrontations", response_model=CasePublic)
async def confront(game_id: UUID, body: ConfrontRequest, service: Service):
    return await service.confront(game_id, body.npc_id, body.evidence_ids, body.testimony_ids,
                                 body.interrogation_ids)


@router.post("/assembly", response_model=CasePublic)
async def assembly(game_id: UUID, body: AssemblyRequest, service: Service):
    return await service.assemble(game_id, body.suspect_id, body.evidence_ids, body.testimony_ids)


@router.post("/assembly/open", response_model=CasePublic)
async def open_assembly(game_id: UUID, body: AssemblyOpenRequest, service: Service):
    return await service.open_assembly(game_id, body.suspect_id, body.evidence_ids, body.testimony_ids, body.speech)


@router.post("/assembly/resolve", response_model=CasePublic)
async def resolve_assembly(game_id: UUID, body: AssemblyResolveRequest, service: Service):
    return await service.resolve_assembly(game_id, body.reply)


@router.post("/evidence/{evidence_id}/inspect", response_model=CasePublic)
async def inspect_evidence(game_id: UUID, evidence_id: UUID, body: SearchRequest, service: Service):
    return await service.inspect(game_id, evidence_id)
