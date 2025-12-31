#!/usr/bin/env bash
set -e

echo "➡️ Cloudflared installer"

# Detect platform
OS=$(uname -s)
ARCH=$(uname -m)

echo "Detected: $OS $ARCH"

# Pick correct download URL
if [[ "$OS" == "Darwin" ]]; then
  URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
  ARCHIVE_NAME="cloudflared-darwin-amd64.tgz"
elif [[ "$OS" == "Linux" ]]; then
  URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
  ARCHIVE_NAME="cloudflared-linux-amd64"
else
  echo "❌ Unsupported OS: $OS"
  exit 1
fi

# If cloudflared not present, download it
if [[ ! -f "./cloudflared" ]]; then
  echo "⬇️ cloudflared binary not found locally – downloading latest release..."

  curl -L "$URL" -o "$ARCHIVE_NAME"

  if [[ "$ARCHIVE_NAME" == *.tgz ]]; then
    tar -xzf "$ARCHIVE_NAME"
  else
    mv "$ARCHIVE_NAME" cloudflared
  fi

  chmod +x cloudflared
fi

# Decide install destination
if [[ "$OS" == "Darwin" ]]; then
  if [[ -d "/opt/homebrew/bin" ]]; then
    INSTALL_PATH="/opt/homebrew/bin/cloudflared"
  else
    INSTALL_PATH="/usr/local/bin/cloudflared"
  fi
else
  INSTALL_PATH="/usr/local/bin/cloudflared"
fi

echo "➡️ Installing to $INSTALL_PATH"
sudo mv cloudflared "$INSTALL_PATH"
sudo chmod +x "$INSTALL_PATH"

echo "✅ Installed successfully"
cloudflared --version
