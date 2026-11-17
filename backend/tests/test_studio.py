"""Estudio de grabación: enlaces, consentimiento, subidas y publicación."""
from __future__ import annotations

import json
import subprocess

from backend.db import open_db

from .conftest import ADMIN, admin, auth, import_dir, make_pack_dir, make_settings, requires_ffmpeg, wav_bytes

PACK = "nah-ejemplo-001"
CONSENT = {
    "credit_name": "Hablante Uno",
    "understands_use": True,
    "understands_withdrawal": True,
    "accepts_license": True,
    "is_adult": True,
}


def test_crear_paquetes_y_enlaces_exige_el_token_de_administracion(client):
    body = {"pack_id": PACK, "language": "L", "variant": "V"}
    assert client.post("/api/studio/packs", json=body).status_code == 401
    assert client.post("/api/studio/packs", json=body, headers=auth("otro-token-cualquiera-000000")).status_code == 403
    assert client.post("/api/studio/packs", json=body, headers=admin()).status_code == 201
    session = {"pack_id": PACK, "role": "speaker", "alias": "Hablante Uno"}
    assert client.post("/api/studio/session", json=session).status_code == 401
    assert client.get("/api/studio/admin/overview").status_code == 401


def test_sin_token_configurado_el_estudio_queda_cerrado(tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    with TestClient(create_app(make_settings(tmp_path, admin_token=""))) as client:
        response = client.post(
            "/api/studio/packs", json={"pack_id": PACK, "language": "L", "variant": "V"}, headers=admin()
        )
        assert response.status_code == 503


def test_no_se_repite_el_codigo_de_un_paquete(client, studio):
    studio.create_pack(PACK)
    again = client.post(
        "/api/studio/packs", json={"pack_id": PACK, "language": "L", "variant": "V"}, headers=admin()
    )
    assert again.status_code == 409


def test_el_enlace_lleva_el_token_despues_del_gato(client, studio):
    studio.create_pack(PACK)
    data = client.post(
        "/api/studio/session",
        json={"pack_id": PACK, "role": "speaker", "alias": "Hablante Uno"},
        headers=admin(),
    ).json()
    assert data["path"] == f"/#/estudio/{data['token']}"
    assert len(data["token"]) >= 40


def test_los_tokens_del_estudio_se_guardan_con_hash(client, studio, settings):
    studio.create_pack(PACK)
    token = studio.session(PACK, "speaker", "Hablante Uno")
    raw = b"".join(path.read_bytes() for path in settings.data_dir.glob("nepantla.db*"))
    assert token.encode() not in raw
    assert ADMIN.encode() not in raw


def test_enlace_desconocido_revocado_o_vencido_no_entra(client, studio, settings):
    studio.create_pack(PACK)
    assert client.get("/api/studio/session", headers=auth("token-que-no-existe-0000000000")).status_code == 401
    token = studio.session(PACK, "speaker", "Hablante Uno")
    assert client.get("/api/studio/session", headers=auth(token)).status_code == 200

    with open_db(settings) as conn:
        conn.execute("UPDATE studio_sessions SET expires_at = '2000-01-01T00:00:00Z'")
    assert client.get("/api/studio/session", headers=auth(token)).status_code == 401

    other = studio.session(PACK, "reviewer", "Enfermera Luz")
    overview = client.get("/api/studio/admin/overview", headers=admin()).json()
    session_id = next(s["session_id"] for s in overview["packs"][0]["sessions"] if s["alias"] == "Enfermera Luz")
    assert client.post(f"/api/studio/session/{session_id}/revoke", headers=admin()).status_code == 200
    assert client.get("/api/studio/session", headers=auth(other)).status_code == 401


def test_la_sesion_dice_el_rol_y_el_paquete(client, studio):
    studio.create_pack(PACK)
    token = studio.session(PACK, "reviewer", "Intérprete Ana", is_interpreter=True)
    data = client.get("/api/studio/session", headers=auth(token)).json()
    assert data["role"] == "reviewer" and data["is_interpreter"] is True
    assert data["pack"]["pack_id"] == PACK and data["pack"]["status"] == "draft"
    assert data["coverage"]["total_phrases"] >= 80


def test_solo_un_revisor_puede_ser_interprete(client, studio):
    studio.create_pack(PACK)
    data = client.post(
        "/api/studio/session",
        json={"pack_id": PACK, "role": "speaker", "alias": "Hablante Uno", "is_interpreter": True},
        headers=admin(),
    ).json()
    assert data["is_interpreter"] is False


def test_el_consentimiento_exige_aceptar_cada_punto(client, studio):
    studio.create_pack(PACK)
    token = studio.session(PACK, "speaker", "Hablante Uno")
    for missing in ("understands_use", "understands_withdrawal", "accepts_license", "is_adult"):
        body = {**CONSENT, missing: False}
        assert client.post("/api/studio/consent", json=body, headers=auth(token)).status_code == 422
    assert client.post("/api/studio/consent", json={**CONSENT, "credit_name": ""}, headers=auth(token)).status_code == 422
    ok = client.post("/api/studio/consent", json=CONSENT, headers=auth(token))
    assert ok.status_code == 201
    data = ok.json()
    assert data["withdrawal_path"] == f"/#/retirar/{data['withdrawal_token']}"
    assert data["license"] == "Licencia de ejemplo"
    # No se firma dos veces con el mismo enlace.
    assert client.post("/api/studio/consent", json=CONSENT, headers=auth(token)).status_code == 409


def test_solo_el_hablante_firma_consentimiento(client, studio):
    studio.create_pack(PACK)
    reviewer = studio.session(PACK, "reviewer", "Enfermera Luz")
    assert client.post("/api/studio/consent", json=CONSENT, headers=auth(reviewer)).status_code == 403


def test_no_se_graba_sin_consentimiento(client, studio):
    studio.create_pack(PACK)
    token = studio.session(PACK, "speaker", "Hablante Uno")
    assert studio.upload(token, "urg-001").status_code == 403


@requires_ffmpeg
def test_la_grabacion_se_normaliza_a_opus_mono_16k(client, studio, settings):
    team = studio.team(PACK)
    response = studio.upload(team["speaker"], "urg-001", wav_bytes(seconds=1.5, rate=44100, channels=2))
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "pending" and 1.3 < data["duration"] < 1.8
    with open_db(settings) as conn:
        rec = conn.execute("SELECT * FROM recordings WHERE id = ?", (data["recording_id"],)).fetchone()
    path = settings.audio_dir / rec["audio_path"]
    assert path.suffix == ".opus" and path.read_bytes().startswith(b"OggS")
    probe = json.loads(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_name,channels:format=bit_rate:format_tags", "-of", "json", str(path)],
            capture_output=True, check=True,
        ).stdout
    )
    assert probe["streams"][0]["codec_name"] == "opus"
    assert probe["streams"][0]["channels"] == 1
    assert int(probe["format"]["bit_rate"]) < 32000  # objetivo ~16 kbps
    assert rec["bytes"] == path.stat().st_size < 12000
    # Sin metadatos del aparato que grabó.
    tags = {k.lower() for k in (probe["format"].get("tags") or {})}
    assert tags <= {"encoder"}


