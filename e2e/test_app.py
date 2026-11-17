"""La app de consulta, de punta a punta, en un teléfono chico.

Cubre lo que pide la especificación para el frontend: reproducción de audio,
modo avión completo, resumen correcto, "Pedir intérprete" en todas las
pantallas, doble revisión, emergencia de un toque y cero datos del paciente.
"""
from __future__ import annotations

import json

import pytest

A = "prueba-a-001"
B = "prueba-b-001"

CONSULT_SCREENS = [
    "#/", "#/variante", "#/escenarios", "#/escenario/urgencias", "#/frase/urgencias/1", "#/resumen",
    "#/interprete", "#/tarjeta", "#/tarjeta/ver", "#/paquetes", f"#/paquete/{A}", "#/ajustes",
    "#/como-funciona", "#/privacidad", "#/acerca",
]


def answer(phone, selector: str, next_hash: str) -> None:
    phone.page.locator(selector).click()
    phone.wait_hash(next_hash)


def test_se_puede_instalar(phone):
    page = phone.open()
    manifest = page.evaluate("fetch(document.querySelector('link[rel=manifest]').href).then(r => r.json())")
    assert manifest["display"] == "standalone" and manifest["name"] == "Nepantla"
    for icon in manifest["icons"]:
        status = page.evaluate("(src) => fetch(src).then(r => r.status)", icon["src"])
        assert status == 200
    phone.wait_until(
        lambda: page.evaluate("navigator.serviceWorker.getRegistration().then(r => Boolean(r && r.active))"),
        message="el service worker no se activó",
    )
    assert page.evaluate("document.documentElement.lang") == "es-MX"


def test_modo_avion_completo(phone):
    """Prueba obligatoria: con el paquete guardado, TODO funciona sin red."""
    page = phone.open()
    phone.save_pack(A)
    phone.wait_until(
        lambda: page.evaluate("navigator.serviceWorker.getRegistration().then(r => Boolean(r && r.active))"),
        message="el service worker no se activó",
    )
    phone.go("#/")
    page.reload()  # ahora el service worker controla la página
    page.wait_for_selector(".inicio")

    page.wait_for_load_state("networkidle")  # que no quede ninguna petición a medias
    phone.context.set_offline(True)
    blocked: list[str] = []
    page.on("requestfailed", lambda request: blocked.append(request.url))
    page.reload()
    page.wait_for_selector(".inicio")
    page.wait_for_selector(".cinta.sin-red")

    # Elegir variante por audio: suena el saludo y se elige.
    phone.go("#/variante")
    page.locator(f'li[data-pack="{A}"] .redondo').click()
    phone.wait_until(phone.is_playing, message="el saludo no sonó sin internet")
    page.locator(f'li[data-pack="{A}"] .elegir').click()
    phone.wait_hash("#/escenarios")

    # Recorre todas las pantallas de la consulta sin conexión.
    for screen in CONSULT_SCREENS:
        phone.go(screen) if phone.hash() != screen else None
        page.wait_for_selector("#contenido > *")
        assert "no se pudo abrir" not in page.inner_text("#contenido")

    # Una frase completa: audio, respuesta y resumen.
    phone.go("#/frase/urgencias/1")
    page.locator(".btn-audio").click()
    phone.wait_until(phone.is_playing, message="la frase no sonó sin internet")
    answer(phone, '.sino .opcion[data-valor="si"]', "#/frase/urgencias/2")
    phone.go("#/resumen")
    assert "¿Le falta el aire?" in page.inner_text(".resumen")

    # Los pictogramas se ven (el sprite quedó guardado).
    assert page.locator("svg.sprite symbol").count() > 100
    assert blocked == [], f"La app intentó usar la red en modo avión: {blocked}"
    phone.context.set_offline(False)


