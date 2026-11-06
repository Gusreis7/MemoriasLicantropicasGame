"""O dossiê depende de declarações estruturadas, não de palavras da persona."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.contracts.errors import NotFoundError
from src.contracts.investigation import InvestigationState
from src.contracts.table import TableState, TableStatement
from src.modules.investigation.scoring import assess_dossier


NOW = datetime(2026, 11, 5, tzinfo=UTC)


def statement(kind, speaker, subject="escobar", *, day=1, root=None, status=None, recipient="player", text="Uma fala qualquer."):
    identifier = uuid4()
    return TableStatement(id=identifier, kind=kind, speaker_id=speaker,
        recipient_id=recipient, subject_id=subject, day=day, period="night",
        source_ids=(uuid4(),), root_id=root or uuid4(), alibi_status=status,
        text=text, created_at=NOW)


def case(*statements):
    return InvestigationState(game_id=uuid4(), phase_ends_at=NOW,
                              table=TableState(statements=statements))


def assess(state, suspect="escobar", reports=None):
    reports = tuple(record.id for record in state.table.statements) if reports is None else reports
    return assess_dossier(state, suspect, (), (), reports)


def test_prose_cannot_change_subject_or_alibi_status():
    alone = statement("alibi", "escobar", status="alone", text="Não digo a palavra sozinho.")
    suspicion = statement("suspicion", "bentinho", text="Capitu, Rubião, ninguém, acompanhado.")
    state = case(alone, suspicion)
    original = assess(state)
    rewritten = state.model_copy(update={"table": TableState(statements=(
        alone.model_copy(update={"text": "Estive acompanhado de todos."}),
        suspicion.model_copy(update={"text": "Não repetirei nomes."}),
    ))})
    assert original.total == assess(rewritten).total == 4
    assert assess(state, "capitu").total == 0


@pytest.mark.parametrize("status", ("accompanied", "partial", "unavailable"))
def test_only_alone_not_waiting_confirmation_is_suspicious(status):
    record = statement("alibi", "escobar", status=status, text="sozinho ninguém sem companhia")
    assert assess(case(record)).total == 0


def test_unselected_private_and_foreign_reports_never_count():
    record = statement("alibi", "escobar", status="alone")
    state = case(record)
    assert assess(state, reports=()).total == 0
    with pytest.raises(NotFoundError):
        assess(state, reports=(uuid4(),))
    private = record.model_copy(update={"recipient_id": "capitu"})
    with pytest.raises(NotFoundError):
        assess(case(private))


def test_retransmission_and_repeated_speaker_do_not_create_independent_sources():
    root = uuid4()
    alone = statement("alibi", "escobar", status="alone")
    first = statement("suspicion", "bentinho", root=root)
    repeated = statement("suspicion", "capitu", root=root)
    assert assess(case(alone, first, repeated)).total == 4
    assert not assess(case(alone, first, repeated)).accepted
    same_speaker = statement("suspicion", "bentinho")
    assert not assess(case(alone, first, same_speaker)).accepted
    independent = statement("sighting", "capitu")
    assert assess(case(alone, first, independent)).custody_route == "witness_reports"


def test_witness_route_requires_same_night_as_selected_alibi():
    alone = statement("alibi", "escobar", status="alone", day=0)
    first = statement("suspicion", "bentinho", day=1)
    second = statement("sighting", "capitu", day=1)
    assert not assess(case(alone, first, second)).accepted


def test_one_id_attached_twice_has_exactly_the_same_weight():
    alone = statement("alibi", "escobar", status="alone")
    state = case(alone)
    assert assess(state, reports=(alone.id, alone.id)).total == 2


def test_selected_confirmed_alibi_cancels_only_same_night_report_weight():
    root = uuid4()
    own = statement("alibi", "escobar", status="accompanied", root=root).model_copy(
        update={"companion_ids": ("capitu",), "location_id": "cafe_largo"})
    companion = statement("alibi", "capitu", subject="capitu", status="accompanied", root=root).model_copy(
        update={"companion_ids": ("escobar",), "location_id": "cafe_largo"})
    accusation = statement("suspicion", "bentinho", day=1)
    state = case(own, companion, accusation)
    assert assess(state, reports=(accusation.id,)).total == 2
    assert assess(state, reports=(own.id, accusation.id)).total == 0
    other_night = statement("suspicion", "bentinho", day=2)
    state = case(own, companion, other_night)
    assert assess(state, reports=(own.id, other_night.id)).total == 2
