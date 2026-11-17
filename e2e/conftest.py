"""Pruebas de punta a punta: la app de verdad en un navegador de verdad.

Cómo correrlas:

    pip install -r requirements-dev.txt
    playwright install chromium      # solo la primera vez
    pytest e2e

Cada módulo levanta su propio servidor en modo demostración, con una base
SQLite nueva en una carpeta temporal y los paquetes de AUDIO DE PRUEBA.

Nota: la política CSP de Nepantla prohíbe `eval`. Por eso aquí no se usa
`page.wait_for_function` (que evalúa texto dentro de la página) sino pequeñas
esperas hechas desde Python.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

playwright_api = pytest.importorskip("playwright.sync_api", reason="hace falta `pip install playwright`")

ROOT = Path(__file__).resolve().parent.parent
ADMIN = "token-admin-solo-para-pruebas-e2e-1234567890"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    def __init__(self, base: str, data_dir: Path) -> None:
        self.base = base
        self.data_dir = data_dir
        self.http = httpx.Client(base_url=base, timeout=20)

    def admin(self) -> dict:
        return {"Authorization": f"Bearer {ADMIN}"}

    @staticmethod
    def auth(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("nepantla-e2e")
    port = free_port()
    env = {
        **os.environ,
        "NEPANTLA_DEV_MODE": "1",
        "NEPANTLA_DATA_DIR": str(data_dir),
        "NEPANTLA_PACKS_DIR": str(ROOT / "packs"),
        "NEPANTLA_ADMIN_TOKEN": ADMIN,
        "NEPANTLA_BACKUPS": "0",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log", "--log-level", "warning"],
        cwd=ROOT,
        env=env,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(f"{base}/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            raise RuntimeError("El servidor de pruebas no arrancó.")
        yield Server(base, data_dir)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture(scope="session")
def browser():
    with playwright_api.sync_playwright() as p:
        args = [
            "--no-sandbox",
            "--autoplay-policy=no-user-gesture-required",
            # Micrófono falso para probar el estudio sin hardware ni permisos.
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
        ]
        try:
            instance = p.chromium.launch(args=args)
        except Exception:
            if shutil.which("google-chrome") is None and shutil.which("chrome") is None:
                pytest.skip("No hay Chromium: corre `playwright install chromium`.")
            instance = p.chromium.launch(channel="chrome", args=args)
        yield instance
        instance.close()


class Phone:
    """Un teléfono chico (360 x 740) con su propio almacenamiento."""

    def __init__(self, browser, base: str) -> None:
        self.base = base
        self.context = browser.new_context(
            viewport={"width": 360, "height": 740},
            device_scale_factor=2,
            locale="es-MX",
            permissions=["microphone"],
            service_workers="allow",
        )
        self.problems: list[str] = []
        self.page = self.new_page()

    def new_page(self):
        page = self.context.new_page()
        page.on("pageerror", lambda error: self.problems.append(f"error de página: {error}"))
        page.on(
            "console",
            lambda message: self.problems.append(f"consola: {message.text}") if message.type == "error" else None,
        )
        return page

    # --- navegación ---
    def open(self, hash_: str = "#/", page=None):
        page = page or self.page
        page.goto(f"{self.base}/{hash_}")
        page.wait_for_selector("#contenido > *")
        return page

    def go(self, hash_: str, page=None):
        """Cambia de pantalla sin recargar (como tocar un enlace)."""
        page = page or self.page
        page.evaluate("(hash) => { location.hash = hash; }", hash_)
        self.wait_hash(hash_, page=page)
        page.wait_for_timeout(120)

    def hash(self, page=None) -> str:
        return (page or self.page).evaluate("location.hash")

    def wait_hash(self, expected: str, page=None, timeout: float = 6.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.hash(page) == expected:
                return
            (page or self.page).wait_for_timeout(50)
        raise AssertionError(f"Se esperaba {expected} y la app está en {self.hash(page)}")

    def wait_until(self, check, timeout: float = 8.0, message: str = "la condición no se cumplió") -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if check():
                return
            self.page.wait_for_timeout(80)
        raise AssertionError(message)

    # --- acciones frecuentes ---
    def save_pack(self, pack_id: str) -> None:
        self.go("#/paquetes")
        card = self.page.locator(f'li[data-pack="{pack_id}"]')
        card.locator('button:has-text("Guardar para usar sin internet")').click()
        card.locator(".chip.listo").wait_for(timeout=30000)

    def choose_variant(self, pack_id: str) -> None:
        self.go("#/variante")
        self.page.locator(f'li[data-pack="{pack_id}"] .elegir').click()
        self.wait_hash("#/escenarios")

    def is_playing(self) -> bool:
        return bool(self.page.evaluate("window.nepantla.audio.isPlaying()"))

    def stored(self) -> dict:
        """Todo lo que la app tiene guardado en este teléfono."""
        return self.page.evaluate(
            """async () => {
                const open = () => new Promise((resolve, reject) => {
                    const request = indexedDB.open('nepantla');
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
                const all = (db, name) => new Promise((resolve) => {
                    const request = db.transaction(name).objectStore(name).getAll();
                    request.onsuccess = () => resolve(request.result);
                });
                const db = await open();
                const out = { local: { ...localStorage }, session: { ...sessionStorage } };
                for (const name of ['packs', 'usage', 'reports']) out[name] = await all(db, name);
                out.audio = (await all(db, 'audio')).map((row) => row.key);
                db.close();
                return out;
            }"""
        )

    def close(self) -> None:
        self.context.close()


@pytest.fixture
def phone(browser, server):
    device = Phone(browser, server.base)
    yield device
    problems = list(device.problems)
    device.close()
    assert problems == [], "La app escribió errores en la consola: " + " | ".join(problems)
