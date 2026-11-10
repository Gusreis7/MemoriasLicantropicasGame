"""Inspectable table graph; canonical facts and Redis/outbox remain authoritative.

Only preparation and commit reserve player actions. Cosmetic inference runs
between those reservations and cannot commit a stale or unauthorized disclosure.
"""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, nullcontext
from datetime import UTC, datetime
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.errors import NodeCancelledError
from langsmith import tracing_context

from src.contracts.assessment import DialogueAssessment
from src.contracts.errors import AccessDeniedError, ConflictError, LLMUnavailableError, NotFoundError, StorageUnavailableError
from src.contracts.model import ConversationMessage, HarnessReply
from src.infrastructure.llm.structured import generate_structured
from src.infrastructure.usage import usage_scope
from src.modules.agents.guard import SAFE_DIALOGUE_REPLY
from src.modules.agents.table_delivery import TableDeliveryPlan, delivery_options, delivery_prompt, render_delivery
from src.modules.agents.trace import DialogueAudit
from src.modules.agents.workflow import DialogueRequest, DialogueState
from src.modules.table.service import PreparedTableTurn


class TableDialogueState(DialogueState, total=False):
    action_scope: Callable[[], AbstractAsyncContextManager[None]]
    prepared: PreparedTableTurn | None
    day: int
    options: tuple[tuple[str, ...], ...]
    previous: str | None
    delivery_plan: TableDeliveryPlan | None


def _facts(prepared):
    # Timestamps are assigned at query time; all factual/permission fields count.
    return (prepared.text, prepared.topic_status, tuple(
        item.model_dump(exclude={'created_at'}) for item in prepared.statements))


