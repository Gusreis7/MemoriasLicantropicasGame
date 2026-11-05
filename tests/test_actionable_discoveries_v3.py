"""Relatos úteis preservam fontes; conquistas exigem ouvir a revelação autorizada."""

from native_fixtures import tool_response, respond_to_tools, invalid_tool_response
from datetime import UTC, datetime
from uuid import uuid4
import json
import pytest
from src.contracts.model import ConversationMessage, LLMResponse
from src.contracts.social import Relationship, SocialState
from src.modules.agents.support import (
    dialogue_supports,
    compact_observations,
    dialogue_focus,
)
from src.modules.knowledge.mechanics import can_confide_personal
from src.modules.knowledge.service import KnowledgeService
from src.modules.knowledge.seeds import seed_social_state
from src.modules.achievements.rules import (
    award,
    discoveries_in_reply,
)
from src.modules.session_master.service import (
    DialogueAssessment,
    local_assessment,
)
from src.modules.session_master.rules import dialogue_transition
from src.modules.investigation.rules import (
    make_initial_investigation,
)

pytestmark = pytest.mark.anyio
NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)


def social_observations():
    return {
        "dia": 1,
        "memoria_social": {
            "confidencias_autorizadas": [],
            "descobertas_autorizadas": ["seminary_bond"],
            "memorias_relevantes": [
                {
                    "claim_id": "seminary",
                    "conteudo": "Bentinho e Escobar estudaram juntos no seminário e mantiveram uma ligação antiga.",
                    "origem": "authored",
                    "quem_falou": "escobar",
                    "tipo": "report",
                    "visibilidade": "public",
                    "compartilhavel": True,
                },
                {
                    "claim_id": "love",
                    "conteudo": "O que sinto por Bentinho vai além da amizade.",
                    "origem": "authored",
                    "quem_falou": "escobar",
                    "tipo": "report",
                    "visibilidade": "private",
                    "compartilhavel": False,
                },
            ],
        },
    }


async def test_supports_select_relevant_authorized_facts_without_private_leak(catalog):
    profile = await catalog.get("escobar")
    supports = dialogue_supports(
        profile, social_observations(), "Você e Bentinho estudaram juntos?"
    )
    assert len(supports) == 1 and supports[0]["id"] == "seminary"
    compact = compact_observations(
        profile, social_observations(), "Como foi o seminário?"
    )
    assert compact["apoios_de_conversa"][0]["statement"] == supports[0]["statement"]
    assert "sinto" not in compact["apoios_de_conversa"][0]["statement"]


async def test_compact_context_excludes_irrelevant_inventory_and_repeated_rules(
    catalog, harness, game
):
    profile = await catalog.get("escobar")
    obs = social_observations()
    obs["proprios_apetrechos"] = [{"nome": "Objeto sem relação"}] * 100
    compact = compact_observations(profile, obs, "Fale do seminário.")
    assert (
        "proprios_apetrechos" not in compact and len(compact["apoios_de_conversa"]) == 1
    )
    prompt = harness._context(
        profile, game.characters[-1], "player", (), "Fale do seminário.", compact
    )[0].content
    assert len(prompt.split("Ficha privada:")[0].split()) < 330
    assert "omitir_quando" not in prompt and "Pessoa sem relação" not in prompt


async def test_relational_impulse_survives_compaction_and_allows_subjective_accusation(
    catalog,
):
    profile = await catalog.get("bentinho")
    observations = {
        "memoria_social": {
            "impulsos_relacionais": [
                {
                    "alvo_id": "escobar",
                    "alvo": "Escobar",
                    "tipo": "suspeitar_e_acusar",
                    "motivo_emocional": "ódio e ciúme",
                }
            ]
        }
    }
    compact = compact_observations(profile, observations, "Quem matou Brás Cubas?")
    assert compact["memoria_social"]["impulsos_relacionais"][0]["alvo_id"] == "escobar"
    focus = dialogue_focus("Quem matou Brás Cubas?", compact)
    assert "não precisa ser neutro" in focus
    assert "opinião" in focus


