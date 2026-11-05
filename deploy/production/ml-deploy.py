#!/usr/bin/env python3
"""Host-only deployment. Accept a commit, never shell or a Compose file from CI."""

import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CONFIG = Path("/etc/ml-game/config.json")
RUNTIME = Path("/run/ml-game")
RELEASE = Path("/srv/ml-data/current-release")
COMMIT = re.compile(r"^[a-f0-9]{40}$")


def run(*args, **kwargs):
    return subprocess.run(list(args), check=True, text=True, **kwargs)


def aws(config, *args):
    return run(
        "aws", "--region", config["aws_region"], *args, capture_output=True
    ).stdout


def validate_manifest(manifest, config, commit):
    if not COMMIT.fullmatch(commit):
        raise ValueError("Invalid commit")
    if (
        set(manifest) != {"schema", "commit", "api_image", "web_image"}
        or manifest["schema"] != 1
        or manifest["commit"] != commit
    ):
        raise ValueError("Unexpected manifest")
    for kind in ("api", "web"):
        expected = config[f"{kind}_repository"]
        if not re.fullmatch(
            re.escape(expected) + r"@sha256:[a-f0-9]{64}", manifest[f"{kind}_image"]
        ):
            raise ValueError(
                "Image outside the authorized repository or without digest"
            )
    return manifest


def atomic_write(path, content, *, uid=0, gid=0, mode=0o600):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def compose(*args):
    return run(
        "docker",
        "compose",
        "--env-file",
        str(RUNTIME / "images.env"),
        "-f",
        "/etc/ml-game/compose.yaml",
        *args,
    )


def main():
    if os.geteuid() != 0:
        raise RuntimeError("Host administrator only")
    if len(sys.argv) > 2:
        raise ValueError("Only one commit argument is accepted")
    requested = RUNTIME / "requested-release"
    commit = (
        sys.argv[1]
        if len(sys.argv) == 2
        else (requested if requested.exists() else RELEASE).read_text().strip()
    )
    if not COMMIT.fullmatch(commit):
        raise ValueError("Expected a full hexadecimal Git commit")
    config = json.loads(CONFIG.read_text())
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    with (RUNTIME / "deploy.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest_file = RUNTIME / "manifest.json"
        aws(
            config,
            "s3api",
            "get-object",
            "--bucket",
            config["releases_bucket"],
            "--key",
            f"releases/{commit}.json",
            str(manifest_file),
        )
        if manifest_file.stat().st_size > 4096:
            raise ValueError("Manifest too large")
        manifest = validate_manifest(
            json.loads(manifest_file.read_text()), config, commit
        )
        # Tie both digests to immutable commit tags, including on a retry/rollback.
        for kind in ("api", "web"):
            repository = config[f"{kind}_repository"].split("/", 1)[1]
            digest = aws(
                config,
                "ecr",
                "describe-images",
                "--repository-name",
                repository,
                "--image-ids",
                f"imageTag={commit}",
                "--query",
                "imageDetails[0].imageDigest",
                "--output",
                "text",
            ).strip()
            if manifest[f"{kind}_image"] != f"{config[f'{kind}_repository']}@{digest}":
                raise ValueError("Commit/digest mismatch")
        # Secrets never enter the manifest, Terraform, Compose environment or logs.
        secret = json.loads(
            aws(
                config,
                "ssm",
                "get-parameter",
                "--name",
                config["admin_password_parameter"],
                "--with-decryption",
                "--output",
                "json",
            )
        )["Parameter"]["Value"]
        if not 24 <= len(secret) <= 1024 or "\n" in secret or "\r" in secret:
            raise ValueError("Admin password must have at least 24 characters")
        atomic_write(RUNTIME / "admin_password", secret, uid=1000, gid=1000, mode=0o400)
        registry = config["api_repository"].split("/")[0]
        token = aws(config, "ecr", "get-login-password")
        run(
            "docker",
            "login",
            "--username",
            "AWS",
            "--password-stdin",
            registry,
            input=token,
            capture_output=True,
        )
        previous = (
            (RUNTIME / "images.env").read_text()
            if (RUNTIME / "images.env").exists()
            else None
        )
        values = {
            "API_IMAGE": manifest["api_image"],
            "WEB_IMAGE": manifest["web_image"],
            "REDIS_IMAGE": config["redis_image"],
            "AWS_REGION": config["aws_region"],
        }
        atomic_write(
            RUNTIME / "images.env",
            "".join(f"{key}={value}\n" for key, value in values.items()),
        )
        try:
            compose("pull")
            compose(
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
                "--force-recreate",
                "api",
                "game",
                "admin",
            )
        except subprocess.CalledProcessError:
            if previous:
                atomic_write(RUNTIME / "images.env", previous)
                compose(
                    "up",
                    "-d",
                    "--wait",
                    "--wait-timeout",
                    "180",
                    "--force-recreate",
                    "api",
                    "game",
                    "admin",
                )
            raise
        finally:
            run("docker", "logout", registry, capture_output=True)
            # docker's auth is also held only in /run, not in a persistent HOME.
        atomic_write(RELEASE, commit + "\n")
        requested.unlink(missing_ok=True)
        print("Release deployed:", commit)


if __name__ == "__main__":
    os.environ["DOCKER_CONFIG"] = "/run/ml-game/docker"
    try:
        main()
    except Exception as error:
        # Never print subprocess captured output: it could contain secret values.
        print("Deployment failed:", type(error).__name__, file=sys.stderr)
        sys.exit(1)
