"""Reportes de "audio incorrecto".

Decisión de privacidad: el reporte lleva paquete, frase y un motivo de una
lista cerrada. No hay texto libre (ahí acabarían escribiéndose datos de
pacientes) y se guarda el día, no la hora.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..db import open_db, today
from ..deps import limit, settings_of
from ..models import ReportIn
from ..services import current_recording
from .packs import load_public_pack

router = APIRouter(prefix="/api", tags=["reportes"])


@router.post("/reports", status_code=201)
def post_report(body: ReportIn, request: Request):
    limit(request, "reports", 30, 60)
    settings = settings_of(request)
    with open_db(settings) as conn:
        load_public_pack(conn, settings, body.pack_id)
        recording = current_recording(conn, body.pack_id, body.phrase_id)
        if recording is None:
            raise HTTPException(404, "Esa frase no tiene audio en este paquete.")
        conn.execute(
            "INSERT INTO reports (recording_id, reason, status, created_at) VALUES (?, ?, 'open', ?)",
            (recording["recording_id"], body.reason, today()),
        )
    return {"ok": True}
