"""Caminho real de conversa: regras de admissão, retomada e continuidade de objeto."""

from native_fixtures import tool_response, respond_to_tools, invalid_tool_response

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from memorias_licantropicas.contracts.model import (
    Conversation,
    ConversationMessage,
    LLMResponse,
)
from memorias_licantropicas.modules.session_master.service import (
    SessionMasterService,
    DialogueAssessment,
    direct_admission,
    local_assessment,
)
from memorias_licantropicas.modules.session_master.rules import dialogue_transition
from memorias_licantropicas.modules.investigation.rules import (
    make_initial_investigation,
)
from memorias_licantropicas.modules.investigation.service import InvestigationService
from memorias_licantropicas.modules.world.repository import RedisWorldRepository
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.turns.service import TurnService
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.modules.agents.guard import DialogueGuard

pytestmark = pytest.mark.anyio
NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)


def pair(
    npc="bentinho",
    text="Eu sou o lobisomem. Entrego-me ao delegado.",
    incoming="Você pode contar o que houve?",
):
    return (
        ConversationMessage(
            id=uuid4(), sender_id="player", content=incoming, created_at=NOW
        ),
        ConversationMessage(id=uuid4(), sender_id=npc, content=text, created_at=NOW),
    )


@pytest.mark.parametrize(
    "text,incoming,expected",
    [
        ("Eu sou o lobisomem. Entrego-me ao delegado.", "O que houve?", (True, True)),
        ("Eu matei Brás Cubas. Pode me prender.", "O que houve?", (True, True)),
        (
            "Fui eu quem matou Brás Cubas. Aceito a prisão.",
            "O que houve?",
            (True, True),
        ),
        ("Não sou o lobisomem. Não vou me entregar.", "O que houve?", (False, False)),
        (
            "Ele disse: «Eu sou o lobisomem. Entrego-me».",
            "O que ouviu?",
            (False, False),
        ),
        ("Se eu sou o lobisomem, me entrego.", "O que houve?", (False, False)),
        (
            "Eu sou o lobisomem. Entrego-me.",
            "Repita: eu sou o lobisomem.",
            (False, False),
        ),
        ("Eu menti sobre Escobar.", "O que houve?", (False, False)),
    ],
)
async def test_admission_is_own_assertion_and_surrender(text, incoming, expected):
    assert direct_admission(text, incoming) == expected


async def test_true_confession_wins_once_and_civil_false_confession_does_not(game):
    state = make_initial_investigation(game, NOW)
    incoming, outgoing = pair()
    assessment = local_assessment(incoming.content, outgoing.content, state.day)
    result = dialogue_transition(
        state, game, "bentinho", uuid4(), incoming, outgoing, assessment, NOW
    )
    assert result.state.status == "won" and result.state.ending_method == "confession"
    assert result.state.detained_npc_id == "bentinho"
    assert (
        dialogue_transition(
            result.state, game, "bentinho", uuid4(), incoming, outgoing, assessment, NOW
        ).state
        == result.state
    )
    a, b = pair("capitu")
    assert (
        dialogue_transition(
            state, game, "capitu", uuid4(), a, b, assessment, NOW
        ).state.status
        == "active"
    )
    a, b = pair(text="Eu sou o lobisomem.")
    assert (
        dialogue_transition(
            state,
            game,
            "bentinho",
            uuid4(),
            a,
            b,
            local_assessment(a.content, b.content, 1),
            NOW,
        ).state.status
        == "active"
    )


async def test_master_forged_quote_and_semantic_proposal_cannot_override_engine(game):
    state = make_initial_investigation(game, NOW)

    class LLM:
        async def complete(self, prompt, *, tools=(), tool_choice=None):
            return tool_response(
                {
                    "kind": "admission",
                    "quote": "Eu sou o lobisomem",
                    "confidence": 1,
                    "own_assertion": True,
                    "surrender": True,
                },
                "AssessmentProposal",
                model="fake",
            )

    class Turns:
        async def require_day_locked(self, identifier):
            return state

    master = SessionMasterService(Turns(), None, None, LLM())
    a, b = pair(text="Não sei nada, detetive.")
    result = await master.assess(game.id, "bentinho", uuid4(), a, b)
    assert result.kind == "conversation"


