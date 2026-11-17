"""Ayudas compartidas por las rutas."""
from __future__ import annotations

import hmac
import sqlite3

from fastapi import HTTPException, Request

from .config import Settings
from .db import now_iso
from .security import hash_token


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


def limit(request: Request, key: str, max_hits: int, window_seconds: float) -> None:
    """Límite de frecuencia. `key` nunca contiene la IP de quien llama."""
    if not request.app.state.limiter.allow(key, max_hits, window_seconds):
        raise HTTPException(429, "Demasiadas solicitudes. Espera un momento e inténtalo otra vez.")


def bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(401, "Falta el token.")
    token = header[7:].strip()
    if not token:
        raise HTTPException(401, "Falta el token.")
    return token


def require_admin(request: Request) -> None:
    settings = settings_of(request)
    if not settings.admin_token:
        raise HTTPException(503, "El estudio no está configurado: falta NEPANTLA_ADMIN_TOKEN.")
    limit(request, "admin-auth", 60, 60)
    token = bearer(request)
    if not hmac.compare_digest(token.encode("utf-8"), settings.admin_token.encode("utf-8")):
        raise HTTPException(403, "Token de administración incorrecto.")


def session_from_token(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM studio_sessions WHERE token_hash = ?", (hash_token(token),)
    ).fetchone()
    if row is None or row["revoked"] or row["expires_at"] < now_iso():
        return None
    return row


def require_session(request: Request, conn: sqlite3.Connection, *roles: str) -> sqlite3.Row:
    limit(request, "studio-auth", 600, 60)
    session = session_from_token(conn, bearer(request))
    if session is None:
        raise HTTPException(401, "Este enlace no es válido o ya venció. Pide uno nuevo.")
    if roles and session["role"] not in roles:
        raise HTTPException(403, "Este enlace no tiene permiso para hacer eso.")
    return session
