"""Offline checks: no AWS/GitHub calls or Terraform apply in this suite."""

from argparse import Namespace
from io import BytesIO
import json
from unittest.mock import MagicMock

from botocore.exceptions import ClientError
import pytest

from scripts import bootstrap_aws as module


def repository():
    return {'full_name': module.REPO, 'name': 'MemoriasLicantropicasGame',
            'id': 20, 'owner': {'login': 'Gusreis7', 'id': 10}}


def test_effective_oidc_subject_uses_real_ids_and_refuses_ambiguity():
    template = {'use_default': True, 'use_immutable_subject': True,
                'sub_claim_prefix': 'repo:Gusreis7@10/MemoriasLicantropicasGame@20'}
    assert module.oidc_prefix(repository(), template) == template['sub_claim_prefix']
    assert module.oidc_prefix(repository(), {'use_default': True, 'use_immutable_subject': False}) == 'repo:' + module.REPO
    with pytest.raises(module.BootstrapError):
        module.oidc_prefix(repository(), {'use_default': True})
    with pytest.raises(module.BootstrapError):
        module.oidc_prefix(repository(), template, 'repo:' + module.REPO)
    template['sub_claim_prefix'] = 'repo:Gusreis7@11/MemoriasLicantropicasGame@20'
    with pytest.raises(module.BootstrapError):
        module.oidc_prefix(repository(), template)


def test_custom_oidc_claims_are_not_silently_accepted():
    with pytest.raises(module.BootstrapError):
        module.oidc_prefix(repository(), {'use_default': False, 'include_claim_keys': ['job_workflow_ref']})


def state(serial=1, lineage='same'):
    return {'lineage': lineage, 'serial': serial, 'resources': [{'type': 'example', 'name': 'existing'}]}


def test_state_lineage_or_serial_divergence_stops_instead_of_overwrite():
    module.check_states(state(), state())
    for remote in (state(2), state(lineage='other')):
        with pytest.raises(module.BootstrapError):
            module.check_states(state(), remote)
    changed = state()
    changed['outputs'] = {'unexpected': {'value': 'other'}}
    with pytest.raises(module.BootstrapError):
        module.check_states(state(), changed)


def test_aws_access_denied_is_not_treated_as_absence():
    call = MagicMock(side_effect=ClientError({'Error': {'Code': 'AccessDenied'}}, 'GetObject'))
    with pytest.raises(module.BootstrapError):
        module.optional(call, {'NoSuchKey'}, Bucket='bucket')
    call.side_effect = ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
    assert module.optional(call, {'NoSuchKey'}) is None


def bootstrap():
    return module.Bootstrap(MagicMock(), Namespace(account_id=None, oidc_subject_prefix=None))


def snapshot(local=None, remote=None):
    return {'account': '123456789012', 'bucket': 'state-bucket', 'prefix': 'repo:' + module.REPO,
            'create_oidc': False, 'local': local, 'remote': remote}


def test_plan_initial_execution_keeps_local_backend_until_apply(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'TF', tmp_path / 'tf')
    module.TF.mkdir()
    monkeypatch.setattr(module, 'WORK', tmp_path / 'work')
    fake_tf = MagicMock(side_effect=lambda *a, **k: json.dumps({'resource_changes': []}) if a[0] == 'show' else '')
    monkeypatch.setattr(module, 'terraform', fake_tf)
    def plan_file(*args, **kwargs):
        if args[0] == 'plan':
            (module.WORK / 'reviewed.tfplan').write_bytes(b'plan')
        return json.dumps({'resource_changes': []}) if args[0] == 'show' else ''
    fake_tf.side_effect = plan_file
    action = bootstrap()
    action.inspect = MagicMock(return_value=snapshot())
    action.backend = MagicMock()
    action.plan()
    action.backend.assert_not_called()
    assert (module.WORK / 'reviewed.json').exists()
    assert all(call.args[0] != 'apply' for call in fake_tf.call_args_list)


def test_remote_plan_reuses_existing_backend_state(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'TF', tmp_path)
    monkeypatch.setattr(module, 'WORK', tmp_path / 'work')
    def fake_tf(*args, **kwargs):
        if args[0] == 'plan':
            (module.WORK / 'reviewed.tfplan').write_bytes(b'plan')
        return json.dumps({'resource_changes': []}) if args[0] == 'show' else ''
    monkeypatch.setattr(module, 'terraform', fake_tf)
    action = bootstrap()
    current = snapshot(remote=state())
    action.inspect = MagicMock(return_value=current)
    action.backend = MagicMock()
    action.plan()
    action.backend.assert_called_once_with(current)


def test_apply_rechecks_state_and_rejects_stale_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'WORK', tmp_path)
    monkeypatch.setattr(module, 'source_digest', lambda: 'source')
    previous = snapshot(remote=state())
    metadata = {k: previous[k] for k in ('account', 'bucket', 'prefix', 'create_oidc')}
    metadata.update(state_digest=module.digest([None, state()]), source_digest='source', plan_digest='unused')
    (tmp_path / 'reviewed.json').write_text(json.dumps(metadata))
    action = bootstrap()
    action.inspect = MagicMock(return_value=snapshot(remote=state(2)))
    fake_tf = MagicMock()
    monkeypatch.setattr(module, 'terraform', fake_tf)
    with pytest.raises(module.BootstrapError):
        action.apply()
    action.inspect.assert_called_once()
    fake_tf.assert_not_called()


