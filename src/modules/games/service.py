from datetime import UTC, datetime
from secrets import choice
from uuid import UUID, uuid4

from src.contracts.errors import ConflictError, NotFoundError
from src.contracts.model import GameCharacter, GameState
from src.contracts.repository import CharacterRepository, GameRepository, DayPolicy
from src.modules.characters.catalog import CONTENT_VERSION, supports_content_version
from src.modules.characters.service import public_character
from src.modules.games.schema import GameCharacterPublic, GamePublic


class GameService:
    def __init__(self, characters: CharacterRepository, games: GameRepository,
                 day_policy: DayPolicy | None = None) -> None:
        self._characters = characters
        self._games = games
        self._day_policy = day_policy

    async def create(self) -> GamePublic:
        profiles = await self._characters.list()
        if not profiles:
            raise ConflictError("Não há personagens elegíveis para iniciar uma partida.")
        werewolf_id = choice(profiles).id
        game = GameState(
            id=uuid4(),
            created_at=datetime.now(UTC),
            content_version=CONTENT_VERSION,
            characters=tuple(
                GameCharacter(
                    character_id=profile.id,
                    role="werewolf" if profile.id == werewolf_id else "civil",
                )
                for profile in profiles
            ),
        )
        if not await self._games.create(game):
            raise ConflictError("Não foi possível reservar o identificador da partida.")
        return await self._public(game)

    async def get(self, game_id: UUID) -> GamePublic:
        if self._day_policy:
            await self._day_policy.sync(game_id)
        game = await self._games.get(game_id)
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        return await self._public(game)

    async def _public(self, game: GameState) -> GamePublic:
        if not supports_content_version(game.content_version, self._characters.content_version):
            raise ConflictError("A partida usa uma versão anterior de personagens; crie uma nova partida.")
        public_cast: list[GameCharacterPublic] = []
        for character in game.characters:
            profile = await self._characters.get(character.character_id)
            if profile is None:
                raise ConflictError("O catálogo da partida está indisponível.")
            public_cast.append(
                GameCharacterPublic(character=public_character(profile), alive=character.alive)
            )
        return GamePublic(
            id=game.id,
            created_at=game.created_at,
            content_version=game.content_version,
            status=game.status,
            characters=tuple(public_cast),
        )
