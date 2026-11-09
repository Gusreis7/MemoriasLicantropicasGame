"""Persona delivery: only canonical table content reaches the public transcript.

A bounded native editorial plan selects authorized equivalent clauses. The model
cannot alter identities, dates, evidence weights, grants or database operations.
"""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from src.contracts.assessment import DialogueAssessment
from src.contracts.model import ConversationMessage, HarnessReply
from src.modules.agents.guard import SAFE_DIALOGUE_REPLY
from src.modules.agents.trace import DialogueAudit
from src.modules.agents.workflow import DialogueRequest
from src.infrastructure.llm.structured import generate_structured
from src.infrastructure.usage import usage_scope
from src.modules.agents.table_delivery import (TableDeliveryPlan, delivery_options, delivery_prompt, render_delivery)


class TableDialogueWorkflow:
    def __init__(self, harness, table_service):
        self.harness, self.table = harness, table_service

    async def respond(self, game_id, npc_id, conversation_id, speaker_id, text):
        h = self.harness
        request = DialogueRequest(game_id, npc_id, conversation_id, speaker_id, text)
        audit = DialogueAudit()
        state = {'request': request, 'audit': audit}
        try:
            async with asyncio.timeout(h._turn_timeout_seconds):
                authorized = await h._workflow.authorize(state)
                incoming = authorized['incoming']
                audit.nodes.append('input_guard')
                guard = h._guard.inspect_input(text)
                statements = ()
                response = None
                delivery_plan = None
                if not guard.allowed:
                    content = SAFE_DIALOGUE_REPLY
                    useful = False
                else:
                    audit.nodes.append('table_query')
                    prepared = await self.table.prepare(game_id, npc_id, speaker_id, text)
                    statements, content = prepared.statements, prepared.text
                    useful = bool(statements)
                    profiles = await h._characters.list()
                    options = delivery_options(prepared, {profile.id: profile.name for profile in profiles})
                    previous = next((message.content[:2400] for message in reversed(authorized['history'])
                        if message.sender_id == npc_id and message.narrative_authorized
                        and message.generation_status == 'accepted'
                        and h._guard.inspect_output(message.content).allowed), None)
                    audit.nodes.append('native_table_delivery')
                    try:
                        # Cosmetic inference gets a small independent budget, preserving time to persist facts.
                        async with asyncio.timeout(min(8.0, h._turn_timeout_seconds / 10)):
                            audit.attempts += 1
                            with usage_scope(game_id, 'table_delivery', npc_id):
                                generated = await generate_structured(h._llm,
                                    delivery_prompt(authorized['profile'], prepared, options, previous),
                                    TableDeliveryPlan, max_attempts=1)
                        if not generated.ok:
                            raise ValueError('delivery_invalid_plan')
                        candidate = render_delivery(generated.value, options)
                        if not h._guard.inspect_output(candidate).allowed:
                            raise ValueError('delivery_unsafe_output')
                        content, response = candidate, generated.response
                        delivery_plan = generated.value
                    except Exception:
                        # A cosmetic failure never fabricates or suppresses a canonical statement.
                        audit.fallback = True
                        audit.error_code = 'table_delivery_fallback'
                        audit.nodes.append('canonical_delivery_fallback')
                await h._workflow._assert_day(request)
                outgoing = ConversationMessage(id=uuid4(), sender_id=npc_id, content=content,
                    created_at=datetime.now(UTC), narrative_authorized=guard.allowed,
                    useful=useful, generation_status='accepted' if guard.allowed else 'guarded')
                assessment = DialogueAssessment(source='local', useful=useful,
                    useful_quote=content[:2400] if useful else '', table_statements=statements,
                    table_delivery_plan=delivery_plan)
                audit.nodes.append('persist_table')
                await h._session_master.persist_exchange(game_id, npc_id, conversation_id, incoming, outgoing, assessment)
                audit.status = 'completed'
                return HarnessReply(conversation_id=conversation_id, message=outgoing,
                    model=response.model if response else 'canonical-table',
                    input_tokens=response.input_tokens if response else None,
                    output_tokens=response.output_tokens if response else None)
        finally:
            await h._workflow._record_trace(request, audit)
