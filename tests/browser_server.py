"""Servidor E2E isolado com Redis real e LLM determinístico. Nunca usa AWS."""

import os
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import uvicorn
import memorias_licantropicas.main as main_module
from memorias_licantropicas.composition import build_services
from memorias_licantropicas.contracts.model import LLMResponse
from memorias_licantropicas.settings import Settings
from pydantic import BaseModel, ConfigDict, Field

clock_offset = [0.0]


class ClockAdvance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seconds: float = Field(default=0, ge=0, le=10000)
    reset: bool = False

settings = Settings(
    _env_file=None, redis_url=os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:16379/0"),
    redis_prefix="ml:browser-test", admin_password="browser-test-password",
    admin_allowed_origins="http://127.0.0.1:7081,http://localhost:7081",
    aws_profile=None, bedrock_api_key=None,
)


def test_services(_settings):
    services = build_services(settings)
    clock = lambda: datetime.now(UTC) + timedelta(seconds=clock_offset[0])
    services.turns._clock = clock
    services.world._clock = clock

    async def complete(messages):
        # Reproduz o envelope que antes aparecia literalmente na interface.
        profile = json.loads(messages[0].content.split("Ficha privada:\n", 1)[1])
        return LLMResponse(content=json.dumps({"remetente": profile["id"],
                           "fala": "Ouvi os rumores sobre Brás Cubas, mas não vi o que aconteceu."}),
                           model="deterministic-browser-test", input_tokens=1, output_tokens=1)

    services.llm.complete = complete
    return services


main_module.build_services = test_services
main_module.Settings = lambda: settings

if __name__ == "__main__":
    app = main_module.create_app()

    @app.post("/api/__test__/clock")
    async def advance_clock(body: ClockAdvance):
        # Rota exclusiva deste executável de teste. Não existe na aplicação/Docker.
        clock_offset[0] = body.seconds if body.reset else clock_offset[0] + body.seconds
        return {"offset": clock_offset[0]}

    uvicorn.run(app, host="127.0.0.1", port=17079)
