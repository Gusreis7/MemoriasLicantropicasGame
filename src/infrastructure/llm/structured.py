"""Saída nativa por ferramentas: LangChain ChatModel e PydanticToolsParser.

O schema viaja em tools, com required e instrução explícita de chamar o DTO.
Conteúdo textual nunca é tratado como objeto estruturado.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from operator import itemgetter
from typing import Any, Generic, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.output_parsers.openai_tools import PydanticToolsParser
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableMap, RunnablePassthrough
from langchain_core.utils.function_calling import convert_to_openai_tool
from langsmith import tracing_context
from pydantic import BaseModel, Field, ValidationError

from src.contracts.errors import LLMUnavailableError
from src.contracts.llm import LLMClient
from src.contracts.model import ChatMessage, LLMResponse

OutputT = TypeVar("OutputT", bound=BaseModel)
MAX_STRUCTURED_ATTEMPTS = 3


@dataclass(frozen=True)
class StructuredResult(Generic[OutputT]):
    value: OutputT | None = field(default=None, repr=False)
    response: LLMResponse | None = field(default=None, repr=False)
    attempts: int = 0
    error_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.value is not None and self.error_code is None


class _TransportCancelled(Exception):
    """Carry cancellation across LangChain 1.7's batched BaseException handling.

    BaseChatModel.agenerate collects BaseException but later treats CancelledError
    as a successful ChatResult. A regular internal exception crosses that boundary
    safely; the public agenerate override restores cancellation for callers.
    """


class MantleChatModel(BaseChatModel):
    """Bridge LangChain para o port assíncrono medido, sem SDK ou retries ocultos."""

    port: Any = Field(exclude=True, repr=False)

    @property
    def _llm_type(self) -> str:
        return "bedrock-mantle-native-tools"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError("Este ChatModel requer execução assíncrona")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        if stop:
            raise ValueError("Stop sequences não fazem parte deste contrato")
        roles = {"system": "system", "human": "user", "ai": "assistant"}
        if any(
            message.type not in roles or not isinstance(message.content, str)
            for message in messages
        ):
            raise TypeError("Somente mensagens textuais de conversa são permitidas")
        prompt = tuple(
            ChatMessage(role=roles[message.type], content=message.content)
            for message in messages
        )
        try:
            response = await self.port.complete(
                prompt,
                tools=tuple(kwargs.get("tools", ())),
                tool_choice=kwargs.get("tool_choice"),
            )
        except asyncio.CancelledError:
            raise _TransportCancelled("Native transport cancelled") from None
        message = AIMessage(
            content=response.content,
            tool_calls=[call.model_dump() for call in response.tool_calls],
            invalid_tool_calls=[
                call.model_dump() for call in response.invalid_tool_calls
            ],
            response_metadata={
                "model_name": response.model,
                "native_input_tokens": response.input_tokens,
                "native_output_tokens": response.output_tokens,
            },
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def agenerate(self, *args, **kwargs):
        try:
            return await super().agenerate(*args, **kwargs)
        except _TransportCancelled:
            raise asyncio.CancelledError() from None

    def bind_tools(self, tools: Sequence, *, tool_choice="auto", **kwargs):
        # Named forcing is deliberately unsupported: Mantle/Qwen accepted it
        # with HTTP 200 but returned plain text during live verification.
        if tool_choice not in (None, "auto", "required"):
            raise ValueError("O bridge Mantle aceita tool_choice='auto' ou 'required'")
        if kwargs:
            raise ValueError("Opções de ferramenta não suportadas")
        converted = tuple(convert_to_openai_tool(tool) for tool in tools)
        return self.bind(tools=converted, tool_choice=tool_choice or "auto")

    def with_structured_output(
        self, schema, *, include_raw=False, method="function_calling", **kwargs
    ):
        """Composição pública provider-aware, usando somente ferramentas nativas.

        BaseChatModel usa tool_choice='any'. Este provedor utiliza 'required':
        uma resposta sem chamada é rejeitada, nunca reinterpretada como JSON.
        """
        if method != "function_calling" or kwargs:
            raise ValueError(
                "Somente structured output por function_calling é suportado"
            )
        if not isinstance(schema, type) or not issubclass(schema, BaseModel):
            raise TypeError("O contrato de saída deve ser um modelo Pydantic")
        bound = self.bind_tools([schema], tool_choice="required")
        parser = PydanticToolsParser(tools=[schema], first_tool_only=True)
        if not include_raw:
            return bound | parser
        parsed = RunnablePassthrough.assign(
            parsed=itemgetter("raw") | parser,
            parsing_error=lambda _: None,
        )
        failure = RunnablePassthrough.assign(parsed=lambda _: None)
        return RunnableMap(raw=bound) | parsed.with_fallbacks(
            [failure], exception_key="parsing_error"
        )


def _response(message: AIMessage) -> LLMResponse:
    metadata = message.response_metadata
    return LLMResponse(
        content=message.content,
        tool_calls=tuple(message.tool_calls),
        invalid_tool_calls=tuple(message.invalid_tool_calls),
        model=metadata["model_name"],
        input_tokens=metadata.get("native_input_tokens"),
        output_tokens=metadata.get("native_output_tokens"),
    )


async def generate_structured(
    client: LLMClient,
    messages: tuple[ChatMessage, ...],
    output_type: type[OutputT],
    *,
    max_attempts: int = 2,
) -> StructuredResult[OutputT]:
    """Uma ferramenta DTO por chamada; falha explícita e orçamento limitado.

    Auth/quota/rede não recebem retry. Parsing inválido pode gerar nova chamada
    idêntica com o mesmo tools schema, sem reenviar conteúdo inválido ao modelo.
    O chamador decide o fallback do domínio. Cancelamento e bugs propagam.
    """
    if (
        type(max_attempts) is not int
        or not 1 <= max_attempts <= MAX_STRUCTURED_ATTEMPTS
    ):
        raise ValueError("max_attempts deve estar entre 1 e 3")
    if not messages:
        raise ValueError("A geração exige mensagens")
    model = MantleChatModel(port=client, cache=False)
    chain = model.with_structured_output(
        output_type, method="function_calling", include_raw=True
    )
    expected_name = convert_to_openai_tool(output_type)["function"]["name"]
    prompt = [(message.role, message.content) for message in messages]
    prompt.insert(1 if messages[0].role == "system" else 0,
                  ("system", f"Conclua esta tarefa chamando exatamente uma vez a ferramenta {expected_name}. "
                   "Preencha os argumentos da ferramenta com o resultado solicitado. "
                   "Não envie a resposta em texto livre fora da chamada da ferramenta."))
    response = None
    error_code = None
    for attempt in range(1, max_attempts + 1):
        try:
            with tracing_context(enabled=False, parent=False):
                result = await chain.ainvoke(prompt)
        except LLMUnavailableError as error:
            error_code = error.code
            if error_code not in {"llm_invalid_response", "llm_response_truncated"}:
                return StructuredResult(attempts=attempt, error_code=error_code)
            continue
        except TimeoutError:
            return StructuredResult(attempts=attempt, error_code="llm_timeout")
        raw = result["raw"]
        response = _response(raw)
        # first_tool_only is a parser convenience, not permission to ignore extra
        # calls. One expected DTO and no malformed call are mandatory.
        if raw.invalid_tool_calls:
            error_code = "invalid_tool_arguments"
            continue
        if len(raw.tool_calls) != 1 or raw.tool_calls[0]["name"] != expected_name:
            error_code = "invalid_tool_response"
            continue
        if result["parsing_error"] is not None:
            error = result["parsing_error"]
            if not isinstance(
                error, (ValidationError, OutputParserException, ValueError)
            ):
                raise error
            error_code = "invalid_schema"
            continue
        if not isinstance(result["parsed"], output_type):
            error_code = "invalid_schema"
            continue
        return StructuredResult(
            value=result["parsed"], response=response, attempts=attempt
        )
    return StructuredResult(
        response=response, attempts=max_attempts, error_code=error_code
    )
