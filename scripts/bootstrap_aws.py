"""Prepare the permanent AWS foundation; never apply an unreviewed plan.

Usage: uv run python scripts/bootstrap_aws.py plan|apply|configure
AWS profile terraform and region us-east-1 are deliberately fixed for this project.
"""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from botocore.exceptions import ClientError
from botocore.session import Session

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / 'infra/terraform/bootstrap'
WORK = ROOT / 'artifacts/aws-bootstrap'
REPO = 'Gusreis7/MemoriasLicantropicasGame'
PROJECT = 'memorias-licantropicas'
REGION = 'us-east-1'
STATE_KEY = 'bootstrap/terraform.tfstate'
PARAMETER = '/memorias-licantropicas/production/admin-password'


class BootstrapError(RuntimeError):
    pass


def run(args, *, input=None, capture=True):
    environment = {key: value for key, value in os.environ.items()
                   if key not in {'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
                                  'AWS_SECURITY_TOKEN', 'AWS_WEB_IDENTITY_TOKEN_FILE', 'AWS_ROLE_ARN',
                                  'AWS_ROLE_SESSION_NAME', 'AWS_DEFAULT_PROFILE', 'AWS_DEFAULT_REGION'}
                   and not key.startswith('TF_CLI_ARGS')}
    environment.update(AWS_PROFILE='terraform', AWS_REGION=REGION,
                       TF_IN_AUTOMATION='true', TF_WORKSPACE='default')
    result = subprocess.run(args, cwd=ROOT, input=input, text=True,
                            capture_output=capture, env=environment)
    if result.returncode:
        raise BootstrapError(f'Comando falhou: {args[0]}. Consulte autenticação e permissões; nenhuma saída sensível foi exibida.')
    return result.stdout if capture else ''


def terraform(*args, capture=True):
    return run(['terraform', f'-chdir={TF}', *args], capture=capture)


def gh(path, *, method='GET', data=None, missing=False):
    args = ['gh', 'api', '--method', method, path]
    if data is not None:
        args += ['--input', '-']
    result = subprocess.run(args, cwd=ROOT, input=json.dumps(data) if data is not None else None,
                            text=True, capture_output=True)
    if result.returncode:
        if missing and re.search(r'HTTP 404\b', result.stderr):
            return None
        raise BootstrapError('GitHub API indisponível ou sem permissão. Execute gh auth login; o subject OIDC não será adivinhado.')
    return json.loads(result.stdout) if result.stdout.strip() else {}


def optional(call, absent, **kwargs):
    try:
        return call(**kwargs)
    except ClientError as error:
        if error.response['Error']['Code'] in absent:
            return None
        operation = getattr(error, 'operation_name', 'consulta')
        raise BootstrapError(f'AWS recusou {operation} ({error.response["Error"]["Code"]}); não é seguro assumir ausência.') from None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def local_state():
    path = TF / 'terraform.tfstate'
    return json.loads(path.read_text()) if path.exists() else None


def populated(state):
    return bool(state and state.get('resources'))


def check_states(local, remote):
    if populated(local) and populated(remote):
        if digest(local) != digest(remote):
            raise BootstrapError('States local e remoto divergem. Recupere a origem correta antes de continuar; nada será sobrescrito.')


def oidc_prefix(repository, template, explicit=None):
    owner = repository['owner']
    allowed = [f'repo:{REPO}', f'repo:{owner["login"]}@{owner["id"]}/{repository["name"]}@{repository["id"]}']
    if repository.get('full_name') != REPO:
        raise BootstrapError('Repositório GitHub inesperado.')
    if not template.get('use_default', False) and template.get('include_claim_keys') != ['repo', 'context']:
        raise BootstrapError('Template OIDC personalizado não suportado: esperado repo/context com environment.')
    immutable = template.get('use_immutable_subject')
    detected = allowed[1] if immutable is True else allowed[0] if immutable is False else None
    reported = template.get('sub_claim_prefix')
    if reported is not None:
        if reported not in allowed or (detected and reported != detected):
            raise BootstrapError('Prefixo OIDC efetivo do GitHub é incompatível com os IDs/formato do repositório.')
        detected = reported
    if explicit and explicit not in allowed:
        raise BootstrapError('Prefixo OIDC não corresponde ao nome/IDs reais do repositório.')
    if explicit and detected and explicit != detected:
        raise BootstrapError('Prefixo informado diverge do formato OIDC retornado pelo GitHub.')
    if not (explicit or detected):
        raise BootstrapError('GitHub não informou o formato imutável. Confira um sub real de um job com environment e repita com --oidc-subject-prefix PREFIXO (sem :environment:...).')
    return explicit or detected


