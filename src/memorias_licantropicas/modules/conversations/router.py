from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from memorias_licantropicas.modules.conversations.schema import (
    ConversationHistory, ConversationPublic, CreateConversation, MessageReply, SendMessage,
)
from memorias_licantropicas.modules.conversations.service import ConversationService

router = APIRouter(prefix="/api/v1/games/{game_id}/conversations", tags=["conversations"])
approach_router = APIRouter(prefix="/api/v1/games/{game_id}", tags=["world"])


async def get_conversation_service(request: Request) -> ConversationService:
    return request.app.state.services.conversations


Service = Annotated[ConversationService, Depends(get_conversation_service)]


@approach_router.post("/approaches", response_model=ConversationPublic)
async def approach(game_id: UUID, body: CreateConversation, service: Service):
    return await service.create(game_id, body.npc_id)


@router.post("", response_model=ConversationPublic, status_code=201)
async def create_conversation(game_id: UUID, body: CreateConversation, service: Service):
    return await service.create(game_id, body.npc_id)


@router.get("/{conversation_id}", response_model=ConversationPublic)
async def get_conversation(game_id: UUID, conversation_id: UUID, service: Service):
    return await service.get(game_id, conversation_id)


@router.post("/{conversation_id}/messages", response_model=MessageReply)
async def send_message(game_id: UUID, conversation_id: UUID, body: SendMessage, service: Service):
    return await service.send(game_id, conversation_id, body.content)


@router.get("/{conversation_id}/messages", response_model=ConversationHistory)
async def get_history(game_id: UUID, conversation_id: UUID, service: Service,
                      limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return await service.history(game_id, conversation_id, limit)
