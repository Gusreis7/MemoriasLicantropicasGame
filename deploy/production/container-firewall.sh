#!/bin/bash
set -Eeuo pipefail
# Docker uses iptables on this dedicated host. No global ACCEPT/DROP policy changes.
iptables -N ML-CONTAINERS 2>/dev/null || true
iptables -F ML-CONTAINERS
# IMDSv2 hop=2 serves only the API's fixed egress address.
iptables -A ML-CONTAINERS ! -s 172.30.254.2/32 -d 169.254.169.254/32 -j DROP
iptables -A ML-CONTAINERS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
# Docker encaminha DNS externo pela rede de saída do container. Libere somente
# os resolvers IPv4 do host e o AmazonProvidedDNS, antes do DROP da rede edge.
for resolver_file in /etc/resolv.conf /run/systemd/resolve/resolv.conf; do
    [ -r "$resolver_file" ] || continue
    while read -r key resolver rest; do
        if [[ "$key" = nameserver && "$resolver" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            for protocol in udp tcp; do
                iptables -A ML-CONTAINERS -s 172.30.252.0/28 -d "$resolver/32" -p "$protocol" --dport 53 -j RETURN
            done
        fi
    done < "$resolver_file"
done
for protocol in udp tcp; do
    iptables -A ML-CONTAINERS -s 172.30.252.0/28 -d 169.254.169.253/32 -p "$protocol" --dport 53 -j RETURN
done
# Caddy pode obter/renovar certificados, sem acesso a IMDS ou serviços do host.
iptables -A ML-CONTAINERS -s 172.30.252.0/28 -p tcp -m multiport --dports 80,443 -j RETURN
iptables -A ML-CONTAINERS -s 172.30.252.0/28 -j DROP
# Proxies may reach the API on their own bridge, but cannot initiate outside flows.
iptables -A ML-CONTAINERS -s 172.30.253.0/28 ! -d 172.30.253.0/28 -j DROP
iptables -A ML-CONTAINERS -j RETURN
iptables -C DOCKER-USER -j ML-CONTAINERS 2>/dev/null || iptables -I DOCKER-USER 1 -j ML-CONTAINERS
# Do not allow proxies to open host services via their bridge gateway.
iptables -C INPUT -s 172.30.253.0/28 -m conntrack --ctstate NEW -j DROP 2>/dev/null || iptables -I INPUT 1 -s 172.30.253.0/28 -m conntrack --ctstate NEW -j DROP
iptables -C INPUT -s 172.30.252.0/28 -m conntrack --ctstate NEW -j DROP 2>/dev/null || iptables -I INPUT 1 -s 172.30.252.0/28 -m conntrack --ctstate NEW -j DROP
