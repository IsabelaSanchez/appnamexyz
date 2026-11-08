#!/bin/bash
set -eu
dnf install -y docker git
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -4 --max-time 90 -fsSL https://github.com/docker/compose/releases/download/v2.40.3/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
curl -4 --max-time 90 -fsSL https://github.com/docker/buildx/releases/download/v0.29.1/buildx-v0.29.1.linux-amd64 -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
mkdir -p /opt/accessibility/config /opt/accessibility/releases
chmod 700 /opt/accessibility/config
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
printf '/swapfile none swap sw 0 0\n' >> /etc/fstab
usermod -aG docker ec2-user