async def test_enigmatic_generation_is_repaired_by_persona_without_template_replacement(
    harness, storage, game, llm
):
    await storage.games.create(game)

    async def context(*args):
        return social_observations()

    harness._context_provider = context
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    async def persist(game_id, npc_id, conversation_id, incoming, outgoing, assessment):
        await storage.memory.append_messages(
            game_id, conversation_id, (incoming, outgoing)
        )

    harness._session_master = SimpleNamespace(
        reconcile=AsyncMock(),
        assess=AsyncMock(
            side_effect=[
                DialogueAssessment(issues=("off_topic",)),
                DialogueAssessment(),
            ]
        ),
        can_disclose_role=AsyncMock(return_value=False),
        persist_exchange=persist,
    )
    replies = iter(
        (
            "As sombras do coração são um espelho que nunca responde.",
            "Bentinho e eu estudamos no seminário; a amizade vem daquele tempo, Floriano.",
        )
    )

    async def complete(prompt, *, tools=(), tool_choice=None):
        llm.calls.append(prompt)
        return tool_response({"fala": next(replies)}, "NpcSpeech", model="fake")

    llm.complete = complete
    reply = await harness.respond(
        game.id,
        "escobar",
        uuid4(),
        "player",
        "Pode me contar o que sabe da amizade com Bentinho?",
    )
    assert (
        "seminário" in reply.message.content and "Pergunte" not in reply.message.content
    )
    assert len(llm.calls) == 2 and "sombras" not in reply.message.content
    assert any("[task:dialogue_repair]" in message.content for message in llm.calls[-1])


async def test_personal_confidence_needs_repeated_meaningful_relationship_gain():
    neutral = Relationship(actor_id="capitu", target_id="player")
    one_help = neutral.model_copy(update={"trust": 5, "affinity": 3})
    earned = neutral.model_copy(update={"trust": 10, "affinity": 6})
    assert not can_confide_personal("capitu", neutral)
    assert not can_confide_personal("capitu", one_help)
    assert can_confide_personal("capitu", earned)
    assert not can_confide_personal("escobar", earned)
    assert can_confide_personal(
        "escobar", earned.model_copy(update={"trust": 20, "affinity": 12})
    )
    assert not can_confide_personal(
        "capitu", earned.model_copy(update={"resentment": 20})
    )


async def test_treatment_is_public_in_fresh_topics_and_initialized_once(catalog):
    profiles = await catalog.list()
    state = seed_social_state(SocialState(game_id=uuid4()), tuple(p.id for p in profiles), NOW)
    treatment = [entry for entry in state.knowledge if "acompanhamento" in entry.proposition]
    assert treatment and all(entry.visibility == "public" for entry in treatment)
    assert state.topics_initialized
    assert seed_social_state(state, tuple(p.id for p in profiles), NOW) == state


@pytest.mark.parametrize(
    "text",
    [
        "Não amo Bentinho.",
        "Nunca amo Bentinho.",
        "Será que amo Bentinho?",
        "Ele me disse: “Amo Bentinho”.",
        "Talvez eu sinta por Bentinho algo além da amizade.",
    ],
)
async def test_mention_negation_question_and_quotation_do_not_award_private_secret(
    text,
):
    assert discoveries_in_reply("escobar", text, ("escobar_affection",)) == ()


async def test_private_discovery_requires_owner_and_authorized_context():
    text = "O que sinto por Bentinho vai além da amizade."
    assert discoveries_in_reply("escobar", text, ()) == ()
    assert discoveries_in_reply("virgilia", text, ("escobar_affection",)) == ()
    assert discoveries_in_reply("escobar", text, ("escobar_affection",)) == (
        "escobar_affection",
    )


