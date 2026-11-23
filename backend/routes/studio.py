"""Estudio de grabación remoto.

Tres tipos de enlace único, creados por quien administra el proyecto:

* speaker  -> firma el consentimiento y graba frases desde su celular.
* reviewer -> escucha y aprueba o rechaza (intérprete o personal de salud).
* guardian -> ve el paquete, lo aprueba para publicarlo, atiende reportes.

Nadie crea una cuenta: el enlace ES el permiso. En la base solo queda el
hash del token, y el token viaja en la cabecera `Authorization`, nunca en la
dirección (así no aparece en registros de servidores intermedios).
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import tempfile
from pathlib import Path as FsPath

from fastapi import APIRouter, File, Form, HTTPException, Path, Request, UploadFile
from fastapi.responses import FileResponse

from ..audio import AudioError, ffmpeg_available, normalize_to_opus, sniff_container
from ..db import days_from_now, now_iso, open_db
from ..deps import limit, require_admin, require_session, settings_of
from ..models import (
    ID_PATTERN,
    ConsentIn,
    PackCreate,
    PackUpdate,
    ReportUpdate,
    ReviewIn,
    SessionCreate,
)
from ..security import hash_token, new_token
from ..services import (
    GREETING_ID,
    build_manifest,
    bump_pack_version,
    coverage,
    evaluate_recording,
    norm_alias,
    remove_audio_file,
)

router = APIRouter(prefix="/api/studio", tags=["estudio"])


def _pack_public(pack: sqlite3.Row) -> dict:
    return {
        "pack_id": pack["id"],
        "language": pack["language"],
        "variant": pack["variant"],
        "community": pack["community"],
        "region": pack["region"],
        "version": pack["version"],
        "status": pack["status"],
        "license": pack["license"],
        "community_label": pack["community_label"],
        "guardians": json.loads(pack["guardians"] or "[]"),
        "is_test": bool(pack["is_test"]),
    }


def _active_consent(conn: sqlite3.Connection, session: sqlite3.Row) -> sqlite3.Row | None:
    if session["consent_id"] is None:
        return None
    consent = conn.execute("SELECT * FROM consents WHERE id = ?", (session["consent_id"],)).fetchone()
    if consent is None or consent["withdrawn_at"]:
        return None
    return consent


# --------------------------------------------------------------- administración


@router.post("/packs", status_code=201)
def create_pack(body: PackCreate, request: Request):
    require_admin(request)
    with open_db(settings_of(request)) as conn:
        if conn.execute("SELECT 1 FROM packs WHERE id = ?", (body.pack_id,)).fetchone():
            raise HTTPException(409, "Ya existe un paquete con ese código.")
        now = now_iso()
        conn.execute(
            """
            INSERT INTO packs (id, variant, language, community, region, version, status, license,
                               community_label, created_at, guardians, is_test, updated_at)
            VALUES (?, ?, ?, ?, ?, '0.1.0', 'draft', ?, ?, ?, ?, 0, ?)
            """,
            (
                body.pack_id, body.variant, body.language, body.community, body.region, body.license,
                body.community_label or None, now,
                json.dumps(body.guardians, ensure_ascii=False), now,
            ),
        )
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (body.pack_id,)).fetchone()
        return _pack_public(pack)


@router.patch("/packs/{pack_id}")
def update_pack(body: PackUpdate, request: Request, pack_id: str = Path(pattern=ID_PATTERN)):
    require_admin(request)
    with open_db(settings_of(request)) as conn:
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (pack_id,)).fetchone()
        if pack is None:
            raise HTTPException(404, "Paquete no encontrado.")
        changes = body.model_dump(exclude_unset=True)
        if "guardians" in changes:
            changes["guardians"] = json.dumps(changes["guardians"] or [], ensure_ascii=False)
        if "community_label" in changes:
            changes["community_label"] = changes["community_label"] or None
        for column, value in changes.items():
            conn.execute(f"UPDATE packs SET {column} = ?, updated_at = ? WHERE id = ?", (value, now_iso(), pack_id))
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (pack_id,)).fetchone()
        return _pack_public(pack)


@router.post("/session", status_code=201)
def create_session(body: SessionCreate, request: Request):
    """Crea un enlace único. El token solo se muestra en esta respuesta."""
    require_admin(request)
    with open_db(settings_of(request)) as conn:
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (body.pack_id,)).fetchone()
        if pack is None:
            raise HTTPException(404, "Paquete no encontrado.")
        if pack["status"] == "withdrawn":
            raise HTTPException(409, "Ese paquete fue retirado.")
        token = new_token()
        expires_at = days_from_now(body.days)
        cur = conn.execute(
            """
            INSERT INTO studio_sessions (token_hash, pack_id, role, alias, is_interpreter,
                                         created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hash_token(token), body.pack_id, body.role, body.alias,
                int(body.is_interpreter and body.role == "reviewer"), now_iso(), expires_at,
            ),
        )
        return {
            "session_id": cur.lastrowid,
            "token": token,
            # El token va después del "#": el navegador no lo manda al servidor.
            "path": f"/#/estudio/{token}",
            "role": body.role,
            "alias": body.alias,
            "is_interpreter": bool(body.is_interpreter and body.role == "reviewer"),
            "pack_id": body.pack_id,
            "expires_at": expires_at,
        }


