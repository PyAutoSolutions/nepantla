"""Retiro de voces, frases y paquetes.

Un solo endpoint, dos tipos de token:

* Token de retiro del hablante (se le entrega al firmar el consentimiento):
  retira toda su voz o una sola frase. No hay que dar explicaciones.
* Enlace del guardián del paquete: retira una frase o el paquete completo.

Al retirar se borra el archivo de audio del servidor y el paquete sube de
versión; los teléfonos borran esas frases en su siguiente conexión.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..db import now_iso, open_db
from ..deps import limit, session_from_token, settings_of
from ..models import WithdrawIn
from ..security import hash_token
from ..services import withdraw_recordings

router = APIRouter(prefix="/api", tags=["retiro"])

WITHDRAWN_CREDIT = "(voz retirada)"


@router.post("/withdraw")
def withdraw(body: WithdrawIn, request: Request):
    limit(request, "withdraw", 30, 60)
    settings = settings_of(request)
    with open_db(settings) as conn:
        consent = conn.execute(
            "SELECT * FROM consents WHERE withdrawal_token_hash = ?", (hash_token(body.token),)
        ).fetchone()

        if consent is not None:
            if body.scope == "pack":
                raise HTTPException(403, "Solo un guardián puede retirar el paquete completo.")
            if body.scope == "phrase" and not body.phrase_id:
                raise HTTPException(422, "Falta indicar la frase.")
            query = "SELECT * FROM recordings WHERE consent_id = ? AND status != 'withdrawn'"
            params: list = [consent["id"]]
            if body.scope == "phrase":
                query += " AND phrase_id = ?"
                params.append(body.phrase_id)
            recordings = conn.execute(query, params).fetchall()
            summary = {
                "kind": "voice" if body.scope == "voice" else "phrase",
                "credit_name": consent["credit_name"],
                "recordings": len(recordings),
                "packs": sorted({rec["pack_id"] for rec in recordings}),
            }
            if body.dry_run:
                return {"dry_run": True, **summary}
            versions = withdraw_recordings(conn, settings, recordings)
            if body.scope == "voice":
                # El consentimiento queda cerrado y el crédito se borra.
                conn.execute(
                    "UPDATE consents SET withdrawn_at = ?, credit_name = ? WHERE id = ?",
                    (now_iso(), WITHDRAWN_CREDIT, consent["id"]),
                )
            return {"dry_run": False, **summary, "versions": versions}

        guardian = session_from_token(conn, body.token)
        if guardian is not None and guardian["role"] == "guardian":
            pack_id = guardian["pack_id"]
            if body.scope == "voice":
                raise HTTPException(422, "Indica si retiras una frase (phrase) o el paquete (pack).")
            if body.scope == "phrase":
                if not body.phrase_id:
                    raise HTTPException(422, "Falta indicar la frase.")
                recordings = conn.execute(
                    "SELECT * FROM recordings WHERE pack_id = ? AND phrase_id = ?"
                    " AND status IN ('approved', 'pending')",
                    (pack_id, body.phrase_id),
                ).fetchall()
                summary = {"kind": "phrase", "recordings": len(recordings), "packs": [pack_id]}
                if body.dry_run:
                    return {"dry_run": True, **summary}
                versions = withdraw_recordings(conn, settings, recordings)
                return {"dry_run": False, **summary, "versions": versions}

            recordings = conn.execute(
                "SELECT * FROM recordings WHERE pack_id = ? AND status != 'withdrawn'", (pack_id,)
            ).fetchall()
            summary = {"kind": "pack", "recordings": len(recordings), "packs": [pack_id]}
            if body.dry_run:
                return {"dry_run": True, **summary}
            withdraw_recordings(conn, settings, recordings)
            conn.execute(
                "UPDATE packs SET status = 'withdrawn', updated_at = ? WHERE id = ?",
                (now_iso(), pack_id),
            )
            version = conn.execute("SELECT version FROM packs WHERE id = ?", (pack_id,)).fetchone()
            return {"dry_run": False, **summary, "versions": {pack_id: version["version"]}}

    raise HTTPException(404, "No reconocemos ese token de retiro.")
