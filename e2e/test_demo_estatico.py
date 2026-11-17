"""La demostración estática servida como simples archivos, sin servidor."""
from __future__ import annotations

import subprocess
import sys
import time

import httpx
import pytest

from .conftest import ROOT, Phone, free_port

A = "prueba-a-001"


@pytest.fixture(scope="module")
def static_site(tmp_path_factory):
    dest = tmp_path_factory.mktemp("demo-estatico") / "dist"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_static_demo.py"), str(dest)], cwd=ROOT, check=True, capture_output=True, timeout=120)
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(dest)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(f"{base}/index.html", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        yield base
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_la_demostracion_estatica_funciona_sin_servidor(browser, static_site):
    phone = Phone(browser, static_site)
    page = phone.page
    sent: list[str] = []
    page.on("request", lambda request: sent.append(f"{request.method} {request.url}") if request.method != "GET" else None)

    phone.open()
    page.wait_for_selector(".inicio")
    phone.save_pack(A)
    phone.choose_variant(A)
    page.wait_for_selector(".mosaico")
    assert "AUDIO DE PRUEBA" in page.inner_text("#cintas")

    phone.go("#/escenario/urgencias")
    phone.go("#/frase/urgencias/1")
    page.locator(".btn-audio").click()
    phone.wait_until(phone.is_playing, message="el audio no sonó en la demostración estática")
    page.locator('.sino .opcion[data-valor="si"]').click()
    phone.wait_hash("#/frase/urgencias/2")
    phone.go("#/interprete")
    phone.go("#/resumen")
    assert "¿Le falta el aire?" in page.inner_text(".resumen")

    # El estudio necesita servidor: la demostración lo dice en lugar de fallar.
    phone.go("#/estudio")
    assert "Esto es una demostración" in page.inner_text("#contenido")

    # Reportar no envía nada, y la app lo dice.
    phone.go(f"#/paquete/{A}")
    page.locator('button:has-text("Reportar audio incorrecto")').click()
    page.locator('dialog button:has-text("Enviar reporte")').click()
    page.wait_for_selector("text=aquí los reportes no se envían")

    # Ni contadores ni reportes: de este teléfono no salió ningún dato.
    page.reload()
    page.wait_for_selector("#contenido .pagina")
    page.wait_for_timeout(600)
    assert sent == [], f"La demostración intentó enviar datos: {sent}"
    assert phone.stored()["usage"] == [] and phone.stored()["reports"] == []
    assert phone.problems == []
    phone.close()
