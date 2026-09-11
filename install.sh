#!/usr/bin/env bash
# Instalador remoto: curl -fsSL <URL>/install.sh | bash
set -euo pipefail

REPOSITORY="https://github.com/Daniel-Carrapeiro-Mendes/shut-down"
ARCHIVE_URL="$REPOSITORY/archive/refs/heads/main.tar.gz"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Baixando o shutdown-bot..."
curl --fail --location --silent --show-error "$ARCHIVE_URL" -o "$TEMP_DIR/shutdown-bot.tar.gz"
mkdir -p "$TEMP_DIR/source"
tar -xzf "$TEMP_DIR/shutdown-bot.tar.gz" -C "$TEMP_DIR/source" --strip-components=1

cd "$TEMP_DIR/source"
sudo ./deploy/install.sh