class TableDialogueWorkflow:
    def __init__(self, harness, table_service):
        self.harness, self.table = harness, table_service
        graph = StateGraph(TableDialogueState)
        graph.add_node('prepare_table', self.prepare)
        graph.add_node('native_table_delivery', self.deliver)
        graph.add_node('revalidate_persist', self.persist)
        graph.add_edge(START, 'prepare_table')
        graph.add_conditional_edges('prepare_table',
            lambda state: 'native_table_delivery' if state['allowed'] else 'revalidate_persist',
            {'native_table_delivery': 'native_table_delivery', 'revalidate_persist': 'revalidate_persist'})
        graph.add_edge('native_table_delivery', 'revalidate_persist')
        graph.add_edge('revalidate_persist', END)
        self.graph = graph.compile(name='npc_table_dialogue')

    async def respond(self, game_id, npc_id, conversation_id, speaker_id, text, *, action_scope=None):
        request = DialogueRequest(game_id, npc_id, conversation_id, speaker_id, text)
        audit = DialogueAudit()
        try:
            # As with the legacy graph, never export prompts or secret game state.
            with tracing_context(enabled=False, parent=False):
                async with asyncio.timeout(self.harness._turn_timeout_seconds):
                    result = await self.graph.ainvoke(
                        {'request': request, 'audit': audit, 'action_scope': action_scope or nullcontext},
                        config={'recursion_limit': 8})
            audit.status = 'fallback' if audit.fallback else 'completed'
            return result['reply']
        except TimeoutError:
            audit.status, audit.error_code = 'error', 'llm_timeout'
            raise LLMUnavailableError('O diálogo excedeu seu prazo total.', code='llm_timeout') from None
        except asyncio.CancelledError:
            audit.status, audit.error_code = 'cancelled', 'cancelled'
            raise
        except NodeCancelledError:
            # LangGraph wraps cancellation raised by a node without task.cancel().
            audit.status, audit.error_code = 'cancelled', 'cancelled'
            raise asyncio.CancelledError() from None
        except Exception as error:
            # Unexpected bugs propagate; only a stable category enters the trace.
            audit.status = 'error'
            audit.error_code = (error.code if isinstance(error, LLMUnavailableError)
                else type(error).__name__ if isinstance(error,
                    (AccessDeniedError, ConflictError, NotFoundError, StorageUnavailableError))
                else 'internal_error')
            raise
        finally:
            await self.harness._workflow._record_trace(request, audit)

    async def prepare(self, state):
        h, request, audit = self.harness, state['request'], state['audit']
        async with state['action_scope']():
            authorized = await h._workflow.authorize(state)
            audit.nodes.append('input_guard')
            allowed = h._guard.inspect_input(request.text).allowed
            day = (await self.table.turns.require_day_locked(request.game_id)).day
            prepared = None
            options, previous = (), None
            if allowed:
                audit.nodes.append('table_query')
                prepared = await self.table.prepare(request.game_id, request.npc_id, request.speaker_id, request.text)
                profiles = await h._characters.list()
                options = delivery_options(prepared, {profile.id: profile.name for profile in profiles})
                previous = next((message.content[:2400] for message in reversed(authorized['history'])
                    if message.sender_id == request.npc_id and message.narrative_authorized
                    and message.generation_status == 'accepted'
                    and h._guard.inspect_output(message.content).allowed), None)
            return {**authorized, 'allowed': allowed, 'prepared': prepared, 'day': day,
                'options': options, 'previous': previous, 'delivery_plan': None,
                'response': None, 'content': prepared.text if prepared else SAFE_DIALOGUE_REPLY}

    @staticmethod
    def fallback(state, code):
        audit = state['audit']
        audit.fallback, audit.error_code = True, code
        audit.nodes.append('canonical_delivery_fallback')
        return {}  # Preparation already installed the canonical answer.

    async def deliver(self, state):
        h, request, audit = self.harness, state['request'], state['audit']
        audit.nodes.append('native_table_delivery')
        # Only expected transport/contract failures use canonical delivery.
        # Provider diagnostics returned by generate_structured remain distinct.
        try:
            async with asyncio.timeout(min(8.0, h._turn_timeout_seconds / 10)):
                audit.attempts += 1
                with usage_scope(request.game_id, 'table_delivery', request.npc_id):
                    generated = await generate_structured(h._llm,
                        delivery_prompt(state['profile'], state['prepared'], state['options'], state['previous']),
                        TableDeliveryPlan, max_attempts=1)
        except TimeoutError:
            return self.fallback(state, 'llm_timeout')
        if not generated.ok:
            return self.fallback(state, generated.error_code)
        try:
            candidate = render_delivery(generated.value, state['options'])
        except ValueError:
            return self.fallback(state, 'delivery_invalid_plan')
        if not h._guard.inspect_output(candidate).allowed:
            return self.fallback(state, 'delivery_unsafe_output')
        return {'content': candidate, 'response': generated.response, 'delivery_plan': generated.value}

    async def persist(self, state):
        h, request, audit = self.harness, state['request'], state['audit']
        async with state['action_scope']():
            audit.nodes.append('revalidate_table')
            await h._workflow._assert_day(request)
            case = await self.table.turns.require_day_locked(request.game_id)
            if case.day != state['day']:
                raise ConflictError('O dia mudou durante a conversa; faça a pergunta novamente.')
            prepared = state['prepared']
            if state['allowed']:
                current = await self.table.prepare(request.game_id, request.npc_id, request.speaker_id, request.text)
                if _facts(current) != _facts(prepared):
                    raise ConflictError('As informações da mesa mudaram; faça a pergunta novamente.')
            statements = prepared.statements if prepared else ()
            content, response = state['content'], state['response']
            useful = bool(statements)
            outgoing = ConversationMessage(id=uuid4(), sender_id=request.npc_id, content=content,
                created_at=datetime.now(UTC), narrative_authorized=state['allowed'], useful=useful,
                generation_status='accepted' if state['allowed'] else 'guarded')
            assessment = DialogueAssessment(source='local', useful=useful,
                useful_quote=content[:2400] if useful else '', table_statements=statements,
                table_delivery_plan=state['delivery_plan'])
            audit.nodes.append('persist_table')
            await h._session_master.persist_exchange(request.game_id, request.npc_id,
                request.conversation_id, state['incoming'], outgoing, assessment)
            return {'reply': HarnessReply(conversation_id=request.conversation_id, message=outgoing,
                model=response.model if response else 'canonical-table',
                input_tokens=response.input_tokens if response else None,
                output_tokens=response.output_tokens if response else None)}
