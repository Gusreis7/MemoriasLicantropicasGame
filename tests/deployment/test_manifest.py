import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ml_host_deployment", ROOT / "deploy/production/ml-deploy.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.commit = "a" * 40
        self.config = {
            "api_repository": "123.dkr.ecr.us-east-1.amazonaws.com/game-api",
            "web_repository": "123.dkr.ecr.us-east-1.amazonaws.com/game-web",
        }
        self.good = {"schema": 1, "commit": self.commit}
        self.good.update(
            api_image=self.config["api_repository"] + "@sha256:" + "b" * 64,
            web_image=self.config["web_repository"] + "@sha256:" + "c" * 64,
        )

    def test_accepts_only_expected_digest_repositories(self):
        self.assertEqual(
            module.validate_manifest(self.good, self.config, self.commit), self.good
        )

    def test_rejects_mutable_or_foreign_images_and_shell_payload(self):
        for value in (
            "other/image:latest",
            self.config["api_repository"] + ":latest",
            self.good["api_image"] + "; touch /tmp/executed",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.validate_manifest(
                    {**self.good, "api_image": value}, self.config, self.commit
                )

    def test_rejects_arbitrary_host_commands_and_unexpected_fields(self):
        for commit in ("main", "a" * 40 + ";id", "$(id)"):
            with self.assertRaises(ValueError):
                module.validate_manifest(self.good, self.config, commit)
        with self.assertRaises(ValueError):
            module.validate_manifest(
                {**self.good, "command": "id"}, self.config, self.commit
            )
        with self.assertRaises(ValueError):
            module.validate_manifest(
                {**self.good, "commit": "b" * 40}, self.config, self.commit
            )
