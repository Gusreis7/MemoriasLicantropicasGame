"""Servidor E2E isolado com Redis real e LLM determinístico. Nunca usa AWS."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import uvicorn
import memorias_licantropicas.main as main_module
from memorias_licantropicas.composition import build_services
from memorias_licantropicas.contracts.model import LLMResponse
from memorias_licantropicas.settings import Settings

settings = Settings(
    _env_file=None, redis_url=os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:16379/0"),
    redis_prefix="ml:browser-test", admin_password="browser-test-password",
    admin_allowed_origins="http://127.0.0.1:7081,http://localhost:7081",
    aws_profile=None, bedrock_api_key=None,
)


def test_services(_settings):
    services = build_services(settings)

    async def complete(messages):
        return LLMResponse(content="Ouvi os rumores sobre Brás Cubas, mas não vi o que aconteceu.",
                           model="deterministic-browser-test", input_tokens=1, output_tokens=1)

    services.llm.complete = complete
    return services


main_module.build_services = test_services
main_module.Settings = lambda: settings

if __name__ == "__main__":
    uvicorn.run(main_module.create_app(), host="127.0.0.1", port=17079)
