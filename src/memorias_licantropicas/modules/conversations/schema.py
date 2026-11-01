from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints


class PublicSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CreateConversation(PublicSchema):
    npc_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class SendMessage(PublicSchema):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


class ConversationPublic(PublicSchema):
    id: UUID
    game_id: UUID
    npc_id: str
    created_at: datetime


class MessagePublic(PublicSchema):
    id: UUID
    speaker: Literal["player", "npc"]
    content: str
    created_at: datetime


class ConversationHistory(PublicSchema):
    conversation_id: UUID
    messages: tuple[MessagePublic, ...]


class MessageReply(PublicSchema):
    conversation_id: UUID
    message: MessagePublic
