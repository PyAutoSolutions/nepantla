"""La demostración estática (scripts/build_static_demo.py).

Es la app de consulta con los paquetes de AUDIO DE PRUEBA, lista para un
hospedaje de archivos sin servidor. Lo importante: que solo lleve audio de
prueba, que respete la doble revisión y que quede con el envío apagado.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def demo(tmp_path_factory) -> Path:
    dest = tmp_path_factory.mktemp("demo") / "dist"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_static_demo.py"), str(dest)],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return dest


def test_la_demostracion_solo_lleva_audio_de_prueba(demo):
    listing = json.loads((demo / "api" / "packs.json").read_text(encoding="utf-8"))
    assert listing["dev_mode"] is True and listing["withdrawn"] == []
    assert {pack["pack_id"] for pack in listing["packs"]} == {"prueba-a-001", "prueba-b-001"}
    for pack in listing["packs"]:
        assert pack["is_test"] is True and pack["status"] == "draft"
        assert "AUDIO DE PRUEBA" in pack["language"]


def test_la_demostracion_respeta_la_doble_revision(demo):
    bundles = {}
    for pack_id in ("prueba-a-001", "prueba-b-001"):
        pack_dir = demo / "api" / "packs" / pack_id
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        bundle = json.loads((pack_dir / "audio.json").read_text(encoding="utf-8"))["audio"]
        bundles[pack_id] = bundle
        assert manifest["phrases"], pack_id
        for entry in manifest["phrases"]:
            assert len(set(entry["reviewed_by"])) >= 2
            data = base64.b64decode(bundle[entry["id"]])
            assert data[:4] == b"OggS" and len(data) == entry["bytes"]
        assert len(base64.b64decode(bundle["greeting"])) == manifest["greeting"]["bytes"]
        # Ni un audio de más: solo lo que el manifest declara.
        assert set(bundle) == {entry["id"] for entry in manifest["phrases"]} | {"greeting"}
    # Las dos frases de un solo revisor del paquete B no viajan en la demostración.
    assert "urg-001" in bundles["prueba-b-001"] and not {"urg-016", "urg-017"} & set(bundles["prueba-b-001"])


def test_la_demostracion_queda_con_el_envio_apagado(demo):
    config = (demo / "js" / "config.js").read_text(encoding="utf-8")
    assert "export const STATIC_DEMO = true;" in config
    assert "__BUILD__" not in (demo / "sw.js").read_text(encoding="utf-8")
    assert (demo / ".nojekyll").is_file() and (demo / "index.html").is_file()
    # El código fuente no cambia: el interruptor solo se activa en la copia.
    source = (ROOT / "frontend" / "js" / "config.js").read_text(encoding="utf-8")
    assert "export const STATIC_DEMO = false;" in source