@pytest.mark.parametrize('remote', [None, state()])
def test_apply_saved_plan_migrates_only_initial_local_state(tmp_path, monkeypatch, remote):
    monkeypatch.setattr(module, 'WORK', tmp_path)
    monkeypatch.setattr(module, 'source_digest', lambda: 'source')
    plan = tmp_path / 'reviewed.tfplan'
    plan.write_bytes(b'reviewed')
    current = snapshot(remote=remote)
    metadata = {k: current[k] for k in ('account', 'bucket', 'prefix', 'create_oidc')}
    metadata.update(state_digest=module.digest([None, remote]), source_digest='source',
                    plan_digest=module.hashlib.sha256(plan.read_bytes()).hexdigest())
    (tmp_path / 'reviewed.json').write_text(json.dumps(metadata))
    action = bootstrap()
    action.inspect = MagicMock(return_value=current)
    action.backend = MagicMock()
    action.outputs = MagicMock()
    action.client = MagicMock()
    action.client.return_value.get_object.side_effect = ClientError(
        {'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
    fake_tf = MagicMock()
    monkeypatch.setattr(module, 'terraform', fake_tf)
    action.apply()
    assert fake_tf.call_args.args[0] == 'apply'
    assert fake_tf.call_args.args[-1] == str(plan)
    if remote is None:
        action.backend.assert_called_once_with(current, migrate=True)
    else:
        action.backend.assert_not_called()
    action.outputs.assert_called_once()


def test_configure_preserves_existing_password_without_decryption(tmp_path, monkeypatch):
    action = bootstrap()
    action.inspect = MagicMock(return_value=snapshot(remote=state()))
    action.backend = MagicMock()
    outputs = {'foundation': {'value': {'account_id': '123456789012'}}}
    for key in ('state_bucket', 'infrastructure_role_arn', 'delivery_role_arn'):
        outputs[key] = {'value': key}
    action.outputs = MagicMock(return_value=outputs)
    def fake_gh(path, **kwargs):
        if path.endswith('/deployment-branch-policies'):
            return {'branch_policies': [{'name': 'main', 'type': 'branch'}]}
        if '/environments/' in path:
            return {'deployment_branch_policy': {'custom_branch_policies': True}}
        return {}
    monkeypatch.setattr(module, 'gh', fake_gh)
    ssm = MagicMock()
    ssm.describe_parameters.return_value = {'Parameters': [{'Name': module.PARAMETER}]}
    action.client = MagicMock(return_value=ssm)
    prompt = MagicMock(side_effect=AssertionError('Existing password must not prompt'))
    monkeypatch.setattr(module.getpass, 'getpass', prompt)
    action.configure()
    ssm.get_parameter.assert_not_called()
    ssm.put_parameter.assert_not_called()


def test_backend_migration_enables_s3_lock_and_never_reconfigures_it(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'TF', tmp_path)
    fake_tf = MagicMock()
    monkeypatch.setattr(module, 'terraform', fake_tf)
    bootstrap().backend(snapshot(), migrate=True)
    args = fake_tf.call_args.args
    assert '-migrate-state' in args and '-force-copy' in args
    assert '-backend-config=use_lockfile=true' in args
    assert '-reconfigure' not in args


def test_terraform_environment_cannot_override_fixed_profile_or_workspace(monkeypatch):
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'wrong-account-key')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'wrong-session')
    monkeypatch.setenv('TF_CLI_ARGS_apply', '-auto-approve')
    monkeypatch.setenv('TF_WORKSPACE', 'unexpected')
    process = MagicMock(return_value=Namespace(returncode=0, stdout='ok'))
    monkeypatch.setattr(module.subprocess, 'run', process)
    module.run(['terraform', 'version'])
    environment = process.call_args.kwargs['env']
    assert environment['AWS_PROFILE'] == 'terraform'
    assert environment['TF_WORKSPACE'] == 'default'
    assert 'AWS_ACCESS_KEY_ID' not in environment
    assert 'AWS_SESSION_TOKEN' not in environment
    assert 'TF_CLI_ARGS_apply' not in environment


def test_source_hash_covers_manual_variables_and_provider_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'TF', tmp_path)
    monkeypatch.setattr(module, 'WORK', tmp_path / 'work')
    lock = tmp_path / '.terraform.lock.hcl'
    lock.write_text('provider-version-1')
    before = module.source_digest()
    variables = tmp_path / 'terraform.tfvars'
    variables.write_text('availability_zone="us-east-1a"')
    assert module.source_digest() != before
    before = module.source_digest()
    lock.write_text('provider-version-2')
    assert module.source_digest() != before


def test_configure_can_restrict_existing_empty_environment_and_store_secret(monkeypatch):
    action = bootstrap()
    action.inspect = MagicMock(return_value=snapshot(remote=state()))
    action.backend = MagicMock()
    outputs = {'foundation': {'value': {'account_id': '123456789012'}}}
    for key in ('state_bucket', 'infrastructure_role_arn', 'delivery_role_arn'):
        outputs[key] = {'value': key}
    action.outputs = MagicMock(return_value=outputs)
    calls = []
    def fake_gh(path, **kwargs):
        calls.append((path, kwargs))
        return {'deployment_branch_policy': None, 'protection_rules': []} if '/environments/' in path else {}
    monkeypatch.setattr(module, 'gh', fake_gh)
    ssm = MagicMock()
    ssm.describe_parameters.return_value = {'Parameters': []}
    action.client = MagicMock(return_value=ssm)
    password = 'a-long-private-password-only-in-memory'
    monkeypatch.setattr(module.getpass, 'getpass', MagicMock(return_value=password))
    action.configure()
    assert sum(kwargs.get('method') == 'PUT' for _, kwargs in calls) == 3
    assert sum(kwargs.get('method') == 'POST' for _, kwargs in calls) == 3
    ssm.put_parameter.assert_called_once_with(Name=module.PARAMETER, Type='SecureString', Value=password, Overwrite=False)
    assert password not in repr(calls)