@router.post("/session/{session_id}/revoke")
def revoke_session(request: Request, session_id: int):
    require_admin(request)
    with open_db(settings_of(request)) as conn:
        cur = conn.execute("UPDATE studio_sessions SET revoked = 1 WHERE id = ?", (session_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Enlace no encontrado.")
    return {"ok": True}


@router.get("/admin/overview")
def admin_overview(request: Request):
    require_admin(request)
    settings = settings_of(request)
    with open_db(settings) as conn:
        packs = []
        for pack in conn.execute("SELECT * FROM packs ORDER BY created_at DESC").fetchall():
            sessions = [
                {
                    "session_id": s["id"],
                    "role": s["role"],
                    "alias": s["alias"],
                    "is_interpreter": bool(s["is_interpreter"]),
                    "has_consent": s["consent_id"] is not None,
                    "expires_at": s["expires_at"],
                    "revoked": bool(s["revoked"]),
                }
                for s in conn.execute(
                    "SELECT * FROM studio_sessions WHERE pack_id = ? ORDER BY id", (pack["id"],)
                )
            ]
            open_reports = conn.execute(
                """
                SELECT COUNT(*) AS n FROM reports p JOIN recordings r ON r.id = p.recording_id
                WHERE r.pack_id = ? AND p.status = 'open'
                """,
                (pack["id"],),
            ).fetchone()["n"]
            packs.append(
                {
                    **_pack_public(pack),
                    "coverage": coverage(conn, pack["id"]),
                    "sessions": sessions,
                    "open_reports": open_reports,
                }
            )
        usage = [
            dict(row)
            for row in conn.execute(
                "SELECT day, pack_id, event, n FROM usage_counts ORDER BY day DESC, pack_id, event LIMIT 400"
            )
        ]
    return {
        "dev_mode": settings.dev_mode,
        "ffmpeg": ffmpeg_available(settings),
        "packs": packs,
        "usage": usage,
    }


# ------------------------------------------------------------- todas las sesiones


@router.get("/session")
def read_session(request: Request):
    settings = settings_of(request)
    with open_db(settings) as conn:
        session = require_session(request, conn)
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (session["pack_id"],)).fetchone()
        consent = _active_consent(conn, session)
        return {
            "role": session["role"],
            "alias": session["alias"],
            "is_interpreter": bool(session["is_interpreter"]),
            "expires_at": session["expires_at"],
            "pack": _pack_public(pack),
            "coverage": coverage(conn, pack["id"]),
            "consent": {"signed": consent is not None, "credit_name": consent["credit_name"] if consent else None},
            "recording_available": ffmpeg_available(settings),
            # El audio del consentimiento es una grabación humana opcional.
            "consent_audio": (settings.frontend_dir / "audio" / "consentimiento.es.opus").is_file(),
        }


@router.get("/recordings/{recording_id}/audio")
def recording_audio(request: Request, recording_id: int):
    """Audio para revisar. No es público: hace falta un enlace del mismo paquete."""
    settings = settings_of(request)
    with open_db(settings) as conn:
        session = require_session(request, conn)
        rec = conn.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,)).fetchone()
        if rec is None or rec["pack_id"] != session["pack_id"] or not rec["audio_path"]:
            raise HTTPException(404, "Grabación no encontrada.")
        if session["role"] == "speaker" and rec["consent_id"] != session["consent_id"]:
            raise HTTPException(403, "Solo puedes escuchar tus propias grabaciones.")
    path = settings.audio_dir / rec["audio_path"]
    if not path.is_file():
        raise HTTPException(404, "Audio no disponible.")
    return FileResponse(path, media_type="audio/ogg", headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------------- hablante


@router.post("/consent", status_code=201)
def sign_consent(body: ConsentIn, request: Request):
    """Registra el consentimiento y entrega el token de retiro (una sola vez)."""
    settings = settings_of(request)
    with open_db(settings) as conn:
        session = require_session(request, conn, "speaker")
        limit(request, f"consent:{session['id']}", 5, 3600)
        if _active_consent(conn, session) is not None:
            raise HTTPException(409, "Ya firmaste el consentimiento con este enlace.")
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (session["pack_id"],)).fetchone()
        token = new_token()
        cur = conn.execute(
            "INSERT INTO consents (credit_name, license, withdrawal_token_hash, signed_at)"
            " VALUES (?, ?, ?, ?)",
            (body.credit_name, pack["license"], hash_token(token), now_iso()),
        )
        conn.execute("UPDATE studio_sessions SET consent_id = ? WHERE id = ?", (cur.lastrowid, session["id"]))
        return {
            "withdrawal_token": token,
            "withdrawal_path": f"/#/retirar/{token}",
            "credit_name": body.credit_name,
            "license": pack["license"],
        }


