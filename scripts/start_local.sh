#!/usr/bin/env bash
# One-command local launch. Keeps the Redis volume and chooses the AWS profile overlay when needed.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if [[ $# -gt 1 || ( $# -eq 1 && "${1}" != "--no-build" ) ]]; then
  echo 'Uso: ./scripts/start_local.sh [--no-build]' >&2
  exit 2
fi

command -v python3 >/dev/null || { echo 'Python 3 não encontrado.' >&2; exit 1; }
command -v docker >/dev/null || { echo 'Docker não encontrado.' >&2; exit 1; }
docker compose version >/dev/null || { echo 'Docker Compose não encontrado.' >&2; exit 1; }

ML_CONFIG_FROM_LAUNCHER=1 python3 scripts/configure_local.py

# Print only mode/profile/path; never put a bearer token into shell output.
mapfile -t auth_config < <(python3 - <<'PY'
import os
from pathlib import Path
import pwd

values = {}
for raw in Path('.env').read_text().splitlines():
    if '=' not in raw or raw.lstrip().startswith('#'):
        continue
    key, value = raw.split('=', 1)
    values[key.strip()] = value.strip().strip('"\'')

token = os.environ.get('AWS_BEARER_TOKEN_BEDROCK') or values.get('AWS_BEARER_TOKEN_BEDROCK', '')
profile = os.environ.get('AWS_PROFILE') or values.get('AWS_PROFILE', '')
config_dir = os.environ.get('AWS_CONFIG_DIR') or values.get('AWS_CONFIG_DIR', '')
if not config_dir:
    sudo_user = os.environ.get('SUDO_USER', '')
    if sudo_user and sudo_user != 'root':
        try:
            config_home = Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            config_home = Path.home()
    else:
        config_home = Path.home()
    config_dir = str(config_home / '.aws')
print('bearer' if token else 'profile' if profile else 'none')
print(profile)
print(config_dir)
PY
)
auth_mode="${auth_config[0]}"
aws_profile="${auth_config[1]}"
aws_config_dir="${auth_config[2]}"

compose_args=(-f compose.yaml)
if [[ "$auth_mode" == profile ]]; then
  if [[ ! -d "$aws_config_dir" ]]; then
    echo "Perfil AWS '$aws_profile' configurado, mas diretório AWS não existe: $aws_config_dir" >&2
    echo 'Configure o AWS CLI ou use AWS_BEARER_TOKEN_BEDROCK no .env.' >&2
    exit 1
  fi
  export AWS_CONFIG_DIR="$aws_config_dir"
  compose_args+=(-f compose.aws-local.yaml)
  echo "Autenticação: perfil AWS '$aws_profile' montado somente para a API."
elif [[ "$auth_mode" == bearer ]]; then
  echo 'Autenticação: token Bedrock configurado no ambiente.'
else
  echo 'Atenção: sem credenciais Bedrock; o jogo inicia, mas os diálogos ficarão indisponíveis.'
fi

docker compose "${compose_args[@]}" config -q
build_arg=(--build)
if [[ "${1:-}" == '--no-build' ]]; then
  build_arg=(--no-build)
fi

show_start_failure() {
  echo 'A inicialização falhou. Estado dos serviços:' >&2
  docker compose "${compose_args[@]}" ps -a >&2 || true
  echo 'Últimas mensagens do Redis:' >&2
  docker compose "${compose_args[@]}" logs --no-color --tail=25 redis >&2 || true
  echo 'Últimas mensagens da API:' >&2
  docker compose "${compose_args[@]}" logs --no-color --tail=25 api >&2 || true
  if docker compose "${compose_args[@]}" logs --no-color --tail=100 redis 2>/dev/null | grep -Eqi 'Bad file format reading the append only file|AOF.*format error'; then
    echo 'Redis: AOF corrompido. Execute ./scripts/repair_redis_aof.sh --repair para backup e reparo explícito.' >&2
  fi
}

echo 'Iniciando e verificando Redis...'
if ! docker compose "${compose_args[@]}" up -d --wait --wait-timeout 120 redis; then
  show_start_failure
  exit 1
fi

echo 'Iniciando API, jogo e painel...'
previous_api_id="$(docker compose "${compose_args[@]}" ps -q api)"
if ! docker compose "${compose_args[@]}" up -d "${build_arg[@]}" --wait --wait-timeout 180; then
  show_start_failure
  exit 1
fi

# The AWS overlay copies the host's SSO/session cache into API tmpfs at container startup.
# Recreate only API on subsequent launches to pick up a renewed login.
current_api_id="$(docker compose "${compose_args[@]}" ps -q api)"
if [[ "$auth_mode" == profile && -n "$previous_api_id" && "$previous_api_id" == "$current_api_id" ]]; then
  if ! docker compose "${compose_args[@]}" up -d --no-deps --no-build --force-recreate --wait --wait-timeout 90 api; then
    show_start_failure
    exit 1
  fi
fi

echo 'Serviços prontos: jogo http://localhost:7077 | painel http://localhost:7078 | API http://localhost:7079/health'
