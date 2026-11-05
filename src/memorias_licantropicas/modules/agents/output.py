"""Leitor de compatibilidade de históricos; gerações novas usam NpcSpeech tipado."""

import json
import re

from memorias_licantropicas.contracts.errors import LLMUnavailableError

_INTERNAL_TAGS = re.compile(
    r"</?(?:think|analysis|reasoning|tool_call|function_call)(?:\s[^>]*)?>|"
    r"<\|(?:analysis|system|assistant|tool|im_start|im_end)\|>",
    re.IGNORECASE,
)
_ENVELOPE_KEYS = re.compile(r'"(?:remetente|fala|tool_calls|function_call|reasoning_content)"\s*:')


def _invalid() -> LLMUnavailableError:
    # Não incluir o texto rejeitado em mensagens públicas, logs ou exceções.
    return LLMUnavailableError("O personagem não retornou uma fala válida. Tente novamente.",
                               code="llm_invalid_response")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Campo repetido.")
        result[key] = value
    return result


def parse_dialogue_output(content: str, expected_sender: str) -> str:
    """Lê prosa ou o envelope legado exato ``{remetente, fala}`` persistido.

    Não procura JSON dentro de prosa, não conserta truncamentos e não executa
    metadados. O remetente do envelope precisa coincidir com o NPC validado no
    servidor. Esta função não participa da geração de novas respostas.
    """
    if not isinstance(content, str) or not expected_sender:
        raise _invalid()
    text = content.strip()
    if not text or len(text) > 8000 or _INTERNAL_TAGS.search(text):
        raise _invalid()

    fenced = text.startswith("```")
    if fenced:
        match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
        if match is None:
            raise _invalid()
        text = match.group(1).strip()

    structured = text.startswith(("{", "["))
    if fenced or structured:
        try:
            value = json.loads(text, object_pairs_hook=_unique_object)
        except (ValueError, TypeError, RecursionError):
            raise _invalid() from None
        if (
            not isinstance(value, dict)
            or set(value) != {"remetente", "fala"}
            or value["remetente"] != expected_sender
            or not isinstance(value["fala"], str)
        ):
            raise _invalid()
        text = value["fala"].strip()

    if (
        not text
        or len(text) > 8000
        or text.startswith(("{", "[", "```"))
        or "```" in text
        or _ENVELOPE_KEYS.search(text)
        or _INTERNAL_TAGS.search(text)
    ):
        raise _invalid()
    return text