def test_resumen_correcto(phone):
    page = phone.open()
    phone.save_pack(A)
    phone.choose_variant(A)
    phone.go("#/frase/urgencias/1")

    answer(phone, '.sino .opcion[data-valor="si"]', "#/frase/urgencias/2")
    answer(phone, '.sino .opcion[data-valor="no"]', "#/frase/urgencias/3")
    answer(phone, '.sino .opcion[data-valor="nose"]', "#/frase/urgencias/4")
    page.locator('.opciones .opcion[data-valor="sintoma-dolor"]').click()
    page.locator('.opciones .opcion[data-valor="sintoma-fiebre"]').click()
    answer(phone, 'button:has-text("Listo")', "#/frase/urgencias/5")
    page.locator('[data-zona="f-pecho"]').click()
    page.locator('[data-lado="espalda"]').click()
    page.locator('[data-zona="e-espalda-baja"]').click()
    answer(phone, 'button:has-text("Listo")', "#/frase/urgencias/6")
    answer(phone, '.dolor .opcion[data-valor="7"]', "#/frase/urgencias/7")
    answer(phone, '.duracion .opcion[data-valor="dias"]', "#/frase/urgencias/8")
    page.locator(".entendio .opcion.no").click()  # "No entendí": la frase se repite sola
    phone.wait_until(phone.is_playing, message="«No entendí» no repitió el audio")

    phone.go("#/resumen")
    lines = [line.strip() for line in page.inner_text(".resumen").splitlines() if line.strip()]
    assert lines == [
        "¿Le falta el aire?", "Sí",
        "¿Le duele el pecho?", "No",
        "¿Tiene sangrado?", "No sabe",
        "¿Qué le pasa?", "Dolor, Fiebre",
        "¿Dónde le duele?", "Pecho, Espalda baja (cintura)",
        "¿Cuánto le duele?", "7 de 10",
        "¿Desde cuándo se siente mal?", "Hace días",
        "¿Se desmayó?", "Sin respuesta", "Marcó «No entendí». Conviene confirmar con intérprete.",
    ]
    body = page.inner_text("#contenido")
    assert "Comunicación asistida, no es diagnóstico." in body
    assert "AUDIO DE PRUEBA" in body

    # Terminar la consulta borra todo.
    page.locator('button:has-text("Terminar consulta")').click()
    page.locator('dialog button:has-text("Terminar y borrar")').click()
    phone.wait_hash("#/")
    phone.go("#/resumen")
    assert "Todavía no hay respuestas" in page.inner_text("#contenido")


def test_pedir_interprete_esta_en_todas_las_pantallas(phone):
    page = phone.open()
    phone.save_pack(A)
    phone.choose_variant(A)
    for screen in CONSULT_SCREENS:
        phone.go(screen) if phone.hash() != screen else None
        link = page.locator('#barra a[href="#/interprete"]')
        assert link.is_visible(), f"Falta «Pedir intérprete» en {screen}"
        assert page.locator('#barra a[href="#/emergencia"]').is_visible(), f"Falta «Emergencia» en {screen}"
    # También en modo paciente (solo el dibujo, con nombre para lectores de pantalla).
    phone.go("#/frase/urgencias/1")
    page.locator('button:has-text("Modo paciente")').click()
    link = page.locator('#barra a[href="#/interprete"]')
    assert link.is_visible() and "Pedir intérprete" in link.inner_text()
    link.click()
    phone.wait_hash("#/interprete")
    assert "Se solicita intérprete de" in page.inner_text(".pide")


def test_modo_paciente_botones_grandes_y_sin_texto_obligatorio(phone):
    page = phone.open()
    phone.save_pack(A)
    phone.choose_variant(A)
    for position in (1, 4, 6, 7):  # sí/no, pictogramas, dolor, duración
        phone.go(f"#/frase/urgencias/{position}")
        if not page.locator("#app.modo-paciente").count():
            page.locator('button:has-text("Modo paciente")').click()
        assert not page.locator(".frase-texto").is_visible()  # el español se oculta
        boxes = page.locator(".zona-paciente button:visible, #barra a:visible").evaluate_all(
            "nodes => nodes.map(n => { const r = n.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), n.getAttribute('aria-label') || n.innerText]; })"
        )
        assert boxes, "no hay botones para el paciente"
        for width, height, name in boxes:
            assert width >= 56 and height >= 56, f"Botón chico en la frase {position}: {name!r} mide {width}x{height}"
            assert name and name.strip(), "Hay un botón sin nombre accesible"
    page.locator(".volver-personal").click()
    assert page.locator(".frase-texto").is_visible()


def test_solo_suenan_frases_con_doble_revision(phone):
    """El paquete B trae urg-016 y urg-017 con UN solo revisor: no existen para la app."""
    page = phone.open()
    phone.save_pack(B)
    stored = phone.stored()
    assert f"{B}/urg-001" in stored["audio"]
    assert f"{B}/urg-016" not in stored["audio"] and f"{B}/urg-017" not in stored["audio"]

    phone.choose_variant(B)
    phone.go("#/frase/urgencias/16")
    assert page.locator(".btn-audio").is_disabled()
    assert "sin audio" in page.inner_text(".frase-meta")
    phone.go("#/frase/urgencias/1")
    assert page.locator(".btn-audio").is_enabled()
    # A la variante B le faltan escenarios enteros: la app lo dice y ofrece intérprete.
    phone.go("#/escenario/nino")
    assert "Pida intérprete" in page.inner_text("#contenido")


