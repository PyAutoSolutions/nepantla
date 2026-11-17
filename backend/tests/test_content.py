"""Contenido: frases en español, pictogramas y paquetes de ejemplo."""
from __future__ import annotations

import json
import re
from collections import Counter

from backend.config import ROOT
from backend.db import open_db
from backend.models import ANSWER_TYPES

FRONTEND = ROOT / "frontend"
DATA = json.loads((FRONTEND / "data" / "phrases.es.json").read_text(encoding="utf-8"))
PHRASES = DATA["phrases"]
SPRITE = (FRONTEND / "icons" / "pictos.svg").read_text(encoding="utf-8")
SYMBOLS = set(re.findall(r'<symbol[^>]*\bid="([^"]+)"', SPRITE))


def test_hay_unas_80_frases_en_6_escenarios():
    assert 75 <= len(PHRASES) <= 90
    assert len(DATA["scenarios"]) == 6
    per_scenario = Counter(p["scenario"] for p in PHRASES)
    assert set(per_scenario) == {s["id"] for s in DATA["scenarios"]}
    assert min(per_scenario.values()) >= 10


def test_los_escenarios_son_los_de_la_especificacion():
    titles = [s["title"] for s in DATA["scenarios"]]
    assert titles == ["Urgencias", "Embarazo", "Niño enfermo", "Medicinas", "Consentimiento", "Señales de alarma"]


def test_ids_unicos_y_con_el_prefijo_de_su_escenario():
    ids = [p["id"] for p in PHRASES]
    assert len(ids) == len(set(ids))
    prefixes = {s["id"]: s["prefix"] for s in DATA["scenarios"]}
    for phrase in PHRASES:
        assert re.fullmatch(rf"{prefixes[phrase['scenario']]}-\d{{3}}", phrase["id"]), phrase["id"]


def test_la_numeracion_no_tiene_huecos():
    for scenario in DATA["scenarios"]:
        numbers = [int(p["id"][-3:]) for p in PHRASES if p["scenario"] == scenario["id"]]
        assert numbers == list(range(1, len(numbers) + 1))


def test_cada_frase_tiene_los_campos_de_la_especificacion():
    for phrase in PHRASES:
        assert {"id", "scenario", "es_text", "answer_type", "pictogram", "priority"} <= set(phrase)
        assert phrase["answer_type"] in ANSWER_TYPES
        assert phrase["priority"] in {"normal", "critica"}
        assert phrase["es_text"].strip() == phrase["es_text"] and len(phrase["es_text"]) <= 80


def test_las_preguntas_son_preguntas_y_las_instrucciones_no():
    for phrase in PHRASES:
        text = phrase["es_text"]
        if phrase["answer_type"] == "none":
            assert text.endswith("."), text
        else:
            assert text.startswith("¿") and text.endswith("?"), text


def test_se_usan_todos_los_tipos_de_respuesta():
    assert {p["answer_type"] for p in PHRASES} == set(ANSWER_TYPES)


def test_los_ejemplos_de_la_especificacion_conservan_su_id():
    by_id = {p["id"]: p["es_text"] for p in PHRASES}
    assert by_id["urg-001"] == "¿Le falta el aire?"
    assert by_id["urg-002"] == "¿Le duele el pecho?"
    assert by_id["emb-003"] == "¿Ha tenido sangrado por la vagina?"
    assert by_id["emb-004"] == "¿Siente menos movimientos del bebé?"
    assert by_id["nin-005"] == "¿Su hijo tiene fiebre?"
    assert by_id["med-006"] == "¿Es alérgico a alguna medicina?"
    assert by_id["con-007"] == "¿Entendió lo que le vamos a hacer?"
    assert by_id["ala-008"] == "Si le pasa esto, regrese de inmediato."


def test_todo_el_contenido_esta_marcado_sin_revision_clinica():
    assert DATA["clinical_review"] == "pendiente"
    assert "SIN REVISIÓN CLÍNICA" in DATA["notice"]


def test_el_modo_emergencia_abre_cinco_frases_criticas():
    by_id = {p["id"]: p for p in PHRASES}
    assert len(DATA["emergency"]) == 5
    for phrase_id in DATA["emergency"]:
        assert by_id[phrase_id]["priority"] == "critica"
        assert by_id[phrase_id]["answer_type"] == "yes_no"


