"""Botón "Reportar audio incorrecto"."""
from __future__ import annotations

import re

from backend.db import open_db

from .conftest import admin, auth, import_dir, make_pack_dir

DOS = ["Intérprete Ana", "Enfermera Luz"]
PACK = "nah-ejemplo-001"


def _pack(settings, tmp_path):
    import_dir(settings, make_pack_dir(tmp_path, PACK, {"urg-001": DOS}))


def _reports(settings):
    with open_db(settings) as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM reports")]


def test_reporte_valido_queda_abierto(client, settings, tmp_path):
    _pack(settings, tmp_path)
    response = client.post(
        "/api/reports", json={"pack_id": PACK, "phrase_id": "urg-001", "reason": "wrong_meaning"}
    )
    assert response.status_code == 201 and response.json() == {"ok": True}
    reports = _reports(settings)
    assert len(reports) == 1
    assert reports[0]["reason"] == "wrong_meaning" and reports[0]["status"] == "open"


def test_el_reporte_guarda_el_dia_y_no_la_hora(client, settings, tmp_path):
    _pack(settings, tmp_path)
    client.post("/api/reports", json={"pack_id": PACK, "phrase_id": "urg-001", "reason": "bad_audio"})
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", _reports(settings)[0]["created_at"])


def test_el_motivo_es_de_una_lista_cerrada(client, settings, tmp_path):
    _pack(settings, tmp_path)
    body = {"pack_id": PACK, "phrase_id": "urg-001", "reason": "La señora Juana dijo que no entendió"}
    assert client.post("/api/reports", json=body).status_code == 422
    assert _reports(settings) == []


def test_no_hay_campo_de_texto_libre(client, settings, tmp_path):
    _pack(settings, tmp_path)
    body = {"pack_id": PACK, "phrase_id": "urg-001", "reason": "other", "note": "paciente de la cama 4"}
    assert client.post("/api/reports", json=body).status_code == 422
    assert _reports(settings) == []


def test_frase_sin_audio_o_paquete_inexistente_da_404(client, settings, tmp_path):
    _pack(settings, tmp_path)
    assert client.post(
        "/api/reports", json={"pack_id": PACK, "phrase_id": "urg-002", "reason": "other"}
    ).status_code == 404
    assert client.post(
        "/api/reports", json={"pack_id": "no-existe-001", "phrase_id": "urg-001", "reason": "other"}
    ).status_code == 404


def test_limite_de_frecuencia(client, settings, tmp_path):
    _pack(settings, tmp_path)
    body = {"pack_id": PACK, "phrase_id": "urg-001", "reason": "bad_audio"}
    codes = [client.post("/api/reports", json=body).status_code for _ in range(32)]
    assert codes[:30] == [201] * 30 and codes[30:] == [429, 429]


def test_el_guardian_ve_los_reportes_y_los_cierra(client, settings, tmp_path, studio):
    _pack(settings, tmp_path)
    client.post("/api/reports", json={"pack_id": PACK, "phrase_id": "urg-001", "reason": "wrong_variant"})
    guardian = studio.session(PACK, "guardian", "Guardiana Uno")
    data = client.get("/api/studio/pack", headers=auth(guardian)).json()
    assert len(data["reports"]) == 1
    report = data["reports"][0]
    assert report["phrase_id"] == "urg-001" and report["reason"] == "wrong_variant" and report["status"] == "open"
    overview = client.get("/api/studio/admin/overview", headers=admin()).json()
    assert overview["packs"][0]["open_reports"] == 1

    done = client.post(
        f"/api/studio/reports/{report['report_id']}", json={"status": "resolved"}, headers=auth(guardian)
    )
    assert done.status_code == 200
    assert _reports(settings)[0]["status"] == "resolved"
    overview = client.get("/api/studio/admin/overview", headers=admin()).json()
    assert overview["packs"][0]["open_reports"] == 0


def test_un_guardian_no_toca_reportes_de_otro_paquete(client, settings, tmp_path, studio):
    _pack(settings, tmp_path)
    client.post("/api/reports", json={"pack_id": PACK, "phrase_id": "urg-001", "reason": "other"})
    studio.create_pack("otro-paquete-001")
    outsider = studio.session("otro-paquete-001", "guardian", "Otra Guardiana")
    report_id = _reports(settings)[0]["id"]
    response = client.post(f"/api/studio/reports/{report_id}", json={"status": "dismissed"}, headers=auth(outsider))
    assert response.status_code == 404
