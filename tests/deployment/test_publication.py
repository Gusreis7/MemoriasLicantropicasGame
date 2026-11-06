import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[2] / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


delivery = load('delivery', 'scripts/deliver_aws.py')
guard = load('plan_guard', 'scripts/check_infrastructure_plan.py')


class Publication(unittest.TestCase):
    def test_only_matching_dns_and_verified_https_count_as_ready(self):
        response = MagicMock(status=200)
        response.geturl.return_value = 'https://game.example/health'
        response.read.return_value = b'{"status":"ok"}'
        with patch.object(delivery.socket, 'getaddrinfo', return_value=[(None, None, None, None, ('203.0.113.10', 443))]), patch.object(delivery.urllib.request, 'urlopen') as request:
            request.return_value.__enter__.return_value = response
            delivery.verify_public_https('game.example', '203.0.113.10', attempts=1)
            request.assert_called_once_with('https://game.example/health', timeout=15)

    def test_old_dns_or_stale_ipv6_never_verify_another_server(self):
        for address in ('203.0.113.9', '2001:db8::1'):
            with patch.object(delivery.socket, 'getaddrinfo', return_value=[(None, None, None, None, (address, 443))]), patch.object(delivery.urllib.request, 'urlopen') as request:
                with self.assertRaises(RuntimeError):
                    delivery.verify_public_https('game.example', '203.0.113.10', attempts=1)
                request.assert_not_called()

    def test_bad_certificate_does_not_pass_health_check(self):
        with patch.object(delivery.socket, 'getaddrinfo', return_value=[(None, None, None, None, ('203.0.113.10', 443))]), patch.object(delivery.urllib.request, 'urlopen', side_effect=OSError('certificate failure')):
            with self.assertRaises(RuntimeError):
                delivery.verify_public_https('game.example', '203.0.113.10', attempts=1)

    def test_apply_refuses_legacy_deletion_and_instance_replacement(self):
        for actions in (['delete'], ['delete', 'create'], ['create', 'delete']):
            plan = {'resource_changes': [{'address': 'legacy.resource', 'change': {'actions': actions}}]}
            with self.assertRaises(ValueError):
                guard.check(plan, 'apply')
            guard.check(plan, 'destroy')
        guard.check({'resource_changes': [{'address': 'aws_eip_association.game', 'change': {'actions': ['create']}}]}, 'apply')
