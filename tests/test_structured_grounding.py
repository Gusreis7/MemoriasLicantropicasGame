import json
from uuid import uuid4

import pytest

from memorias_licantropicas.infrastructure.llm.structured import generate_structured
from memorias_licantropicas.contracts.model import ChatMessage, LLMResponse
from native_fixtures import respond_to_tools, invalid_tool_response
from memorias_licantropicas.contracts.generation import Extraction
from memorias_licantropicas.modules.knowledge.service import attributed_utterance
from memorias_licantropicas.modules.agents.grounding import grounding_issues


@pytest.mark.anyio
async def test_extraction_requires_the_declared_native_output_tool():
    class Client:
        async def complete(self, messages, *, tools=(), tool_choice=None):
            return respond_to_tools({"claims": []}, tools, tool_choice)

    result = await generate_structured(
        Client(), (ChatMessage(role="user", content="Extraia relatos."),), Extraction
    )
    assert result.ok and result.value.claims == ()
    assert (
        result.response.content == ""
        and result.response.tool_calls[0].name == "Extraction"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "text",
    ["Aqui: {}", '```json\n{"claims": []}\n```', '{"claims":[],"claims":[]}', "[]"],
)
async def test_free_text_is_never_rescued_as_native_structured_output(text):
    class Client:
        async def complete(self, messages, *, tools=(), tool_choice=None):
            return LLMResponse(content=text, model="unstructured-provider")

    result = await generate_structured(
        Client(), (ChatMessage(role="user", content="Extraia relatos."),), Extraction
    )
    assert not result.ok and result.error_code == "invalid_tool_response"


@pytest.mark.anyio
async def test_invalid_claim_rejects_the_native_batch_without_partial_acceptance():
    good = {
        "message_id": str(uuid4()),
        "source_span": "Virgília esteve no cais.",
        "proposition": "Virgília esteve no cais.",
        "kind": "report",
    }
    bad = {**good, "kind": "accusation"}

    class Client:
        async def complete(self, messages, *, tools=(), tool_choice=None):
            return respond_to_tools({"claims": [bad, good]}, tools, tool_choice)

    result = await generate_structured(
        Client(), (ChatMessage(role="user", content="Extraia relatos."),), Extraction
    )
    assert (
        not result.ok and result.error_code == "invalid_schema" and result.value is None
    )


def test_unrecorded_presence_and_invented_source_are_rejected_without_rewriting():
    for presence in ("Eu estava no cais ontem.", "Andei pelo cais ontem."):
        assert grounding_issues(presence, {}, {}) == ("unsupported_presence",)
    for speech, names in (
        ("Soube por Escobar que você perguntou.", {"escobar": "Escobar"}),
        (
            "Ouvi dizer, de Virgília, que esteve no cais.",
            {"virgilia": "Virgília Neves"},
        ),
        (
            "Ouvi dizer, pela senhora Virgília, que esteve no cais.",
            {"virgilia": "Virgília Neves"},
        ),
    ):
        assert grounding_issues(speech, {}, names) == ("unsupported_source",)


def test_third_party_location_is_not_mistaken_for_the_speakers_presence():
    assert grounding_issues("Bentinho estava no cais ontem.", {}, {}) == ()


def test_personal_activity_is_usable_without_formal_interrogation():
    context = {
        "suas_atividades": [
            {"dia": 0, "periodo": "night", "local_id": "cais_lanternas"}
        ]
    }
    text = "Eu estava no cais, cuidando de meus afazeres."
    assert grounding_issues(text, context, {}) == ()


def test_official_version_and_heard_source_remain_authorized():
    context = {
        "suas_versoes_de_interrogatorio": [
            {"local_id": "cais_lanternas", "fala": "Estava no cais."}
        ],
        "memoria_social": {"memorias_relevantes": [{"quem_falou": "escobar"}]},
    }
    text = "Estava no cais. Escobar me contou que Floriano perguntou por mim."
    assert grounding_issues(text, context, {"escobar": "Escobar"}) == ()


def test_canonical_quote_preserves_pronoun_addressee_and_negation():
    original = "Virgília me contou que viu você no cais ontem. Eu não presenciei isso."
    quote = attributed_utterance(original, "Floriano", "Bentinho")
    assert quote == f"Floriano disse a Bentinho: «{original}»"
    assert "Floriano foi ao cais" not in quote