def test_cada_pictograma_existe_en_el_sprite():
    needed = {p["pictogram"] for p in PHRASES}
    needed |= {s["pictogram"] for s in DATA["scenarios"]}
    needed |= {o["pictogram"] for o in DATA["options"].values() if "pictogram" in o}
    needed |= {p["pictogram"] for p in DATA["system_phrases"]}
    missing = sorted(needed - SYMBOLS)
    assert missing == []


def test_el_sprite_no_repite_ids_y_no_trae_estilos_en_linea():
    ids = re.findall(r'<symbol[^>]*\bid="([^"]+)"', SPRITE)
    assert len(ids) == len(set(ids)) and len(ids) >= 100
    assert " style=" not in SPRITE and "<style" not in SPRITE and "<script" not in SPRITE


def test_las_opciones_de_respuesta_existen():
    for phrase in PHRASES:
        if phrase["answer_type"] == "pictogram":
            assert len(phrase["options"]) >= 2
            for option in phrase["options"]:
                assert option in DATA["options"], option
        else:
            assert "options" not in phrase
    for option in DATA["options"].values():
        assert option["es"] and ("pictogram" in option or "numeral" in option)


def test_las_fuentes_citadas_existen():
    for scenario in DATA["scenarios"]:
        for source in scenario.get("sources", []):
            assert source in DATA["sources"]
    for source in DATA["sources"].values():
        assert source["url"].startswith("https://") and source["title"]


def test_las_frases_se_cargan_en_la_base(settings, client):
    with open_db(settings) as conn:
        rows = conn.execute("SELECT id, es_text FROM phrases WHERE active = 1 ORDER BY position").fetchall()
    assert [row["id"] for row in rows] == ["greeting"] + [p["id"] for p in PHRASES]


def test_el_service_worker_guarda_todo_el_cascaron():
    """Si se añade un archivo al frontend y no a la lista del service worker,
    la app fallaría en modo avión. Esta prueba lo impide."""
    source = (FRONTEND / "sw.js").read_text(encoding="utf-8")
    listed = set(re.findall(r'"\./([^"]*)"', source.split("const SHELL")[1].split("];")[0]))
    expected = set()
    for path in FRONTEND.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(FRONTEND).as_posix()
        if relative == "sw.js" or relative.startswith("audio/") or relative.endswith((".md", ".txt")):
            continue
        expected.add(relative)
    assert listed - {""} == expected
    assert "" in listed  # la raíz "./"


def test_los_paquetes_de_ejemplo_son_audio_de_prueba_etiquetado():
    """Nunca se publican como si fueran una lengua real."""
    packs = sorted((ROOT / "packs").glob("pack-*/manifest.json"))
    assert len(packs) >= 1
    for manifest_file in packs:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest["is_test"] is True
        assert manifest["status"] == "draft"
        assert "AUDIO DE PRUEBA" in manifest["language"]
        assert manifest["format_version"] == 1
        for phrase in manifest["phrases"]:
            assert (manifest_file.parent / phrase["audio"]).is_file()
        readme = (manifest_file.parent / "README.md").read_text(encoding="utf-8")
        assert "AUDIO DE PRUEBA" in readme
        assert (manifest_file.parent / "LICENSE.txt").is_file()


def test_el_paquete_de_prueba_principal_cubre_todas_las_frases():
    manifest = json.loads((ROOT / "packs" / "pack-prueba-a-001" / "manifest.json").read_text(encoding="utf-8"))
    assert {p["id"] for p in manifest["phrases"]} == {p["id"] for p in PHRASES}
    assert manifest["greeting"]["audio"] == "greeting.opus"
    for phrase in manifest["phrases"]:
        assert len(set(phrase["reviewed_by"])) >= 2


def test_los_paquetes_de_ejemplo_se_importan_solos_y_solo_se_ven_en_modo_demo(tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    from .conftest import make_settings

    demo = make_settings(tmp_path / "demo", dev_mode=True, import_example_packs=True, packs_dir=ROOT / "packs")
    with TestClient(create_app(demo)) as client:
        packs = client.get("/api/packs").json()["packs"]
        assert {p["pack_id"] for p in packs} >= {"prueba-a-001"}
        assert all(p["is_test"] and p["status"] == "draft" for p in packs)
        audio = client.get("/api/packs/prueba-a-001/audio/urg-001.opus")
        assert audio.status_code == 200 and audio.content.startswith(b"OggS")

    real = make_settings(tmp_path / "real", dev_mode=False, import_example_packs=True, packs_dir=ROOT / "packs")
    with TestClient(create_app(real)) as client:
        assert client.get("/api/packs").json()["packs"] == []
        assert client.get("/api/packs/prueba-a-001/manifest.json").status_code == 404
