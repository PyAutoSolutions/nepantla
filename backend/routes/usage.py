"""Conteos de uso agregados.

Decisión de privacidad (la más importante del backend):

Este endpoint guarda una sola cosa: "tal día, tal paquete, tal evento, N
veces". Para que eso sea verdad y no solo una promesa:

* El modelo de entrada rechaza cualquier campo extra.
* El `pack_id` debe existir: no se puede usar como "campo libre" para
  guardar un identificador disfrazado.
* El día lo pone el servidor al recibir (UTC). El teléfono no manda fecha ni
  hora, así que tampoco se puede reconstruir cuándo fue una consulta.
* Esta función no lee `request.client` ni ninguna cabecera: ni IP ni
  navegador llegan a la base ni a los registros.
* El límite de frecuencia es global, no por IP.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..db import open_db, today
from ..deps import limit, settings_of
from ..models import UsageIn

router = APIRouter(prefix="/api", tags=["uso"])


@router.post("/usage", status_code=204)
def post_usage(body: UsageIn, request: Request) -> Response:
    limit(request, "usage", 600, 60)
    with open_db(settings_of(request)) as conn:
        pack = conn.execute("SELECT 1 FROM packs WHERE id = ?", (body.pack_id,)).fetchone()
        if pack is None:
            raise HTTPException(404, "Paquete no encontrado.")
        conn.execute(
            """
            INSERT INTO usage_counts (day, pack_id, event, n) VALUES (?, ?, ?, ?)
            ON CONFLICT(day, pack_id, event) DO UPDATE SET n = n + excluded.n
            """,
            (today(), body.pack_id, body.event, body.n),
        )
    return Response(status_code=204)
