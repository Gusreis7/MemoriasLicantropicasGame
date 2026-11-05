from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from memorias_licantropicas.contracts.errors import ConflictError, NotFoundError
from memorias_licantropicas.contracts.model import GameCharacter, GameState
from memorias_licantropicas.modules.games.service import GameService
from memorias_licantropicas.modules.characters.catalog import supports_content_version

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("winner", ["bentinho", "capitu", "escobar", "rubiao", "virgilia", "florenca", "bacamarte"])
async def test_every_suspect_can_be_drawn(catalog, storage, monkeypatch, winner):
    monkeypatch.setattr("memorias_licantropicas.modules.games.service.choice",
                        lambda profiles: next(profile for profile in profiles if profile.id == winner))
    public = await GameService(catalog, storage.games).create()
    game = await storage.games.get(public.id)
    assert len(game.characters) == 7
    assert [npc.character_id for npc in game.characters if npc.role == "werewolf"] == [winner]
    assert all(npc.alive for npc in game.characters)
    assert game.created_at.utcoffset().total_seconds() == 0


async def test_empty_cast_and_id_conflict_are_rejected(catalog):
    empty = AsyncMock()
    empty.list.return_value = ()
    games = AsyncMock()
    with pytest.raises(ConflictError):
        await GameService(empty, games).create()
    games.create.assert_not_awaited()
    games.create.return_value = False
    with pytest.raises(ConflictError):
        await GameService(catalog, games).create()


async def test_missing_game_raises_domain_error(catalog, storage):
    with pytest.raises(NotFoundError):
        await GameService(catalog, storage.games).get(uuid4())


async def test_catalog_v3_reads_existing_v2_game_without_rewriting_it(catalog, storage, game):
    legacy = game.model_copy(update={"id": uuid4(), "content_version": "2"})
    assert await storage.games.create(legacy)
    public = await GameService(catalog, storage.games).get(legacy.id)
    assert public.content_version == "2"
    assert await storage.games.get(legacy.id) == legacy
    assert supports_content_version("2", catalog.content_version)
    assert supports_content_version("3", catalog.content_version)
    assert not supports_content_version("1", catalog.content_version)
    assert not supports_content_version("2", "4")


@pytest.mark.parametrize("roles", [(), ("civil",), ("werewolf", "werewolf")])
async def test_game_requires_exactly_one_werewolf(game, roles):
    with pytest.raises(ValidationError):
        GameState(id=game.id, created_at=game.created_at, characters=tuple(
            GameCharacter(character_id=str(i), role=role) for i, role in enumerate(roles)))


async def test_game_rejects_duplicate_characters(game):
    with pytest.raises(ValidationError):
        GameState(id=game.id, created_at=game.created_at, characters=(
            GameCharacter(character_id="capitu", role="werewolf"),
            GameCharacter(character_id="capitu", role="civil")))