def test_emergencia_de_un_toque(phone):
    page = phone.open()
    phone.save_pack(A)
    phone.go("#/")
    page.locator('#barra a[href="#/emergencia"]').click()
    phone.wait_hash("#/frase/emergencia/1")  # con un solo paquete no pregunta nada más
    asked = []
    for position in range(1, 6):
        asked.append(page.inner_text(".frase-texto"))
        target = f"#/frase/emergencia/{position + 1}" if position < 5 else "#/resumen"
        answer(phone, '.sino .opcion[data-valor="no"]', target)
    assert asked == [
        "¿Le falta el aire?", "¿Le duele el pecho?", "¿Tiene sangrado?",
        "¿Es alérgico a alguna medicina?", "¿Está embarazada?",
    ]
    assert page.locator(".resumen li").count() == 5


def usage_on_server(server) -> dict:
    rows = server.http.get("/api/studio/admin/overview", headers=server.admin()).json()["usage"]
    for row in rows:
        assert set(row) == {"day", "pack_id", "event", "n"} and len(row["day"]) == 10
    return {(row["pack_id"], row["event"]): row["n"] for row in rows}


def test_no_se_guarda_nada_del_paciente(phone, server):
    before = usage_on_server(server)
    page = phone.open()
    phone.save_pack(A)
    phone.choose_variant(A)
    phone.go("#/escenario/urgencias")
    phone.go("#/frase/urgencias/6")
    answer(phone, '.dolor .opcion[data-valor="9"]', "#/frase/urgencias/7")
    phone.go("#/interprete")
    phone.go("#/resumen")

    stored = phone.stored()
    dump = json.dumps(stored, ensure_ascii=False)
    for forbidden in ("9 de 10", '"value"', "answers", "understood", "notUnderstood"):
        assert forbidden not in dump, f"Quedó guardado algo de la consulta: {forbidden}"
    assert set(stored["local"]) <= {"nepantla.demo", "nepantla.contacto"}
    assert stored["session"] == {}
    # Lo único pendiente de enviar son conteos sin identificadores.
    assert stored["usage"], "deberían existir contadores locales"
    for row in stored["usage"]:
        assert set(row) == {"key", "pack_id", "event", "n"}
    events = {row["event"] for row in stored["usage"]}
    assert events == {"pack_downloaded", "scenario_opened", "interpreter_requested", "summary_generated"}

    # Los conteos salen en lote al volver a abrir la app, no en el momento.
    assert usage_on_server(server) == before
    phone.go("#/")
    page.reload()
    page.wait_for_selector(".inicio")
    expected = dict(before)
    for event in events:
        expected[(A, event)] = expected.get((A, event), 0) + 1
    phone.wait_until(lambda: usage_on_server(server) == expected, message="los contadores no llegaron al servidor")
    assert phone.stored()["usage"] == []


def test_tarjeta_de_salida_con_qr(phone):
    page = phone.open()
    phone.save_pack(A)
    phone.choose_variant(A)
    phone.go("#/tarjeta")
    page.locator('.alternar .opcion:has-text("dos veces al día")').click()
    page.locator('.alternar .opcion:has-text("si le falta el aire")').click()
    for _ in range(3):
        page.locator('[aria-label="Un día más"]').click()
    page.locator('a:has-text("Ver tarjeta")').click()
    phone.wait_hash("#/tarjeta/ver")
    card = page.inner_text(".tarjeta")
    assert "dos veces al día" in card and "si le falta el aire" in card and "días" in card
    assert page.locator(".tarjeta .qr svg path").count() == 1

    # El QR lleva solo la lista de indicaciones (después del "#"), nada más.
    expected = f"#/t/{A}/med-008.ala-001/3"
    zxingcpp = pytest.importorskip("zxingcpp", reason="sin lector de QR: `pip install zxing-cpp`")
    from PIL import Image
    import io

    png = page.locator(".tarjeta .qr").screenshot(scale="device")
    decoded = zxingcpp.read_barcodes(Image.open(io.BytesIO(png)))
    assert decoded and decoded[0].text == f"{phone.base}/{expected}"

    # Abrirlo en el teléfono de la familia muestra la misma tarjeta, con audio.
    phone.go(expected)
    text = page.inner_text(".tarjeta")
    assert "dos veces al día" in text and "si le falta el aire" in text
    page.locator(".tarjeta .redondo").first.click()
    phone.wait_until(phone.is_playing, message="la indicación de la tarjeta no sonó")


