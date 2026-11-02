import json
from uuid import uuid4

import pytest

from memorias_licantropicas.infrastructure.llm.json_output import parse_json_object
from memorias_licantropicas.modules.knowledge.service import parse_extraction, attributed_utterance
from memorias_licantropicas.modules.agents.grounding import ground_dialogue_output


@pytest.mark.parametrize("text", ['{}', '```json\n{}\n```', '```\n{}\n```'])
def test_accepts_only_complete_json_envelope(text):
    assert parse_json_object(text) == {}


@pytest.mark.parametrize("text", ['Aqui: {}', '```json\n{}\n``` depois', '{"a":1,"a":2}', '[]'])
def test_rejects_prose_duplicates_and_nonobject(text):
    with pytest.raises(ValueError):
        parse_json_object(text)


def test_bad_claim_does_not_erase_independently_valid_claim():
    good = {"message_id": str(uuid4()), "source_span": "Virgília esteve no cais.", "proposition": "Virgília esteve no cais.", "kind": "report"}
    bad = {**good, "kind": "accusation"}
    parsed = parse_extraction('```json\n' + json.dumps({"claims": [bad, good]}) + '\n```')
    assert len(parsed.claims) == 1
    assert parsed.claims[0].kind == "report"


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
