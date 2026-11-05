from datetime import timedelta
import traceback

import pytest
from botocore.exceptions import ProfileNotFound

import src.infrastructure.llm.aws_credentials as module
from src.contracts.errors import LLMUnavailableError

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


@pytest.mark.parametrize("failure", [ProfileNotFound(profile="private-profile"), RuntimeError("private-profile"), OSError("private-cache")])
async def test_missing_profile_is_sanitized(monkeypatch, failure):
    def fail(**kwargs):
        raise failure
    monkeypatch.setattr(module, "provide_token", fail)
    provider = module.ProfileTokenProvider("terraform", "us-east-1")
    with pytest.raises(LLMUnavailableError) as error:
        await provider.get_token()
    assert error.value.code == "llm_credentials_unavailable"
    assert "private-profile" not in str(error.value)
    formatted = "".join(traceback.format_exception(error.value))
    assert all(secret not in formatted for secret in ("private-profile", "private-cache", "terraform"))


async def test_expired_container_cache_refreshes_from_mounted_profile(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_cache = source / "login" / "cache" / "session.json"
    source_cache.parent.mkdir(parents=True)
    source_cache.write_text('{"session":"renewed"}')
    attempts = 0

    def generate(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("expired container cache")
        return "renewed-token"

    monkeypatch.setattr(module, "provide_token", generate)
    provider = module.ProfileTokenProvider(
        "terraform", "us-east-1",
        refresh_source_dir=source,
        config_dir=target,
    )

    assert await provider.get_token() == "renewed-token"
    assert attempts == 2
    assert (target / "login" / "cache" / "session.json").read_text() == '{"session":"renewed"}'


async def test_profile_refresh_never_follows_symlinks(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    private = tmp_path / "outside.json"
    private.write_text("outside")
    (source / "linked.json").symlink_to(private)

    monkeypatch.setattr(module, "provide_token", lambda **kwargs: (_ for _ in ()).throw(RuntimeError()))
    provider = module.ProfileTokenProvider(
        "terraform", "us-east-1",
        refresh_source_dir=source,
        config_dir=target,
    )

    with pytest.raises(LLMUnavailableError):
        await provider.get_token()
    assert not (target / "linked.json").exists()
