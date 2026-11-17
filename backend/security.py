"""Tokens, límites de frecuencia y cabeceras de seguridad.

Decisiones de privacidad que viven aquí:

* Los tokens (retiro de voz y enlaces del estudio) son aleatorios de 256 bits
  y solo se guarda su hash SHA-256. Si alguien roba la base, no puede retirar
  voces ni entrar al estudio.
* Los límites de frecuencia NO usan la dirección IP. Se cuentan por enlace
  del estudio o de forma global por endpoint, y solo en memoria.
* La política CSP prohíbe cualquier script, estilo, fuente o conexión que no
  venga del propio servidor: sin analítica ni recursos de terceros.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RateLimiter:
    """Ventana deslizante en memoria. La clave nunca es una IP."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data: blob:",
        "media-src 'self' blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "worker-src 'self'",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": CSP,
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    # El micrófono solo lo usa el estudio de grabación, en este mismo origen.
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=(), interest-cohort=()",
}

HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware:
    """Añade las cabeceras a todas las respuestas y fuerza HTTPS si se pide."""

    def __init__(self, app: ASGIApp, force_https: bool = False) -> None:
        self.app = app
        self.force_https = force_https

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        forwarded_proto = headers.get("x-forwarded-proto", "").split(",")[0].strip()
        is_https = scope.get("scheme") == "https" or forwarded_proto == "https"

        if self.force_https and forwarded_proto == "http" and scope["method"] in {"GET", "HEAD"}:
            host = headers.get("host", "")
            query = scope.get("query_string", b"").decode("latin-1")
            location = f"https://{host}{scope['path']}" + (f"?{query}" if query else "")
            await send(
                {
                    "type": "http.response.start",
                    "status": 308,
                    "headers": [(b"location", location.encode("latin-1")), (b"content-length", b"0")],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra = list(message.get("headers", []))
                for name, value in SECURITY_HEADERS.items():
                    if name.lower().encode() not in existing:
                        extra.append((name.encode(), value.encode()))
                if is_https and b"strict-transport-security" not in existing:
                    extra.append((b"Strict-Transport-Security", HSTS.encode()))
                message = {**message, "headers": extra}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodyLimitMiddleware:
    """Corta cualquier cuerpo de petición más grande que el límite.

    Revisa `Content-Length` y además cuenta los bytes reales mientras llegan,
    para que tampoco pase una subida "por trozos" sin tamaño declarado.
    """

    def __init__(self, app: ASGIApp, default_limit: int, path_limits: dict[str, int] | None = None) -> None:
        self.app = app
        self.default_limit = default_limit
        self.path_limits = path_limits or {}

    def _limit_for(self, path: str) -> int:
        return self.path_limits.get(path, self.default_limit)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        limit = self._limit_for(scope["path"])
        for name, value in scope["headers"]:
            if name == b"content-length" and value.isdigit() and int(value) > limit:
                await self._reject(send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # FastAPI deja pasar tal cual las HTTPException que nacen
                    # mientras lee el cuerpo; cualquier otra la volvería un 400.
                    raise HTTPException(status_code=413, detail="El archivo es demasiado grande.")
            return message

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = '{"detail":"El archivo es demasiado grande."}'.encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
