import json, os, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ContainerPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                str(ROOT / "deploy/production/compose.yaml"),
                "config",
                "--format",
                "json",
            ],
            env={
                **os.environ,
                "API_IMAGE": "api@sha256:" + "a" * 64,
                "WEB_IMAGE": "web@sha256:" + "b" * 64,
                "REDIS_IMAGE": "redis@sha256:" + "c" * 64,
                "AWS_REGION": "us-east-1",
            },
            text=True,
        )
        cls.config = json.loads(config)
        cls.services = cls.config["services"]

    def test_no_public_admin_api_or_redis(self):
        self.assertFalse(self.services["api"].get("ports"))
        self.assertFalse(self.services["redis"].get("ports"))
        self.assertTrue(
            all(p["host_ip"] == "127.0.0.1" for p in self.services["admin"]["ports"])
        )
        self.assertFalse(self.config["networks"]["frontend"].get("internal", False))
        self.assertTrue(self.config["networks"]["backend"]["internal"])

    def test_all_runtime_services_are_nonroot_readonly_without_privileges(self):
        for name, service in self.services.items():
            with self.subTest(service=name):
                self.assertNotEqual(service["user"].split(":")[0], "0")
                self.assertTrue(service["read_only"])
                self.assertIn("ALL", service["cap_drop"])
                self.assertIn("no-new-privileges:true", service["security_opt"])
                self.assertFalse(service.get("privileged", False))
                self.assertEqual(
                    service["tmpfs"], ["/tmp:rw,noexec,nosuid,nodev,size=64m"]
                )
                self.assertFalse(
                    any(
                        "docker.sock" in v.get("source", "")
                        for v in service.get("volumes", [])
                    )
                )

    def test_credentials_and_redis_isolation(self):
        env = self.services["api"]["environment"]
        self.assertNotIn("AWS_ACCESS_KEY_ID", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertNotIn("AWS_BEARER_TOKEN_BEDROCK", env)
        self.assertEqual(env["AWS_USE_DEFAULT_CREDENTIALS"], "true")
        self.assertEqual(set(self.services["redis"]["networks"]), {"backend"})
        self.assertEqual(set(self.services["admin"]["networks"]), {"frontend"})

    def test_api_default_gateway_matches_firewall_egress_network(self):
        networks = self.services["api"]["networks"]
        egress = networks["egress"]
        self.assertEqual(egress["ipv4_address"], "172.30.254.2")
        self.assertTrue(all(egress["gw_priority"] > value.get("gw_priority", 0)
                            for name, value in networks.items() if name != "egress"))
