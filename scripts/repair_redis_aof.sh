#!/usr/bin/env bash
# Recovery is deliberately separate from normal startup: --fix truncates an invalid AOF tail.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if [[ $# -gt 1 || ( $# -eq 1 && "${1}" != "--repair" && "${1}" != "--check" ) ]]; then
  echo 'Uso: ./scripts/repair_redis_aof.sh [--check|--repair]' >&2
  exit 2
fi

command -v docker >/dev/null || { echo 'Docker não encontrado.' >&2; exit 1; }
docker compose version >/dev/null

if [[ "${1:-}" != "--repair" ]]; then
  echo 'Estado do Redis:'
  docker compose -f compose.yaml ps -a redis
  echo 'Últimas mensagens do Redis:'
  docker compose -f compose.yaml logs --no-color --tail=30 redis
  echo 'Se o log indicar AOF corrompido, execute ./scripts/repair_redis_aof.sh --repair.'
  exit 0
fi

container_id="$(docker compose -f compose.yaml ps -aq redis)"
if [[ -z "$container_id" ]]; then
  echo 'Container Redis não encontrado. Execute make setup uma vez e verifique o erro.' >&2
  exit 1
fi
if [[ "$(docker inspect -f '{{.State.Running}}' "$container_id")" == true ]]; then
  echo 'Redis está em execução. Pare apenas o Redis antes de reparar: docker compose stop redis' >&2
  exit 1
fi
volume_name="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' "$container_id")"
if [[ -z "$volume_name" ]]; then
  echo 'Volume /data do Redis não encontrado; nenhuma alteração feita.' >&2
  exit 1
fi

mkdir -p artifacts/redis-backups
chmod 700 artifacts/redis-backups
backup_dir="$(mktemp -d "$root_dir/artifacts/redis-backups/redis-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
chmod 700 "$backup_dir"
echo "Criando backup do volume em $backup_dir/redis-volume-before-repair.tar"
docker run --rm \
  --env "BACKUP_UID=$(id -u)" --env "BACKUP_GID=$(id -g)" \
  --mount "type=volume,source=$volume_name,target=/data,readonly" \
  --mount "type=bind,source=$backup_dir,target=/backup" \
  redis:7.4-alpine sh -c '
    tar -C /data -cf /backup/redis-volume-before-repair.tar .
    sha256sum /backup/redis-volume-before-repair.tar > /backup/SHA256SUMS
    chown "$BACKUP_UID:$BACKUP_GID" /backup/redis-volume-before-repair.tar /backup/SHA256SUMS
    chmod 600 /backup/redis-volume-before-repair.tar /backup/SHA256SUMS
  '
tar -tf "$backup_dir/redis-volume-before-repair.tar" >/dev/null

echo 'Backup verificado. Reparando o AOF incremental; entradas após a primeira corrupção podem ser descartadas.'
docker run --rm \
  --mount "type=volume,source=$volume_name,target=/data" \
  redis:7.4-alpine sh -c '
    set -eu
    manifest=/data/appendonlydir/appendonly.aof.manifest
    test -f "$manifest" || { echo "Manifesto AOF não encontrado." >&2; exit 1; }
    printf "y\n" | redis-check-aof --fix "$manifest"
  '

echo 'Validando a leitura do volume...'
docker compose -f compose.yaml up -d --no-deps --wait redis
docker compose -f compose.yaml exec -T redis redis-cli DBSIZE | xargs -I{} echo 'Chaves no Redis: {}'
echo "Backup de retorno: $backup_dir/redis-volume-before-repair.tar"
echo 'Agora execute make up para subir os outros serviços.'