def test_reportar_audio_incorrecto(phone, server):
    page = phone.open()
    phone.save_pack(A)
    phone.go(f"#/paquete/{A}")
    text = page.inner_text("#contenido")
    for label in ("Variante", "Comunidad", "Quién grabó", "Quién revisó", "Fecha", "Versión", "Licencia"):
        assert label in text
    page.locator('button:has-text("Reportar audio incorrecto")').click()
    page.locator("#reporte-frase").select_option("urg-002")
    page.locator('input[name="motivo"][value="wrong_variant"]').check()
    assert page.locator("dialog textarea, dialog input[type=text]").count() == 0  # sin texto libre
    page.locator('dialog button:has-text("Enviar reporte")').click()
    page.wait_for_selector("text=El reporte ya está con los guardianes")


AUDIT = """() => {
    const visible = (n) => {
        const r = n.getBoundingClientRect();
        const s = getComputedStyle(n);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const name = (n) => (n.getAttribute('aria-label') || n.innerText || '').trim();
    const controls = [...document.querySelectorAll('a[href], button, [role=button]')].filter(visible);
    const fields = [...document.querySelectorAll('main input, main select, main textarea')].filter(visible);
    return {
        unnamed: controls.filter((n) => !name(n)).map((n) => n.outerHTML.slice(0, 140)),
        unlabeled: fields.filter((n) => !(n.labels && n.labels.length) && !n.getAttribute('aria-label')).map((n) => n.outerHTML.slice(0, 140)),
        headings: document.querySelectorAll('main h1').length,
        mains: document.querySelectorAll('main').length,
        looseIcons: [...document.querySelectorAll('svg.ic')].filter((s) => s.getAttribute('aria-hidden') !== 'true').length,
        title: document.title,
    };
}"""


def test_accesibilidad_basica_en_todas_las_pantallas(phone):
    """Lo que un lector de pantalla necesita: nombres, títulos y etiquetas."""
    page = phone.open()
    phone.save_pack(A)
    phone.choose_variant(A)
    titles = set()
    for screen in CONSULT_SCREENS + ["#/frase/urgencias/4", "#/frase/urgencias/5", "#/frase/urgencias/6", "#/retirar"]:
        phone.go(screen) if phone.hash() != screen else None
        page.wait_for_selector("#contenido h1", state="attached")
        report = page.evaluate(AUDIT)
        assert report["unnamed"] == [], f"{screen}: botones o enlaces sin nombre: {report['unnamed']}"
        assert report["unlabeled"] == [], f"{screen}: campos sin etiqueta: {report['unlabeled']}"
        assert report["headings"] == 1, f"{screen}: debe haber un solo título principal"
        assert report["mains"] == 1
        assert report["looseIcons"] == 0, f"{screen}: hay pictogramas decorativos sin ocultar al lector"
        titles.add(report["title"])
    assert len(titles) >= 12  # cada pantalla cambia el título de la pestaña
    # El mapa del cuerpo se puede usar con teclado.
    phone.go("#/frase/urgencias/5")
    zone = page.locator('[data-zona="f-cabeza"]')
    zone.focus()
    page.keyboard.press("Enter")
    assert zone.get_attribute("aria-pressed") == "true" and zone.get_attribute("aria-label") == "Cabeza"


def test_primera_carga_en_red_3g(browser, server):
    """Objetivo de la especificación: carga inicial rápida en 3G.

    Se simula una red 3G (1.6 Mbps de bajada, 300 ms de latencia) con el
    teléfono recién sacado de la caja: sin caché y sin service worker.
    """
    import time

    from .conftest import Phone

    device = Phone(browser, server.base)
    page = device.page
    transferred = {"bytes": 0, "requests": 0}

    def count(response) -> None:
        transferred["requests"] += 1
        transferred["bytes"] += int(response.headers.get("content-length", 0) or 0)

    page.on("response", count)
    session = device.context.new_cdp_session(page)
    session.send("Network.enable")
    session.send(
        "Network.emulateNetworkConditions",
        {"offline": False, "latency": 300, "downloadThroughput": 1.6 * 1024 * 1024 / 8, "uploadThroughput": 750 * 1024 / 8},
    )
    started = time.time()
    page.goto(f"{server.base}/")
    page.wait_for_selector(".inicio .marca")
    seconds = time.time() - started
    print(f"\nPrimera pantalla en 3G simulado: {seconds:.1f} s, {transferred['requests']} peticiones")
    assert seconds < 5, f"La primera pantalla tardó {seconds:.1f} s en 3G"
    assert device.problems == []
    device.close()
