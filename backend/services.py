"""Reglas del proyecto en un solo lugar.

* Doble revisión: una grabación solo entra al paquete con la aprobación de
  dos personas distintas y al menos una debe ser intérprete de esa lengua.
* Versionado: cada aprobación y cada retiro suben la versión del paquete.
* Retiro: al retirar una voz se borra el archivo de audio del servidor.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Iterable

from .config import Settings
from .db import now_iso

GREETING_ID = "greeting"
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def bump(version: str, part: str = "patch") -> str:
    match = _SEMVER.match(version or "")
    if not match:
        return "0.1.0"
    major, minor, patch = (int(x) for x in match.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump_pack_version(conn: sqlite3.Connection, pack_id: str, part: str = "patch") -> str:
    row = conn.execute("SELECT version FROM packs WHERE id = ?", (pack_id,)).fetchone()
    new_version = bump(row["version"], part)
    conn.execute(
        "UPDATE packs SET version = ?, updated_at = ? WHERE id = ?",
        (new_version, now_iso(), pack_id),
    )
    return new_version


def norm_alias(alias: str) -> str:
    """Compara nombres sin importar mayúsculas ni espacios de más."""
    return " ".join(str(alias).split()).casefold()


def approvers(conn: sqlite3.Connection, recording_id: int) -> list[sqlite3.Row]:
    """Revisores que aprobaron, sin repetir a la misma persona."""
    rows = conn.execute(
        """
        SELECT reviewer_alias, reviewer_role FROM reviews
        WHERE recording_id = ? AND verdict = 'approve' ORDER BY id
        """,
        (recording_id,),
    ).fetchall()
    unique: dict[str, sqlite3.Row] = {}
    for row in rows:
        unique.setdefault(norm_alias(row["reviewer_alias"]), row)
    return list(unique.values())


def evaluate_recording(conn: sqlite3.Connection, recording_id: int) -> dict:
    """Decide el estado de una grabación después de cada revisión."""
    rec = conn.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,)).fetchone()
    result = {"status": rec["status"], "approvals": 0, "needs_interpreter": False, "version": None}
    if rec["status"] != "pending":
        return result

    rejected = conn.execute(
        "SELECT 1 FROM reviews WHERE recording_id = ? AND verdict = 'reject' LIMIT 1",
        (recording_id,),
    ).fetchone()
    if rejected:
        conn.execute("UPDATE recordings SET status = 'rejected' WHERE id = ?", (recording_id,))
        result["status"] = "rejected"
        return result

    who = approvers(conn, recording_id)
    result["approvals"] = len(who)
    has_interpreter = any(row["reviewer_role"] == "interpreter" for row in who)
    if len(who) >= 2 and not has_interpreter:
        result["needs_interpreter"] = True
    if len(who) >= 2 and has_interpreter:
        # La grabación anterior de esa frase deja de ser la vigente.
        conn.execute(
            """
            UPDATE recordings SET status = 'superseded'
            WHERE pack_id = ? AND phrase_id = ? AND status = 'approved'
            """,
            (rec["pack_id"], rec["phrase_id"]),
        )
        conn.execute(
            "UPDATE recordings SET status = 'approved', approved_at = ? WHERE id = ?",
            (now_iso(), recording_id),
        )
        result["status"] = "approved"
        result["version"] = bump_pack_version(conn, rec["pack_id"])
    return result


def _approved_rows(conn: sqlite3.Connection, pack_id: str) -> list[dict]:
    """Grabaciones vigentes del paquete, cada una con sus revisores."""
    recs = conn.execute(
        """
        SELECT r.id, r.phrase_id, r.approved_at, r.bytes, r.audio_path,
               c.credit_name, p.position
        FROM recordings r
        JOIN consents c ON c.id = r.consent_id
        JOIN phrases p ON p.id = r.phrase_id
        WHERE r.pack_id = ? AND r.status = 'approved' AND p.active = 1
        ORDER BY p.position
        """,
        (pack_id,),
    ).fetchall()
    reviews = conn.execute(
        """
        SELECT v.recording_id, v.reviewer_alias
        FROM reviews v JOIN recordings r ON r.id = v.recording_id
        WHERE r.pack_id = ? AND r.status = 'approved' AND v.verdict = 'approve'
        ORDER BY v.id
        """,
        (pack_id,),
    ).fetchall()
    by_recording: dict[int, dict[str, str]] = {}
    for row in reviews:
        names = by_recording.setdefault(row["recording_id"], {})
        names.setdefault(norm_alias(row["reviewer_alias"]), row["reviewer_alias"])

    out = []
    for rec in recs:
        reviewed_by = list(by_recording.get(rec["id"], {}).values())
        # Regla dura, aunque el estado diga "approved": sin dos revisores
        # distintos la frase no existe para la app.
        if len(reviewed_by) < 2:
            continue
        out.append(
            {
                "recording_id": rec["id"],
                "phrase_id": rec["phrase_id"],
                "audio_path": rec["audio_path"],
                "bytes": rec["bytes"],
                "reviewed_by": reviewed_by,
                "recorded_by": rec["credit_name"],
                "approved_at": (rec["approved_at"] or "")[:10],
            }
        )
    return out


def current_recording(conn: sqlite3.Connection, pack_id: str, phrase_id: str) -> dict | None:
    for row in _approved_rows(conn, pack_id):
        if row["phrase_id"] == phrase_id:
            return row
    return None


def build_manifest(conn: sqlite3.Connection, pack: sqlite3.Row) -> dict:
    """Arma el manifest.json público del paquete (formato abierto v1)."""
    greeting = None
    phrases = []
    for row in _approved_rows(conn, pack["id"]):
        entry = {
            "reviewed_by": row["reviewed_by"],
            "recorded_by": row["recorded_by"],
            "approved_at": row["approved_at"],
            "bytes": row["bytes"],
        }
        if row["phrase_id"] == GREETING_ID:
            greeting = {"audio": "greeting.opus", **entry}
        else:
            phrases.append({"id": row["phrase_id"], "audio": f"audio/{row['phrase_id']}.opus", **entry})
    return {
        "format_version": 1,
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
        "greeting": greeting,
        "phrases": phrases,
    }


def pack_summary(conn: sqlite3.Connection, pack: sqlite3.Row) -> dict:
    manifest = build_manifest(conn, pack)
    total = sum(p["bytes"] for p in manifest["phrases"])
    if manifest["greeting"]:
        total += manifest["greeting"]["bytes"]
    summary = {k: v for k, v in manifest.items() if k not in {"phrases", "greeting", "format_version"}}
    summary.update(
        {
            "phrase_count": len(manifest["phrases"]),
            "total_bytes": total,
            "has_greeting": manifest["greeting"] is not None,
            "updated_at": (pack["updated_at"] or "")[:10],
        }
    )
    return summary


def coverage(conn: sqlite3.Connection, pack_id: str) -> dict:
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM phrases WHERE active = 1 AND id != ?", (GREETING_ID,)
    ).fetchone()["n"]
    approved = [r for r in _approved_rows(conn, pack_id) if r["phrase_id"] != GREETING_ID]
    counts = {
        row["status"]: row["n"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM recordings WHERE pack_id = ? GROUP BY status",
            (pack_id,),
        )
    }
    return {
        "total_phrases": total,
        "approved": len(approved),
        "pending": counts.get("pending", 0),
        "rejected": counts.get("rejected", 0),
        "has_greeting": current_recording(conn, pack_id, GREETING_ID) is not None,
    }


def remove_audio_file(settings: Settings, audio_path: str) -> None:
    """Borra el archivo solo si de verdad está dentro de la carpeta de audios."""
    if not audio_path:
        return
    root = settings.audio_dir.resolve()
    path = (settings.audio_dir / audio_path).resolve()
    if root in path.parents and path.is_file():
        path.unlink()


def withdraw_recordings(
    conn: sqlite3.Connection, settings: Settings, recordings: Iterable[sqlite3.Row]
) -> dict[str, str]:
    """Retira grabaciones: borra el audio y sube la versión de cada paquete
    que pierde una frase vigente. Devuelve {pack_id: versión nueva}."""
    touched: set[str] = set()
    for rec in recordings:
        if rec["status"] == "withdrawn":
            continue
        if rec["status"] == "approved":
            touched.add(rec["pack_id"])
        remove_audio_file(settings, rec["audio_path"])
        conn.execute(
            "UPDATE recordings SET status = 'withdrawn', audio_path = '' WHERE id = ?",
            (rec["id"],),
        )
    return {pack_id: bump_pack_version(conn, pack_id) for pack_id in sorted(touched)}
