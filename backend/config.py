"""Configuración de Nepantla.

Todo se controla con variables de entorno para que el mismo código sirva en
la computadora de casa, en las pruebas y en Railway.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


@dataclass
class Settings:
    # Carpeta con la base SQLite, los audios y las copias de seguridad.
    # En Railway debe apuntar al volumen persistente (por ejemplo /data).
    data_dir: Path = ROOT / "data"
    frontend_dir: Path = ROOT / "frontend"
    packs_dir: Path = ROOT / "packs"

    # Modo desarrollo/demo: deja ver paquetes en borrador (incluidos los de
    # prueba). En producción real debe quedar apagado.
    dev_mode: bool = False

    # Secreto del operador para crear paquetes y enlaces del estudio.
    # No es una "cuenta de usuario": pacientes y personal nunca lo usan.
    admin_token: str = ""

    # Redirige http -> https cuando el proxy avisa que la petición llegó sin TLS.
    force_https: bool = False

    import_example_packs: bool = True
    enable_backups: bool = True
    backup_keep: int = 14

    # Límites de las subidas del estudio de grabación.
    max_upload_bytes: int = 3 * 1024 * 1024
    max_audio_seconds: float = 30.0
    min_audio_seconds: float = 0.3
    session_days: int = 30

    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("NEPANTLA_DATA_DIR", ROOT / "data")),
            packs_dir=Path(os.environ.get("NEPANTLA_PACKS_DIR", ROOT / "packs")),
            dev_mode=_flag("NEPANTLA_DEV_MODE"),
            admin_token=os.environ.get("NEPANTLA_ADMIN_TOKEN", "").strip(),
            force_https=_flag("NEPANTLA_FORCE_HTTPS"),
            import_example_packs=_flag("NEPANTLA_IMPORT_EXAMPLE_PACKS", True),
            enable_backups=_flag("NEPANTLA_BACKUPS", True),
            backup_keep=int(os.environ.get("NEPANTLA_BACKUP_KEEP", "14")),
            max_upload_bytes=int(os.environ.get("NEPANTLA_MAX_UPLOAD_BYTES", 3 * 1024 * 1024)),
            max_audio_seconds=float(os.environ.get("NEPANTLA_MAX_AUDIO_SECONDS", "30")),
            session_days=int(os.environ.get("NEPANTLA_SESSION_DAYS", "30")),
            ffmpeg=os.environ.get("NEPANTLA_FFMPEG", "ffmpeg"),
            ffprobe=os.environ.get("NEPANTLA_FFPROBE", "ffprobe"),
        )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "nepantla.db"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def phrases_file(self) -> Path:
        return self.frontend_dir / "data" / "phrases.es.json"