@requires_ffmpeg
def test_el_archivo_guardado_tiene_nombre_al_azar(client, studio, settings):
    team = studio.team(PACK)
    studio.upload(team["speaker"], "urg-001")
    with open_db(settings) as conn:
        audio_path = conn.execute("SELECT audio_path FROM recordings").fetchone()[0]
    folder, name = audio_path.split("/")
    assert folder == PACK and "urg-001" not in name and len(name) == 24 + len(".opus")


def test_un_archivo_que_no_es_audio_se_rechaza(client, studio):
    team = studio.team(PACK)
    for payload in (b"#EXTM3U\n/etc/passwd\n", b"<html>hola</html>", b"MZ\x90\x00binario", b""):
        assert studio.upload(team["speaker"], "urg-001", payload).status_code in (415, 422)


@requires_ffmpeg
def test_audio_corrupto_con_cabecera_valida_se_rechaza(client, studio, settings):
    team = studio.team(PACK)
    response = studio.upload(team["speaker"], "urg-001", b"OggS" + b"\x00" * 400)
    assert response.status_code == 422
    assert not any((settings.audio_dir / PACK).glob("*.opus")) if (settings.audio_dir / PACK).exists() else True


@requires_ffmpeg
def test_grabacion_demasiado_corta_o_larga_se_rechaza(tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    from .conftest import Studio

    with TestClient(create_app(make_settings(tmp_path, max_audio_seconds=2.0))) as client:
        studio = Studio(client)
        team = studio.team(PACK)
        assert studio.upload(team["speaker"], "urg-001", wav_bytes(seconds=0.1)).status_code == 422
        assert studio.upload(team["speaker"], "urg-001", wav_bytes(seconds=1.0)).status_code == 201
        long = studio.upload(team["speaker"], "urg-002", wav_bytes(seconds=6.0, rate=16000, channels=1))
        assert long.status_code == 422


def test_frase_inexistente_da_404(client, studio):
    team = studio.team(PACK)
    assert studio.upload(team["speaker"], "frase-inventada-9").status_code == 404


def test_subida_demasiado_grande_da_413(tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    from .conftest import Studio

    with TestClient(create_app(make_settings(tmp_path, max_upload_bytes=20_000))) as client:
        studio = Studio(client)
        team = studio.team(PACK)
        # Pasa el filtro general pero supera el límite de la grabación.
        assert studio.upload(team["speaker"], "urg-001", b"RIFF" + b"\x00" * 30_000).status_code == 413
        # Ni siquiera se lee: lo corta el límite de tamaño del servidor.
        assert studio.upload(team["speaker"], "urg-001", b"RIFF" + b"\x00" * 300_000).status_code == 413


def test_subida_por_trozos_sin_tamano_declarado_tambien_se_corta(tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    with TestClient(create_app(make_settings(tmp_path, max_upload_bytes=20_000))) as client:
        def chunks():
            for _ in range(40):
                yield b"x" * 10_000

        response = client.post(
            "/api/studio/recordings",
            content=chunks(),
            headers={"Content-Type": "multipart/form-data; boundary=abc", **auth("token-cualquiera-0000000000")},
        )
        assert response.status_code == 413


def test_cuerpos_json_enormes_se_rechazan(client):
    big = {"pack_id": "nah-ejemplo-001", "event": "scenario_opened", "relleno": "x" * 50_000}
    assert client.post("/api/usage", json=big).status_code == 413


@requires_ffmpeg
def test_limite_de_frecuencia_por_enlace_no_por_ip(client, studio):
    team = studio.team(PACK)
    other = studio.session(PACK, "speaker", "Hablante Dos")
    studio.consent(other, "Hablante Dos")
    audio = wav_bytes(seconds=0.5, rate=16000, channels=1)
    codes = [studio.upload(team["speaker"], "urg-001", audio).status_code for _ in range(32)]
    assert codes[:30] == [201] * 30 and codes[30:] == [429, 429]
    # Otro enlace no se ve afectado aunque venga de la misma IP.
    assert studio.upload(other, "urg-001", audio).status_code == 201


@requires_ffmpeg
def test_el_audio_en_revision_no_es_publico(client, studio):
    team = studio.team(PACK)
    rec = studio.upload(team["speaker"], "urg-001").json()["recording_id"]
    assert client.get(f"/api/studio/recordings/{rec}/audio").status_code == 401
    assert client.get(f"/api/packs/{PACK}/audio/urg-001.opus").status_code == 404
    ok = client.get(f"/api/studio/recordings/{rec}/audio", headers=auth(team["nurse"]))
    assert ok.status_code == 200 and ok.content.startswith(b"OggS")
    assert ok.headers["cache-control"] == "no-store"
    # Otro hablante no puede escuchar grabaciones ajenas.
    other = studio.session(PACK, "speaker", "Hablante Dos")
    studio.consent(other, "Hablante Dos")
    assert client.get(f"/api/studio/recordings/{rec}/audio", headers=auth(other)).status_code == 403


@requires_ffmpeg
def test_el_hablante_ve_su_avance(client, studio):
    team = studio.team(PACK)
    studio.approved_phrase(team, "urg-001")
    studio.upload(team["speaker"], "urg-002")
    phrases = client.get("/api/studio/phrases", headers=auth(team["speaker"])).json()["phrases"]
    assert phrases[0]["id"] == "greeting"  # el saludo se graba primero
    by_id = {p["id"]: p for p in phrases}
    assert by_id["urg-001"]["mine"] == "approved" and by_id["urg-001"]["pack_has_approved"] is True
    assert by_id["urg-002"]["mine"] == "pending"
    assert by_id["urg-003"]["mine"] is None
    assert len(phrases) >= 80


@requires_ffmpeg
def test_el_guardian_publica_el_paquete(client, studio):
    team = studio.team(PACK)
    assert client.post("/api/studio/pack/approve", headers=auth(team["guardian"])).status_code == 409  # vacío
    studio.approved_phrase(team, "urg-001")
    assert client.get("/api/packs").json()["packs"] == []  # borrador: invisible
    published = studio.publish(team)
    assert published["status"] == "approved" and published["changed"] is True
    assert published["version"] == "0.2.0"
    packs = client.get("/api/packs").json()["packs"]
    assert [p["pack_id"] for p in packs] == [PACK]
    assert client.get(f"/api/packs/{PACK}/audio/urg-001.opus").status_code == 200
    # Publicar otra vez no cambia nada.
    assert studio.publish(team)["changed"] is False


def test_solo_el_guardian_publica(client, studio):
    team_tokens = {
        "speaker": None, "reviewer": None,
    }
    studio.create_pack(PACK)
    team_tokens["speaker"] = studio.session(PACK, "speaker", "Hablante Uno")
    team_tokens["reviewer"] = studio.session(PACK, "reviewer", "Enfermera Luz")
    for token in team_tokens.values():
        assert client.post("/api/studio/pack/approve", headers=auth(token)).status_code == 403


def test_un_paquete_de_audio_de_prueba_nunca_se_publica(dev_client, tmp_path):
    """Los audios de relleno no pueden pasar por una lengua real."""
    settings = dev_client.app.state.settings
    import_dir(
        settings,
        make_pack_dir(tmp_path, "prueba-x-001", {"urg-001": ["Revisor A", "Revisor B"]}, status="draft", is_test=True),
    )
    token = dev_client.post(
        "/api/studio/session",
        json={"pack_id": "prueba-x-001", "role": "guardian", "alias": "Guardiana Uno"},
        headers=admin(),
    ).json()["token"]
    response = dev_client.post("/api/studio/pack/approve", headers=auth(token))
    assert response.status_code == 409
    assert "PRUEBA" in response.json()["detail"]


@requires_ffmpeg
def test_el_panel_de_administracion_resume_el_avance(client, studio):
    team = studio.team(PACK)
    studio.approved_phrase(team, "urg-001")
    studio.upload(team["speaker"], "urg-002")
    overview = client.get("/api/studio/admin/overview", headers=admin()).json()
    pack = overview["packs"][0]
    assert pack["coverage"]["approved"] == 1 and pack["coverage"]["pending"] == 1
    assert {s["role"] for s in pack["sessions"]} == {"speaker", "reviewer", "guardian"}
    assert overview["ffmpeg"] is True
    # El panel nunca devuelve tokens.
    assert "token" not in json.dumps(overview)


def test_el_administrador_puede_corregir_datos_del_paquete(client, studio):
    studio.create_pack(PACK)
    response = client.patch(
        f"/api/studio/packs/{PACK}",
        json={"license": "CC BY-NC 4.0", "guardians": ["Guardiana Uno", "Guardián Dos"]},
        headers=admin(),
    )
    assert response.status_code == 200
    assert response.json()["license"] == "CC BY-NC 4.0"
    assert response.json()["guardians"] == ["Guardiana Uno", "Guardián Dos"]
    assert client.patch(f"/api/studio/packs/{PACK}", json={"status": "approved"}, headers=admin()).status_code == 422


def test_el_audio_del_consentimiento_solo_se_ofrece_si_existe(client, studio, settings):
    """El consentimiento hablado lo graba una persona. Mientras no exista el
    archivo, el servidor lo dice y la app no enseña el botón."""
    team = studio.team()
    session = client.get("/api/studio/session", headers=auth(team["speaker"])).json()
    expected = (settings.frontend_dir / "audio" / "consentimiento.es.opus").is_file()
    assert session["consent_audio"] is expected
