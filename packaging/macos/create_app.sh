#!/usr/bin/env bash
set -euo pipefail

APP_NAME="EventRadar"
BUNDLE_ID="com.eventradar.app"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_DIR="$DIST_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
BUNDLED_APP_DIR="$RESOURCES_DIR/app"

echo "Building $APP_NAME.app"
echo "Project: $ROOT_DIR"

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$BUNDLED_APP_DIR"

rsync -a "$ROOT_DIR/" "$BUNDLED_APP_DIR/" \
  --exclude ".git" \
  --exclude ".DS_Store" \
  --exclude ".env" \
  --exclude "venv" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "*/__pycache__" \
  --exclude ".pytest_cache" \
  --exclude ".mypy_cache" \
  --exclude ".ruff_cache" \
  --exclude "logs" \
  --exclude "data" \
  --exclude "dist"

mkdir -p \
  "$BUNDLED_APP_DIR/data/automation" \
  "$BUNDLED_APP_DIR/data/daily_archives" \
  "$BUNDLED_APP_DIR/data/discovery" \
  "$BUNDLED_APP_DIR/data/events" \
  "$BUNDLED_APP_DIR/data/personal_assistant"
touch \
  "$BUNDLED_APP_DIR/data/.gitkeep" \
  "$BUNDLED_APP_DIR/data/automation/.gitkeep" \
  "$BUNDLED_APP_DIR/data/daily_archives/.gitkeep" \
  "$BUNDLED_APP_DIR/data/discovery/.gitkeep" \
  "$BUNDLED_APP_DIR/data/events/.gitkeep" \
  "$BUNDLED_APP_DIR/data/personal_assistant/.gitkeep"

cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>LSUIElement</key>
  <false/>
</dict>
</plist>
EOF

cat > "$MACOS_DIR/$APP_NAME" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_NAME="EventRadar"
SUPPORT_DIR="$HOME/Library/Application Support/$APP_NAME"
RUNTIME_DIR="$SUPPORT_DIR/app"
VENV_DIR="$SUPPORT_DIR/venv"
LOG_DIR="$SUPPORT_DIR/logs"
PID_FILE="$SUPPORT_DIR/eventradar.pid"
PORT="${EVENTRADAR_PORT:-5001}"
HOST="${EVENTRADAR_HOST:-127.0.0.1}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUNDLED_APP_DIR="$BUNDLE_DIR/Resources/app"

mkdir -p "$SUPPORT_DIR" "$RUNTIME_DIR" "$LOG_DIR"

copy_app_source() {
  if [[ ! -f "$RUNTIME_DIR/app.py" ]]; then
    rsync -a "$BUNDLED_APP_DIR/" "$RUNTIME_DIR/"
  else
    rsync -a "$BUNDLED_APP_DIR/" "$RUNTIME_DIR/" \
      --exclude ".env" \
      --exclude "data" \
      --exclude "logs" \
      --exclude "venv" \
      --exclude ".venv" \
      --exclude "__pycache__" \
      --exclude "*/__pycache__"
  fi
}

env_value() {
  local key="$1"
  if [[ -f "$RUNTIME_DIR/.env" ]]; then
    grep -E "^${key}=" "$RUNTIME_DIR/.env" | tail -1 | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//"
  fi
}

set_env_value() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "$RUNTIME_DIR/.env"; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$RUNTIME_DIR/.env"
    rm -f "$RUNTIME_DIR/.env.bak"
  else
    printf '%s=%s\n' "$key" "$value" >> "$RUNTIME_DIR/.env"
  fi
}

port_is_available() {
  ! lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
}

is_healthy() {
  curl -fsS "http://$HOST:$PORT/api/health" >/dev/null 2>&1
}

open_app() {
  /usr/bin/open "http://$HOST:$PORT/events.html"
}

notify() {
  local title="$1"
  local message="$2"
  /usr/bin/osascript -e "display notification \"$message\" with title \"$title\"" >/dev/null 2>&1 || true
}

copy_app_source

cd "$RUNTIME_DIR"

mkdir -p data/automation data/daily_archives data/discovery data/events data/personal_assistant logs

if [[ ! -f ".env" ]]; then
  if [[ -f "env.example" ]]; then
    cp env.example .env
  else
    touch .env
  fi
fi

set_env_value "PORT" "$PORT"
set_env_value "HOST" "$HOST"
set_env_value "SITE_URL" "http://$HOST:$PORT"

configured_port="$(env_value PORT)"
configured_host="$(env_value HOST)"
PORT="${configured_port:-$PORT}"
HOST="${configured_host:-$HOST}"

if is_healthy; then
  open_app
  exit 0
fi

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" >/dev/null 2>&1; then
    open_app
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if ! port_is_available; then
  notify "$APP_NAME" "Port $PORT is already in use. Edit $RUNTIME_DIR/.env and choose another PORT."
  /usr/bin/open "$LOG_DIR"
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    notify "$APP_NAME" "Python 3 is required. Please install Python 3 and reopen EventRadar."
    exit 1
  fi
  python3 -m venv "$VENV_DIR"
fi

REQ_HASH="$(shasum -a 256 requirements.txt | awk '{print $1}')"
REQ_MARKER="$VENV_DIR/.requirements.sha256"
if [[ ! -f "$REQ_MARKER" ]] || [[ "$(cat "$REQ_MARKER")" != "$REQ_HASH" ]]; then
  "$VENV_DIR/bin/python" -m pip install --upgrade pip >> "$LOG_DIR/install.log" 2>&1
  "$VENV_DIR/bin/python" -m pip install -r requirements.txt >> "$LOG_DIR/install.log" 2>&1
  echo "$REQ_HASH" > "$REQ_MARKER"
fi

nohup "$VENV_DIR/bin/python" app.py >> "$LOG_DIR/eventradar.log" 2>&1 &
echo $! > "$PID_FILE"

for _ in {1..60}; do
  if is_healthy; then
    open_app
    notify "$APP_NAME" "EventRadar is running at http://$HOST:$PORT/events.html"
    exit 0
  fi
  sleep 1
done

notify "$APP_NAME" "EventRadar did not start. Opening logs."
/usr/bin/open "$LOG_DIR"
exit 1
EOF

chmod +x "$MACOS_DIR/$APP_NAME"

echo "Built: $APP_DIR"
echo
echo "Double-click dist/$APP_NAME.app to launch EventRadar."
echo "Runtime data will be stored in ~/Library/Application Support/$APP_NAME/"
