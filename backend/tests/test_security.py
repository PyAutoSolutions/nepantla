"""Cabeceras, HTTPS, copias de seguridad y "cero recursos de terceros"."""
from __future__ import annotations

import re
import sqlite3

from fastapi.testclient import TestClient

from backend.backup import backup_now, prune
from backend.config import ROOT
from backend.main import create_app

from .conftest import make_settings

FRONTEND = ROOT / "frontend"


def test_cabeceras_de_seguridad_en_la_app_y_en_la_api(client):
    for path in ("/", "/api/packs", "/api/health", "/no-existe"):
        headers = client.get(path).headers
        csp = headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp and "'unsafe-eval'" not in csp
        assert "connect-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert headers["referrer-policy"] == "no-referrer"
        assert headers["x-content-type-options"] == "nosniff"
        assert "microphone=(self)" in headers["permissions-policy"]


def test_las_respuestas_de_error_tambien_llevan_cabeceras(client):
    response = client.post("/api/usage", content=b"x" * 40_000, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert "content-security-policy" in response.headers


def test_nunca_se_ponen_cookies(client):
    for path in ("/", "/api/packs", "/api/health"):
        assert "set-cookie" not in client.get(path).headers


def test_hsts_solo_cuando_la_peticion_llego_por_https(client):
    assert "strict-transport-security" not in client.get("/api/health").headers
    secure = client.get("/api/health", headers={"X-Forwarded-Proto": "https"})
    assert "max-age=" in secure.headers["strict-transport-security"]


def test_redirige_a_https_cuando_se_pide(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, force_https=True))) as client:
        response = client.get(
            "/api/packs?x=1", headers={"X-Forwarded-Proto": "http", "Host": "nepantla.example"},
            follow_redirects=False,
        )
        assert response.status_code == 308
        assert response.headers["location"] == "https://nepantla.example/api/packs?x=1"
        ok = client.get("/api/packs", headers={"X-Forwarded-Proto": "https"})
        assert ok.status_code == 200


def test_no_hay_paginas_de_documentacion_con_scripts_externos(client, dev_client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404
    assert dev_client.get("/docs").status_code == 404
    assert dev_client.get("/api/openapi.json").status_code == 200


def test_la_app_se_sirve_en_la_raiz(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Nepantla" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_el_manifest_de_la_pwa_tiene_su_tipo(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    data = response.json()
    assert data["display"] == "standalone" and data["start_url"]
    sizes = {icon["sizes"] for icon in data["icons"]}
    assert {"192x192", "512x512"} <= sizes


def test_el_service_worker_lleva_la_huella_del_despliegue(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"
    assert "__BUILD__" not in response.text
    assert client.get("/api/health").json()["build"] in response.text


def test_el_frontend_no_carga_nada_de_otros_servidores():
    """Sin CDN, sin fuentes externas, sin analítica: todo sale de este servidor."""
    pattern = re.compile(r"""(?:src|href|action)\s*=\s*["'](?:https?:)?//""", re.I)
    loaders = re.compile(r"""(?:fetch|import|importScripts|XMLHttpRequest|url)\s*\(\s*["'`](?:https?:)?//""", re.I)
    checked = 0
    for path in FRONTEND.rglob("*"):
        if path.suffix not in {".html", ".js", ".css", ".webmanifest"} or "vendor" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert not pattern.search(text), f"{path} enlaza un recurso externo"
        assert not loaders.search(text), f"{path} carga algo de otro servidor"
        checked += 1
    assert checked >= 5


def test_el_html_no_tiene_scripts_ni_estilos_en_linea():
    """La política CSP los bloquearía; mejor que ni existan."""
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html)
    assert "<style" not in html
    assert not re.search(r"\sstyle\s*=", html)
    assert not re.search(r"\son[a-z]+\s*=", html)


def test_el_codigo_no_usa_lo_que_la_especificacion_prohibe():
    """Sin reconocimiento ni síntesis de voz, sin cookies, sin rastreadores."""
    banned = [
        "SpeechRecognition", "webkitSpeechRecognition", "speechSynthesis", "SpeechSynthesisUtterance",
        "document.cookie", "google-analytics", "googletagmanager", "gtag(", "navigator.sendBeacon",
        "openai", "anthropic", "generativelanguage",
    ]
    for path in list(FRONTEND.rglob("*.js")) + list(FRONTEND.rglob("*.html")):
        if "vendor" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for word in banned:
            assert word.lower() not in text.lower(), f"{path} contiene {word}"


def test_copia_de_seguridad_diaria(settings, client):
    target = backup_now(settings)
    assert target.is_file() and re.fullmatch(r"nepantla-\d{4}-\d{2}-\d{2}\.db", target.name)
    copy = sqlite3.connect(target)
    tables = {row[0] for row in copy.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    copy.close()
    assert {"packs", "phrases", "recordings"} <= tables


def test_solo_se_guardan_las_ultimas_copias(settings, client):
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    for day in range(1, 21):
        (settings.backup_dir / f"nepantla-2026-01-{day:02d}.db").write_bytes(b"x")
    prune(settings)
    names = sorted(path.name for path in settings.backup_dir.glob("*.db"))
    assert len(names) == settings.backup_keep == 14
    assert names[0] == "nepantla-2026-01-07.db"


def test_el_registro_de_accesos_esta_apagado(client):
    import logging

    assert logging.getLogger("uvicorn.access").disabled is True


def test_health(client):
    data = client.get("/api/health").json()
    assert data["ok"] is True and data["dev_mode"] is False and data["studio"] is True


def test_los_archivos_grandes_viajan_comprimidos(client):
    """Carga inicial ligera en redes lentas: CSS, JS y JSON salen con gzip."""
    for path in ("/css/app.css", "/app.js", "/data/phrases.es.json", "/icons/pictos.svg"):
        response = client.get(path, headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip", path
        assert response.headers["content-security-policy"]


def test_el_cascaron_de_la_app_es_pequeno():
    """Objetivo de la especificación: carga inicial rápida en 3G."""
    import gzip

    total = 0
    for path in FRONTEND.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".js", ".css", ".json", ".svg", ".webmanifest"}:
            total += len(gzip.compress(path.read_bytes()))
    assert total < 120 * 1024, f"El cascarón comprimido pesa {total / 1024:.0f} KB"