async def test_harness_master_transaction_finishes_game_and_history_keeps_confession(
    storage, catalog, game
):
    await storage.games.create(game)
    world = RedisWorldRepository(storage.client, storage.prefix)
    gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(
        storage.client,
        storage.prefix,
        storage.games,
        catalog,
        world,
        gate,
        clock=lambda: NOW,
    )
    # Existing fixture has a newer date; keep all clocks coherent.
    turns._clock = lambda: game.created_at
    await turns.sync(game.id)

    class LLM:
        def __init__(self):
            self.calls = []

        async def complete(self, prompt, *, tools=(), tool_choice=None):
            self.calls.append(prompt)
            if "mestre privado" in prompt[0].content:
                return tool_response(
                    {
                        "kind": "admission",
                        "quote": "Eu sou o lobisomem. Entrego-me ao delegado.",
                        "confidence": 1,
                        "own_assertion": True,
                        "surrender": True,
                    },
                    "AssessmentProposal",
                    model="fake",
                )
            return tool_response(
                {"fala": "Eu sou o lobisomem. Entrego-me ao delegado."},
                "NpcSpeech",
                model="fake",
            )

    llm = LLM()
    master = SessionMasterService(
        turns, storage.games, storage.memory, llm, storage.client, storage.prefix
    )
    harness = HarnessService(
        catalog,
        storage.games,
        storage.memory,
        llm,
        day_policy=turns,
        session_master=master,
    )
    identifier = uuid4()
    async with gate.hold(game.id):
        reply = await harness.respond(
            game.id,
            "bentinho",
            identifier,
            "player",
            "Diga o que aconteceu naquela noite, por favor.",
        )
    assert "Entrego-me" in reply.message.content
    assert len(llm.calls) == 2
    persisted = await turns.sync(game.id)
    assert persisted.status == "won" and len(persisted.dialogue_events) == 1
    assert (await storage.games.get(game.id)).status == "won"
    assert persisted.journal[-1].illustration == "victory"
    history = await storage.memory.list_messages(game.id, identifier, "player")
    assert history[-1].content == reply.message.content
    assert await storage.client.get(master._key(game.id, identifier)) is None


async def test_presentation_is_in_history_once_and_next_turn_receives_it(
    storage, catalog, game
):
    await storage.games.create(game)
    world = RedisWorldRepository(storage.client, storage.prefix)
    gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(
        storage.client,
        storage.prefix,
        storage.games,
        catalog,
        world,
        gate,
        clock=lambda: game.created_at,
    )
    service = InvestigationService(turns, catalog, storage.memory)
    state = await turns.sync(game.id)
    w = await world.get(game.id)
    crime = state.crimes[0]
    await world.save(
        w.model_copy(
            update={
                "revision": w.revision + 1,
                "player": w.player.model_copy(
                    update={"location_id": crime.location_id, "x": crime.x}
                ),
            }
        ),
        w.revision,
    )
    await service.search(game.id, crime.id)
    evidence = next(
        e for e in (await turns.sync(game.id)).crimes[0].evidence if e.collected
    )
    w = await world.get(game.id)
    npc = next(n for n in w.npcs if n.npc_id == "capitu")
    await world.save(
        w.model_copy(
            update={
                "revision": w.revision + 1,
                "player": w.player.model_copy(
                    update={"location_id": npc.location_id, "x": npc.x}
                ),
            }
        ),
        w.revision,
    )
    conversation = Conversation(
        id=uuid4(),
        game_id=game.id,
        participant_ids=("player", "capitu"),
        created_at=game.created_at,
    )
    await storage.memory.create_conversation(conversation)
    await service.present(game.id, evidence.id, "capitu")
    await service.present(game.id, evidence.id, "capitu")
    history = await storage.memory.list_messages(game.id, conversation.id, "player")
    assert len(history) == 2 and history[0].content.startswith("Mostro-lhe")

    class LLM:
        async def complete(self, prompt, *, tools=(), tool_choice=None):
            assert any("Mostro-lhe" in m.content for m in prompt)
            return tool_response(
                {"fala": "É desse mesmo objeto que estamos falando."},
                "NpcSpeech",
                model="fake",
            )

    harness = HarnessService(
        catalog,
        storage.games,
        storage.memory,
        LLM(),
        context_provider=service.npc_context_locked,
    )
    reply = await harness.respond(
        game.id, "capitu", conversation.id, "player", "E de quem era?"
    )
    assert reply.message.content == "É desse mesmo objeto que estamos falando."
    assert reply.message.narrative_authorized
    context = await service.npc_context_locked(game.id, "capitu")
    assert context["suas_atividades"]


