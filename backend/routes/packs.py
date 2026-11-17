"""Paquetes de lengua: lista pública, manifest y audios.

Reglas:
* Solo se listan paquetes aprobados. Los borradores (y los paquetes de
  prueba, que siempre son borradores) solo aparecen en modo desarrollo.
* Un paquete retirado responde 410 y aparece en `withdrawn`, para que los
  teléfonos que lo tenían lo borren en su siguiente conexión.
* Un audio solo se sirve si su grabación tiene dos revisores distintos.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import FileResponse, JSONResponse

from ..config import Settings
from ..db import open_db
from ..deps import settings_of
from ..models import ID_PATTERN
from ..services import GREETING_ID, build_manifest, current_recording, pack_summary

router = APIRouter(prefix="/api/packs", tags=["paquetes"])

NO_CACHE = {"Cache-Control": "no-cache"}


def is_visible(pack: sqlite3.Row, settings: Settings) -> bool:
    return pack["status"] == "approved" or (settings.dev_mode and pack["status"] == "draft")


def load_public_pack(conn: sqlite3.Connection, settings: Settings, pack_id: str) -> sqlite3.Row:
    pack = conn.execute("SELECT * FROM packs WHERE id = ?", (pack_id,)).fetchone()
    if pack is None:
        raise HTTPException(404, "Paquete no encontrado.")
    if pack["status"] == "withdrawn":
        raise HTTPException(410, "Este paquete fue retirado por sus guardianes.")
    if not is_visible(pack, settings):
        raise HTTPException(404, "Paquete no encontrado.")
    return pack


@router.get("")
def list_packs(request: Request):
    settings = settings_of(request)
    with open_db(settings) as conn:
        rows = conn.execute("SELECT * FROM packs ORDER BY language, variant").fetchall()
        packs = [pack_summary(conn, row) for row in rows if is_visible(row, settings)]
        withdrawn = [row["id"] for row in rows if row["status"] == "withdrawn"]
    return JSONResponse(
        {"dev_mode": settings.dev_mode, "packs": packs, "withdrawn": withdrawn}, headers=NO_CACHE
    )


@router.get("/{pack_id}/manifest.json")
def get_manifest(request: Request, pack_id: str = Path(pattern=ID_PATTERN)):
    settings = settings_of(request)
    with open_db(settings) as conn:
        pack = load_public_pack(conn, settings, pack_id)
        manifest = build_manifest(conn, pack)
    return JSONResponse(manifest, headers=NO_CACHE)


def _audio_response(request: Request, pack_id: str, phrase_id: str) -> FileResponse:
    settings = settings_of(request)
    with open_db(settings) as conn:
        load_public_pack(conn, settings, pack_id)
        recording = current_recording(conn, pack_id, phrase_id)
    if recording is None:
        raise HTTPException(404, "Esta frase no tiene audio revisado en este paquete.")
    path = settings.audio_dir / recording["audio_path"]
    if not path.is_file():
        raise HTTPException(404, "Audio no disponible.")
    return FileResponse(path, media_type="audio/ogg", headers=NO_CACHE)


@router.get("/{pack_id}/audio/{phrase_id}.opus")
def get_audio(
    request: Request,
    pack_id: str = Path(pattern=ID_PATTERN),
    phrase_id: str = Path(pattern=ID_PATTERN),
):
    if phrase_id == GREETING_ID:
        raise HTTPException(404, "El saludo se pide en greeting.opus.")
    return _audio_response(request, pack_id, phrase_id)


@router.get("/{pack_id}/greeting.opus")
def get_greeting(request: Request, pack_id: str = Path(pattern=ID_PATTERN)):
    return _audio_response(request, pack_id, GREETING_ID)
