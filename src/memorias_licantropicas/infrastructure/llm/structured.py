"""Saídas tipadas: transporte, parsing estrito e tentativas com orçamento explícito.

O endpoint Mantle continua recebendo Chat Completions. Esta camada não promete
constrained decoding: instrui o formato, valida o documento inteiro e entrega
uma falha tipada ao chamador, que decide o fallback apropriado ao domínio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Generic, TypeVar

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, ValidationError

from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.contracts.llm import LLMClient
from memorias_licantropicas.contracts.model import ChatMessage, LLMResponse

OutputT = TypeVar("OutputT", bound=BaseModel)
MAX_OUTPUT_CHARACTERS = 8000
MAX_STRUCTURED_ATTEMPTS = 3


class StructuredOutputError(ValueError):
    """Erro estável, sem conteúdo do modelo, schema privado ou mensagem original."""

    def __init__(self, code: str):
        self.code = (
            code if code in {"invalid_json", "invalid_schema"} else "invalid_schema"
        )
        super().__init__(self.code)


@dataclass(frozen=True)
class StructuredResult(Generic[OutputT]):
    value: OutputT | None = field(default=None, repr=False)
    response: LLMResponse | None = field(default=None, repr=False)
    attempts: int = 0
    error_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.value is not None and self.error_code is None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non_finite_number")


class StrictPydanticOutputParser(PydanticOutputParser[OutputT]):
    """LangChain parser com validação JSON estrita, inclusive em modelos aninhados.

    A validação JSON permite representações JSON próprias (array -> tuple,
    string -> UUID), sem aceitar coerções como string numérica -> integer.
    O parser-base usa model_validate em Python; esse hook mantém a semântica
    correta de JSON para contratos strict com tuplas ou identificadores UUID.
    """

    def _parse_obj(self, obj) -> OutputT:
        return self.pydantic_object.model_validate_json(
            json.dumps(obj, ensure_ascii=False, allow_nan=False),
            strict=True,
            extra="forbid",
        )


def _parser(output_type: type[OutputT]) -> StrictPydanticOutputParser[OutputT]:
    if not isinstance(output_type, type) or not issubclass(output_type, BaseModel):
        raise TypeError("output_type deve ser um modelo Pydantic")
    return StrictPydanticOutputParser(pydantic_object=output_type)


def parse_model_output(text: str, output_type: type[OutputT]) -> OutputT:
    """Valida um objeto JSON inteiro. Nenhum reparo de prosa, fence ou truncamento."""
    parser = _parser(output_type)
    if not isinstance(text, str) or not 1 <= len(text) <= MAX_OUTPUT_CHARACTERS:
        raise StructuredOutputError("invalid_json")
    try:
        document = json.loads(
            text, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if not isinstance(document, dict):
            raise ValueError("object_required")
    except (ValueError, TypeError, RecursionError):
        raise StructuredOutputError("invalid_json") from None
    # LangChain's default JSON parser can repair partial JSON and strip fences.
    # The preceding lexical gate prevents those compatibility paths from running.
    try:
        return parser.parse(text)
    except (ValidationError, ValueError, TypeError, RecursionError):
        raise StructuredOutputError("invalid_schema") from None


def format_instructions(output_type: type[OutputT]) -> str:
    """Instruções geradas pelo mesmo parser que valida o contrato recebido."""
    return (
        "CONTRATO DE SAÍDA ESTRUTURADA: retorne somente um objeto JSON completo. "
        "Não inclua prosa externa, Markdown, cercas, raciocínio ou campos adicionais. "
        "Preserve os tipos JSON; não use strings para números ou booleanos.\n"
        + _parser(output_type).get_format_instructions()
    )


def _with_format(messages: tuple[ChatMessage, ...], instructions: str):
    # Keep the final user message in the final slot for transports/test clients.
    index = len(messages) - 1 if messages[-1].role == "user" else len(messages)
    return (
        *messages[:index],
        ChatMessage(role="system", content=instructions),
        *messages[index:],
    )


async def generate_structured(
    client: LLMClient,
    messages: tuple[ChatMessage, ...],
    output_type: type[OutputT],
    *,
    max_attempts: int = 2,
) -> StructuredResult[OutputT]:
    """Tenta gerar o contrato; o chamador aplica um fallback explícito se falhar.

    Só falhas de formato recebem nova tentativa. Auth, quota, timeout e rede
    retornam imediatamente; cancelamento continua propagando. Cada tentativa
    invoca o cliente recebido, inclusive o cliente medido do aplicativo.
    Não reenvia respostas rejeitadas nem detalhes de exceções ao modelo.
    """
    if (
        type(max_attempts) is not int
        or not 1 <= max_attempts <= MAX_STRUCTURED_ATTEMPTS
    ):
        raise ValueError("max_attempts deve estar entre 1 e 3")
    if not messages:
        raise ValueError("A geração exige mensagens")
    instructions = format_instructions(output_type)
    response = None
    error_code = None
    for attempt in range(1, max_attempts + 1):
        retry = (
            "\nA tentativa anterior não cumpriu o contrato. Gere novamente o objeto "
            "completo conforme o schema; mantenha somente os dados autorizados."
            if attempt > 1
            else ""
        )
        try:
            response = await client.complete(
                _with_format(messages, instructions + retry)
            )
        except LLMUnavailableError as error:
            error_code = error.code
            if error_code not in {"llm_invalid_response", "llm_response_truncated"}:
                return StructuredResult(attempts=attempt, error_code=error_code)
            continue
        except TimeoutError:
            return StructuredResult(attempts=attempt, error_code="llm_timeout")
        try:
            value = parse_model_output(response.content, output_type)
        except StructuredOutputError as error:
            error_code = error.code
            continue
        return StructuredResult(value=value, response=response, attempts=attempt)
    return StructuredResult(
        response=response, attempts=max_attempts, error_code=error_code
    )
