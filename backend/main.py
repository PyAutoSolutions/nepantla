"""Nepantla: servidor FastAPI.

Arranque local:

    uvicorn backend.main:app --reload --no-access-log

`--no-access-log` importa: el registro de accesos de uvicorn imprime la IP de
cada petición. Además lo apagamos aquí por código, por si alguien olvida la
bandera.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .audio import ffmpeg_available
from .backup import BackupLoop
from .config import Settings
from .db import init_db, open_db, seed_phrases
from .packs_io import import_example_packs
from .routes import packs, reports, studio, usage, withdraw
from .security import BodyLimitMiddleware, RateLimiter, SecurityHeadersMiddleware

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("audio/ogg", ".opus")

# Decisión de privacidad: sin registro de accesos (ahí viaja la IP).
logging.getLogger("uvicorn.access").disabled = True

JSON_BODY_LIMIT = 16 * 1024


def frontend_build_id(settings: Settings) -> str:
    """Huella del frontend: cambia cuando cambia cualquier archivo.

    El service worker la usa como nombre de caché, así cada despliegue
    actualiza la app instalada sin que nadie tenga que acordarse de subir un
    número de versión a mano.
    """
    digest = hashlib.sha256()
    for path in sorted(settings.frontend_dir.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(settings.frontend_dir).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


class FrontendFiles(StaticFiles):
    """Archivos estáticos que siempre se revalidan (el caché real lo lleva
    el service worker)."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.audio_dir.mkdir(parents=True, exist_ok=True)
        init_db(settings.db_path)
        with open_db(settings) as conn:
            seed_phrases(conn, settings.phrases_file)
            if settings.import_example_packs:
                import_example_packs(conn, settings)
        app.state.build_id = frontend_build_id(settings)
        backups = BackupLoop(settings) if settings.enable_backups else None
        if backups:
            backups.start()
        try:
            yield
        finally:
            if backups:
                backups.stop()

    # Sin /docs ni /redoc: esas páginas cargan scripts de un CDN externo y la
    # regla del proyecto es cero recursos de terceros.
    app = FastAPI(
        title="Nepantla",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.dev_mode else None,
    )
    app.state.settings = settings
    app.state.limiter = RateLimiter()
    app.state.build_id = "dev"

    # El último que se añade es el más externo: las cabeceras de seguridad
    # también cubren las respuestas 413 del límite de tamaño.
    app.add_middleware(
        BodyLimitMiddleware,
        default_limit=JSON_BODY_LIMIT,
        path_limits={"/api/studio/recordings": settings.max_upload_bytes + 64 * 1024},
    )
    app.add_middleware(SecurityHeadersMiddleware, force_https=settings.force_https)
    # Compresión para que la primera carga sea ligera en redes lentas (3G).
    app.add_middleware(GZipMiddleware, minimum_size=800)

    app.include_router(packs.router)
    app.include_router(usage.router)
    app.include_router(reports.router)
    app.include_router(studio.router)
    app.include_router(withdraw.router)

    @app.get("/api/health")
    def health():
        return {
            "ok": True,
            "dev_mode": settings.dev_mode,
            "build": app.state.build_id,
            "studio": bool(settings.admin_token),
            "ffmpeg": ffmpeg_available(settings),
        }

    @app.get("/sw.js", include_in_schema=False)
    def service_worker(request: Request) -> Response:
        source = (settings.frontend_dir / "sw.js").read_text(encoding="utf-8")
        body = source.replace("__BUILD__", request.app.state.build_id)
        return Response(
            body,
            media_type="text/javascript",
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
        )

    app.mount("/", FrontendFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
