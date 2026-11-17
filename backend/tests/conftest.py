"""Utilidades comunes de las pruebas.

Cada prueba levanta la app completa con una base SQLite nueva en una
carpeta temporal: nada toca los datos reales.
"""
from __future__ import annotations

import io
import json
import math
import shutil
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import ROOT, Settings
from backend.main import create_app

ADMIN = "token-admin-solo-para-pruebas-1234567890"

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="hace falta ffmpeg para probar la normalización de audio",
)


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
        data_dir=tmp_path / "data",
        frontend_dir=ROOT / "frontend",
        packs_dir=tmp_path / "packs",
        dev_mode=False,
        admin_token=ADMIN,
        force_https=False,
        import_example_packs=False,
        enable_backups=False,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def dev_client(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, dev_mode=True))) as test_client:
        yield test_client


def admin() -> dict:
    return {"Authorization": f"Bearer {ADMIN}"}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def wav_bytes(seconds: float = 1.0, freq: float = 440.0, rate: int = 44100, channels: int = 2) -> bytes:
    """Un tono en WAV estéreo a 44.1 kHz: a propósito distinto del formato final."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            sample = int(12000 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", sample) * channels
        out.writeframes(bytes(frames))
    return buffer.getvalue()


class Studio:
    """Atajos para recorrer el flujo del estudio en las pruebas."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def create_pack(self, pack_id: str = "nah-ejemplo-001", **extra) -> dict:
        body = {
            "pack_id": pack_id,
            "language": "Lengua de ejemplo",
            "variant": "Variante de ejemplo",
            "community": "Comunidad de ejemplo",
            "license": "Licencia de ejemplo",
            "guardians": ["Guardiana Uno"],
        }
        body.update(extra)
        response = self.client.post("/api/studio/packs", json=body, headers=admin())
        assert response.status_code == 201, response.text
        return response.json()

    def session(self, pack_id: str, role: str, alias: str, is_interpreter: bool = False) -> str:
        response = self.client.post(
            "/api/studio/session",
            json={"pack_id": pack_id, "role": role, "alias": alias, "is_interpreter": is_interpreter},
            headers=admin(),
        )
        assert response.status_code == 201, response.text
        return response.json()["token"]

    def consent(self, token: str, credit_name: str = "Hablante Uno") -> str:
        response = self.client.post(
            "/api/studio/consent",
            json={
                "credit_name": credit_name,
                "understands_use": True,
                "understands_withdrawal": True,
                "accepts_license": True,
                "is_adult": True,
            },
            headers=auth(token),
        )
        assert response.status_code == 201, response.text
        return response.json()["withdrawal_token"]

    def upload(self, token: str, phrase_id: str, data: bytes | None = None):
        return self.client.post(
            "/api/studio/recordings",
            data={"phrase_id": phrase_id},
            files={"audio": ("grabacion.wav", data if data is not None else wav_bytes(), "audio/wav")},
            headers=auth(token),
        )

    def review(self, token: str, recording_id: int, verdict: str = "approve", note: str = ""):
        return self.client.post(
            "/api/studio/reviews",
            json={"recording_id": recording_id, "verdict": verdict, "note": note},
            headers=auth(token),
        )

    def team(self, pack_id: str = "nah-ejemplo-001") -> dict:
        """Paquete con hablante (ya con consentimiento), intérprete, enfermera y guardiana."""
        self.create_pack(pack_id)
        speaker = self.session(pack_id, "speaker", "Hablante Uno")
        return {
            "pack_id": pack_id,
            "speaker": speaker,
            "withdrawal": self.consent(speaker),
            "interpreter": self.session(pack_id, "reviewer", "Intérprete Ana", is_interpreter=True),
            "nurse": self.session(pack_id, "reviewer", "Enfermera Luz"),
            "guardian": self.session(pack_id, "guardian", "Guardiana Uno"),
        }

    def approved_phrase(self, team: dict, phrase_id: str = "urg-001") -> int:
        """Graba una frase y la pasa por las dos revisiones."""
        uploaded = self.upload(team["speaker"], phrase_id)
        assert uploaded.status_code == 201, uploaded.text
        recording_id = uploaded.json()["recording_id"]
        assert self.review(team["interpreter"], recording_id).status_code == 201
        second = self.review(team["nurse"], recording_id)
        assert second.status_code == 201 and second.json()["status"] == "approved", second.text
        return recording_id

    def publish(self, team: dict) -> dict:
        response = self.client.post("/api/studio/pack/approve", headers=auth(team["guardian"]))
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
def studio(client) -> Studio:
    return Studio(client)


def make_pack_dir(
    root: Path,
    pack_id: str,
    phrases: dict[str, list[str]],
    *,
    status: str = "approved",
    is_test: bool = False,
    greeting: list[str] | None = None,
    version: str = "1.0.0",
) -> Path:
    """Crea una carpeta `pack-<codigo>/` en formato abierto con audios falsos."""
    pack_dir = root / f"pack-{pack_id}"
    (pack_dir / "audio").mkdir(parents=True)
    manifest = {
        "format_version": 1,
        "pack_id": pack_id,
        "language": "Lengua de ejemplo",
        "variant": "Variante de ejemplo",
        "community": "Comunidad de ejemplo",
        "version": version,
        "status": status,
        "license": "Licencia de ejemplo",
        "community_label": None,
        "guardians": ["Guardiana Uno"],
        "is_test": is_test,
        "phrases": [],
    }
    for phrase_id, reviewers in phrases.items():
        (pack_dir / "audio" / f"{phrase_id}.opus").write_bytes(b"OggS-audio-falso-" + phrase_id.encode())
        manifest["phrases"].append(
            {
                "id": phrase_id,
                "audio": f"audio/{phrase_id}.opus",
                "reviewed_by": reviewers,
                "recorded_by": "Hablante Uno",
                "approved_at": "2026-12-01",
            }
        )
    if greeting is not None:
        (pack_dir / "greeting.opus").write_bytes(b"OggS-saludo-falso")
        manifest["greeting"] = {
            "audio": "greeting.opus",
            "reviewed_by": greeting,
            "recorded_by": "Hablante Uno",
            "approved_at": "2026-12-01",
        }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return pack_dir


def import_dir(settings: Settings, pack_dir: Path, **kwargs) -> dict:
    from backend.db import open_db
    from backend.packs_io import import_pack_dir

    with open_db(settings) as conn:
        return import_pack_dir(conn, settings, pack_dir, **kwargs)
