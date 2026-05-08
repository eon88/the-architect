#!/bin/bash
set -e

# ─── The Architect – Hostinger VPS Deployment Script ───────────────────────
# Run once on a fresh VPS (Ubuntu 22.04 recommended) as root or a sudo user.
# Usage: bash deploy.sh
# ---------------------------------------------------------------------------

REPO_URL="https://github.com/eon88/the-architect.git"
APP_DIR="/opt/the-architect"

echo "==> [1/6] Installing Docker..."
if ! command -v docker &>/dev/null; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  echo "    Docker installed."
else
  echo "    Docker already installed, skipping."
fi

echo "==> [2/6] Cloning / updating repository..."
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull origin main
else
  git clone "$REPO_URL" "$APP_DIR"
fi

echo "==> [3/6] Setting up environment file..."
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo ""
  echo "  *** ACTION REQUIRED ***"
  echo "  Edit $APP_DIR/.env and set strong passwords before continuing."
  echo "  Re-run this script after saving the file."
  echo ""
  exit 1
else
  echo "    .env already exists, skipping."
fi

echo "==> [4/6] Opening firewall ports (ufw)..."
if command -v ufw &>/dev/null; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
  echo "    Firewall configured."
else
  echo "    ufw not found, skipping firewall setup."
fi

echo "==> [5/6] Building and starting containers..."
cd "$APP_DIR"
docker compose pull db nginx 2>/dev/null || true
docker compose up -d --build

echo "==> [6/6] Checking container health..."
sleep 5
docker compose ps

echo ""
echo "✓ Deployment complete! The app is running on port 80."
echo "  Visit http://$(curl -s ifconfig.me) to verify."
echo ""
echo "  Useful commands:"
echo "    View logs      : docker compose -f $APP_DIR/docker-compose.yml logs -f"
echo "    Stop app       : docker compose -f $APP_DIR/docker-compose.yml down"
echo "    Restart app    : docker compose -f $APP_DIR/docker-compose.yml restart"
