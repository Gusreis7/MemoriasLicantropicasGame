"""Leitor de registros históricos Redis; não processa respostas novas do LLM."""

import json

from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError

from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.modules.agents.guard import DialogueGuard


class LegacyDialogueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    remetente: StrictStr
    fala: StrictStr


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_stored_field")
        result[key] = value
    return result


def read_persisted_dialogue(content: str, expected_sender: str) -> str:
    """Lê prosa canônica ou o envelope conhecido de versões antigas do banco.

    O formato antigo é tratado apenas na fronteira de leitura da persistência.
    Geração atual exige tool calls e nunca chama esta função para recuperar texto.
    """
    try:
        if not isinstance(content, str) or not expected_sender:
            raise ValueError("invalid_stored_message")
        text = content.strip()
        if not text or len(text) > 8000:
            raise ValueError("invalid_stored_message")
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) < 3 or lines[0].casefold() not in {"```", "```json"} or lines[-1] != "```":
                raise ValueError("invalid_stored_envelope")
            text = "\n".join(lines[1:-1]).strip()
            record = LegacyDialogueRecord.model_validate(json.loads(text, object_pairs_hook=_unique_fields))
            if record.remetente != expected_sender:
                raise ValueError("stored_sender_mismatch")
            text = record.fala.strip()
        elif text.startswith("{"):
            record = LegacyDialogueRecord.model_validate(json.loads(text, object_pairs_hook=_unique_fields))
            if record.remetente != expected_sender:
                raise ValueError("stored_sender_mismatch")
            text = record.fala.strip()
        if not text or not DialogueGuard().inspect_output(text, allow_role_disclosure=True).allowed:
            raise ValueError("unsafe_stored_message")
        return text
    except (ValidationError, ValueError, TypeError, RecursionError):
        raise LLMUnavailableError("O registro histórico não contém uma fala válida.", code="llm_invalid_response") from None
