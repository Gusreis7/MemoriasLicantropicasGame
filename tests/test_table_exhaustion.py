"""Exhaustion depends on disclosed facts, not word-for-word repeated questions."""
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.contracts.table import TableState, NightRecord, NightPresence
from src.modules.table.service import GameTableService
from src.modules.table.rules import disclose_statements

pytestmark = pytest.mark.anyio
NOW = datetime(2026, 11, 9, tzinfo=UTC)


class Turns:
    def __init__(self):
        self.case = SimpleNamespace(day=2, table=TableState(nights=(self.night(1),)), crimes=(),
                                    active_evidence_by_npc={}, testimonies=())

    @staticmethod
    def night(day):
        return NightRecord(id=uuid4(), day=day, created_at=NOW,
            presences=(NightPresence(id=uuid4(), npc_id='capitu', day=day, location_id='cabana_capitu'),))

    async def require_day_locked(self, game_id):
        return self.case

    def now(self):
        return NOW


class Characters:
    async def list(self):
        return (SimpleNamespace(id='capitu', name='Capitu'),)


@pytest.fixture
def table(monkeypatch):
    async def no_knowledge(*args, **kwargs):
        return ()
    monkeypatch.setattr('src.modules.agents.table_agent.prepare_knowledge_turn', no_knowledge)
    turns = Turns()
    return GameTableService(turns, Characters(), None), turns, uuid4()


async def test_unknown_topic_admits_not_knowing_and_invites_another_subject(table):
    service, _, game = table
    result = await service.prepare(game, 'capitu', 'player', 'Qual a distância até Saturno?')
    assert result.topic_status == 'unknown' and not result.statements
    assert 'Não sei' in result.text and 'outra coisa' in result.text


async def test_disclosed_alibi_is_exhausted_even_for_a_differently_worded_question(table):
    service, turns, game = table
    first = await service.prepare(game, 'capitu', 'player', 'Onde passou a noite 1?')
    assert first.statements and first.topic_status == 'information'
    turns.case.table = disclose_statements(turns.case.table, first.statements)
    again = await service.prepare(game, 'capitu', 'player', 'Qual seu álibi na noite 1?')
    assert again.topic_status == 'exhausted' and not again.statements
    assert 'Não sei de mais nada' in again.text and 'outra coisa' in again.text


async def test_new_night_reopens_topic_and_recipient_has_separate_disclosure(table):
    service, turns, game = table
    first = await service.prepare(game, 'capitu', 'player', 'Onde passou a noite 1?')
    turns.case.table = disclose_statements(turns.case.table, first.statements)
    peer = await service.prepare(game, 'capitu', 'escobar', 'Onde passou a noite 1?')
    assert peer.statements and peer.statements[0].recipient_id == 'escobar'
    turns.case.day = 3
    turns.case.table = turns.case.table.model_copy(update={'nights': (*turns.case.table.nights, turns.night(2))})
    fresh = await service.prepare(game, 'capitu', 'player', 'Onde passou a noite 2?')
    assert fresh.statements and fresh.statements[0].day == 2


async def test_explicit_repeat_can_restate_a_known_alibi(table):
    service, turns, game = table
    first = await service.prepare(game, 'capitu', 'player', 'Onde passou a noite 1?')
    turns.case.table = disclose_statements(turns.case.table, first.statements)
    result = await service.prepare(game, 'capitu', 'player', 'Repita seu álibi da noite 1.')
    assert result.statements and result.statements[0].id == first.statements[0].id
    assert result.text == first.text


from test_table_knowledge import table_knowledge


async def test_gossip_exposes_next_eligible_facts_before_declaring_exhaustion(table_knowledge, game):
    from src.modules.agents.table_agent import PersonaTableAgent
    knowledge, _ = table_knowledge
    agent = PersonaTableAgent(knowledge, game.id, 'capitu')
    first = await agent.query('Conte fofocas.', NOW)
    known = {item.id for item in first}
    second = await agent.query('Conte fofocas.', NOW, excluded_statement_ids=known)
    assert second and not known & {item.id for item in second}
    assert all(item.speaker_id == 'capitu' and item.kind == 'gossip' for item in second)


async def test_new_source_version_reopens_same_root_without_new_independent_root():
    from src.contracts.social import KnowledgeEntry
    from src.modules.agents.table_agent import PersonaTableAgent
    root = uuid4()
    first_entry = KnowledgeEntry(id=uuid4(), owner_id='capitu', root_id=root,
        source_message_id=uuid4(), speaker_id='player', source_span='Ouvi dizer que aconteceu.',
        proposition='Ouvi dizer que aconteceu.', kind='report', created_at=NOW)

    class Knowledge:
        _characters = Characters()
        entries = (first_entry,)

        async def shared_entries(self, *args):
            return self.entries

    knowledge = Knowledge()
    turns = Turns()
    game = uuid4()
    service = GameTableService(turns, Characters(), knowledge)
    first = await service.prepare(game, 'capitu', 'player', 'Conte fofocas.')
    turns.case.table = disclose_statements(turns.case.table, first.statements)
    exhausted = await service.prepare(game, 'capitu', 'player', 'Conte fofocas.')
    assert exhausted.topic_status == 'exhausted'
    correction = first_entry.model_copy(update={'id': uuid4(), 'source_message_id': uuid4(),
        'kind': 'correction', 'proposition': 'Corrijo o relato: isso não aconteceu.'})
    knowledge.entries = (correction,)
    revised = await service.prepare(game, 'capitu', 'player', 'Conte fofocas.')
    assert revised.topic_status == 'information' and len(revised.statements) == 1
    assert revised.statements[0].id != first.statements[0].id
    assert revised.statements[0].source_ids == (correction.id,)
    assert revised.statements[0].text == correction.proposition
    assert revised.statements[0].root_id == first.statements[0].root_id == root
    saved = disclose_statements(turns.case.table, revised.statements)
    assert len(saved.statements) == 2
    assert len({statement.root_id for statement in saved.statements}) == 1
