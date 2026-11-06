"""Trusted main branch only. Build immutable ECR images, scan, then request fixed SSM deploy."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import socket
import urllib.request
import re


class AWSCommandError(RuntimeError):
    def __init__(self, service, operation, code):
        self.code = code
        super().__init__(f'AWS {service} {operation} failed ({code})')


def verify_image_scan(repository, image_digest, attempts=60):
    for attempt in range(attempts):
        try:
            result = json.loads(cli('ecr', 'describe-image-scan-findings',
                                    '--repository-name', repository, '--image-id',
                                    f'imageDigest={image_digest}', '--output', 'json'))
        except AWSCommandError as error:
            if error.code not in ('ScanNotFoundException', 'ImageNotFoundException'):
                raise
            result = {}
        status = result.get('imageScanStatus', {}).get('status', 'PENDING')
        if status == 'COMPLETE':
            findings = result.get('imageScanFindings')
            if not isinstance(findings, dict):
                raise RuntimeError('ECR scan completed without findings payload; release blocked')
            counts = findings.get('findingSeverityCounts', {})
            if counts.get('HIGH', 0) or counts.get('CRITICAL', 0):
                for finding in findings.get('findings', []):
                    if finding.get('severity') in ('HIGH', 'CRITICAL'):
                        attrs = {x['key']: x['value'] for x in finding.get('attributes', [])}
                        print('Blocked finding:', finding.get('name'), finding['severity'],
                              attrs.get('package_name', 'unknown'), attrs.get('package_version', 'unknown'), flush=True)
                raise RuntimeError(f'ECR blocked {repository}: HIGH={counts.get("HIGH", 0)}, CRITICAL={counts.get("CRITICAL", 0)}. Update OS packages/base image; scan is not bypassed.')
            print(f'ECR scan complete: {repository}', flush=True)
            return
        if status not in ('PENDING', 'IN_PROGRESS'):
            raise RuntimeError(f'ECR scan cannot approve {repository}: status={status}')
        if attempt + 1 < attempts:
            time.sleep(5)
    raise TimeoutError(f'ECR scan still pending for {repository}; retry delivery later')


def verify_public_https(domain, expected_ip, attempts=60):
    url = f"https://{domain}/health"
    for attempt in range(attempts):
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)}
            if addresses != {expected_ip}:
                raise ValueError("DNS does not point exclusively to the game Elastic IP")
            with urllib.request.urlopen(url, timeout=15) as response:
                if response.status == 200 and response.geturl() == url and json.loads(response.read(4096)).get('status') == 'ok':
                    return
        except (OSError, ValueError):
            pass
        if attempt + 1 < attempts:
            time.sleep(10)
    raise RuntimeError(f"Release installed, but HTTPS is not ready. Check the A record for {domain} -> {expected_ip}, stale AAAA records and Caddy logs.")


def cli(*args, allow_missing=False):
    result = subprocess.run(
        ["aws", "--region", os.environ["AWS_REGION"], *args],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        if allow_missing and "ImageNotFoundException" in result.stderr:
            return None
        match = re.search(r'An error occurred \(([A-Za-z0-9_.-]+)\)', result.stderr)
        raise AWSCommandError(args[0], args[1], match.group(1) if match else f'exit_{result.returncode}')
    return result.stdout


def main():
    commit = os.environ["GITHUB_SHA"]
    if len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        raise ValueError("Full commit required")
    if (
        os.environ.get("GITHUB_REPOSITORY") != "Gusreis7/MemoriasLicantropicasGame"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise ValueError("Only the authorized main branch can deliver")
    with tempfile.TemporaryDirectory() as temporary:
        state = Path(temporary) / "bootstrap.json"
        cli(
            "s3api",
            "get-object",
            "--bucket",
            os.environ["STATE_BUCKET"],
            "--key",
            "bootstrap/terraform.tfstate",
            str(state),
        )
        foundation = json.loads(state.read_text())["outputs"]["foundation"]["value"]
        if foundation["aws_region"] != os.environ["AWS_REGION"]:
            raise ValueError("Region mismatch")
        instances = json.loads(
            cli(
                "ec2",
                "describe-instances",
                "--filters",
                f"Name=tag:Project,Values={foundation['project']}",
                "Name=instance-state-name,Values=running",
                "--query",
                "Reservations[].Instances[].InstanceId",
                "--output",
                "json",
            )
        )
        if len(instances) != 1:
            raise RuntimeError(
                "Run infrastructure/apply first; expected one running game instance"
            )
        images = {}
        for kind in ("api", "web"):
            repository = foundation[f"{kind}_repository"]
            name = repository.split("/", 1)[1]
            digest = cli(
                "ecr",
                "describe-images",
                "--repository-name",
                name,
                "--image-ids",
                f"imageTag={commit}",
                "--query",
                "imageDetails[0].imageDigest",
                "--output",
                "text",
                allow_missing=True,
            )
            if digest is None:
                args = [
                    "docker",
                    "buildx",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "--provenance=false",
                    "--tag",
                    repository + ":" + commit,
                    "--push",
                ]
                if kind == "web":
                    args += ["--file", "frontend/Dockerfile"]
                subprocess.run([*args, "."], check=True)
                digest = cli(
                    "ecr",
                    "describe-images",
                    "--repository-name",
                    name,
                    "--image-ids",
                    f"imageTag={commit}",
                    "--query",
                    "imageDetails[0].imageDigest",
                    "--output",
                    "text",
                )
            digest = digest.strip()
            if (
                not digest.startswith("sha256:")
                or len(digest) != 71
                or any(character not in "0123456789abcdef" for character in digest[7:])
            ):
                raise ValueError("Invalid registry digest")
            verify_image_scan(name, digest)
            images[f"{kind}_image"] = repository + "@" + digest
        manifest = Path(temporary) / "release.json"
        manifest.write_text(json.dumps({"schema": 1, "commit": commit, **images}))
        cli(
            "s3api",
            "put-object",
            "--bucket",
            foundation["releases_bucket"],
            "--key",
            f"releases/{commit}.json",
            "--body",
            str(manifest),
            "--content-type",
            "application/json",
            "--server-side-encryption",
            "AES256",
        )
        response = json.loads(
            cli(
                "ssm",
                "send-command",
                "--document-name",
                foundation["deploy_document"],
                "--instance-ids",
                instances[0],
                "--parameters",
                json.dumps({"CommitId": [commit]}),
                "--output",
                "json",
            )
        )
        command = response["Command"]["CommandId"]
        for _ in range(180):
            try:
                record = json.loads(
                    cli(
                        "ssm",
                        "get-command-invocation",
                        "--command-id",
                        command,
                        "--instance-id",
                        instances[0],
                        "--output",
                        "json",
                    )
                )
            except RuntimeError:
                time.sleep(10)
                continue
            if record["Status"] == "Success":
                break
            if record["Status"] in ("Failed", "Cancelled", "TimedOut"):
                raise RuntimeError(
                    "Remote deployment failed; inspect SSM status as an operator"
                )
            time.sleep(10)
        else:
            raise TimeoutError("Deployment did not finish")
        verify_public_https(foundation["domain_name"], foundation["elastic_ip"])
        print("Healthy HTTPS release:", commit)


if __name__ == "__main__":
    main()
