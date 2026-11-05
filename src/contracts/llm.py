from typing import Any, Protocol

from src.contracts.model import ChatMessage, LLMResponse


class LLMClient(Protocol):
    async def complete(
        self,
        messages: tuple[ChatMessage, ...],
        *,
        tools: tuple[dict[str, Any], ...] = (),
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse: ...


class TokenProvider(Protocol):
    async def get_token(self) -> str: ...
