"""Copia de seguridad diaria de la base SQLite.

Usa la API de respaldo de SQLite, que copia de forma segura aunque el
servidor esté atendiendo peticiones. Guarda las últimas N copias.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .config import Settings
from .db import today


def backup_now(settings: Settings) -> Path:
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    target = settings.backup_dir / f"nepantla-{today()}.db"
    source = sqlite3.connect(str(settings.db_path))
    try:
        dest = sqlite3.connect(str(target))
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    prune(settings)
    return target


def prune(settings: Settings) -> None:
    copies = sorted(settings.backup_dir.glob("nepantla-*.db"))
    for old in copies[: max(0, len(copies) - settings.backup_keep)]:
        old.unlink(missing_ok=True)


class BackupLoop:
    """Hilo en segundo plano: revisa cada hora si ya existe la copia de hoy."""

    def __init__(self, settings: Settings, interval_seconds: float = 3600) -> None:
        self.settings = settings
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _tick(self) -> None:
        target = self.settings.backup_dir / f"nepantla-{today()}.db"
        if not target.exists():
            try:
                backup_now(self.settings)
            except Exception:  # una copia fallida no debe tumbar el servidor
                pass

    def _run(self) -> None:
        self._tick()
        while not self._stop.wait(self.interval):
            self._tick()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="nepantla-backup", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