@router.get("/phrases")
def speaker_phrases(request: Request):
    """Frases a grabar, con el estado de la última grabación de este hablante."""
    with open_db(settings_of(request)) as conn:
        session = require_session(request, conn, "speaker")
        consent = _active_consent(conn, session)
        mine: dict[str, sqlite3.Row] = {}
        if consent is not None:
            for rec in conn.execute(
                "SELECT * FROM recordings WHERE consent_id = ? AND pack_id = ? ORDER BY id",
                (consent["id"], session["pack_id"]),
            ):
                mine[rec["phrase_id"]] = rec  # se queda la más reciente
        notes = {}
        for rec in mine.values():
            if rec["status"] == "rejected":
                note = conn.execute(
                    "SELECT note FROM reviews WHERE recording_id = ? AND verdict = 'reject' ORDER BY id DESC LIMIT 1",
                    (rec["id"],),
                ).fetchone()
                notes[rec["phrase_id"]] = note["note"] if note else ""
        taken = {
            row["phrase_id"]
            for row in conn.execute(
                "SELECT phrase_id FROM recordings WHERE pack_id = ? AND status = 'approved'",
                (session["pack_id"],),
            )
        }
        phrases = []
        for p in conn.execute("SELECT * FROM phrases WHERE active = 1 ORDER BY position"):
            rec = mine.get(p["id"])
            phrases.append(
                {
                    "id": p["id"],
                    "scenario": p["scenario"],
                    "es_text": p["es_text"],
                    "priority": p["priority"],
                    "pictogram": p["pictogram"],
                    "mine": rec["status"] if rec else None,
                    "recording_id": rec["id"] if rec and rec["audio_path"] else None,
                    "note": notes.get(p["id"], ""),
                    "pack_has_approved": p["id"] in taken,
                }
            )
        return {"phrases": phrases}


