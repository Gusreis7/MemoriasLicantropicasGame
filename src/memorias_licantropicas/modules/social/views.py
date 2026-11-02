"""Relatos que o detetive ouviu, sem expor encontros privados dos NPCs."""

from uuid import UUID

from pydantic import AwareDatetime

from memorias_licantropicas.contracts.errors import ConflictError, NotFoundError, StorageUnavailableError
from memorias_licantropicas.contracts.model import Contract
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.modules.conversations.service import public_message


class HeardReport(Contract):
    id: UUID
    speaker_id: str
    speaker_name: str
    content: str
    created_at: AwareDatetime
    source_name: str | None = None


class HeardReports(Contract):
    reports: tuple[HeardReport, ...] = ()


class SocialReadService:
    def __init__(self, repository, games, characters):
        self._repository = repository
        self._games = games
        self._characters = characters

    async def reports(self, game_id: UUID) -> HeardReports:
        game = await self._games.get(game_id)
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        if game.content_version != self._characters.content_version:
            raise ConflictError("A partida usa uma versão anterior de personagens.")
        cast = {member.character_id: member for member in game.characters}
        reports = []
        for record in await self._repository.recent_exchanges(game_id, 100):
            member = cast.get(record.npc_id)
            profile = await self._characters.get(record.npc_id)
            if member is None or profile is None or record.incoming.sender_id != "player" or record.outgoing.sender_id != record.npc_id:
                raise StorageUnavailableError("Registro de diálogo inconsistente.")
            message = public_message(record.outgoing, HarnessService._private_markers(profile, member))
            reports.append(HeardReport(id=message.id, speaker_id=record.npc_id,
                speaker_name=profile.name, content=message.content, created_at=message.created_at))
        return HeardReports(reports=tuple(reports))
