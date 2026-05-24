# macOS Packaging

This folder contains lightweight packaging scripts for EventRadar.

## Build `.app`

```bash
bash packaging/macos/create_app.sh
```

Output:

```text
dist/EventRadar.app
```

Double-click the app to launch EventRadar. On first run it will:

- copy the bundled project to `~/Library/Application Support/EventRadar/app`
- create a Python virtual environment at `~/Library/Application Support/EventRadar/venv`
- install `requirements.txt`
- create `.env` from `env.example` if needed
- start FastAPI on `127.0.0.1:5001`
- open `http://127.0.0.1:5001/events.html`

Logs are written to:

```text
~/Library/Application Support/EventRadar/logs/
```

## Build `.dmg`

```bash
bash packaging/macos/create_dmg.sh
```

Output:

```text
dist/EventRadar.dmg
```

The DMG contains `EventRadar.app` and an Applications shortcut.

## Notes

- The app is unsigned. On another Mac, use right-click -> Open the first time, or sign/notarize it before distribution.
- Python 3 must be installed on the target Mac for this lightweight package.
- Runtime data is intentionally stored outside the app bundle so the app can live in `/Applications`.
