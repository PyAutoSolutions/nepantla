"""Normalización de audio con ffmpeg.

El navegador graba en lo que puede (WebM/Opus en Chrome y Firefox, MP4/AAC en
Safari). Aquí todo se convierte a lo que pide la especificación: Opus, mono,
16 kHz, unos 16 kbps.

Decisiones de privacidad:
* Se eliminan los metadatos del archivo (`-map_metadata -1`): nada de modelo
  de teléfono, fecha ni etiquetas de la app que grabó.
* Solo se aceptan contenedores de audio conocidos, detectados por sus
  primeros bytes. Así ffmpeg nunca abre "listas de reproducción" que podrían
  apuntar a otros archivos del servidor.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .config import Settings

TIMEOUT_SECONDS = 40
TARGET_PEAK_DB = -1.5


class AudioError(Exception):
    """El archivo no se pudo leer o convertir."""


def ffmpeg_available(settings: Settings) -> bool:
    return shutil.which(settings.ffmpeg) is not None and shutil.which(settings.ffprobe) is not None


def sniff_container(head: bytes) -> str | None:
    """Devuelve el formato de entrada para ffmpeg o None si no es audio válido."""
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "matroska"  # WebM (Chrome, Firefox, Android)
    if head.startswith(b"OggS"):
        return "ogg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "mp4"  # Safari / iOS
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "wav"
    if head.startswith(b"caff"):
        return "caf"
    return None


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AudioError("La conversión tardó demasiado.") from exc
    except FileNotFoundError as exc:
        raise AudioError("ffmpeg no está instalado en el servidor.") from exc


def probe(settings: Settings, path: Path) -> dict:
    result = _run(
        [
            settings.ffprobe, "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels:format=duration",
            "-of", "json", str(path),
        ]
    )
    if result.returncode != 0:
        raise AudioError("No se pudo leer el audio.")
    data = json.loads(result.stdout or b"{}")
    streams = data.get("streams") or [{}]
    return {
        "codec": streams[0].get("codec_name"),
        "sample_rate": int(streams[0].get("sample_rate") or 0),
        "channels": int(streams[0].get("channels") or 0),
        "duration": float((data.get("format") or {}).get("duration") or 0.0),
    }


def _peak_db(settings: Settings, fmt: str, src: Path) -> float | None:
    result = _run(
        [
            settings.ffmpeg, "-nostdin", "-hide_banner", "-f", fmt, "-i", str(src),
            "-vn", "-af", "volumedetect", "-f", "null", "-",
        ]
    )
    match = re.search(rb"max_volume:\s*(-?\d+(?:\.\d+)?) dB", result.stderr or b"")
    return float(match.group(1)) if match else None


def normalize_to_opus(settings: Settings, src: Path, dst: Path, fmt: str) -> dict:
    """Convierte `src` a Opus mono 16 kHz ~16 kbps en `dst`.

    Sube o baja el volumen para que el pico quede en -1.5 dB. Es una
    ganancia fija (no un compresor): no deforma la voz.
    """
    peak = _peak_db(settings, fmt, src)
    filters = ["highpass=f=70"]
    if peak is not None and peak > -80:
        gain = max(-20.0, min(30.0, TARGET_PEAK_DB - peak))
        filters.append(f"volume={gain:.1f}dB")

    dst.parent.mkdir(parents=True, exist_ok=True)
    result = _run(
        [
            settings.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", fmt, "-i", str(src),
            "-vn", "-sn", "-dn", "-map", "0:a:0",
            "-map_metadata", "-1", "-map_chapters", "-1",
            "-fflags", "+bitexact", "-flags:a", "+bitexact",
            "-t", str(settings.max_audio_seconds + 1),
            "-af", ",".join(filters),
            "-ac", "1", "-ar", "16000",
            "-c:a", "libopus", "-b:a", "16k", "-vbr", "on", "-application", "voip",
            "-f", "opus", str(dst),
        ]
    )
    if result.returncode != 0 or not dst.is_file() or dst.stat().st_size == 0:
        dst.unlink(missing_ok=True)
        raise AudioError("No se pudo convertir el audio. Intenta grabar otra vez.")

    info = probe(settings, dst)
    info["bytes"] = dst.stat().st_size
    return info
