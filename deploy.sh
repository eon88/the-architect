#!/bin/bash
set -e

REPO=/tmp/arch2
DEPLOY=/docker/the-architect

echo "==> Pulling latest code..."
git -C "$REPO" pull

echo "==> Copying files..."
cp -r "$REPO"/web_app/* "$DEPLOY"/web_app/
cp "$REPO"/requirements.txt "$DEPLOY"/
cp "$REPO"/docker-compose.yml "$DEPLOY"/

echo "==> Building and restarting..."
cd "$DEPLOY"
docker compose build --no-cache
docker compose up -d

echo ""
docker compose ps
