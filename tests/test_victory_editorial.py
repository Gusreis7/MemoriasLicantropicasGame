"""O mestre publica opinião assinada a partir do desfecho e autoria reais."""

from native_fixtures import tool_response, respond_to_tools, invalid_tool_response
import json
from datetime import UTC, datetime

import pytest

from src.contracts.model import LLMResponse
from src.modules.investigation.rules import (
    make_initial_investigation,
    make_crime,
)
from src.modules.session_master.editorial import (
    final_edition,
    SIGNATURE,
)
from src.modules.session_master.service import SessionMasterService

pytestmark = pytest.mark.anyio
NOW = datetime(2026, 11, 4, tzinfo=UTC)


@pytest.mark.parametrize("method", ["detention", "confession", "assembly"])
@pytest.mark.parametrize("unavailable", [False, True])
async def test_signed_editorial_uses_actual_deaths_and_method(
    game, method, unavailable
):
    names = {"bentinho": "Bentinho", "capitu": "Capitu", "escobar": "Escobar"}
    state = make_initial_investigation(game, NOW)
    wolf_crime = make_crime(
        game, 1, "capitu", "praca_verde", NOW, killer_id="bentinho", cause="werewolf"
    )
    human_crime = make_crime(
        game, 1, "escobar", "praca_verde", NOW, killer_id="capitu", cause="civil"
    )
    state = state.model_copy(
        update={
            "status": "won",
            "phase": "finished",
            "ending_method": method,
            "crimes": (wolf_crime, human_crime),
        }
    )
    state = state.model_copy(
        update={
            "journal": (
                *state.journal,
                final_edition(state, names, werewolf_id="bentinho"),
            )
        }
    )
    calls = []

    class LLM:
        async def complete(self, prompt, *, tools=(), tool_choice=None):
            calls.append(prompt)
            if unavailable:
                from src.contracts.errors import LLMUnavailableError

                raise LLMUnavailableError("offline")
            return tool_response(
                {
                    "opinion": "A persistência de Floriano merece o reconhecimento desta cidade. Que o alívio de hoje nos ensine a preservar a memória das vítimas e a exigir justiça."
                },
                "EditorialProposal",
                model="fake",
            )

    from src.modules.session_master.editorial import victory_article
    edition = await victory_article(state, names, 'bentinho', LLM())
    result = state.model_copy(update={'journal': (*state.journal[:-1], edition)})
    body = result.journal[-1].body
    assert "Bentinho era o lobisomem" in body
    assert "Capitu (1)" in body
    assert "Escobar" not in body
    assert body.endswith(SIGNATURE)
    assert len(result.journal) == len(state.journal)
    assert result.status == "won"
    payload = json.loads(calls[0][-1].content)
    assert "Capitu" in payload["fatos_confirmados"]
    assert "Escobar" not in payload["fatos_confirmados"]
    assert ("persistência de Floriano" in body) != unavailable
