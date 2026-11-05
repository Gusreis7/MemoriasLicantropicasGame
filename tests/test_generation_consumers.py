"""Falhas externas são tipadas; pareceres não escolhem metadados internos."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from memorias_licantropicas.contracts.errors import StorageUnavailableError
from memorias_licantropicas.contracts.model import ConversationMessage, LLMResponse
from memorias_licantropicas.modules.session_master.service import SessionMasterService

pytestmark = pytest.mark.anyio


def exchange():
    return (
        ConversationMessage(id=uuid4(), sender_id="player", content="O que sabe sobre Capitu?", created_at=datetime.now(UTC)),
        ConversationMessage(id=uuid4(), sender_id="escobar", content="Capitu e Bentinho vivem juntos; o ciúme dele é conhecido.", created_at=datetime.now(UTC)),
    )


class Turns:
    async def require_day_locked(self, game_id):
        return SimpleNamespace(day=1)


class Client:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        return LLMResponse(content=self.value, model="contract-fixture")


@pytest.mark.parametrize("output", [
    '```json\n{"kind":"conversation"}\n```',
    '{"issues":[{"type":"off_topic"}]}',
    '{"kind":"conversation","source":"local"}',
    '{"kind":"conversation","discovery_ids":["escobar_affection"]}',
    '{"kind":"conversation","corrected_reply":"SEGREDO_INTERNO"}',
    '{"kind":"conversation","repair_support_id":"arbitrary"}',
    '{"own_assertion":"true"}',
])
async def test_master_rejects_shape_repairs_coercions_and_control_fields(output):
    client = Client(output)
    master = SessionMasterService(Turns(), None, None, client)
    incoming, outgoing = exchange()
    assessment = await master.assess(uuid4(), "escobar", uuid4(), incoming, outgoing)
    assert client.calls == 2
    assert assessment.source == "fallback" and assessment.error_code in {"invalid_json", "invalid_schema"}
    assert not assessment.discovery_ids and not assessment.useful and not assessment.surrender
    assert assessment.corrected_reply is None


async def test_useful_report_requires_a_literal_quote_from_the_npc():
    client = Client(json.dumps({"useful": True, "useful_quote": "Uma fala que o NPC nunca disse."}))
    master = SessionMasterService(Turns(), None, None, client)
    incoming, outgoing = exchange()
    assessment = await master.assess(uuid4(), "escobar", uuid4(), incoming, outgoing)
    assert assessment.source == "model" and not assessment.useful
    assert assessment.useful_quote == ""


async def test_corrupt_session_outbox_is_preserved_for_recovery_without_exposing_content(storage):
    master = SessionMasterService(Turns(), None, None, redis=storage.client, prefix=storage.prefix)
    game_id, conversation_id = uuid4(), uuid4()
    key = master._key(game_id, conversation_id)
    await storage.client.set(key, '{"SECRET_BAD_RECORD": true}')
    with pytest.raises(StorageUnavailableError) as failure:
        await master.reconcile(game_id, conversation_id)
    assert "SECRET_BAD_RECORD" not in str(failure.value)
    assert await storage.client.exists(key)
