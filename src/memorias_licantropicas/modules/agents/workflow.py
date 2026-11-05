"""Nós do diálogo e limites de reparo, sem checkpointer ou memória oculta.

O grafo executa uma troca por invocação. Redis/outbox permanece a autoridade da
sessão; o gate externo continua serializando ações e a persistência revalida o dia.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from memorias_licantropicas.contracts.errors import (
    AccessDeniedError,
    ConflictError,
    LLMUnavailableError,
    NotFoundError,
    StorageUnavailableError,
)
from memorias_licantropicas.contracts.model import (
    CharacterProfile,
    ChatMessage,
    Conversation,
    ConversationMessage,
    GameCharacter,
    HarnessReply,
    LLMResponse,
)
from memorias_licantropicas.infrastructure.llm.structured import generate_structured
from memorias_licantropicas.infrastructure.usage import usage_scope
from memorias_licantropicas.modules.agents.grounding import ground_dialogue_output
from memorias_licantropicas.modules.agents.guard import SAFE_DIALOGUE_REPLY
from memorias_licantropicas.modules.agents.schema import NpcSpeech
from memorias_licantropicas.modules.agents.support import (
    compact_observations,
    unauthorized_personal_disclosure,
)
from memorias_licantropicas.modules.agents.trace import DialogueAudit, DialogueTrace
from memorias_licantropicas.modules.characters.catalog import supports_content_version

if TYPE_CHECKING:
    from memorias_licantropicas.modules.agents.service import HarnessService

logger = logging.getLogger(__name__)
PLAYER_ID = "player"
MAX_REPAIRS = 1
TRACE_TIMEOUT_SECONDS = 1.0
TECHNICAL_FALLBACK = (
    "Não consegui organizar minha resposta agora, detetive. Pode reformular a pergunta?"
)
PARSE_FAILURES = {
    "invalid_json",
    "invalid_schema",
    "llm_invalid_response",
    "llm_response_truncated",
}


@dataclass(frozen=True)
class DialogueRequest:
    game_id: UUID
    npc_id: str
    conversation_id: UUID
    speaker_id: str
    text: str


class DialogueState(TypedDict, total=False):
    request: DialogueRequest
    audit: DialogueAudit
    profile: CharacterProfile
    npc: GameCharacter
    incoming: ConversationMessage
    history: tuple[ConversationMessage, ...]
    observations: dict | None
    names: dict[str, str]
    prompt: tuple[ChatMessage, ...]
    response: LLMResponse | None
    content: str
    assessment: Any
    issues: tuple[str, ...]
    repairs: int
    allowed: bool
    role_disclosure: bool
    fallback_reason: str | None
    error_code: str | None
    reply: HarnessReply


def _step(state: DialogueState, name: str):
    state["audit"].nodes.append(name)


class _InvocationClient:
    """Conta inclusive a chamada cancelada, antes de delegar ao cliente medido."""

    def __init__(self, client, audit):
        self._client, self._audit = client, audit

    async def complete(self, messages):
        self._audit.attempts += 1
        return await self._client.complete(messages)


class DialogueWorkflow:
    def __init__(self, harness: HarnessService):
        self.harness = harness
        graph = StateGraph(DialogueState)
        for name in (
            "authorize",
            "input_guard",
            "context",
            "generate",
            "master_review",
            "semantic_validation",
            "repair",
            "output_guard",
            "fallback",
            "error",
            "persist",
        ):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "authorize")
        graph.add_edge("authorize", "input_guard")
        graph.add_conditional_edges(
            "input_guard",
            lambda s: "context" if s["allowed"] else "fallback",
            {"context": "context", "fallback": "fallback"},
        )
        graph.add_edge("context", "generate")
        graph.add_conditional_edges(
            "generate",
            self.generation_route,
            {
                "master_review": "master_review",
                "fallback": "fallback",
                "error": "error",
            },
        )
        graph.add_conditional_edges(
            "master_review",
            self.master_route,
            {
                "fallback": "fallback",
                "error": "error",
                "semantic_validation": "semantic_validation",
            },
        )
        graph.add_conditional_edges(
            "semantic_validation",
            self.review_route,
            {
                "repair": "repair",
                "fallback": "fallback",
                "output_guard": "output_guard",
            },
        )
        graph.add_edge("repair", "generate")
        graph.add_conditional_edges(
            "output_guard",
            lambda s: "persist" if s["allowed"] else "fallback",
            {"persist": "persist", "fallback": "fallback"},
        )
        graph.add_edge("fallback", "persist")
        graph.add_edge("error", END)
        graph.add_edge("persist", END)
        self.graph = graph.compile(name="npc_dialogue_v2")

    async def respond(self, game_id, npc_id, conversation_id, speaker_id, text):
        request = DialogueRequest(game_id, npc_id, conversation_id, speaker_id, text)
        audit = DialogueAudit()
        try:
            with tracing_context(enabled=False, parent=False):
                async with asyncio.timeout(self.harness._turn_timeout_seconds):
                    result = await self.graph.ainvoke(
                        {"request": request, "audit": audit, "repairs": 0},
                        config={"recursion_limit": 24},
                    )
            audit.status = "fallback" if audit.fallback else "completed"
            return result["reply"]
        except TimeoutError:
            audit.status, audit.error_code = "error", "llm_timeout"
            raise LLMUnavailableError(
                "O diálogo excedeu seu prazo total.", code="llm_timeout"
            ) from None
        except asyncio.CancelledError:
            audit.status, audit.error_code = "cancelled", "cancelled"
            raise
        except Exception as error:
            audit.status = "error"
            audit.error_code = (
                error.code
                if isinstance(error, LLMUnavailableError)
                else type(error).__name__
                if isinstance(
                    error,
                    (
                        AccessDeniedError,
                        ConflictError,
                        NotFoundError,
                        StorageUnavailableError,
                    ),
                )
                else "internal_error"
            )
            raise
        finally:
            await self._record_trace(request, audit)

    async def _record_trace(self, request, audit):
        trace = DialogueTrace(
            invocation_id=audit.invocation_id,
            game_id=request.game_id,
            conversation_id=request.conversation_id,
            npc_id=request.npc_id,
            nodes=tuple(audit.nodes),
            attempts=audit.attempts,
            review_attempts=audit.review_attempts,
            status=audit.status,
            error_code=audit.error_code,
            fallback=audit.fallback,
        )
        logger.info(
            "dialogue_graph status=%s attempts=%d fallback=%s code=%s invocation=%s",
            trace.status,
            trace.attempts,
            trace.fallback,
            trace.error_code,
            trace.invocation_id,
        )
        if self.harness._trace_sink is not None:
            try:
                async with asyncio.timeout(TRACE_TIMEOUT_SECONDS):
                    await self.harness._trace_sink(trace)
            except Exception:
                # Observabilidade é best-effort e nunca mascara falha/cancelamento
                # do diálogo. Somente código estável vai ao log, sem exception text.
                logger.warning(
                    "dialogue_graph code=trace_persistence_failed invocation=%s",
                    trace.invocation_id,
                )

    async def authorize(self, state):
        _step(state, "authorize")
        request, h = state["request"], self.harness
        if (
            not isinstance(request.text, str)
            or not request.text.strip()
            or len(request.text) > 8000
        ):
            raise ConflictError("A mensagem deve conter entre 1 e 8000 caracteres.")
        if request.npc_id == PLAYER_ID or request.npc_id == request.speaker_id:
            raise AccessDeniedError("A conversa exige um NPC e outro participante.")
        game = await h._games.get(request.game_id)
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        if not supports_content_version(
            game.content_version, h._characters.content_version
        ):
            raise ConflictError(
                "A partida usa uma versão anterior de personagens; crie uma nova partida."
            )
        cast = {member.character_id: member for member in game.characters}
        npc = cast.get(request.npc_id)
        if npc is None:
            raise NotFoundError("NPC não encontrado nesta partida.")
        if not npc.alive:
            raise AccessDeniedError("Este NPC não pode conversar.")
        if request.speaker_id != PLAYER_ID:
            speaker = cast.get(request.speaker_id)
            if speaker is None or not speaker.alive:
                raise AccessDeniedError(
                    "O interlocutor não pode participar desta conversa."
                )
        profile = await h._characters.get(request.npc_id)
        if profile is None:
            raise NotFoundError("Ficha do NPC não encontrada.")
        if h._session_master is not None:
            await h._session_master.reconcile(request.game_id, request.conversation_id)
        participants = {request.npc_id, request.speaker_id}
        conversation = await h._memory.get_conversation(
            request.game_id, request.conversation_id
        )
        if conversation is None:
            proposed = Conversation(
                id=request.conversation_id,
                game_id=request.game_id,
                participant_ids=(request.npc_id, request.speaker_id),
                created_at=datetime.now(UTC),
            )
            conversation = (
                proposed
                if await h._memory.create_conversation(proposed)
                else await h._memory.get_conversation(
                    request.game_id, request.conversation_id
                )
            )
            if conversation is None:
                raise ConflictError("Não foi possível estabelecer a conversa.")
        if (
            conversation.game_id != request.game_id
            or set(conversation.participant_ids) != participants
        ):
            raise AccessDeniedError("Os participantes não correspondem à conversa.")
        history = (
            await h._memory.list_messages(
                request.game_id,
                request.conversation_id,
                viewer_id=request.npc_id,
                limit=h._history_limit,
            )
            if h._history_limit
            else ()
        )
        if any(message.sender_id not in participants for message in history):
            raise StorageUnavailableError("O histórico da conversa está inconsistente.")
        await self._assert_day(request)
        return {
            "profile": profile,
            "npc": npc,
            "history": history,
            "incoming": ConversationMessage(
                id=uuid4(),
                sender_id=request.speaker_id,
                content=request.text,
                created_at=datetime.now(UTC),
            ),
            "assessment": None,
            "role_disclosure": False,
            "observations": None,
        }

    async def _assert_day(self, request):
        if self.harness._day_policy and request.speaker_id == PLAYER_ID:
            await self.harness._day_policy.assert_dialogue_open(request.game_id)

    def input_guard(self, state):
        _step(state, "input_guard")
        decision = self.harness._guard.inspect_input(state["request"].text)
        return {
            "allowed": decision.allowed,
            "fallback_reason": None if decision.allowed else "input_guard",
        }

    async def context(self, state):
        _step(state, "context")
        request, h = state["request"], self.harness
        observations = (
            await h._context_provider(request.game_id, request.npc_id)
            if h._context_provider
            else None
        )
        if h._knowledge_provider:
            observations = dict(observations or {})
            observations["memoria_social"] = await h._knowledge_provider(
                request.game_id, request.npc_id
            )
        observations = compact_observations(
            state["profile"], observations, request.text
        )
        return {
            "observations": observations,
            "names": {item.id: item.name for item in await h._characters.list()},
            "prompt": h._context(
                state["profile"],
                state["npc"],
                request.speaker_id,
                state["history"],
                request.text,
                observations,
            ),
        }

    async def generate(self, state):
        _step(state, "generate")
        request = state["request"]
        with usage_scope(request.game_id, "player_dialogue", request.npc_id):
            generated = await generate_structured(
                _InvocationClient(self.harness._llm, state["audit"]),
                state["prompt"],
                NpcSpeech,
                max_attempts=2,
            )
        return {
            "response": generated.response,
            "content": generated.value.fala if generated.ok else "",
            "error_code": generated.error_code,
            "issues": (),
            "assessment": None,
        }

    @staticmethod
    def generation_route(state):
        code = state.get("error_code")
        if code:
            return "fallback" if code in PARSE_FAILURES else "error"
        return "master_review"

    @staticmethod
    def master_route(state):
        if state.get("fallback_reason"):
            if state.get("error_code") in {
                "llm_authentication_failed",
                "llm_credentials_missing",
                "llm_credentials_unavailable",
            }:
                return "error"
            return "fallback"
        return "semantic_validation"

    async def master_review(self, state):
        _step(state, "master_review")
        master = self.harness._session_master
        if master is None:
            return {"assessment": None, "fallback_reason": None}
        request = state["request"]
        draft = ConversationMessage(
            id=uuid4(),
            sender_id=request.npc_id,
            content=state["content"],
            created_at=datetime.now(UTC),
        )
        assessment = await master.assess(
            request.game_id,
            request.npc_id,
            request.conversation_id,
            state["incoming"],
            draft,
            observations=state["observations"],
            profile=state["profile"],
        )
        state["audit"].review_attempts += getattr(assessment, "attempts", 0)
        if getattr(assessment, "source", None) == "fallback":
            return {
                "assessment": None,
                "fallback_reason": "master_unavailable",
                "error_code": assessment.error_code or "master_unavailable",
            }
        return {
            "assessment": assessment,
            "fallback_reason": None,
            "role_disclosure": await master.can_disclose_role(
                request.game_id, request.npc_id, state["incoming"], draft, assessment
            ),
        }

    def semantic_validation(self, state):
        _step(state, "semantic_validation")
        observations, content = state["observations"], state["content"]
        issues = list(
            state["assessment"].issues if state["assessment"] is not None else ()
        )
        if ground_dialogue_output(content, observations, state["names"]) != content:
            issues.append("unsupported_fact")
        if unauthorized_personal_disclosure(
            state["request"].npc_id, content, observations
        ):
            issues.append("unauthorized_confidence")
        return {"issues": tuple(dict.fromkeys(issues))}

    @staticmethod
    def review_route(state):
        if state["issues"]:
            return "repair" if state["repairs"] < MAX_REPAIRS else "fallback"
        return "output_guard"

    def repair(self, state):
        _step(state, "repair")
        # Somente códigos de qualidade são retornados ao modelo; nenhuma tentativa
        # rejeitada (que pode conter segredo) vira mensagem assistant no novo prompt.
        allowed_codes = {
            "invented_event",
            "unauthorized_confidence",
            "narrator_style",
            "wrong_address",
            "off_topic",
            "unsupported_fact",
            "unhelpful_guidance",
        }
        codes = tuple(code for code in state["issues"] if code in allowed_codes)
        repair = ChatMessage(
            role="system",
            content=(
                "[task:dialogue_repair] Refaça a resposta à mensagem atual na sua própria voz. "
                "A revisão encontrou: " + ", ".join(codes) + ". "
                "Use exclusivamente fatos autorizados pertinentes; mantenha fontes e versões. "
                "Responda à pergunta diretamente. Preserve seus segredos privados. "
                "Retorne somente o objeto JSON com o campo fala, conforme o contrato."
            ),
        )
        prompt = state["prompt"]
        return {
            "prompt": (*prompt[:-1], repair, prompt[-1]),
            "repairs": state["repairs"] + 1,
            "fallback_reason": None,
            "role_disclosure": False,
        }

    def output_guard(self, state):
        _step(state, "output_guard")
        h = self.harness
        authorized = (
            (state["observations"] or {})
            .get("memoria_social", {})
            .get("confidencias_autorizadas", ())
        )
        decision = h._guard.inspect_output(
            state["content"],
            h._private_markers(state["profile"], state["npc"], authorized),
            allow_role_disclosure=state["role_disclosure"],
        )
        return {
            "allowed": decision.allowed,
            "fallback_reason": None if decision.allowed else "output_guard",
        }

    def fallback(self, state):
        _step(state, "fallback")
        audit = state["audit"]
        reason = (
            state.get("fallback_reason") or state.get("error_code") or "review_rejected"
        )
        audit.fallback, audit.error_code = True, state.get("error_code") or reason
        guarded = reason in {"input_guard", "output_guard"}
        return {
            "content": SAFE_DIALOGUE_REPLY if guarded else TECHNICAL_FALLBACK,
            "allowed": False,
            "assessment": None,
            "role_disclosure": False,
            "fallback_reason": reason,
        }

    def error(self, state):
        _step(state, "error")
        raise LLMUnavailableError(
            "O serviço de diálogo está temporariamente indisponível.",
            code=state.get("error_code") or "llm_unavailable",
        )

    async def persist(self, state):
        _step(state, "persist")
        from memorias_licantropicas.modules.session_master.reports import useful_report
        from memorias_licantropicas.modules.session_master.service import (
            DialogueAssessment,
        )
        from memorias_licantropicas.modules.achievements.rules import (
            discoveries_in_reply,
        )

        request, h = state["request"], self.harness
        assessment = state.get("assessment")
        useful = state["allowed"] and useful_report(
            state["content"],
            state["observations"],
            kind=assessment.kind if assessment else "conversation",
            quote=assessment.useful_quote if assessment else "",
            suggested=assessment.useful if assessment else False,
        )
        if assessment is not None:
            allowed = (
                (state["observations"] or {})
                .get("memoria_social", {})
                .get("descobertas_autorizadas", ())
            )
            assessment = assessment.model_copy(
                update={
                    "discovery_ids": discoveries_in_reply(
                        request.npc_id, state["content"], allowed
                    ),
                    "eligible_discovery_ids": tuple(allowed),
                    "useful": useful,
                    "useful_quote": state["content"][:2400] if useful else "",
                }
            )
        outgoing = ConversationMessage(
            id=uuid4(),
            sender_id=request.npc_id,
            content=state["content"],
            created_at=datetime.now(UTC),
            narrative_authorized=state["allowed"],
            useful=useful,
        )
        await self._assert_day(request)
        if h._session_master is not None:
            await h._session_master.persist_exchange(
                request.game_id,
                request.npc_id,
                request.conversation_id,
                state["incoming"],
                outgoing,
                assessment or DialogueAssessment(),
            )
        else:
            await h._memory.append_messages(
                request.game_id, request.conversation_id, (state["incoming"], outgoing)
            )
        response = state.get("response")
        guarded = state.get("fallback_reason") in {"input_guard", "output_guard"}
        return {
            "reply": HarnessReply(
                conversation_id=request.conversation_id,
                message=outgoing,
                model=("dialogue-guard" if guarded else "dialogue-fallback")
                if state["audit"].fallback
                else response.model,
                input_tokens=None if state["audit"].fallback else response.input_tokens,
                output_tokens=None
                if state["audit"].fallback
                else response.output_tokens,
            )
        }
