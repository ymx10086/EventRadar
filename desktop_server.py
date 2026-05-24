#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Desktop entrypoint for EventRadar.

This keeps the existing FastAPI app intact while moving all mutable runtime
state to the macOS user Application Support directory.
"""

import argparse
import logging
import os
import socket
import sys
from pathlib import Path

from dotenv import load_dotenv


APP_NAME = "EventRadar"


def app_support_dir() -> Path:
    override = os.getenv("EVENTRADAR_APP_SUPPORT", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".eventradar"


def find_available_port(host: str = "127.0.0.1", preferred: int = 0) -> int:
    if preferred:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, preferred))
                return preferred
            except OSError:
                pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def ensure_runtime_env(support_dir: Path, host: str, port: int) -> Path:
    data_dir = support_dir / "data"
    logs_dir = support_dir / "logs"
    env_path = support_dir / ".env"

    for directory in (
        support_dir,
        data_dir,
        logs_dir,
        data_dir / "automation",
        data_dir / "daily_archives",
        data_dir / "discovery",
        data_dir / "events",
        data_dir / "personal_assistant",
        data_dir / "qrcodes",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    if not env_path.exists():
        template = Path(__file__).resolve().parent / "env.example"
        if template.exists():
            env_path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_path.touch()

    load_dotenv(env_path, override=True)

    env_defaults = {
        "EVENTRADAR_DESKTOP": "true",
        "EVENTRADAR_APP_SUPPORT": str(support_dir),
        "EVENTRADAR_DATA_DIR": str(data_dir),
        "EVENTRADAR_ENV_PATH": str(env_path),
        "EVENTRADAR_CREDENTIALS_PATH": str(data_dir / ".credentials.json"),
        "EVENTRADAR_QRCODE_DIR": str(data_dir / "qrcodes"),
        "RSS_DB_PATH": str(data_dir / "rss.db"),
        "EVENTS_DB_PATH": str(data_dir / "events.db"),
        "DAILY_ARCHIVE_DIR": str(data_dir / "daily_archives"),
        "EVENTS_OUTPUT_DIR": str(data_dir / "events"),
        "PERSONAL_ASSISTANT_DIR": str(data_dir / "personal_assistant"),
        "ACCOUNT_DISCOVERY_DIR": str(data_dir / "discovery"),
        "AUTOMATION_HISTORY_DIR": str(data_dir / "automation"),
        "HOST": host,
        "PORT": str(port),
        "SITE_URL": f"http://{host}:{port}",
        "PUBLIC_URL": "",
    }
    for key, value in env_defaults.items():
        os.environ[key] = value

    return env_path


def configure_logging(support_dir: Path) -> None:
    log_path = support_dir / "logs" / "eventradar.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EventRadar desktop server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("EVENTRADAR_PORT", "0") or 0))
    parser.add_argument("--app-support", default="")
    args = parser.parse_args()

    support_dir = Path(args.app_support).expanduser() if args.app_support else app_support_dir()
    port = find_available_port(args.host, args.port)
    env_path = ensure_runtime_env(support_dir, args.host, port)
    configure_logging(support_dir)

    import uvicorn
    from app import app

    print(f"EVENTRADAR_DESKTOP_READY http://{args.host}:{port}", flush=True)
    print(f"Runtime: {support_dir}", flush=True)
    print(f"Env: {env_path}", flush=True)

    uvicorn.run(app, host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
