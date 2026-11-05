import json
from uuid import uuid4

import pytest

from memorias_licantropicas.infrastructure.llm.structured import parse_model_output, StructuredOutputError
from memorias_licantropicas.contracts.generation import Extraction
from memorias_licantropicas.modules.knowledge.service import attributed_utterance
from memorias_licantropicas.modules.agents.grounding import ground_dialogue_output


def test_extraction_requires_complete_typed_document():
    assert parse_model_output('{"claims": []}', Extraction).claims == ()


@pytest.mark.parametrize("text", ['Aqui: {}', '```json\n{"claims": []}\n```', '{"claims":[],"claims":[]}', '[]'])
def test_rejects_prose_fences_duplicates_and_nonobject(text):
    with pytest.raises(StructuredOutputError):
        parse_model_output(text, Extraction)


def test_invalid_claim_rejects_batch_instead_of_silent_partial_acceptance():
    good = {"message_id": str(uuid4()), "source_span": "Virgília esteve no cais.", "proposition": "Virgília esteve no cais.", "kind": "report"}
    bad = {**good, "kind": "accusation"}
    with pytest.raises(StructuredOutputError):
        parse_model_output(json.dumps({"claims": [bad, good]}), Extraction)


def test_unrecorded_presence_and_invented_source_are_replaced():
    for invented_presence in ("Eu estava no cais ontem.", "Andei pelo cais ontem."):
        response = ground_dialogue_output(invented_presence, {}, {})
        assert response != invented_presence
        assert "não me lembro" in response
        assert "no cais" not in response and "interrogatório" not in response
    for invented_source, names in (
        ("Soube por Escobar que você perguntou.", {"escobar": "Escobar"}),
        ("Ouvi dizer, de Virgília, que esteve no cais.", {"virgilia": "Virgília Neves"}),
        ("Ouvi dizer, pela senhora Virgília, que esteve no cais.", {"virgilia": "Virgília Neves"}),
    ):
        response = ground_dialogue_output(invented_source, {}, names)
        assert response != invented_source
        assert "não ouvi" in response
        assert not any(name in response for name in ("Escobar", "Virgília"))


def test_personal_activity_is_usable_without_formal_interrogation():
    context = {"suas_atividades": [{"dia": 0, "periodo": "night", "local_id": "cais_lanternas"}]}
    text = "Eu estava no cais, cuidando de meus afazeres."
    assert ground_dialogue_output(text, context, {}) == text


def test_official_version_and_heard_source_remain_authorized():
    context = {"suas_versoes_de_interrogatorio": [{"local_id": "cais_lanternas", "fala": "Estava no cais."}],
               "memoria_social": {"memorias_relevantes": [{"quem_falou": "escobar"}]}}
    text = "Estava no cais. Escobar me contou que Floriano perguntou por mim."
    assert ground_dialogue_output(text, context, {"escobar": "Escobar"}) == text


def test_canonical_quote_preserves_pronoun_addressee_and_negation():
    original = "Virgília me contou que viu você no cais ontem. Eu não presenciei isso."
    quote = attributed_utterance(original, "Floriano", "Bentinho")
    assert quote == f"Floriano disse a Bentinho: «{original}»"
    assert "Floriano foi ao cais" not in quote
