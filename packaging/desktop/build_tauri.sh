#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

bash packaging/desktop/build_pyinstaller.sh

if ! command -v cargo >/dev/null 2>&1 || ! command -v rustc >/dev/null 2>&1; then
  echo "Rust toolchain is required for Tauri builds." >&2
  echo "Install it from https://rustup.rs/ and rerun this script." >&2
  exit 1
fi

if [[ ! -d "src-tauri/target" ]]; then
  echo "Building Tauri app..."
else
  echo "Rebuilding Tauri app..."
fi

npm install
npm run tauri:build
