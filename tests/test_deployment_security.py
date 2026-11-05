import httpx
import pytest
from memorias_licantropicas.settings import Settings
from memorias_licantropicas.infrastructure.llm import aws_credentials

pytestmark = pytest.mark.anyio


async def test_instance_role_token_uses_default_chain_without_local_profile(
    monkeypatch,
):
    seen = {}

    def provide(**kwargs):
        seen.update(kwargs)
        return "short-lived-test"

    monkeypatch.setattr(aws_credentials, "provide_token", provide)
    assert (
        await aws_credentials.ProfileTokenProvider(None, "us-east-1").get_token()
        == "short-lived-test"
    )
    assert (
        seen["aws_credentials_provider"] is None
        and seen["expiry"].total_seconds() == 900
    )


async def test_admin_password_comes_from_mounted_secret_not_html_environment(tmp_path):
    secret = tmp_path / "admin_password"
    secret.write_text(" strong-password-for-local-test-only ")
    settings = Settings(_env_file=None, admin_password="", admin_password_file=secret)
    assert settings.admin_password.get_secret_value() == secret.read_text()
    assert secret.read_text() not in repr(settings)
    assert Settings(_env_file=None, admin_password_file="").admin_password_file is None


async def test_production_docs_disabled_and_host_header_checked(monkeypatch):
    import memorias_licantropicas.main as module

    monkeypatch.setattr(
        module,
        "Settings",
        lambda: Settings(
            _env_file=None,
            api_docs_enabled=False,
            allowed_hosts="game.example,localhost",
        ),
    )
    app = module.create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://game.example"
    ) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await client.get(path)).status_code == 404
        assert (
            await client.get("/health", headers={"Host": "attacker.example"})
        ).status_code == 400


async def test_anonymous_admin_read_and_unsupported_writes_are_blocked(api_client):
    assert (await api_client.get("/admin/api/v1/games")).status_code == 401
    assert (await api_client.get("/admin/api/v1/health")).status_code == 401
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = await api_client.request(
            method, "/admin/api/v1/games", json={"role": "admin"}
        )
        assert response.status_code in (401, 403, 404, 405)
