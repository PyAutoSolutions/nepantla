"""Retiro de voces: cualquier voz puede retirarse, y el paquete también."""
from __future__ import annotations

from backend.db import open_db
from backend.security import hash_token

from .conftest import auth, requires_ffmpeg

pytestmark = requires_ffmpeg
PACK = "nah-ejemplo-001"


def _published(studio, phrases=("urg-001", "urg-002")):
    team = studio.team(PACK)
    for phrase_id in phrases:
        studio.approved_phrase(team, phrase_id)
    studio.publish(team)
    return team


def _manifest(client):
    return client.get(f"/api/packs/{PACK}/manifest.json").json()


def _audio_files(settings):
    folder = settings.audio_dir / PACK
    return sorted(folder.glob("*.opus")) if folder.exists() else []


def test_retirar_la_voz_quita_las_frases_borra_el_audio_y_sube_la_version(client, studio, settings):
    team = _published(studio)
    before = _manifest(client)
    assert len(before["phrases"]) == 2 and len(_audio_files(settings)) == 2

    response = client.post("/api/withdraw", json={"token": team["withdrawal"]})
    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "voice" and data["recordings"] == 2
    assert data["versions"][PACK] != before["version"]

    after = _manifest(client)
    assert after["phrases"] == []
    assert after["version"] == data["versions"][PACK]
    assert _audio_files(settings) == []  # el archivo ya no existe en el servidor
    assert client.get(f"/api/packs/{PACK}/audio/urg-001.opus").status_code == 404


def test_retirar_la_voz_borra_tambien_el_credito(client, studio, settings):
    team = _published(studio)
    client.post("/api/withdraw", json={"token": team["withdrawal"]})
    with open_db(settings) as conn:
        consent = conn.execute("SELECT credit_name, withdrawn_at FROM consents").fetchone()
        statuses = {row["status"] for row in conn.execute("SELECT status FROM recordings")}
    assert consent["credit_name"] == "(voz retirada)" and consent["withdrawn_at"]
    assert statuses == {"withdrawn"}


def test_tambien_se_retiran_las_grabaciones_que_seguian_en_revision(client, studio, settings):
    team = studio.team(PACK)
    studio.upload(team["speaker"], "urg-001")
    assert len(_audio_files(settings)) == 1
    client.post("/api/withdraw", json={"token": team["withdrawal"]})
    assert _audio_files(settings) == []
    assert client.get("/api/studio/queue", headers=auth(team["nurse"])).json()["queue"] == []


def test_retirar_una_sola_frase(client, studio, settings):
    team = _published(studio)
    response = client.post(
        "/api/withdraw", json={"token": team["withdrawal"], "scope": "phrase", "phrase_id": "urg-002"}
    )
    assert response.status_code == 200 and response.json()["recordings"] == 1
    assert [p["id"] for p in _manifest(client)["phrases"]] == ["urg-001"]
    assert len(_audio_files(settings)) == 1
    # El consentimiento sigue vigente: puede seguir grabando.
    assert studio.upload(team["speaker"], "urg-003").status_code == 201


def test_retirar_frase_exige_decir_cual(client, studio):
    team = _published(studio)
    assert client.post("/api/withdraw", json={"token": team["withdrawal"], "scope": "phrase"}).status_code == 422


def test_token_desconocido_da_404_y_no_cambia_nada(client, studio):
    _published(studio)
    response = client.post("/api/withdraw", json={"token": "x" * 43})
    assert response.status_code == 404
    assert len(_manifest(client)["phrases"]) == 2


def test_el_token_de_retiro_se_guarda_solo_como_hash(client, studio, settings):
    team = _published(studio)
    with open_db(settings) as conn:
        stored = conn.execute("SELECT withdrawal_token_hash FROM consents").fetchone()[0]
    assert stored == hash_token(team["withdrawal"])
    raw = b"".join(path.read_bytes() for path in settings.data_dir.glob("nepantla.db*"))
    assert team["withdrawal"].encode() not in raw


def test_la_vista_previa_no_retira_nada(client, studio):
    team = _published(studio)
    preview = client.post("/api/withdraw", json={"token": team["withdrawal"], "dry_run": True}).json()
    assert preview == {
        "dry_run": True, "kind": "voice", "credit_name": "Hablante Uno",
        "recordings": 2, "packs": [PACK],
    }
    assert len(_manifest(client)["phrases"]) == 2


def test_retirar_dos_veces_no_falla(client, studio):
    team = _published(studio)
    first = client.post("/api/withdraw", json={"token": team["withdrawal"]}).json()
    second = client.post("/api/withdraw", json={"token": team["withdrawal"]})
    assert second.status_code == 200 and second.json()["recordings"] == 0
    assert _manifest(client)["version"] == first["versions"][PACK]


def test_tras_retirar_su_voz_hay_que_firmar_de_nuevo_para_grabar(client, studio):
    team = _published(studio)
    client.post("/api/withdraw", json={"token": team["withdrawal"]})
    assert studio.upload(team["speaker"], "urg-001").status_code == 403
    session = client.get("/api/studio/session", headers=auth(team["speaker"])).json()
    assert session["consent"]["signed"] is False
    new_token = studio.consent(team["speaker"], "Hablante Uno")
    assert new_token != team["withdrawal"]
    assert studio.upload(team["speaker"], "urg-001").status_code == 201


def test_el_hablante_no_puede_retirar_el_paquete_entero(client, studio):
    team = _published(studio)
    response = client.post("/api/withdraw", json={"token": team["withdrawal"], "scope": "pack"})
    assert response.status_code == 403
    assert client.get("/api/packs").json()["withdrawn"] == []


def test_el_guardian_retira_una_frase(client, studio, settings):
    team = _published(studio)
    version = _manifest(client)["version"]
    response = client.post(
        "/api/withdraw", json={"token": team["guardian"], "scope": "phrase", "phrase_id": "urg-001"}
    )
    assert response.status_code == 200 and response.json()["recordings"] == 1
    manifest = _manifest(client)
    assert [p["id"] for p in manifest["phrases"]] == ["urg-002"]
    assert manifest["version"] != version
    assert len(_audio_files(settings)) == 1


def test_el_guardian_retira_el_paquete_completo(client, studio, settings):
    team = _published(studio)
    response = client.post("/api/withdraw", json={"token": team["guardian"], "scope": "pack"})
    assert response.status_code == 200 and response.json()["kind"] == "pack"
    data = client.get("/api/packs").json()
    assert data["packs"] == [] and data["withdrawn"] == [PACK]
    assert client.get(f"/api/packs/{PACK}/manifest.json").status_code == 410
    assert _audio_files(settings) == []
    # Ya no se puede grabar ni crear enlaces para un paquete retirado.
    assert studio.upload(team["speaker"], "urg-003").status_code == 409


def test_un_revisor_no_puede_retirar_nada(client, studio):
    team = _published(studio)
    for scope in ("pack", "phrase"):
        body = {"token": team["nurse"], "scope": scope, "phrase_id": "urg-001"}
        assert client.post("/api/withdraw", json=body).status_code == 404
    assert len(_manifest(client)["phrases"]) == 2


def test_el_retiro_no_acepta_campos_extra(client, studio):
    team = _published(studio)
    body = {"token": team["withdrawal"], "reason": "ya no quiero"}
    assert client.post("/api/withdraw", json=body).status_code == 422
