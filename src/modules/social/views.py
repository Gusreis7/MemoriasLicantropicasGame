"""Relatos que o detetive ouviu, sem expor encontros privados dos NPCs."""

from uuid import UUID

from pydantic import AwareDatetime

from src.contracts.errors import ConflictError, NotFoundError, StorageUnavailableError
from src.contracts.model import Contract
from src.modules.agents.service import HarnessService
from src.modules.conversations.service import public_message
from src.modules.characters.catalog import supports_content_version


class HeardReport(Contract):
    useful: bool = False
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
        if not supports_content_version(game.content_version, self._characters.content_version):
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
                speaker_name=profile.name, content=message.content, created_at=message.created_at, useful=message.useful))
        return HeardReports(reports=tuple(reports))
