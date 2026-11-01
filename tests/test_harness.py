from uuid import uuid4

import pytest

from memorias_licantropicas.contracts.errors import AccessDeniedError, ConflictError, LLMUnavailableError
from memorias_licantropicas.contracts.model import GameCharacter, GameState

pytestmark = pytest.mark.anyio


async def test_dialogue_persists_pair_and_remembers_own_conversation(harness, storage, game, llm):
    await storage.games.create(game)
    conversation_id = uuid4()
    reply = await harness.respond(game.id, "bentinho", conversation_id, "player", "Onde estava?")
    history = await storage.memory.list_messages(game.id, conversation_id, "bentinho")
    assert [message.sender_id for message in history] == ["player", "bentinho"]
    assert history[0].content == "Onde estava?"
    assert history[1] == reply.message
    assert reply.model == "stub"
    await harness.respond(game.id, "bentinho", conversation_id, "player", "Tem certeza?")
    assert any("Onde estava?" in message.content for message in llm.calls[-1])


async def test_inference_failure_does_not_save_partial_exchange(harness, storage, game, llm):
    await storage.games.create(game)
    llm.error = LLMUnavailableError("Indisponível")
    conversation_id = uuid4()
    with pytest.raises(LLMUnavailableError):
        await harness.respond(game.id, "bentinho", conversation_id, "player", "Bom dia")
    assert await storage.memory.list_messages(game.id, conversation_id, "player") == ()


async def test_private_context_does_not_include_other_npc_secrets(harness, storage, game, llm, catalog):
    await storage.games.create(game)
    await harness.respond(game.id, "bentinho", uuid4(), "player", "Bom dia")
    system = llm.calls[0][0].content
    assert (await catalog.get("bentinho")).werewolf_objective in system
    assert (await catalog.get("capitu")).werewolf_objective not in system
    assert (await catalog.get("escobar")).bio not in system


@pytest.mark.parametrize("role", ["civil", "werewolf"])
async def test_bacamarte_denial_does_not_receive_secret_role(harness, storage, game, llm, catalog, role):
    cast = (GameCharacter(character_id="bacamarte", role=role),
            GameCharacter(character_id="capitu", role="civil" if role == "werewolf" else "werewolf"))
    state = GameState(id=game.id, created_at=game.created_at, characters=cast, content_version=game.content_version)
    await storage.games.create(state)
    await harness.respond(state.id, "bacamarte", uuid4(), "player", "O que pensa dos crimes?")
    prompt = llm.calls[0][0].content
    assert (await catalog.get("bacamarte")).werewolf_objective not in prompt
    assert '"condicao_conhecida": "Você é o lobisomem' not in prompt


async def test_conversation_cannot_be_rebound_to_another_npc(harness, storage, game, conversation, llm):
    with pytest.raises(AccessDeniedError):
        await harness.respond(game.id, "capitu", conversation.id, "player", "Bom dia")
    assert llm.calls == []


async def test_npc_can_address_another_npc(harness, storage, game, llm):
    await storage.games.create(game)
    conversation_id = uuid4()
    await harness.respond(game.id, "bentinho", conversation_id, "capitu", "Precisamos conversar")
    history = await storage.memory.list_messages(game.id, conversation_id, "capitu")
    assert [message.sender_id for message in history] == ["capitu", "bentinho"]
    with pytest.raises(AccessDeniedError):
        await storage.memory.list_messages(game.id, conversation_id, "player")


@pytest.mark.parametrize("text", ["", "   ", "x" * 8001])
async def test_invalid_text_never_calls_model(harness, game, llm, text):
    with pytest.raises(ConflictError):
        await harness.respond(game.id, "bentinho", uuid4(), "player", text)
    assert llm.calls == []
