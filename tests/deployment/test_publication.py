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
    def test_scan_waits_for_indexing_and_processing(self):
        missing = delivery.AWSCommandError('ecr', 'describe-image-scan-findings', 'ScanNotFoundException')
        with patch.object(delivery, 'cli', side_effect=[missing, '{"imageScanStatus":{"status":"IN_PROGRESS"}}', '{"imageScanStatus":{"status":"COMPLETE"},"imageScanFindings":{"findingSeverityCounts":{}}}']) as api, patch.object(delivery.time, 'sleep'):
            delivery.verify_image_scan('api', 'sha256:test', attempts=3)
            self.assertEqual(api.call_count, 3)

    def test_scan_never_bypasses_failures_or_vulnerabilities(self):
        cases = [
            '{"imageScanStatus":{"status":"COMPLETE"},"imageScanFindings":{"findingSeverityCounts":{"HIGH":1}}}',
            '{"imageScanStatus":{"status":"COMPLETE"}}',
            '{"imageScanStatus":{"status":"UNSUPPORTED_IMAGE"}}',
            delivery.AWSCommandError('ecr', 'describe-image-scan-findings', 'AccessDeniedException'),
        ]
        for result in cases:
            with self.subTest(result=result), patch.object(delivery, 'cli') as api:
                if isinstance(result, Exception):
                    api.side_effect = result
                else:
                    api.return_value = result
                with self.assertRaises(RuntimeError):
                    delivery.verify_image_scan('api', 'sha256:test', attempts=1)
                self.assertEqual(api.call_count, 1)

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
