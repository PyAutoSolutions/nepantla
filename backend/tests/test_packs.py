"""Paquetes: qué se lista, qué se sirve y qué no."""
from __future__ import annotations

import json

from backend.db import open_db
from backend.packs_io import export_pack

from .conftest import import_dir, make_pack_dir

DOS = ["Intérprete Ana", "Enfermera Luz"]


def test_sin_paquetes_la_lista_esta_vacia(client):
    data = client.get("/api/packs").json()
    assert data == {"dev_mode": False, "packs": [], "withdrawn": []}


def test_paquete_aprobado_aparece_en_la_lista(client, settings, tmp_path):
    import_dir(settings, make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": DOS, "urg-002": DOS}))
    packs = client.get("/api/packs").json()["packs"]
    assert [p["pack_id"] for p in packs] == ["nah-ejemplo-001"]
    assert packs[0]["phrase_count"] == 2
    assert packs[0]["total_bytes"] > 0
    assert packs[0]["status"] == "approved"


def test_borrador_no_se_ve_fuera_del_modo_desarrollo(client, settings, tmp_path):
    import_dir(settings, make_pack_dir(tmp_path, "nah-borrador-001", {"urg-001": DOS}, status="draft"))
    assert client.get("/api/packs").json()["packs"] == []
    assert client.get("/api/packs/nah-borrador-001/manifest.json").status_code == 404
    assert client.get("/api/packs/nah-borrador-001/audio/urg-001.opus").status_code == 404


def test_borrador_si_se_ve_en_modo_desarrollo(dev_client, tmp_path):
    settings = dev_client.app.state.settings
    import_dir(settings, make_pack_dir(tmp_path, "nah-borrador-001", {"urg-001": DOS}, status="draft"))
    data = dev_client.get("/api/packs").json()
    assert data["dev_mode"] is True
    assert [p["pack_id"] for p in data["packs"]] == ["nah-borrador-001"]
    assert data["packs"][0]["status"] == "draft"
    assert dev_client.get("/api/packs/nah-borrador-001/manifest.json").status_code == 200


def test_manifest_tiene_el_formato_abierto(client, settings, tmp_path):
    import_dir(settings, make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": DOS}, greeting=DOS))
    manifest = client.get("/api/packs/nah-ejemplo-001/manifest.json").json()
    for field in (
        "format_version", "pack_id", "language", "variant", "community", "version",
        "status", "license", "community_label", "guardians", "phrases",
    ):
        assert field in manifest
    assert manifest["format_version"] == 1
    assert manifest["guardians"] == ["Guardiana Uno"]
    phrase = manifest["phrases"][0]
    assert phrase["id"] == "urg-001"
    assert phrase["audio"] == "audio/urg-001.opus"
    assert phrase["reviewed_by"] == DOS
    assert phrase["recorded_by"] == "Hablante Uno"
    assert phrase["approved_at"] == "2026-12-01"
    assert manifest["greeting"]["audio"] == "greeting.opus"


def test_frase_con_un_solo_revisor_no_existe_para_la_app(client, settings, tmp_path):
    """Regla 1: nada se reproduce sin dos revisores."""
    pack_dir = make_pack_dir(
        tmp_path, "nah-ejemplo-001", {"urg-001": DOS, "urg-002": ["Intérprete Ana"], "urg-003": []}
    )
    result = import_dir(settings, pack_dir)
    assert result["approved_phrases"] == 1 and result["pending_phrases"] == 2
    manifest = client.get("/api/packs/nah-ejemplo-001/manifest.json").json()
    assert [p["id"] for p in manifest["phrases"]] == ["urg-001"]
    assert client.get("/api/packs/nah-ejemplo-001/audio/urg-001.opus").status_code == 200
    assert client.get("/api/packs/nah-ejemplo-001/audio/urg-002.opus").status_code == 404
    assert client.get("/api/packs/nah-ejemplo-001/audio/urg-003.opus").status_code == 404


def test_el_mismo_revisor_repetido_no_cuenta_como_dos(client, settings, tmp_path):
    pack_dir = make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": ["Ana", "  ana "]})
    assert import_dir(settings, pack_dir)["approved_phrases"] == 0
    assert client.get("/api/packs/nah-ejemplo-001/manifest.json").json()["phrases"] == []


def test_aunque_la_base_diga_aprobada_sin_dos_revisores_no_se_sirve(client, settings, tmp_path):
    """Defensa en profundidad: la regla se revisa al servir, no solo al aprobar."""
    import_dir(settings, make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": DOS}))
    with open_db(settings) as conn:
        conn.execute("DELETE FROM reviews WHERE reviewer_alias = 'Enfermera Luz'")
    assert client.get("/api/packs/nah-ejemplo-001/manifest.json").json()["phrases"] == []
    assert client.get("/api/packs/nah-ejemplo-001/audio/urg-001.opus").status_code == 404


def test_el_audio_se_sirve_como_ogg_y_sin_cache(client, settings, tmp_path):
    import_dir(settings, make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": DOS}, greeting=DOS))
    response = client.get("/api/packs/nah-ejemplo-001/audio/urg-001.opus")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/ogg")
    assert response.headers["cache-control"] == "no-cache"
    assert response.content.startswith(b"OggS")
    greeting = client.get("/api/packs/nah-ejemplo-001/greeting.opus")
    assert greeting.status_code == 200 and greeting.content == b"OggS-saludo-falso"


def test_saludo_sin_doble_revision_no_se_sirve(client, settings, tmp_path):
    import_dir(settings, make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": DOS}, greeting=["Ana"]))
    assert client.get("/api/packs/nah-ejemplo-001/greeting.opus").status_code == 404
    assert client.get("/api/packs/nah-ejemplo-001/manifest.json").json()["greeting"] is None
    assert client.get("/api/packs").json()["packs"][0]["has_greeting"] is False


def test_paquete_retirado_responde_410_y_se_anuncia(client, settings, tmp_path):
    """Los teléfonos necesitan saber que deben borrarlo."""
    import_dir(settings, make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": DOS}))
    with open_db(settings) as conn:
        conn.execute("UPDATE packs SET status = 'withdrawn' WHERE id = 'nah-ejemplo-001'")
    data = client.get("/api/packs").json()
    assert data["packs"] == [] and data["withdrawn"] == ["nah-ejemplo-001"]
    assert client.get("/api/packs/nah-ejemplo-001/manifest.json").status_code == 410
    assert client.get("/api/packs/nah-ejemplo-001/audio/urg-001.opus").status_code == 410


def test_paquete_inexistente_da_404(client):
    assert client.get("/api/packs/no-existe-001/manifest.json").status_code == 404
    assert client.get("/api/packs/no-existe-001/audio/urg-001.opus").status_code == 404


def test_identificadores_raros_se_rechazan(client):
    for bad in ("..%2F..%2Fetc", "A", "con espacio", "x" * 80):
        assert client.get(f"/api/packs/{bad}/manifest.json").status_code in (404, 422)
    assert client.get("/api/packs/nah-ejemplo-001/audio/..%2Fmanifest.opus").status_code in (404, 422)


def test_importar_no_pisa_un_paquete_que_ya_existe(settings, client, tmp_path):
    first = make_pack_dir(tmp_path / "a", "nah-ejemplo-001", {"urg-001": DOS}, version="1.0.0")
    second = make_pack_dir(tmp_path / "b", "nah-ejemplo-001", {"urg-001": DOS, "urg-002": DOS}, version="2.0.0")
    assert import_dir(settings, first)["imported"] is True
    assert import_dir(settings, second)["imported"] is False
    assert client.get("/api/packs").json()["packs"][0]["version"] == "1.0.0"
    assert import_dir(settings, second, force=True)["imported"] is True
    assert client.get("/api/packs").json()["packs"][0]["version"] == "2.0.0"


def test_importar_ignora_frases_desconocidas_y_rutas_fuera_del_paquete(settings, client, tmp_path):
    pack_dir = make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": DOS})
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    (tmp_path / "secreto.opus").write_bytes(b"no deberia copiarse")
    manifest["phrases"].append(
        {"id": "urg-002", "audio": "../secreto.opus", "reviewed_by": DOS, "recorded_by": "X"}
    )
    manifest["phrases"].append(
        {"id": "inventada-999", "audio": "audio/urg-001.opus", "reviewed_by": DOS, "recorded_by": "X"}
    )
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = import_dir(settings, pack_dir)
    assert result["approved_phrases"] == 1 and result["skipped"] == 2


def test_paquete_de_prueba_solo_puede_ser_borrador(settings, client, tmp_path):
    import pytest

    from backend.packs_io import PackError

    pack_dir = make_pack_dir(tmp_path, "prueba-x-001", {"urg-001": DOS}, status="approved", is_test=True)
    with pytest.raises(PackError):
        import_dir(settings, pack_dir)


def test_exportar_e_importar_conserva_el_paquete(settings, client, tmp_path):
    import_dir(settings, make_pack_dir(tmp_path / "a", "nah-ejemplo-001", {"urg-001": DOS, "emb-003": DOS}, greeting=DOS))
    with open_db(settings) as conn:
        out = export_pack(conn, settings, "nah-ejemplo-001", tmp_path / "salida")
    assert (out / "manifest.json").is_file()
    assert (out / "audio" / "urg-001.opus").is_file()
    assert (out / "audio" / "emb-003.opus").is_file()
    assert (out / "greeting.opus").is_file()
    assert (out / "LICENSE.txt").is_file() and (out / "README.md").is_file()
    exported = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    served = client.get("/api/packs/nah-ejemplo-001/manifest.json").json()
    assert exported == served


def test_importar_entrega_un_token_de_retiro_por_voz(settings, client, tmp_path):
    result = import_dir(settings, make_pack_dir(tmp_path, "nah-ejemplo-001", {"urg-001": DOS}))
    assert list(result["tokens"]) == ["Hablante Uno"]
    token = result["tokens"]["Hablante Uno"]
    with open_db(settings) as conn:
        stored = conn.execute("SELECT withdrawal_token_hash FROM consents").fetchone()[0]
    assert token not in stored and len(stored) == 64
