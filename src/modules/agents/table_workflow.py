"""Persona delivery: only canonical table content reaches the public transcript.

The model selects a delivery from a finite catalogue. It never supplies factual
prose, identities, dates, evidence weights, grants, or database operations.
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from src.contracts.assessment import DialogueAssessment
from src.contracts.model import ChatMessage, ConversationMessage, HarnessReply
from src.infrastructure.llm.structured import generate_structured
from src.infrastructure.usage import usage_scope
from src.modules.agents.guard import SAFE_DIALOGUE_REPLY
from src.modules.agents.trace import DialogueAudit
from src.modules.agents.workflow import DialogueRequest


class TableDelivery(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    tone: Literal['direct', 'cordial', 'reserved']


OPENINGS = {'direct': '', 'cordial': 'Pois bem, Floriano. ', 'reserved': 'Escute, detetive. '}


class TableDialogueWorkflow:
    def __init__(self, harness, table_service):
        self.harness, self.table = harness, table_service

    async def respond(self, game_id, npc_id, conversation_id, speaker_id, text):
        h = self.harness
        request = DialogueRequest(game_id, npc_id, conversation_id, speaker_id, text)
        audit = DialogueAudit()
        state = {'request': request, 'audit': audit}
        response = None
        try:
            async with asyncio.timeout(h._turn_timeout_seconds):
                authorized = await h._workflow.authorize(state)
                incoming, profile = authorized['incoming'], authorized['profile']
                audit.nodes.append('input_guard')
                guard = h._guard.inspect_input(text)
                statements = ()
                tone = 'direct'
                if not guard.allowed:
                    content = SAFE_DIALOGUE_REPLY
                    useful = False
                else:
                    audit.nodes.append('table_query')
                    prepared = await self.table.prepare(game_id, npc_id, speaker_id, text)
                    statements, content = prepared.statements, prepared.text
                    useful = bool(statements)
                    # The renderer never receives secret values, biographies,
                    # private objectives, raw user prose, history or the table.
                    prompt = (
                        ChatMessage(role='system', content='[task:table_delivery] Escolha apenas o tom de uma fala já decidida pela mesa. Use a ferramenta. Nenhum fato pode ser criado ou alterado.'),
                        ChatMessage(role='user', content=json.dumps({'personagem': profile.name, 'voz': profile.personality,
                            'tipos_de_relato': [item.kind for item in statements]}, ensure_ascii=False)),
                    )
                    audit.nodes.append('delivery')
                    audit.attempts += 1
                    try:
                        async with asyncio.timeout(min(5., h._turn_timeout_seconds / 3)):
                            with usage_scope(game_id, 'table_delivery', npc_id):
                                result = await generate_structured(h._llm, prompt, TableDelivery, max_attempts=1)
                        response = result.response
                        if result.ok:
                            tone = result.value.tone
                        else:
                            audit.error_code = result.error_code
                    except Exception as error:
                        # Authoritative information is still available when the
                        # optional delivery provider is unavailable.
                        audit.error_code = getattr(error, 'code', 'delivery_unavailable')
                    content = OPENINGS[tone] + content
                await h._workflow._assert_day(request)
                outgoing = ConversationMessage(id=uuid4(), sender_id=npc_id, content=content,
                    created_at=datetime.now(UTC), narrative_authorized=guard.allowed,
                    useful=useful, generation_status='accepted' if guard.allowed else 'guarded')
                assessment = DialogueAssessment(source='local', useful=useful,
                    useful_quote=content[:2400] if useful else '', table_statements=statements)
                audit.nodes.append('persist_table')
                await h._session_master.persist_exchange(game_id, npc_id, conversation_id, incoming, outgoing, assessment)
                audit.status = 'completed'
                return HarnessReply(conversation_id=conversation_id, message=outgoing,
                    model=response.model if response else 'canonical-table',
                    input_tokens=response.input_tokens if response else None,
                    output_tokens=response.output_tokens if response else None)
        finally:
            await h._workflow._record_trace(request, audit)