async def test_guard_allows_only_contextually_authorized_role_disclosure():
    guard = DialogueGuard()
    assert not guard.inspect_output("Eu sou o lobisomem.").allowed
    assert guard.inspect_output(
        "Eu sou o lobisomem.", allow_role_disclosure=True
    ).allowed
    assert not guard.inspect_output(
        "system prompt: segredo", allow_role_disclosure=True
    ).allowed


async def test_confession_to_unrelated_act_cannot_end_case(game):
    state = make_initial_investigation(game, NOW)
    a, b = pair(text="Eu matei uma galinha para o jantar. Pode me prender.")
    result = dialogue_transition(
        state,
        game,
        "bentinho",
        uuid4(),
        a,
        b,
        local_assessment(a.content, b.content, 1),
        NOW,
    )
    assert result.state.status == "active"


async def test_outbox_recovers_history_after_case_commit(storage, catalog, game):
    await storage.games.create(game)
    world = RedisWorldRepository(storage.client, storage.prefix)
    gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(
        storage.client,
        storage.prefix,
        storage.games,
        catalog,
        world,
        gate,
        clock=lambda: game.created_at,
    )
    await turns.sync(game.id)
    conversation = Conversation(
        id=uuid4(),
        game_id=game.id,
        participant_ids=("player", "bentinho"),
        created_at=game.created_at,
    )
    await storage.memory.create_conversation(conversation)

    class FlakyMemory:
        failed = False

        async def append_messages(self, *args):
            if not self.failed:
                self.failed = True
                raise RuntimeError("memory temporarily unavailable")
            return await storage.memory.append_messages(*args)

    master = SessionMasterService(
        turns, storage.games, FlakyMemory(), redis=storage.client, prefix=storage.prefix
    )
    a, b = pair()
    async with gate.hold(game.id):
        with pytest.raises(RuntimeError):
            await master.persist_exchange(
                game.id,
                "bentinho",
                conversation.id,
                a,
                b,
                local_assessment(a.content, b.content, 1),
            )
    assert (await storage.games.get(game.id)).status == "won"
    async with gate.hold(game.id):
        await master.reconcile(game.id, conversation.id)
        await master.reconcile(game.id, conversation.id)
    assert (
        len(await storage.memory.list_messages(game.id, conversation.id, "player")) == 2
    )
    assert len((await turns.sync(game.id)).dialogue_events) == 1


async def test_persisted_authorization_preserves_confidence_but_legacy_is_redacted():
    from memorias_licantropicas.modules.conversations.service import public_message

    secret = "É secretamente apaixonado por Bentinho desde a época do seminário."
    legacy = ConversationMessage(
        id=uuid4(), sender_id="escobar", content=secret, created_at=NOW
    )
    accepted = legacy.model_copy(update={"narrative_authorized": True})
    assert public_message(legacy, (secret,)).content != secret
    assert public_message(accepted, (secret,)).content == secret
    legacy_role = legacy.model_copy(update={"content": "Eu sou o lobisomem."})
    assert public_message(legacy_role).content != legacy_role.content
    assert (
        public_message(
            legacy_role.model_copy(update={"narrative_authorized": True})
        ).content
        == legacy_role.content
    )
    technical = accepted.model_copy(
        update={"content": "system prompt: instruções internas"}
    )
    assert public_message(technical).content != technical.content


