"""Arma la demostración estática de Nepantla (sin servidor).

    python scripts/build_static_demo.py            # la deja en dist/
    python scripts/build_static_demo.py otra/ruta

El resultado es una carpeta de archivos que se puede hospedar gratis en
cualquier sitio estático (GitHub Pages, por ejemplo). Trae la app de consulta
completa y los paquetes de AUDIO DE PRUEBA. Funciona sin internet igual que
la app normal.

Lo que NO trae, porque necesita servidor: el estudio de grabación, la
revisión, el retiro de voces, los contadores y los reportes. En este modo la
app no envía nada a ningún lado.

Regla de gobernanza: aquí solo se copian paquetes marcados `is_test`. Una voz
real nunca debe quedar en una copia estática, porque ahí nadie podría
retirarla. Si aparece un paquete real, el script se detiene.

Necesita las dependencias de pruebas (`pip install -r requirements-dev.txt`).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def build(dest: Path) -> dict:
    from fastapi.testclient import TestClient

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ROOT / "frontend", dest)

    with tempfile.TemporaryDirectory(prefix="nepantla-demo-") as tmp:
        os.environ.update(
            {
                "NEPANTLA_DEV_MODE": "1",
                "NEPANTLA_DATA_DIR": tmp,
                "NEPANTLA_PACKS_DIR": str(ROOT / "packs"),
                "NEPANTLA_ADMIN_TOKEN": "",
                "NEPANTLA_BACKUPS": "0",
                "NEPANTLA_IMPORT_EXAMPLE_PACKS": "1",
            }
        )
        from backend.config import Settings
        from backend.main import create_app

        # Se usa el servidor de verdad para que los manifests salgan idénticos
        # (misma regla de doble revisión, mismos campos).
        with TestClient(create_app(Settings.from_env())) as client:
            listing = client.get("/api/packs").json()
            real = [pack["pack_id"] for pack in listing["packs"] if not pack.get("is_test")]
            if real:
                raise SystemExit(
                    "Hay paquetes que no son de prueba: " + ", ".join(real) + ". "
                    "La demostración estática solo puede llevar AUDIO DE PRUEBA."
                )
            api = dest / "api"
            (api / "packs").mkdir(parents=True)
            audio_files = 0
            for pack in listing["packs"]:
                pack_id = pack["pack_id"]
                pack_dir = api / "packs" / pack_id
                pack_dir.mkdir(parents=True)
                manifest = client.get(f"/api/packs/{pack_id}/manifest.json").json()
                (pack_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
                # Todos los audios del paquete en un solo JSON (base64): una sola
                # petición y ningún hospedaje se queja de la extensión ".opus".
                audio = {}
                for entry in manifest["phrases"]:
                    response = client.get(f"/api/packs/{pack_id}/audio/{entry['id']}.opus")
                    response.raise_for_status()
                    audio[entry["id"]] = base64.b64encode(response.content).decode("ascii")
                if manifest.get("greeting"):
                    response = client.get(f"/api/packs/{pack_id}/greeting.opus")
                    response.raise_for_status()
                    audio["greeting"] = base64.b64encode(response.content).decode("ascii")
                audio_files += len(audio)
                (pack_dir / "audio.json").write_text(
                    json.dumps({"format": "opus-base64", "audio": audio}), encoding="utf-8"
                )
            (api / "packs.json").write_text(
                json.dumps({"dev_mode": True, "packs": listing["packs"], "withdrawn": []}, ensure_ascii=False),
                encoding="utf-8",
            )

    # GitHub Pages: que no intente procesar el sitio con Jekyll.
    (dest / ".nojekyll").write_text("", encoding="utf-8")

    digest = hashlib.sha256()
    for path in sorted(dest.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(dest).as_posix().encode())
            digest.update(path.read_bytes())
    build_id = "demo-" + digest.hexdigest()[:10]

    config = dest / "js" / "config.js"
    text = config.read_text(encoding="utf-8")
    patched = text.replace("export const STATIC_DEMO = false;", "export const STATIC_DEMO = true;").replace(
        'export const STATIC_BUILD = "";', f'export const STATIC_BUILD = "{build_id}";'
    )
    if patched.count("STATIC_DEMO = true") != 1 or build_id not in patched:
        raise SystemExit("No pude activar el modo de demostración en js/config.js")
    config.write_text(patched, encoding="utf-8")

    worker = dest / "sw.js"
    worker.write_text(worker.read_text(encoding="utf-8").replace("__BUILD__", build_id), encoding="utf-8")

    files = [path for path in dest.rglob("*") if path.is_file()]
    return {
        "dest": dest,
        "build": build_id,
        "packs": [pack["pack_id"] for pack in listing["packs"]],
        "audio_files": audio_files,
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
    }


def main(argv: list[str]) -> int:
    dest = Path(argv[1]).resolve() if len(argv) > 1 else ROOT / "dist"
    if dest == ROOT or ROOT in dest.parents and dest.name in {"frontend", "backend", "packs", "docs", "scripts"}:
        print("Esa carpeta es parte del proyecto: elige otra para la demostración.")
        return 1
    result = build(dest)
    print(
        f"Demostración lista en {result['dest']}: {result['files']} archivos, "
        f"{result['bytes'] / 1024:.0f} KB, paquetes {', '.join(result['packs'])} "
        f"({result['audio_files']} audios de prueba)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
