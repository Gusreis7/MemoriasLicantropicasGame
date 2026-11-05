"""Fachada do diálogo: dependências explícitas e workflow LangGraph por invocação."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from src.contracts.llm import LLMClient
from src.contracts.model import (
    CharacterProfile,
    ConversationMessage,
    GameCharacter,
    HarnessReply,
)
from src.contracts.repository import (
    CharacterRepository,
    DayPolicy,
    GameRepository,
    MemoryRepository,
)
from src.modules.agents.guard import DialogueGuard
from src.modules.agents.trace import TraceSink
from src.prompts.dialogue import (
    MAX_HISTORY_CHARACTERS,
    build_dialogue_prompt,
    private_context,
    private_markers,
)

PLAYER_ID = "player"


class HarnessService:
    def __init__(
        self,
        characters: CharacterRepository,
        games: GameRepository,
        memory: MemoryRepository,
        llm: LLMClient,
        history_limit: int = 20,
        guard: DialogueGuard | None = None,
        day_policy: DayPolicy | None = None,
        context_provider: Callable[[UUID, str], Awaitable[dict]] | None = None,
        knowledge_provider: Callable[[UUID, str], Awaitable[dict]] | None = None,
        session_master=None,
        trace_sink: TraceSink | None = None,
        turn_timeout_seconds: float = 60,
    ) -> None:
        if not 0 <= history_limit <= 100:
            raise ValueError("O limite de histórico deve estar entre 0 e 100.")
        if not 0 < turn_timeout_seconds <= 120:
            raise ValueError(
                "O prazo da conversa deve ser maior que zero e no máximo 120 segundos."
            )
        self._turn_timeout_seconds = turn_timeout_seconds
        self._characters, self._games, self._memory, self._llm = (
            characters,
            games,
            memory,
            llm,
        )
        self._history_limit = history_limit
        self._guard = guard if guard is not None else DialogueGuard()
        self._day_policy = day_policy
        self._context_provider, self._knowledge_provider = (
            context_provider,
            knowledge_provider,
        )
        self._session_master, self._trace_sink = session_master, trace_sink
        from src.modules.agents.workflow import DialogueWorkflow

        self._workflow = DialogueWorkflow(self)

    @property
    def graph(self):
        """Grafo compilado inspecionável; nenhum histórico é guardado nele."""
        return self._workflow.graph

    async def respond(
        self,
        game_id: UUID,
        npc_id: str,
        conversation_id: UUID,
        speaker_id: str,
        text: str,
    ) -> HarnessReply:
        return await self._workflow.respond(
            game_id, npc_id, conversation_id, speaker_id, text
        )

    # Leitores de histórico e projeções sociais usam as mesmas funções puras.
    _private_context = staticmethod(private_context)
    _private_markers = staticmethod(private_markers)

    def _context(
        self,
        profile: CharacterProfile,
        state: GameCharacter,
        speaker_id: str,
        history: tuple[ConversationMessage, ...],
        text: str,
        observations=None,
    ):
        return build_dialogue_prompt(
            self._guard, profile, state, speaker_id, history, text, observations
        )
