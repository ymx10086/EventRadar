#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x "venv/bin/python" ]]; then
  python3 -m venv venv
fi

venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt pyinstaller
venv/bin/python -m PyInstaller --clean --noconfirm packaging/desktop/eventradar-server.spec

mkdir -p src-tauri/bin

if command -v rustc >/dev/null 2>&1; then
  target_triple="$(rustc -vV | awk '/host:/ {print $2}')"
else
  case "$(uname -m)" in
    arm64|aarch64) target_triple="aarch64-apple-darwin" ;;
    x86_64|amd64) target_triple="x86_64-apple-darwin" ;;
    *) echo "Unable to infer Rust target triple. Install Rust or set a supported macOS arch." >&2; exit 1 ;;
  esac
fi

cp dist/eventradar-server "src-tauri/bin/eventradar-server-$target_triple"
chmod +x "src-tauri/bin/eventradar-server-$target_triple"

echo "Built sidecar: src-tauri/bin/eventradar-server-$target_triple"
