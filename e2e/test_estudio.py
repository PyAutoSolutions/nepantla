"""El estudio de grabación de punta a punta, con un micrófono falso.

Una sola historia larga, porque así es como se usa:

  coordinación crea el paquete y los enlaces
  -> la hablante acepta el consentimiento y graba
  -> dos personas revisan (una es intérprete)
  -> la guardiana publica el paquete
  -> una clínica lo guarda y lo usa
  -> la hablante retira su voz: se borra del servidor y del teléfono
  -> la guardiana retira el paquete: desaparece del teléfono
"""
from __future__ import annotations

from .conftest import ADMIN, Phone

PACK = "ejemplo-estudio-001"


def make_link(page, role: str, alias: str, interpreter: bool = False) -> str:
    card = page.locator("li.paquete", has_text="Variante del estudio")
    token = card.locator(".token").first
    previous = token.inner_text().strip() if token.count() else ""
    card.locator('select[name="rol"]').select_option(role)
    card.locator('input[name="alias"]').fill(alias)
    box = card.locator('input[name="interprete"]')
    box.check() if interpreter else box.uncheck()
    card.locator('button:has-text("Crear enlace")').click()
    for _ in range(100):  # espera a que aparezca el enlace NUEVO, no el anterior
        link = token.inner_text().strip() if token.count() else ""
        if link and link != previous:
            assert "#/estudio/" in link
            return link
        page.wait_for_timeout(50)
    raise AssertionError("No apareció el enlace nuevo.")


def review_everything(browser, server, link: str, expected: int) -> None:
    reviewer = Phone(browser, server.base)
    page = reviewer.page
    page.goto(link)
    page.wait_for_selector('button:has-text("Aprobar")')
    assert reviewer.hash() == "#/estudio"  # el permiso ya no está en la barra de direcciones
    page.locator('button:has-text("Escuchar la grabación")').click()
    reviewer.wait_until(reviewer.is_playing, message="el revisor no pudo escuchar la grabación")
    for _ in range(expected):
        page.locator('button:has-text("Aprobar")').click()
        page.wait_for_timeout(400)
    page.wait_for_selector("text=No hay grabaciones esperando")
    assert reviewer.problems == []
    reviewer.close()