@router.post("/recordings", status_code=201)
def upload_recording(request: Request, phrase_id: str = Form(...), audio: UploadFile = File(...)):
    settings = settings_of(request)
    with open_db(settings) as conn:
        session = require_session(request, conn, "speaker")
        # Límite por enlace (no por IP): 30 por minuto y 800 por día.
        limit(request, f"upload-min:{session['id']}", 30, 60)
        limit(request, f"upload-day:{session['id']}", 800, 86400)

        consent = _active_consent(conn, session)
        if consent is None:
            raise HTTPException(403, "Antes de grabar hay que aceptar el consentimiento.")
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (session["pack_id"],)).fetchone()
        if pack["status"] == "withdrawn":
            raise HTTPException(409, "Este paquete fue retirado.")
        phrase = conn.execute(
            "SELECT * FROM phrases WHERE id = ? AND active = 1", (phrase_id,)
        ).fetchone()
        if phrase is None:
            raise HTTPException(404, "Frase no encontrada.")

        data = audio.file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, "El archivo es demasiado grande.")
        fmt = sniff_container(data[:16])
        if fmt is None:
            raise HTTPException(415, "Ese archivo no es un audio que podamos leer.")
        if not ffmpeg_available(settings):
            raise HTTPException(503, "El servidor no tiene ffmpeg; no se puede guardar la grabación.")

        relative = f"{session['pack_id']}/{secrets.token_hex(12)}.opus"
        target = settings.audio_dir / relative
        with tempfile.TemporaryDirectory(prefix="nepantla-") as tmp:
            source = FsPath(tmp) / "entrada"
            source.write_bytes(data)
            try:
                info = normalize_to_opus(settings, source, target, fmt)
            except AudioError as exc:
                raise HTTPException(422, str(exc)) from exc

        if not (settings.min_audio_seconds <= info["duration"] <= settings.max_audio_seconds):
            target.unlink(missing_ok=True)
            raise HTTPException(
                422,
                f"La grabación debe durar entre {settings.min_audio_seconds:g} y "
                f"{settings.max_audio_seconds:g} segundos.",
            )

        try:
            # Una grabación nueva reemplaza a la que aún estaba en revisión.
            for old in conn.execute(
                "SELECT * FROM recordings WHERE consent_id = ? AND pack_id = ? AND phrase_id = ?"
                " AND status = 'pending'",
                (consent["id"], session["pack_id"], phrase_id),
            ).fetchall():
                remove_audio_file(settings, old["audio_path"])
                conn.execute(
                    "UPDATE recordings SET status = 'superseded', audio_path = '' WHERE id = ?",
                    (old["id"],),
                )
            cur = conn.execute(
                """
                INSERT INTO recordings (pack_id, phrase_id, audio_path, speaker_alias, consent_id,
                                        status, created_at, bytes)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    session["pack_id"], phrase_id, relative, session["alias"], consent["id"],
                    now_iso(), info["bytes"],
                ),
            )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return {
            "recording_id": cur.lastrowid,
            "phrase_id": phrase_id,
            "status": "pending",
            "duration": round(info["duration"], 2),
            "bytes": info["bytes"],
        }


# ----------------------------------------------------------------------- revisor


@router.get("/queue")
def review_queue(request: Request):
    """Grabaciones en espera que este revisor todavía no ha escuchado."""
    with open_db(settings_of(request)) as conn:
        session = require_session(request, conn, "reviewer")
        me = norm_alias(session["alias"])
        items = []
        for rec in conn.execute(
            """
            SELECT r.id, r.phrase_id, r.speaker_alias, r.created_at, p.es_text, p.scenario, p.position
            FROM recordings r JOIN phrases p ON p.id = r.phrase_id
            WHERE r.pack_id = ? AND r.status = 'pending'
            ORDER BY p.position, r.id
            """,
            (session["pack_id"],),
        ).fetchall():
            if norm_alias(rec["speaker_alias"]) == me:
                continue  # nadie revisa su propia voz
            reviewers = conn.execute(
                "SELECT reviewer_alias, reviewer_role FROM reviews WHERE recording_id = ?", (rec["id"],)
            ).fetchall()
            if any(norm_alias(r["reviewer_alias"]) == me for r in reviewers):
                continue
            items.append(
                {
                    "recording_id": rec["id"],
                    "phrase_id": rec["phrase_id"],
                    "es_text": rec["es_text"],
                    "scenario": rec["scenario"],
                    "approvals": len(reviewers),
                    "has_interpreter": any(r["reviewer_role"] == "interpreter" for r in reviewers),
                }
            )
        return {"queue": items}


@router.post("/reviews", status_code=201)
def post_review(body: ReviewIn, request: Request):
    with open_db(settings_of(request)) as conn:
        session = require_session(request, conn, "reviewer")
        limit(request, f"review:{session['id']}", 240, 60)
        rec = conn.execute("SELECT * FROM recordings WHERE id = ?", (body.recording_id,)).fetchone()
        if rec is None or rec["pack_id"] != session["pack_id"]:
            raise HTTPException(404, "Grabación no encontrada.")
        if rec["status"] != "pending":
            raise HTTPException(409, "Esta grabación ya no está en revisión.")
        if norm_alias(rec["speaker_alias"]) == norm_alias(session["alias"]):
            raise HTTPException(403, "No puedes revisar tu propia grabación.")
        already = [
            r for r in conn.execute("SELECT reviewer_alias FROM reviews WHERE recording_id = ?", (rec["id"],))
            if norm_alias(r["reviewer_alias"]) == norm_alias(session["alias"])
        ]
        if already:
            raise HTTPException(409, "Ya revisaste esta grabación.")
        conn.execute(
            """
            INSERT INTO reviews (recording_id, reviewer_alias, verdict, note, created_at, reviewer_role)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rec["id"], session["alias"], body.verdict, body.note, now_iso(),
                "interpreter" if session["is_interpreter"] else "health",
            ),
        )
        result = evaluate_recording(conn, rec["id"])
        return {"recording_id": rec["id"], **result}