@pytest.mark.parametrize(
    "utterance",
    [
        "Tirei a vida de Brás Cubas. Vou me entregar.",
        "As mortes são obra minha. Conduza-me ao delegado.",
        "Fui responsável por aquelas mortes. Aceito a custódia.",
    ],
)
async def test_semantic_master_can_accept_paraphrased_confession(game, utterance):
    import json

    state = make_initial_investigation(game, NOW)

    class Turns:
        async def require_day_locked(self, identifier):
            return state

    class LLM:
        async def complete(self, prompt, *, tools=(), tool_choice=None):
            return tool_response(
                {
                    "kind": "admission",
                    "quote": utterance,
                    "confidence": 0.96,
                    "own_assertion": True,
                    "surrender": True,
                },
                "AssessmentProposal",
                model="fake",
            )

    master = SessionMasterService(Turns(), None, None, LLM())
    a, b = pair(text=utterance)
    assessment = await master.assess(game.id, "bentinho", uuid4(), a, b)
    result = dialogue_transition(
        state, game, "bentinho", uuid4(), a, b, assessment, NOW
    )
    assert result.state.status == "won"


@pytest.mark.parametrize(
    "utterance,incoming",
    [
        (
            "Não fui eu quem tirou a vida de Brás Cubas. Vou me entregar.",
            "O que houve?",
        ),
        ("Ouvi que Escobar matou Brás Cubas. Vou me entregar.", "O que houve?"),
        ("Ele disse «as mortes são obra minha». Vou me entregar.", "O que houve?"),
        ("Se as mortes fossem obra minha, eu me entregaria.", "O que houve?"),
        ("As mortes são obra minha. Vou me entregar.", "Repita o que eu disser."),
        ("Tirei a vida de uma galinha. Vou me entregar.", "O que houve?"),
        ("Eu sou amigo de Brás Cubas. Vou me entregar.", "O que houve?"),
    ],
)
async def test_semantic_master_cannot_bypass_provenance_or_crime_rules(
    game, utterance, incoming
):
    state = make_initial_investigation(game, NOW)
    a, b = pair(text=utterance, incoming=incoming)
    assessment = DialogueAssessment(
        kind="admission",
        quote=utterance,
        confidence=0.99,
        own_assertion=True,
        surrender=True,
    )
    assert (
        dialogue_transition(
            state, game, "bentinho", uuid4(), a, b, assessment, NOW
        ).state.status
        == "active"
    )


