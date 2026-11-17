"""Genera los paquetes de ejemplo con AUDIO DE PRUEBA.

    python scripts/make_test_packs.py

Crea `packs/pack-prueba-a-001/` y `packs/pack-prueba-b-001/` en el formato
abierto de Nepantla (ver docs/PACK_FORMAT.md).

Por qué los audios son tonos y no palabras
------------------------------------------
La regla del proyecto es "solo audio humano revisado". Un audio de relleno
con voz sintética podría confundirse con una grabación de verdad, así que
aquí no hay voz de ningún tipo: cada frase es una melodía corta de tonos
puros, distinta para cada frase. Nadie puede tomarla por una lengua.

Además, cada paquete de prueba:
* lleva `"is_test": true` y `"status": "draft"`, así que el servidor solo lo
  muestra en modo demostración y se niega a publicarlo;
* dice AUDIO DE PRUEBA en el nombre de la lengua, en el README y en las
  etiquetas internas de cada archivo .opus.

Necesita ffmpeg con libopus. No usa ninguna biblioteca fuera de Python.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHRASES_FILE = ROOT / "frontend" / "data" / "phrases.es.json"
PACKS_DIR = ROOT / "packs"

RATE = 16000
NOTE_SECONDS = 0.15
GAP_SECONDS = 0.045
REVIEWERS = ["Revisor de prueba 1", "Revisor de prueba 2"]
SPEAKER = "Generador de tonos (no es una voz)"

# Escalas pentatónicas (Hz). Cada paquete suena en un registro distinto para
# que la pantalla "elegir variante por audio" se pueda probar de verdad.
SCALES = {
    "prueba-a-001": [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50],
    "prueba-b-001": [196.00, 220.00, 261.63, 293.66, 329.63, 392.00],
}

PACKS = {
    "prueba-a-001": {
        "variant": "Tonos agudos (prueba A)",
        "community": "Ninguna: es un paquete de demostración",
        "greeting": [0, 2, 4, 5],          # arpegio que sube
        "harmonic": 0.0,
        "phrases": "all",
        "single_review": [],
    },
    "prueba-b-001": {
        "variant": "Tonos graves (prueba B)",
        "community": "Ninguna: es un paquete de demostración",
        "greeting": [5, 4, 2, 0],          # arpegio que baja
        "harmonic": 0.35,
        # Paquete incompleto a propósito: sirve para ver cómo se comporta la
        # app cuando a una variante le faltan frases.
        "phrases": "emergency+urgencias",
        # Estas dos frases llevan UN solo revisor: la app no debe mostrarlas.
        "single_review": ["urg-016", "urg-017"],
    },
}


def tone(freq: float, seconds: float, harmonic: float) -> list[int]:
    """Un tono con entrada y salida suaves (sin chasquidos)."""
    total = int(seconds * RATE)
    fade = int(0.012 * RATE)
    samples = []
    for i in range(total):
        t = i / RATE
        value = math.sin(2 * math.pi * freq * t) + harmonic * math.sin(2 * math.pi * freq * 2 * t)
        envelope = min(1.0, i / fade, (total - 1 - i) / fade)
        samples.append(int(9500 * envelope * value / (1 + harmonic)))
    return samples


def melody(pack_id: str, phrase_id: str, steps: list[int] | None = None) -> list[int]:
    """Melodía de 3 o 4 notas que depende solo del paquete y de la frase."""
    scale = SCALES[pack_id]
    harmonic = PACKS[pack_id]["harmonic"]
    if steps is None:
        digest = hashlib.sha256(f"{pack_id}/{phrase_id}".encode()).digest()
        count = 3 + digest[0] % 2
        steps = [digest[1 + i] % len(scale) for i in range(count)]
    samples: list[int] = [0] * int(0.03 * RATE)
    for step in steps:
        samples += tone(scale[step], NOTE_SECONDS, harmonic)
        samples += [0] * int(GAP_SECONDS * RATE)
    return samples


def write_opus(samples: list[int], target: Path, title: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nepantla-tonos-") as tmp:
        wav_path = Path(tmp) / "tono.wav"
        with wave.open(str(wav_path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(RATE)
            out.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        subprocess.run(
            [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(wav_path),
                "-map_metadata", "-1",
                "-metadata", f"title=AUDIO DE PRUEBA: {title}",
                "-metadata", "artist=Nepantla (tonos generados, sin voz)",
                "-metadata", "comment=AUDIO DE PRUEBA. No es una voz ni una lengua real.",
                "-fflags", "+bitexact", "-flags:a", "+bitexact",
                "-ac", "1", "-ar", str(RATE),
                "-c:a", "libopus", "-b:a", "16k", "-vbr", "on", "-application", "voip",
                "-f", "opus", str(target),
            ],
            check=True,
        )


def phrase_ids(data: dict, selection: str) -> list[str]:
    everything = [p["id"] for p in data["phrases"]]
    if selection == "all":
        return everything
    wanted = set(data["emergency"]) | {p["id"] for p in data["phrases"] if p["scenario"] == "urgencias"}
    return [phrase_id for phrase_id in everything if phrase_id in wanted]


def build_pack(data: dict, pack_id: str, today: str) -> dict:
    spec = PACKS[pack_id]
    pack_dir = PACKS_DIR / f"pack-{pack_id}"
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    (pack_dir / "audio").mkdir(parents=True)

    entries = []
    for phrase_id in phrase_ids(data, spec["phrases"]):
        write_opus(melody(pack_id, phrase_id), pack_dir / "audio" / f"{phrase_id}.opus", phrase_id)
        reviewers = REVIEWERS[:1] if phrase_id in spec["single_review"] else REVIEWERS
        entries.append(
            {
                "id": phrase_id,
                "audio": f"audio/{phrase_id}.opus",
                "reviewed_by": reviewers,
                "recorded_by": SPEAKER,
                "approved_at": today,
            }
        )
    write_opus(melody(pack_id, "greeting", spec["greeting"]), pack_dir / "greeting.opus", "saludo")

    manifest = {
        "format_version": 1,
        "pack_id": pack_id,
        "language": "AUDIO DE PRUEBA (no es una lengua real)",
        "variant": spec["variant"],
        "community": spec["community"],
        "version": "0.1.0",
        "status": "draft",
        "license": "CC0 1.0: tonos generados por computadora, sin voz humana",
        "community_label": None,
        "guardians": ["Equipo de pruebas de Nepantla"],
        "is_test": True,
        "greeting": {
            "audio": "greeting.opus",
            "reviewed_by": REVIEWERS,
            "recorded_by": SPEAKER,
            "approved_at": today,
        },
        "phrases": entries,
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (pack_dir / "LICENSE.txt").write_text(
        "AUDIO DE PRUEBA\n\n"
        "Estos archivos son tonos generados por computadora con\n"
        "scripts/make_test_packs.py. No contienen voz humana ni representan a\n"
        "ninguna lengua, comunidad o persona.\n\n"
        "Se entregan al dominio público (CC0 1.0 Universal):\n"
        "https://creativecommons.org/publicdomain/zero/1.0/deed.es\n",
        encoding="utf-8",
    )
    single = len(spec["single_review"])
    (pack_dir / "README.md").write_text(
        f"# Paquete `{pack_id}`: AUDIO DE PRUEBA\n\n"
        "**Esto no es una lengua real.** Cada \"frase\" es una melodía corta de tonos\n"
        "generados por computadora. Existe para poder probar y mostrar Nepantla\n"
        "sin usar la voz de nadie.\n\n"
        f"- Variante de prueba: {spec['variant']}\n"
        f"- Frases con audio: {len(entries)}"
        + (f" ({single} con un solo revisor, que la app no muestra)\n" if single else "\n")
        + "- Estado: `draft` y `is_test: true`. El servidor solo lo enseña en modo\n"
        "  demostración (`NEPANTLA_DEV_MODE=1`) y se niega a publicarlo.\n"
        "- Revisores y \"hablante\": nombres de relleno.\n\n"
        "Para regenerarlo: `python scripts/make_test_packs.py`.\n\n"
        "Formato abierto de Nepantla, versión 1. Ver `docs/PACK_FORMAT.md`.\n",
        encoding="utf-8",
    )
    size = sum(f.stat().st_size for f in pack_dir.rglob("*.opus"))
    return {"pack_id": pack_id, "phrases": len(entries), "audio_bytes": size}


def main() -> int:
    if shutil.which("ffmpeg") is None:
        print("Hace falta ffmpeg (con libopus) para generar los audios de prueba.")
        return 1
    data = json.loads(PHRASES_FILE.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    for pack_id in PACKS:
        result = build_pack(data, pack_id, today)
        print(f"{result['pack_id']}: {result['phrases']} frases, {result['audio_bytes'] / 1024:.0f} KB de audio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
