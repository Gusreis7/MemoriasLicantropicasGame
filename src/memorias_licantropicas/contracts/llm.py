from typing import Protocol

from memorias_licantropicas.contracts.model import ChatMessage, LLMResponse


class LLMClient(Protocol):
    async def complete(self, messages: tuple[ChatMessage, ...]) -> LLMResponse: ...


class TokenProvider(Protocol):
    async def get_token(self) -> str: ...
