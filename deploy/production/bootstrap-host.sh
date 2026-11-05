#!/bin/bash
set -Eeuo pipefail
umask 077
# AL2023 supplies AWS CLI. Only official distribution packages are installed.
dnf install -y docker jq iptables
command -v aws >/dev/null
systemctl enable --now docker
install -d -m 0755 /usr/local/lib/docker/cli-plugins
curl --fail --silent --show-error --location https://github.com/docker/compose/releases/download/v5.7.0/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
printf '%s  %s\n' 7758048ad38e580f22559603312874fec8bb638d021a9e64182385fc17cc12a2 /usr/local/lib/docker/cli-plugins/docker-compose | sha256sum -c -
chmod 0755 /usr/local/lib/docker/cli-plugins/docker-compose
# Published ports require a routable bridge. The host firewall restricts egress.
/usr/local/sbin/ml-container-firewall
cat > /etc/systemd/system/ml-imds-firewall.service <<'UNIT'
[Unit]
After=docker.service
Requires=docker.service
PartOf=docker.service
Before=ml-game.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ml-container-firewall
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
UNIT
volume=$(jq -r '.data_volume_id' /etc/ml-game/config.json)
serial=${volume//-/}
device=''
for attempt in $(seq 1 120); do
    device=$(lsblk -dnpo PATH,SERIAL | awk -v expected="$serial" '$2==expected {print $1}')
    [ -n "$device" ] && break
    sleep 5
done
[ -n "$device" ] && [ -b "$device" ]
filesystem=$(lsblk -ndo FSTYPE "$device")
if [ -z "$filesystem" ]; then mkfs.ext4 "$device"; else [ "$filesystem" = ext4 ]; fi
install -d -m 0755 /srv/ml-data
uuid=$(blkid -s UUID -o value "$device")
grep -q "UUID=$uuid " /etc/fstab || printf 'UUID=%s /srv/ml-data ext4 defaults,nodev,nosuid,noexec,nofail 0 2\n' "$uuid" >> /etc/fstab
mountpoint -q /srv/ml-data || mount /srv/ml-data
install -d -o 999 -g 999 -m 0700 /srv/ml-data/redis
# Neither ec2-user nor a container can edit the host deployment files.
chown -R root:root /etc/ml-game
chmod 0755 /etc/ml-game
chmod 0644 /etc/ml-game/*.conf /etc/ml-game/compose.yaml
chmod 0600 /etc/ml-game/config.json
systemctl daemon-reload
systemctl enable ml-imds-firewall.service ml-game.service