async def test_discoveries_are_from_npc_not_question_and_retry_is_idempotent(game):
    state = make_initial_investigation(game, NOW)
    incoming = ConversationMessage(
        id=uuid4(),
        sender_id="player",
        content="Escobar é apaixonado por Bentinho e estudaram no seminário?",
        created_at=NOW,
    )
    outgoing = ConversationMessage(
        id=uuid4(),
        sender_id="escobar",
        content="Não sei do que está falando.",
        created_at=NOW,
        narrative_authorized=True,
    )
    assessment = DialogueAssessment(
        discovery_ids=("seminary_bond", "escobar_affection"),
        eligible_discovery_ids=("seminary_bond",),
    )
    transition = dialogue_transition(
        state, game, "escobar", uuid4(), incoming, outgoing, assessment, NOW
    )
    assert transition.state.achievements == ()
    outgoing = outgoing.model_copy(
        update={
            "id": uuid4(),
            "content": "Bentinho e Escobar estudaram juntos no seminário e mantiveram uma amizade.",
        }
    )
    assessment = DialogueAssessment(
        discovery_ids=("seminary_bond",), eligible_discovery_ids=("seminary_bond",)
    )
    result = dialogue_transition(
        state, game, "escobar", uuid4(), incoming, outgoing, assessment, NOW
    )
    assert [a.id for a in result.state.achievements] == ["seminary_bond"]
    assert result.state.achievements[0].source_message_id == outgoing.id
    assert (
        dialogue_transition(
            result.state, game, "escobar", uuid4(), incoming, outgoing, assessment, NOW
        ).state
        == result.state
    )


async def test_public_discovery_can_join_fragments_from_different_conversations(game):
    state = make_initial_investigation(game, NOW)
    incoming = ConversationMessage(
        id=uuid4(), sender_id="player", content="O que sabe deles?", created_at=NOW
    )
    first = ConversationMessage(
        id=uuid4(),
        sender_id="capitu",
        content="Capitu e Bentinho são casados.",
        created_at=NOW,
        narrative_authorized=True,
    )
    a = DialogueAssessment(eligible_discovery_ids=("marriage_triangle",))
    state = dialogue_transition(
        state, game, "capitu", uuid4(), incoming, first, a, NOW
    ).state
    assert state.achievements == ()
    second = ConversationMessage(
        id=uuid4(),
        sender_id="escobar",
        content="Capitu e Escobar são amigos.",
        created_at=NOW,
        narrative_authorized=True,
    )
    result = dialogue_transition(
        state, game, "escobar", uuid4(), incoming, second, a, NOW
    )
    assert [d.id for d in result.state.achievements] == ["marriage_triangle"]


async def test_personal_trace_award_is_idempotent_and_does_not_change_proofs(game):
    state = make_initial_investigation(game, NOW)
    updated = award(
        state, "personal_trace", NOW, source_message_id=state.crimes[0].evidence[0].id
    )
    assert updated.crimes == state.crimes and updated.testimonies == state.testimonies
    assert award(updated, "personal_trace", NOW) == updated
    assert award(state, "invented-achievement", NOW) == state


async def test_local_guard_rejects_paraphrased_early_confidence():
    from src.modules.agents.support import (
        unauthorized_personal_disclosure,
    )

    obs = social_observations()
    assert unauthorized_personal_disclosure(
        "escobar", "Sou um amigo que o ama como talvez não deva.", obs
    )
    assert not unauthorized_personal_disclosure("escobar", "Não amo Bentinho.", obs)
    assert not unauthorized_personal_disclosure(
        "capitu", "Dizem que quero separar-me de Bentinho.", obs
    )
    assert unauthorized_personal_disclosure(
        "capitu", "Quero me separar de Bentinho.", obs
    )
    obs["memoria_social"]["descobertas_autorizadas"] = ["escobar_affection"]
    assert not unauthorized_personal_disclosure(
        "escobar", "Sou um amigo que o ama como talvez não deva.", obs
    )


async def test_compact_context_keeps_source_access_without_loading_every_transcript(
    catalog,
):
    from src.modules.agents.grounding import grounding_issues

    profile = await catalog.get("virgilia")
    obs = social_observations()
    obs["memoria_social"]["encontros_anteriores"] = [
        {"interlocutor_id": "capitu", "falas": [{"fala": "Uma acusação do detetive."}]}
    ]
    compact = compact_observations(profile, obs, "Por que está aborrecida comigo?")
    reply = "Capitu me contou sua acusação, Floriano. Quero que esclareça o que disse a ela."
    assert grounding_issues(reply, compact, {"capitu": "Capitu"}) == ()
