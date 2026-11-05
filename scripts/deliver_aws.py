"""Trusted main branch only. Build immutable ECR images, scan, then request fixed SSM deploy."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


def cli(*args, allow_missing=False):
    result = subprocess.run(
        ["aws", "--region", os.environ["AWS_REGION"], *args],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        if allow_missing and "ImageNotFoundException" in result.stderr:
            return None
        raise RuntimeError("AWS command failed: " + args[0] + " " + args[1])
    return result.stdout


def main():
    commit = os.environ["GITHUB_SHA"]
    if not re.fullmatch("[a-f0-9]{40}", commit):
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
            if not re.fullmatch("sha256:[a-f0-9]{64}", digest):
                raise ValueError("Invalid registry digest")
            # ECR basic scanning is enabled at repository creation. Fail closed.
            cli(
                "ecr",
                "wait",
                "image-scan-complete",
                "--repository-name",
                name,
                "--image-id",
                f"imageDigest={digest}",
            )
            findings = json.loads(
                cli(
                    "ecr",
                    "describe-image-scan-findings",
                    "--repository-name",
                    name,
                    "--image-id",
                    f"imageDigest={digest}",
                    "--output",
                    "json",
                )
            )
            counts = findings.get("imageScanFindings", {}).get(
                "findingSeverityCounts", {}
            )
            if counts.get("HIGH", 0) or counts.get("CRITICAL", 0):
                raise RuntimeError(
                    "Image blocked by HIGH/CRITICAL vulnerability findings; update base/dependencies"
                )
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
        target = json.loads(
            cli(
                "elbv2",
                "describe-target-groups",
                "--names",
                "mlgame-production",
                "--query",
                "TargetGroups[0].TargetGroupArn",
                "--output",
                "json",
            )
        )
        cli(
            "elbv2",
            "wait",
            "target-in-service",
            "--target-group-arn",
            target,
            "--targets",
            f"Id={instances[0]},Port=8080",
        )
        print("Healthy release:", commit)


if __name__ == "__main__":
    main()
