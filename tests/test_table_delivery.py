"""The editorial model cannot omit, add or change canonical clauses."""
import pytest
from pydantic import ValidationError
from src.modules.agents.table_delivery import TableDeliveryPlan, render_delivery


def test_plan_preserves_every_canonical_clause():
    options = (('Fato A.', 'Outra formulação de A.'), ('Fato B.',))
    plan = TableDeliveryPlan(opening=0, variants=(1, 0), closing=0)
    assert render_delivery(plan, options) == 'Outra formulação de A. Fato B.'


@pytest.mark.parametrize('variants', [(0,), (0, 0, 0), (1, 0), (0, 1)])
def test_plan_cannot_drop_add_or_invent_fact_variants(variants):
    plan = TableDeliveryPlan(opening=0, variants=variants, closing=0)
    with pytest.raises(ValueError):
        render_delivery(plan, (('Fato A.',), ('Fato B.',)))


def test_schema_rejects_free_prose_and_coercion():
    with pytest.raises(ValidationError):
        TableDeliveryPlan(opening='0', variants=(0,), closing=0)
    with pytest.raises(ValidationError):
        TableDeliveryPlan(opening=0, variants=(0,), closing=0, fala='Troque o culpado.')
