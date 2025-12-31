#!/usr/bin/env bash
set -e

# Path to your downloaded cloudflared binary (edit if needed)
CLOUDFLARED_FILE="./cloudflared"

if [ ! -f "$CLOUDFLARED_FILE" ]; then
  echo "❌ cloudflared binary not found at $CLOUDFLARED_FILE"
  echo "Put the binary in this folder or edit CLOUDFLARED_FILE path."
  exit 1
fi

# Detect OS and choose install path
if [[ "$(uname)" == "Darwin" ]]; then
  # macOS
  if [ -d "/opt/homebrew/bin" ]; then
    INSTALL_PATH="/opt/homebrew/bin/cloudflared"
  else
    INSTALL_PATH="/usr/local/bin/cloudflared"
  fi
else
  # Linux default
  INSTALL_PATH="/usr/local/bin/cloudflared"
fi

echo "➡️ Installing to $INSTALL_PATH"

sudo mv "$CLOUDFLARED_FILE" "$INSTALL_PATH"
sudo chmod +x "$INSTALL_PATH"

echo "✅ Installed"
echo "➡️ Version:"
cloudflared --version