def source_digest():
    paths = set(TF.glob('*.tf')) | set(TF.glob('*.tfvars')) | set(TF.glob('*.tfvars.json'))
    paths.add(TF / '.terraform.lock.hcl')
    if (WORK / 'bootstrap.tfvars.json').exists():
        paths.add(WORK / 'bootstrap.tfvars.json')
    return digest({str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): p.read_text()
                   for p in sorted(paths) if p.name != 'backend.tf' and p.exists()})


class Bootstrap:
    def __init__(self, session, args):
        self.session, self.args = session, args

    def client(self, service):
        return self.session.create_client(service, region_name=REGION)

    def inspect(self):
        identity = self.client('sts').get_caller_identity()
        account = identity['Account']
        if self.args.account_id and account != self.args.account_id:
            raise BootstrapError('Identidade AWS diferente de --account-id.')
        print(f'Identidade confirmada: {identity["Arn"]}; região {REGION}; perfil terraform.')
        bucket = f'{PROJECT}-{account}-tfstate'
        s3 = self.client('s3')
        exists = optional(s3.head_bucket, {'404', 'NoSuchBucket', 'NotFound'}, Bucket=bucket,
                          ExpectedBucketOwner=account) is not None
        remote = None
        if exists:
            obj = optional(s3.get_object, {'NoSuchKey'}, Bucket=bucket, Key=STATE_KEY,
                           ExpectedBucketOwner=account)
            if obj:
                remote = json.loads(obj['Body'].read())
        local = local_state()
        check_states(local, remote)
        for saved in (local, remote):
            if not saved:
                continue
            foundation = saved.get('outputs', {}).get('foundation', {}).get('value', {})
            if foundation.get('account_id', account) != account:
                raise BootstrapError('State pertence a outra conta AWS. Recupere o backend correto.')
            for resource in saved.get('resources', []):
                if resource.get('type') == 'aws_caller_identity':
                    for instance in resource.get('instances', []):
                        if instance.get('attributes', {}).get('account_id', account) != account:
                            raise BootstrapError('State contém identidade AWS de outra conta.')
        inventory = []
        paginator = self.client('resourcegroupstaggingapi').get_paginator('get_resources')
        for page in paginator.paginate(TagFilters=[{'Key': 'Project', 'Values': [PROJECT]}]):
            inventory += [r['ResourceARN'] for r in page['ResourceTagMappingList']]
        # Tagged inventory alone omits some IAM/global/untagged resources.
        for role in ('runtime', 'infrastructure', 'delivery'):
            found = optional(self.client('iam').get_role, {'NoSuchEntity'}, RoleName=f'{PROJECT}-{role}')
            if found:
                inventory.append(found['Role']['Arn'])
        zones = self.client('route53').list_hosted_zones_by_name(DNSName='memoriaslicantropicasgame.gustavodreis.dev.br')
        inventory += [z['Id'] for z in zones['HostedZones'] if z['Name'].rstrip('.') == 'memoriaslicantropicasgame.gustavodreis.dev.br']
        for suffix in ('api', 'web'):
            found = optional(self.client('ecr').describe_repositories, {'RepositoryNotFoundException'}, repositoryNames=[f'{PROJECT}-{suffix}'])
            if found:
                inventory += [r['repositoryArn'] for r in found['repositories']]
        releases = optional(s3.head_bucket, {'404', 'NoSuchBucket', 'NotFound'},
                            Bucket=f'{PROJECT}-{account}-releases', ExpectedBucketOwner=account)
        if releases is not None:
            inventory.append(f's3://{PROJECT}-{account}-releases')
        if not populated(local) and not populated(remote) and (inventory or exists):
            raise BootstrapError('Há recursos/bucket deste projeto sem state gerenciável. Recupere/importe o state antes de planejar ou aplicar.')
        print(f'State local: {bool(populated(local))}; state S3: {bool(populated(remote))}; recursos encontrados: {len(inventory)}.')
        repository = gh(f'repos/{REPO}')
        template = gh(f'repos/{REPO}/actions/oidc/customization/sub')
        prefix = oidc_prefix(repository, template, self.args.oidc_subject_prefix)
        print(f'Prefixo OIDC conferido: {prefix}')
        provider_arn = f'arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com'
        provider = optional(self.client('iam').get_open_id_connect_provider, {'NoSuchEntity'}, OpenIDConnectProviderArn=provider_arn)
        if provider and 'sts.amazonaws.com' not in provider['ClientIDList']:
            raise BootstrapError('Provider OIDC existente não permite audience sts.amazonaws.com.')
        managed = any(r.get('type') == 'aws_iam_openid_connect_provider' and r.get('name') == 'github'
                      for r in (remote or local or {}).get('resources', []))
        return {'account': account, 'bucket': bucket, 'local': local, 'remote': remote,
                'prefix': prefix, 'create_oidc': managed or provider is None}

    def backend(self, state, *, migrate=False):
        path = TF / 'backend.tf'
        expected = 'terraform { backend "s3" {} }\n'
        if path.exists() and re.sub(r'\s+', '', path.read_text()) != re.sub(r'\s+', '', expected):
            raise BootstrapError('backend.tf existente não corresponde ao backend S3 esperado; revise-o manualmente.')
        path.write_text(expected)
        options = ['-migrate-state', '-force-copy'] if migrate else ['-reconfigure']
        terraform('init', '-input=false', '-lockfile=readonly', *options,
                  f'-backend-config=bucket={state["bucket"]}', f'-backend-config=key={STATE_KEY}',
                  f'-backend-config=region={REGION}', '-backend-config=encrypt=true', '-backend-config=use_lockfile=true', capture=False)

    def plan(self):
        state = self.inspect()
        WORK.mkdir(parents=True, exist_ok=True)
        os.chmod(WORK, 0o700)
        if populated(state['remote']):
            self.backend(state)
        else:
            if (TF / 'backend.tf').exists():
                raise BootstrapError('Backend S3 configurado, mas sem state remoto. Recupere o state em vez de inicializar uma base vazia.')
            terraform('init', '-input=false', '-lockfile=readonly', capture=False)
        variables = {'aws_region': REGION, 'project': PROJECT,
                     'domain_name': 'memoriaslicantropicasgame.gustavodreis.dev.br',
                     'admin_password_parameter': PARAMETER,
                     'github_oidc_subject_prefix': state['prefix'],
                     'create_github_oidc_provider': state['create_oidc']}
        varfile = WORK / 'bootstrap.tfvars.json'
        varfile.write_text(json.dumps(variables))
        terraform('validate', capture=False)
        terraform('plan', '-input=false', '-lock-timeout=5m', f'-var-file={varfile}', f'-out={WORK / "reviewed.tfplan"}', capture=False)
        plan = json.loads(terraform('show', '-json', str(WORK / 'reviewed.tfplan')))
        if any('delete' in r['change']['actions'] for r in plan.get('resource_changes', [])):
            raise BootstrapError('Plano inclui remoção/substituição. Revise e execute a migração manualmente; apply automático recusado.')
        metadata = {k: state[k] for k in ('account', 'bucket', 'prefix', 'create_oidc')}
        metadata.update(state_digest=digest([state['local'], state['remote']]), source_digest=source_digest(),
                        plan_digest=hashlib.sha256((WORK / 'reviewed.tfplan').read_bytes()).hexdigest())
        (WORK / 'reviewed.json').write_text(json.dumps(metadata, indent=2))
        print('Plano salvo em artifacts/aws-bootstrap/reviewed.tfplan. Revise e execute a etapa apply separadamente.')

    def apply(self):
        metadata = json.loads((WORK / 'reviewed.json').read_text())
        state = self.inspect()  # fresh identity/state/resources/OIDC check before every apply
        if any(state[k] != metadata[k] for k in ('account', 'bucket', 'prefix', 'create_oidc')):
            raise BootstrapError('Contexto mudou desde o plan. Gere um novo plano.')
        if metadata['state_digest'] != digest([state['local'], state['remote']]) or metadata['source_digest'] != source_digest():
            raise BootstrapError('State ou código mudou desde o plan. Gere um novo plano.')
        if metadata['plan_digest'] != hashlib.sha256((WORK / 'reviewed.tfplan').read_bytes()).hexdigest():
            raise BootstrapError('Arquivo do plano foi alterado.')
        terraform('apply', '-input=false', '-lock-timeout=5m', str(WORK / 'reviewed.tfplan'), capture=False)
        if not populated(state['remote']):
            # Local bootstrap is now authoritative. Never overwrite a concurrent remote state.
            obj = optional(self.client('s3').get_object, {'NoSuchKey'}, Bucket=state['bucket'], Key=STATE_KEY,
                           ExpectedBucketOwner=state['account'])
            if obj:
                raise BootstrapError('State remoto apareceu durante a aplicação; migração automática recusada. Preserve o state local.')
            self.backend(state, migrate=True)
        self.outputs()
        print('Fundação aplicada. A delegação DNS é externa; depois execute configure.')

    def outputs(self):
        outputs = json.loads(terraform('output', '-json'))
        print('NS reais para delegar no DNS pai:')
        for ns in outputs['dns_nameservers']['value']:
            print(f'  {ns}')
        return outputs

    def configure(self):
        state = self.inspect()
        if not populated(state['remote']):
            raise BootstrapError('Configure exige fundação aplicada com state remoto.')
        self.backend(state)
        outputs = self.outputs()
        if outputs['foundation']['value']['account_id'] != state['account']:
            raise BootstrapError('Outputs pertencem a outra conta.')
        variables = {'AWS_ACCOUNT_ID': state['account'], 'AWS_REGION': REGION,
                     'TF_STATE_BUCKET': outputs['state_bucket']['value'],
                     'AWS_INFRASTRUCTURE_ROLE_ARN': outputs['infrastructure_role_arn']['value'],
                     'AWS_DELIVERY_ROLE_ARN': outputs['delivery_role_arn']['value']}
        for name, value in variables.items():
            path = f'repos/{REPO}/actions/variables/{name}'
            if gh(path, missing=True) is None:
                gh(f'repos/{REPO}/actions/variables', method='POST', data={'name': name, 'value': value})
            else:
                gh(path, method='PATCH', data={'name': name, 'value': value})
        for name in ('infrastructure', 'destruction', 'production'):
            path = f'repos/{REPO}/environments/{name}'
            environment = gh(path, missing=True)
            if environment is None or (environment.get('deployment_branch_policy') is None
                                       and not environment.get('protection_rules')):
                gh(path, method='PUT', data={'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True}})
                gh(path + '/deployment-branch-policies', method='POST', data={'name': 'main', 'type': 'branch'})
            else:
                policy = environment.get('deployment_branch_policy') or {}
                if not policy.get('custom_branch_policies'):
                    raise BootstrapError(f'Ambiente {name} existente sem política customizada de main. Ajuste manualmente preservando aprovações/reviewers.')
                rules = gh(path + '/deployment-branch-policies')['branch_policies']
                if not rules or any(r['name'] != 'main' or r.get('type', 'branch') != 'branch' for r in rules):
                    raise BootstrapError(f'Ambiente {name} admite referências além de main; revise antes de continuar.')
        ssm = self.client('ssm')
        existing = ssm.describe_parameters(ParameterFilters=[{'Key': 'Name', 'Option': 'Equals', 'Values': [PARAMETER]}])['Parameters']
        if existing:
            print('Senha administrativa já cadastrada: preservada. Rotação é explícita em configure_aws_admin.py --overwrite.')
        else:
            password = getpass.getpass('Senha administrativa (24–1024 caracteres): ')
            confirmation = getpass.getpass('Confirme a senha: ')
            if password != confirmation or not 24 <= len(password) <= 1024 or '\r' in password or '\n' in password:
                raise BootstrapError('Senhas diferentes ou tamanho inválido.')
            ssm.put_parameter(Name=PARAMETER, Type='SecureString', Value=password, Overwrite=False)
            print('SecureString cadastrado sem exibir o valor.')
        print('Configuração concluída. Execute AWS infrastructure: plan/apply e depois AWS delivery, após delegação DNS.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('plan', 'apply', 'configure'))
    parser.add_argument('--account-id', help='Recusar outra conta AWS (recomendado em todas as etapas).')
    parser.add_argument('--oidc-subject-prefix', help='Prefixo conferido de um sub real quando a API não informa o formato.')
    args = parser.parse_args()
    try:
        getattr(Bootstrap(Session(profile='terraform'), args), args.stage)()
    except (BootstrapError, ClientError, OSError, ValueError, KeyError) as error:
        if isinstance(error, BootstrapError):
            print(str(error), file=sys.stderr)
        else:
            print(f'Configuração interrompida ({type(error).__name__}); preserve states e consulte permissões/configuração.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
