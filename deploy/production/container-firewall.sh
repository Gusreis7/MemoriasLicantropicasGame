#!/bin/bash
set -Eeuo pipefail
# Docker uses iptables on this dedicated host. No global ACCEPT/DROP policy changes.
iptables -N ML-CONTAINERS 2>/dev/null || true
iptables -F ML-CONTAINERS
# IMDSv2 hop=2 serves only the API's fixed egress address.
iptables -A ML-CONTAINERS ! -s 172.30.254.2/32 -d 169.254.169.254/32 -j DROP
iptables -A ML-CONTAINERS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
# Proxies may reach the API on their own bridge, but cannot initiate outside flows.
iptables -A ML-CONTAINERS -s 172.30.253.0/28 ! -d 172.30.253.0/28 -j DROP
iptables -A ML-CONTAINERS -j RETURN
iptables -C DOCKER-USER -j ML-CONTAINERS 2>/dev/null || iptables -I DOCKER-USER 1 -j ML-CONTAINERS
# Do not allow proxies to open host services via their bridge gateway.
iptables -C INPUT -s 172.30.253.0/28 -m conntrack --ctstate NEW -j DROP 2>/dev/null || iptables -I INPUT 1 -s 172.30.253.0/28 -m conntrack --ctstate NEW -j DROP
