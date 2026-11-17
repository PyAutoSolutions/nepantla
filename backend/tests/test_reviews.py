"""Regla de doble revisión: dos personas distintas, una intérprete."""
from __future__ import annotations

from backend.db import open_db

from .conftest import auth, requires_ffmpeg

pytestmark = requires_ffmpeg
PACK = "nah-ejemplo-001"


def _manifest_ids(client, team):
    """Lo que vería la app (el paquete está en borrador: se consulta por el guardián)."""
    data = client.get("/api/studio/pack", headers=auth(team["guardian"])).json()
    return [entry["id"] for entry in data["approved"]]


def _version(client, team):
    return client.get("/api/studio/pack", headers=auth(team["guardian"])).json()["pack"]["version"]


def test_una_sola_aprobacion_no_basta(client, studio):
    team = studio.team(PACK)
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    result = studio.review(team["interpreter"], rec).json()
    assert result["status"] == "pending" and result["approvals"] == 1
    assert _manifest_ids(client, team) == []


def test_dos_aprobaciones_con_interprete_aprueban_y_suben_la_version(client, studio):
    team = studio.team(PACK)
    assert _version(client, team) == "0.1.0"
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    studio.review(team["nurse"], rec)
    result = studio.review(team["interpreter"], rec).json()
    assert result["status"] == "approved" and result["approvals"] == 2
    assert result["version"] == "0.1.1"
    assert _manifest_ids(client, team) == ["urg-001"]
    assert _version(client, team) == "0.1.1"


def test_dos_aprobaciones_sin_interprete_no_bastan(client, studio):
    team = studio.team(PACK)
    doctor = studio.session(PACK, "reviewer", "Doctor Raúl")
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    studio.review(team["nurse"], rec)
    result = studio.review(doctor, rec).json()
    assert result["status"] == "pending"
    assert result["needs_interpreter"] is True
    assert _manifest_ids(client, team) == []
    # En cuanto la escucha una intérprete, entra.
    assert studio.review(team["interpreter"], rec).json()["status"] == "approved"


def test_la_misma_persona_con_dos_enlaces_no_cuenta_dos_veces(client, studio):
    team = studio.team(PACK)
    otra_vez = studio.session(PACK, "reviewer", "  intérprete ANA ", is_interpreter=True)
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    assert studio.review(team["interpreter"], rec).status_code == 201
    repeat = studio.review(otra_vez, rec)
    assert repeat.status_code == 409
    assert _manifest_ids(client, team) == []


def test_nadie_revisa_su_propia_voz(client, studio):
    team = studio.team(PACK)
    self_review = studio.session(PACK, "reviewer", "Hablante Uno", is_interpreter=True)
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    assert studio.review(self_review, rec).status_code == 403
    queue = client.get("/api/studio/queue", headers=auth(self_review)).json()["queue"]
    assert queue == []


def test_un_rechazo_descarta_la_grabacion_y_avisa_al_hablante(client, studio):
    team = studio.team(PACK)
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    studio.review(team["nurse"], rec)
    result = studio.review(team["interpreter"], rec, verdict="reject", note="Se oye un gallo al fondo").json()
    assert result["status"] == "rejected"
    assert _manifest_ids(client, team) == []
    phrases = client.get("/api/studio/phrases", headers=auth(team["speaker"])).json()["phrases"]
    mine = next(p for p in phrases if p["id"] == "urg-001")
    assert mine["mine"] == "rejected" and mine["note"] == "Se oye un gallo al fondo"


def test_no_se_revisa_una_grabacion_que_ya_se_decidio(client, studio):
    team = studio.team(PACK)
    rec = studio.approved_phrase(team, "urg-001")
    doctor = studio.session(PACK, "reviewer", "Doctor Raúl")
    assert studio.review(doctor, rec).status_code == 409


def test_una_grabacion_nueva_aprobada_reemplaza_a_la_anterior(client, studio, settings):
    team = studio.team(PACK)
    first = studio.approved_phrase(team, "urg-001")
    second = studio.approved_phrase(team, "urg-001")
    assert first != second
    with open_db(settings) as conn:
        states = {
            row["id"]: row["status"]
            for row in conn.execute("SELECT id, status FROM recordings WHERE phrase_id = 'urg-001'")
        }
    assert states == {first: "superseded", second: "approved"}
    assert _manifest_ids(client, team) == ["urg-001"]
    assert _version(client, team) == "0.1.2"


def test_regrabar_reemplaza_la_que_seguia_en_revision(client, studio, settings):
    team = studio.team(PACK)
    first = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    second = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    queue = client.get("/api/studio/queue", headers=auth(team["nurse"])).json()["queue"]
    assert [item["recording_id"] for item in queue] == [second]
    with open_db(settings) as conn:
        old = conn.execute("SELECT status, audio_path FROM recordings WHERE id = ?", (first,)).fetchone()
    assert old["status"] == "superseded" and old["audio_path"] == ""


def test_la_cola_no_repite_lo_que_ya_revise(client, studio):
    team = studio.team(PACK)
    rec1 = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    rec2 = studio.upload(team["speaker"], "urg-002").json()["recording_id"]
    studio.review(team["nurse"], rec1)
    nurse_queue = client.get("/api/studio/queue", headers=auth(team["nurse"])).json()["queue"]
    assert [item["recording_id"] for item in nurse_queue] == [rec2]
    interpreter_queue = client.get("/api/studio/queue", headers=auth(team["interpreter"])).json()["queue"]
    assert [item["recording_id"] for item in interpreter_queue] == [rec1, rec2]
    assert interpreter_queue[0]["approvals"] == 1


def test_un_revisor_de_otro_paquete_no_puede_opinar(client, studio):
    team = studio.team(PACK)
    studio.create_pack("otro-paquete-001")
    outsider = studio.session("otro-paquete-001", "reviewer", "Intérprete Externa", is_interpreter=True)
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    assert studio.review(outsider, rec).status_code == 404
    assert client.get(f"/api/studio/recordings/{rec}/audio", headers=auth(outsider)).status_code == 404


def test_solo_los_revisores_revisan(client, studio):
    team = studio.team(PACK)
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    assert studio.review(team["speaker"], rec).status_code == 403
    assert studio.review(team["guardian"], rec).status_code == 403


def test_el_manifest_publica_quien_grabo_y_quien_reviso(client, studio):
    team = studio.team(PACK)
    studio.approved_phrase(team, "urg-001")
    studio.publish(team)
    phrase = client.get(f"/api/packs/{PACK}/manifest.json").json()["phrases"][0]
    assert phrase["recorded_by"] == "Hablante Uno"
    assert sorted(phrase["reviewed_by"]) == ["Enfermera Luz", "Intérprete Ana"]
    assert len(phrase["approved_at"]) == 10