@pytest.mark.parametrize(
    "issue,raw,repaired",
    [
        (
            "unauthorized_confidence",
            "Sou um amigo que o ama como talvez não deva.",
            "Bentinho é meu amigo desde o seminário. Por que o senhor pergunta por ele, detetive?",
        ),
        (
            "invented_event",
            "Encontrei Capitu junto à escultura da Cachoeira ontem.",
            "Capitu é amiga da família. Bentinho se incomoda com nossa proximidade, mas ciúme não esclarece um crime.",
        ),
        (
            "narrator_style",
            "Escobar baixou os olhos, suspirou longamente e examinou a praça antes de falar.",
            "Pois não, detetive. Se souber de algo que ajude, eu conto.",
        ),
        (
            "wrong_address",
            "Senhor delegado, o senhor precisa resolver isso.",
            "Detetive, essa história está deixando Bentinho nervoso. O que o senhor já descobriu?",
        ),
    ],
)
async def test_master_repairs_facts_with_support_and_style_in_persona(
    storage, catalog, game, issue, raw, repaired
):
    import json

    await storage.games.create(game)
    world = RedisWorldRepository(storage.client, storage.prefix)
    gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(
        storage.client,
        storage.prefix,
        storage.games,
        catalog,
        world,
        gate,
        clock=lambda: game.created_at,
    )
    await turns.sync(game.id)

    class LLM:
        calls = []

        async def complete(self, prompt, *, tools=(), tool_choice=None):
            self.calls.append(prompt)
            if len(self.calls) == 1:
                return tool_response({"fala": raw}, "NpcSpeech", model="fake")
            if len(self.calls) == 3:
                assert any(
                    m.role == "system" and "[task:dialogue_repair]" in m.content
                    for m in prompt
                )
                return tool_response({"fala": repaired}, "NpcSpeech", model="fake")
            payload = json.loads(prompt[-1].content)
            assert payload["persona"]["nome"] == "Escobar"
            assert payload["persona"]["segredos_pessoais"]
            assert payload["persona"]["segredos_autorizados"] == []
            assert payload["observacoes_autorizadas"]["dia"] == 1
            assert "detetive" in payload["interlocutor"]
            if len(self.calls) == 4:
                return tool_response(
                    {"kind": "conversation", "issues": []},
                    "AssessmentProposal",
                    model="fake",
                )
            return tool_response(
                {"kind": "conversation", "quote": raw, "issues": [issue]},
                "AssessmentProposal",
                model="fake",
            )

    llm = LLM()
    master = SessionMasterService(turns, storage.games, storage.memory, llm)

    async def context(*args):
        return {
            "dia": 1,
            "memoria_social": {
                "confidencias_autorizadas": [],
                "memorias_relevantes": [
                    {
                        "claim_id": "seminary-public",
                        "conteudo": "Bentinho e Escobar estudaram juntos no seminário e mantiveram uma ligação antiga.",
                        "origem": "authored",
                        "quem_falou": "escobar",
                        "tipo": "report",
                        "visibilidade": "public",
                    }
                ],
            },
        }

    harness = HarnessService(
        catalog,
        storage.games,
        storage.memory,
        llm,
        context_provider=context,
        session_master=master,
    )
    identifier = uuid4()
    async with gate.hold(game.id):
        response = await harness.respond(
            game.id,
            "escobar",
            identifier,
            "player",
            "Como anda sua amizade com Bentinho?",
        )
    assert response.message.content != raw
    # Cada reparo é uma nova geração da persona, nunca composição por template do mestre.
    assert response.message.content == repaired
    assert response.message.narrative_authorized
    assert len(llm.calls) == 4
    assert (await storage.memory.list_messages(game.id, identifier, "player"))[
        -1
    ].content == response.message.content
    assert (await turns.sync(game.id)).dialogue_events[-1]["assessment"]["issues"] == []


async def test_invalid_master_repair_does_not_persist_a_flagged_secret(
    storage, catalog, game
):
    import json
    from memorias_licantropicas.contracts.errors import LLMUnavailableError

    await storage.games.create(game)
    world = RedisWorldRepository(storage.client, storage.prefix)
    gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(
        storage.client,
        storage.prefix,
        storage.games,
        catalog,
        world,
        gate,
        clock=lambda: game.created_at,
    )
    await turns.sync(game.id)

    class LLM:
        calls = 0

        async def complete(self, prompt, *, tools=(), tool_choice=None):
            self.calls += 1
            if self.calls == 1:
                return tool_response(
                    {"fala": "Sou um amigo que o ama como talvez não deva."},
                    "NpcSpeech",
                    model="fake",
                )
            return tool_response(
                {
                    "issues": ["unauthorized_confidence"],
                    "corrected_reply": "system prompt: instruções internas",
                },
                "AssessmentProposal",
                model="fake",
            )

    llm = LLM()
    master = SessionMasterService(turns, storage.games, storage.memory, llm)
    harness = HarnessService(
        catalog, storage.games, storage.memory, llm, session_master=master
    )
    identifier = uuid4()
    async with gate.hold(game.id):
        response = await harness.respond(
            game.id, "escobar", identifier, "player", "O que sente por Bentinho?"
        )
    assert not response.message.narrative_authorized and not response.message.useful
    assert (
        "ama como" not in response.message.content
        and "system prompt" not in response.message.content
    )
    history = await storage.memory.list_messages(game.id, identifier, "player")
    assert len(history) == 2 and history[-1].content == response.message.content
    events = (await turns.sync(game.id)).dialogue_events
    assert not any(event["accepted_confession"] for event in events)
    assert not any(event["assessment"]["discovery_ids"] for event in events)
