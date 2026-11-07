"""Persona delivery: only canonical table content reaches the public transcript.

Delivery tone is local and deterministic. Models never delay canonical table
answers or supply identities, dates, evidence weights, grants or database operations.
"""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from src.contracts.assessment import DialogueAssessment
from src.contracts.model import ConversationMessage, HarnessReply
from src.modules.agents.guard import SAFE_DIALOGUE_REPLY
from src.modules.agents.trace import DialogueAudit
from src.modules.agents.workflow import DialogueRequest


OPENINGS = {'direct': '', 'cordial': 'Pois bem, Floriano. ', 'reserved': 'Escute, detetive. '}
TONES = {'bacamarte': 'direct', 'bentinho': 'reserved', 'capitu': 'reserved',
         'escobar': 'cordial', 'florenca': 'cordial', 'rubiao': 'cordial', 'virgilia': 'reserved'}


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
                tone = 'direct'
                if not guard.allowed:
                    content = SAFE_DIALOGUE_REPLY
                    useful = False
                else:
                    audit.nodes.append('table_query')
                    prepared = await self.table.prepare(game_id, npc_id, speaker_id, text)
                    statements, content = prepared.statements, prepared.text
                    useful = bool(statements)
                    # This cosmetic choice must not reserve the player while waiting for a model.
                    tone = TONES.get(npc_id, 'direct')
                    audit.nodes.append('local_delivery')
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
                    model='canonical-table', input_tokens=None, output_tokens=None)
        finally:
            await h._workflow._record_trace(request, audit)
