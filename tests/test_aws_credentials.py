from datetime import timedelta

import pytest
from botocore.exceptions import ProfileNotFound

import memorias_licantropicas.infrastructure.llm.aws_credentials as module
from memorias_licantropicas.contracts.errors import LLMUnavailableError

pytestmark = pytest.mark.anyio


async def test_profile_and_region_reach_token_generator_without_aws(monkeypatch):
    seen = {}
    credentials = object()

    class Session:
        def __init__(self, profile):
            seen["profile"] = profile

        def get_credentials(self):
            return credentials

    def generate(**kwargs):
        assert kwargs["aws_credentials_provider"].load() is credentials
        assert kwargs["region"] == "us-east-1"
        assert kwargs["expiry"] == timedelta(minutes=15)
        return "test-token"

    monkeypatch.setattr(module, "Session", Session)
    monkeypatch.setattr(module, "provide_token", generate)
    provider = module.ProfileTokenProvider("terraform", "us-east-1")
    assert await provider.get_token() == "test-token"
    assert seen["profile"] == "terraform"


@pytest.mark.parametrize("failure", [ProfileNotFound(profile="private-profile"), RuntimeError("private-profile")])
async def test_missing_profile_is_sanitized(monkeypatch, failure):
    def fail(**kwargs):
        raise failure
    monkeypatch.setattr(module, "provide_token", fail)
    with pytest.raises(LLMUnavailableError) as error:
        await module.ProfileTokenProvider("terraform", "us-east-1").get_token()
    assert "private-profile" not in str(error.value)