# ---------------------------------------------------------------------- guardián


def _reports_for(conn: sqlite3.Connection, pack_id: str) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT p.id AS report_id, r.phrase_id, p.reason, p.status, p.created_at
            FROM reports p JOIN recordings r ON r.id = p.recording_id
            WHERE r.pack_id = ? ORDER BY p.id DESC LIMIT 200
            """,
            (pack_id,),
        )
    ]


@router.get("/pack")
def guardian_pack(request: Request):
    with open_db(settings_of(request)) as conn:
        session = require_session(request, conn, "guardian")
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (session["pack_id"],)).fetchone()
        manifest = build_manifest(conn, pack)
        ids = {
            row["phrase_id"]: row["id"]
            for row in conn.execute(
                "SELECT id, phrase_id FROM recordings WHERE pack_id = ? AND status = 'approved'",
                (pack["id"],),
            )
        }
        texts = {p["id"]: p["es_text"] for p in conn.execute("SELECT id, es_text FROM phrases")}
        approved = [
            {**entry, "es_text": texts.get(entry["id"], ""), "recording_id": ids.get(entry["id"])}
            for entry in manifest["phrases"]
        ]
        if manifest["greeting"]:
            approved.insert(
                0,
                {
                    "id": GREETING_ID, **manifest["greeting"],
                    "es_text": texts.get(GREETING_ID, ""), "recording_id": ids.get(GREETING_ID),
                },
            )
        done = {entry["id"] for entry in approved}
        missing = [
            {"id": p["id"], "es_text": p["es_text"]}
            for p in conn.execute("SELECT id, es_text FROM phrases WHERE active = 1 ORDER BY position")
            if p["id"] not in done
        ]
        return {
            "pack": _pack_public(pack),
            "coverage": coverage(conn, pack["id"]),
            "approved": approved,
            "missing": missing,
            "reports": _reports_for(conn, pack["id"]),
        }


@router.post("/pack/approve")
def guardian_approve(request: Request):
    """El guardián publica el paquete. Un paquete de prueba nunca se publica."""
    with open_db(settings_of(request)) as conn:
        session = require_session(request, conn, "guardian")
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (session["pack_id"],)).fetchone()
        if pack["is_test"]:
            raise HTTPException(409, "Un paquete de AUDIO DE PRUEBA no puede publicarse como lengua real.")
        if pack["status"] == "withdrawn":
            raise HTTPException(409, "Este paquete fue retirado.")
        if pack["status"] == "approved":
            return {**_pack_public(pack), "changed": False}
        state = coverage(conn, pack["id"])
        if state["approved"] == 0:
            raise HTTPException(409, "Todavía no hay ninguna frase con doble revisión.")
        conn.execute("UPDATE packs SET status = 'approved' WHERE id = ?", (pack["id"],))
        bump_pack_version(conn, pack["id"], "minor")
        pack = conn.execute("SELECT * FROM packs WHERE id = ?", (pack["id"],)).fetchone()
        return {**_pack_public(pack), "changed": True, "coverage": state}


@router.post("/reports/{report_id}")
def update_report(body: ReportUpdate, request: Request, report_id: int):
    with open_db(settings_of(request)) as conn:
        session = require_session(request, conn, "guardian")
        row = conn.execute(
            """
            SELECT p.id FROM reports p JOIN recordings r ON r.id = p.recording_id
            WHERE p.id = ? AND r.pack_id = ?
            """,
            (report_id, session["pack_id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Reporte no encontrado.")
        conn.execute("UPDATE reports SET status = ? WHERE id = ?", (body.status, report_id))
    return {"ok": True}