def test_del_microfono_a_la_clinica_y_de_regreso(browser, server, phone):
    # --- Coordinación: paquete y enlaces personales ---
    admin = Phone(browser, server.base)
    page = admin.open("#/admin")
    page.fill("#admin-token", ADMIN)
    page.click('button:has-text("Entrar")')
    page.fill("#p-id", PACK)
    page.fill("#p-lengua", "Lengua de ejemplo")
    page.fill("#p-variante", "Variante del estudio")
    page.fill("#p-comunidad", "Comunidad de ejemplo")
    page.fill("#p-licencia", "Licencia de ejemplo")
    page.fill("#p-guardianes", "Guardiana Uno")
    page.click('button:has-text("Crear paquete")')
    page.wait_for_selector('li.paquete:has-text("Variante del estudio")')
    links = {
        "speaker": make_link(page, "speaker", "Hablante Uno"),
        "interpreter": make_link(page, "reviewer", "Intérprete Ana", interpreter=True),
        "nurse": make_link(page, "reviewer", "Enfermera Luz"),
        "guardian": make_link(page, "guardian", "Guardiana Uno"),
    }
    assert admin.stored()["session"] == {}  # el token de administración no se guarda
    assert admin.problems == []
    admin.close()

    # --- Hablante: consentimiento, código de retiro y dos grabaciones ---
    speaker = Phone(browser, server.base)
    page = speaker.page
    page.goto(links["speaker"])
    page.wait_for_selector("#credito")
    assert speaker.hash() == "#/estudio"
    assert page.locator(".grabadora").count() == 0  # no se puede grabar sin consentir
    for key in ("understands_use", "understands_withdrawal", "accepts_license", "is_adult"):
        page.check(f"#c-{key}")
    page.fill("#credito", "Hablante Uno")
    page.click('button:has-text("Acepto y quiero grabar")')
    page.wait_for_selector(".token")
    withdrawal = page.locator(".token").first.inner_text().strip()
    assert len(withdrawal) >= 40
    page.click('button:has-text("Ya lo guardé")')
    page.wait_for_selector(".grabadora")
    for _ in range(2):  # el saludo y la primera frase
        page.click(".grabadora .btn-audio")
        page.wait_for_timeout(1200)
        page.click(".grabadora .btn-audio")
        page.click('button:has-text("Guardar y seguir")')
        page.wait_for_selector("text=Grabación guardada")
        page.wait_for_timeout(300)
    assert "2 de" in page.inner_text("#contenido")
    assert speaker.problems == []
    speaker.close()

    # Con una sola revisión todavía no existe para nadie.
    assert server.http.get(f"/api/packs/{PACK}/manifest.json").json()["phrases"] == []

    # --- Doble revisión: intérprete y enfermera ---
    review_everything(browser, server, links["interpreter"], 2)
    assert server.http.get(f"/api/packs/{PACK}/manifest.json").json()["phrases"] == []
    review_everything(browser, server, links["nurse"], 2)
    manifest = server.http.get(f"/api/packs/{PACK}/manifest.json").json()
    assert [p["id"] for p in manifest["phrases"]] == ["urg-001"] and manifest["greeting"]
    assert manifest["phrases"][0]["reviewed_by"] == ["Intérprete Ana", "Enfermera Luz"]
    assert manifest["status"] == "draft"

    # --- Guardiana: publica ---
    guardian = Phone(browser, server.base)
    page = guardian.page
    page.goto(links["guardian"])
    page.click('button:has-text("Aprobar y publicar")')
    page.click('dialog button:has-text("Publicar")')
    page.wait_for_selector("text=Publicado")
    assert server.http.get(f"/api/packs/{PACK}/manifest.json").json()["status"] == "approved"

    # --- Clínica: guarda el paquete y lo usa ---
    clinic = phone.open()
    phone.save_pack(PACK)
    phone.choose_variant(PACK)
    phone.go("#/frase/urgencias/1")
    clinic.locator(".btn-audio").click()
    phone.wait_until(phone.is_playing, message="la grabación aprobada no sonó en la clínica")
    assert f"{PACK}/urg-001" in phone.stored()["audio"]

    # --- La hablante retira su voz ---
    leaving = Phone(browser, server.base)
    page = leaving.open(f"#/retirar/{withdrawal}")
    page.wait_for_selector("#codigo")
    assert leaving.hash() == "#/retirar" and page.input_value("#codigo") == withdrawal
    page.click('button:has-text("Retirar toda mi voz")')
    page.click('dialog button:has-text("Retirar")')
    page.wait_for_selector("text=Se borraron 2 grabación(es)")
    assert leaving.problems == []
    leaving.close()
    after = server.http.get(f"/api/packs/{PACK}/manifest.json").json()
    assert after["phrases"] == [] and after["greeting"] is None
    assert server.http.get(f"/api/packs/{PACK}/audio/urg-001.opus").status_code == 404
    assert not any((server.data_dir / "audio" / PACK).glob("*.opus"))  # los archivos ya no existen

    # En su siguiente conexión, el teléfono de la clínica borra esos audios.
    phone.go("#/")
    clinic.reload()
    clinic.wait_for_selector(".inicio")
    phone.wait_until(
        lambda: not [key for key in phone.stored()["audio"] if key.startswith(PACK)],
        message="el teléfono conservó una voz retirada",
    )

    # --- La guardiana retira el paquete completo ---
    page = guardian.page
    page.reload()
    page.click('button:has-text("Retirar el paquete completo")')
    page.click('dialog button:has-text("Retirar")')
    page.wait_for_selector("text=Paquete retirado")
    assert guardian.problems == []
    guardian.close()
    listing = server.http.get("/api/packs").json()
    assert PACK in listing["withdrawn"] and PACK not in [p["pack_id"] for p in listing["packs"]]
    assert server.http.get(f"/api/packs/{PACK}/manifest.json").status_code == 410

    clinic.reload()
    clinic.wait_for_selector(".inicio")
    clinic.wait_for_selector("text=retiraron")
    assert PACK not in [record["pack_id"] for record in phone.stored()["packs"]]
