"""/api/usage: solo conteos agregados, nada identificable."""
from __future__ import annotations

import re
import sqlite3

from backend.db import open_db

from .conftest import import_dir, make_pack_dir

DOS = ["Intérprete Ana", "Enfermera Luz"]
PACK = "nah-ejemplo-001"


def _pack(settings, tmp_path):
    import_dir(settings, make_pack_dir(tmp_path, PACK, {"urg-001": DOS}))


def _rows(settings):
    with open_db(settings) as conn:
        return [tuple(row) for row in conn.execute("SELECT day, pack_id, event, n FROM usage_counts ORDER BY event")]


def test_evento_valido_se_cuenta(client, settings, tmp_path):
    _pack(settings, tmp_path)
    response = client.post("/api/usage", json={"pack_id": PACK, "event": "scenario_opened"})
    assert response.status_code == 204 and response.content == b""
    rows = _rows(settings)
    assert len(rows) == 1
    assert rows[0][1:] == (PACK, "scenario_opened", 1)


def test_los_conteos_se_suman_por_dia_paquete_y_evento(client, settings, tmp_path):
    _pack(settings, tmp_path)
    for _ in range(3):
        client.post("/api/usage", json={"pack_id": PACK, "event": "summary_generated"})
    client.post("/api/usage", json={"pack_id": PACK, "event": "summary_generated", "n": 7})
    client.post("/api/usage", json={"pack_id": PACK, "event": "pack_downloaded"})
    assert [(event, n) for _, _, event, n in _rows(settings)] == [
        ("pack_downloaded", 1),
        ("summary_generated", 10),
    ]


def test_solo_se_guarda_el_dia_nunca_la_hora(client, settings, tmp_path):
    _pack(settings, tmp_path)
    client.post("/api/usage", json={"pack_id": PACK, "event": "interpreter_requested"})
    day = _rows(settings)[0][0]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)


def test_los_cuatro_eventos_permitidos(client, settings, tmp_path):
    _pack(settings, tmp_path)
    for event in ("pack_downloaded", "scenario_opened", "summary_generated", "interpreter_requested"):
        assert client.post("/api/usage", json={"pack_id": PACK, "event": event}).status_code == 204


def test_evento_desconocido_se_rechaza(client, settings, tmp_path):
    _pack(settings, tmp_path)
    assert client.post("/api/usage", json={"pack_id": PACK, "event": "paciente_atendido"}).status_code == 422
    assert _rows(settings) == []


def test_cualquier_campo_extra_se_rechaza(client, settings, tmp_path):
    """No hay forma de colar datos de un paciente en este endpoint."""
    _pack(settings, tmp_path)
    for extra in (
        {"patient_name": "Juana"},
        {"answers": {"urg-001": "si"}},
        {"device_id": "abc123"},
        {"timestamp": "2026-12-01T10:22:31"},
        {"note": "dolor de pecho"},
    ):
        body = {"pack_id": PACK, "event": "scenario_opened", **extra}
        assert client.post("/api/usage", json=body).status_code == 422
    assert _rows(settings) == []


def test_el_paquete_debe_existir(client, settings, tmp_path):
    """El pack_id no puede usarse como campo libre para guardar otra cosa."""
    _pack(settings, tmp_path)
    assert client.post("/api/usage", json={"pack_id": "juana-perez-1980", "event": "scenario_opened"}).status_code == 404
    assert _rows(settings) == []


def test_n_tiene_tope(client, settings, tmp_path):
    _pack(settings, tmp_path)
    assert client.post("/api/usage", json={"pack_id": PACK, "event": "scenario_opened", "n": 0}).status_code == 422
    assert client.post("/api/usage", json={"pack_id": PACK, "event": "scenario_opened", "n": 100000}).status_code == 422


def test_no_se_guarda_ip_ni_navegador_en_ningun_lado(client, settings, tmp_path):
    """Busca la IP y el agente en los bytes crudos de la base."""
    _pack(settings, tmp_path)
    headers = {
        "User-Agent": "NavegadorSecreto/9.9 (TelefonoDeJuana)",
        "X-Forwarded-For": "203.0.113.77",
        "X-Real-IP": "203.0.113.77",
        "Referer": "https://clinica.example/consulta/123",
    }
    for _ in range(5):
        assert client.post(
            "/api/usage", json={"pack_id": PACK, "event": "scenario_opened"}, headers=headers
        ).status_code == 204

    # Vuelca el WAL al archivo principal para leer todo lo escrito.
    conn = sqlite3.connect(settings.db_path)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    raw = b"".join(path.read_bytes() for path in settings.data_dir.glob("nepantla.db*"))
    for secret in (b"NavegadorSecreto", b"TelefonoDeJuana", b"203.0.113.77", b"clinica.example", b"testclient"):
        assert secret not in raw


def test_la_tabla_solo_tiene_columnas_agregadas(settings, client):
    with open_db(settings) as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(usage_counts)")]
    assert columns == ["day", "pack_id", "event", "n"]


def test_no_existe_ninguna_tabla_de_pacientes(settings, client):
    with open_db(settings) as conn:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        columns = {
            col["name"]
            for table in tables
            for col in conn.execute(f"PRAGMA table_info({table})")
        }
    assert tables == {
        "packs", "phrases", "recordings", "reviews", "consents", "reports",
        "usage_counts", "studio_sessions", "sqlite_sequence",
    }
    for forbidden in ("ip", "user_agent", "device_id", "patient", "paciente", "diagnosis", "answers"):
        assert forbidden not in columns


def test_la_respuesta_no_pone_cookies(client, settings, tmp_path):
    _pack(settings, tmp_path)
    response = client.post("/api/usage", json={"pack_id": PACK, "event": "scenario_opened"})
    assert "set-cookie" not in response.headers
    assert client.cookies == {} or len(client.cookies) == 0


def test_limite_de_frecuencia_global(client, settings, tmp_path):
    _pack(settings, tmp_path)
    codes = [
        client.post("/api/usage", json={"pack_id": PACK, "event": "scenario_opened"}).status_code
        for _ in range(605)
    ]
    assert codes[:600] == [204] * 600
    assert 429 in codes[600:]
