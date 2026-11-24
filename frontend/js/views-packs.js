/* Nepantla: paquetes de lengua, ficha pública, reportes, ajustes y páginas
   de información (cómo funciona, privacidad, acerca de). */

import * as audio from "./audio.js";
import * as core from "./core.js";
import { button, confirmDialog, dataList, h, icon, linkButton, toast } from "./dom.js";
import { ApiError, downloadPack, fetchManifest, sendReport, track } from "./net.js";
import * as store from "./store.js";

const STATUS_ES = { draft: "Borrador (sin aprobar)", approved: "Aprobado por sus guardianes", withdrawn: "Retirado" };

function testNotice() {
  return h(
    "div",
    { class: "aviso" },
    icon("bandera"),
    h("span", null, h("strong", null, "AUDIO DE PRUEBA. "), "No es una lengua real: son tonos generados por computadora para probar la app."),
  );
}

/* ------------------------------------------------- Descargas y paquetes */

export async function viewPacks(app) {
  let offlineNote = null;
  if (app.online) {
    try {
      await app.sync({ quiet: true });
    } catch {
      offlineNote = "No se pudo consultar el servidor. Se muestran solo los paquetes guardados en este teléfono.";
    }
  } else {
    offlineNote = "Sin internet: se muestran solo los paquetes guardados en este teléfono.";
  }

  const total = app.data.phrases.length;
  const local = new Map(app.packs.map((record) => [record.pack_id, record]));
  const remote = new Map((offlineNote ? [] : app.serverPacks || []).map((pack) => [pack.pack_id, pack]));
  const ids = [...new Set([...remote.keys(), ...local.keys()])];

  const cards = ids.map((id) => {
    const record = local.get(id) || null;
    const info = remote.get(id) || (record ? record.manifest : null);
    const title = core.packTitle(info);
    const available = record ? app.playableSet(record) : new Set();
    const pending = record ? core.diffManifest(record.have, record.manifest).missing.length : 0;
    const phraseCount = remote.has(id) ? remote.get(id).phrase_count : [...available].filter((x) => x !== core.GREETING_ID).length;
    const actions = h("div", { class: "fila" });
    const progress = h("progress", { max: 1, value: 0, hidden: true, "aria-label": `Descarga de ${title}` });

    async function save() {
      for (const node of actions.querySelectorAll("button")) node.disabled = true;
      progress.hidden = false;
      try {
        await downloadPack(id, (done, all) => {
          progress.max = Math.max(1, all);
          progress.value = done;
        });
        if (!record) await track(id, "pack_downloaded");
        await app.reloadPacks();
        toast(`${title}: guardado. Ya funciona sin internet.`);
      } catch (error) {
        toast(error instanceof ApiError ? error.message : "No se pudo guardar el paquete. Revise la conexión.");
      }
      app.render();
    }

    async function remove() {
      const ok = await confirmDialog({
        title: "¿Borrar este paquete del teléfono?",
        body: `${title} dejará de funcionar sin internet hasta que lo guarde otra vez.`,
        okLabel: "Borrar",
        danger: true,
      });
      if (!ok) return;
      await store.deletePack(id);
      if (app.activePackId === id) app.activePackId = null;
      await app.reloadPacks();
      app.render();
    }

    if (!record) {
      actions.append(
        button("Guardar para usar sin internet", { iconName: "descargar", cls: "btn btn-chico", disabled: !remote.has(id), onclick: save }),
      );
    } else {
      if (pending && remote.has(id)) {
        actions.append(button(`Actualizar (${pending} audios)`, { iconName: "descargar", cls: "btn btn-chico", onclick: save }));
      }
      actions.append(button("Borrar del teléfono", { iconName: "borrar", cls: "btn btn-linea btn-chico", onclick: remove }));
    }
    actions.append(linkButton("Ficha del paquete", `#/paquete/${id}`, { iconName: "documento", cls: "btn btn-linea btn-chico" }));

    return h(
      "li",
      { class: `paquete ${info.is_test ? "prueba" : ""}`.trim(), dataset: { pack: id } },
      h(
        "div",
        { class: "paquete-cabeza" },
        icon("paquete"),
        h(
          "div",
          null,
          h("h2", null, title),
          h(
            "div",
            { class: "etiquetas fila" },
            info.is_test ? h("span", { class: "chip critica" }, "AUDIO DE PRUEBA") : null,
            record
              ? h("span", { class: "chip listo" }, icon("ok"), "Guardado en este teléfono")
              : h("span", { class: "chip apagado" }, "Sin guardar"),
            record && pending ? h("span", { class: "chip" }, "Hay actualización") : null,
            record && !remote.has(id) && !offlineNote ? h("span", { class: "chip apagado" }, "Ya no está en el servidor") : null,
          ),
        ),
      ),
      dataList([
        ["Comunidad", info.community],
        ["Versión", info.version],
        ["Estado", STATUS_ES[info.status] || info.status],
        ["Frases con audio", `${phraseCount} de ${total}`],
        ["Tamaño", remote.has(id) ? core.formatBytes(remote.get(id).total_bytes) : null],
      ]),
      progress,
      actions,
    );
  });

  const node = h(
    "div",
    { class: "pagina" },
    h("h1", null, "Paquetes de lengua"),
    h(
      "p",
      { class: "menor" },
      "Cada paquete trae las frases grabadas por hablantes de una variante. Solo entran grabaciones aprobadas por dos revisores.",
    ),
    offlineNote ? h("div", { class: "aviso calma" }, icon("sin-red"), h("span", null, offlineNote)) : null,
    cards.length
      ? h("ul", { class: "paquetes" }, cards)
      : h(
          "div",
          { class: "aviso" },
          icon("info"),
          h(
            "span",
            null,
            h("strong", null, "Todavía no hay paquetes publicados. "),
            "Nepantla no trae audios «de fábrica»: cada lengua necesita hablantes que graben, dos revisores y la aprobación de sus guardianes. Mientras tanto, pida intérprete.",
          ),
        ),
    h("p", { class: "menor" }, "¿Grabó para un paquete y quiere quitar su voz? ", h("a", { href: "#/retirar" }, "Retirar mi voz"), "."),
  );
  return { title: "Paquetes de lengua", back: "#/", node };
}

/* ------------------------------------------------------ Ficha del paquete */

/** Quién revisó las frases en español y cuándo, o que sigue pendiente. */
function clinicalReview(data) {
  const people = Array.isArray(data.clinical_reviewers) ? data.clinical_reviewers : [];
  if (data.clinical_review !== "revisada" || people.length === 0) {
    return "Pendiente: todavía no la firma una persona de salud.";
  }
  return people.map((p) => [p.name, p.role ? `(${p.role})` : "", p.date ? `, ${p.date}` : ""].join(" ").replace(" ,", ",").trim()).join("; ");
}

export async function viewPack(app, packId) {
  const record = app.packs.find((p) => p.pack_id === packId) || null;
  let manifest = record ? record.manifest : null;
  if (app.online) {
    try {
      manifest = await fetchManifest(packId);
    } catch (error) {
      if (!manifest) {
        const gone = error.status === 410;
        return {
          title: "Ficha del paquete",
          back: "#/paquetes",
          node: h(
            "div",
            { class: "pagina" },
            h("h1", null, gone ? "Paquete retirado" : "Paquete no encontrado"),
            h(
              "p",
              null,
              gone
                ? "Sus guardianes retiraron este paquete. Ya no se puede descargar ni usar."
                : "No encontramos ese paquete. Puede que no esté publicado o que no haya conexión.",
            ),
          ),
        };
      }
    }
  }
  if (!manifest) return { redirect: "#/paquetes" };

  const entries = [...core.playableEntries(manifest).values()];
  const speakers = core.distinctReviewers(entries.map((e) => e.recorded_by));
  const reviewers = core.distinctReviewers(entries.flatMap((e) => e.reviewed_by));
  const lastDate = entries.map((e) => e.approved_at).filter(Boolean).sort().pop() || "";
  const phraseEntries = core.playableEntries(manifest);
  phraseEntries.delete(core.GREETING_ID);

  const node = h(
    "div",
    { class: "pagina" },
    h("h1", null, core.packTitle(manifest)),
    manifest.is_test ? testNotice() : null,
    dataList([
      ["Lengua", manifest.language],
      ["Variante", manifest.variant],
      ["Comunidad", manifest.community],
      ["Región", manifest.region || (manifest.is_test ? "" : "Sin registrar")],
      ["Quién grabó", speakers.join(", ") || "Nadie todavía"],
      ["Quién revisó", reviewers.join(", ") || "Nadie todavía"],
      ["Fecha", lastDate],
      ["Versión", manifest.version],
      ["Estado", STATUS_ES[manifest.status] || manifest.status],
      ["Licencia", manifest.license || "Sin definir"],
      ["Revisión clínica de las frases", clinicalReview(app.data)],
      ["Etiqueta comunitaria", manifest.community_label],
      ["Guardianes", (manifest.guardians || []).join(", ") || "Sin registrar"],
      ["Frases con audio", `${phraseEntries.size} de ${app.data.phrases.length}`],
      ["Código", manifest.pack_id],
    ]),
    h(
      "div",
      { class: "aviso calma" },
      icon("escudo"),
      h(
        "span",
        null,
        "Las voces son de quienes las grabaron y de su comunidad. Los guardianes pueden retirar el paquete, y cada hablante puede retirar su voz cuando quiera.",
      ),
    ),
    phraseEntries.size
      ? button("Reportar audio incorrecto", {
          iconName: "bandera",
          cls: "btn btn-ancho",
          onclick: () => reportDialog(app, manifest, record, phraseEntries),
        })
      : null,
    linkButton("Retirar mi voz", "#/retirar", { iconName: "escudo", cls: "btn btn-linea btn-chico btn-ancho" }),
  );
  return { title: "Ficha del paquete", back: "#/paquetes", node };
}

function reportDialog(app, manifest, record, phraseEntries) {
  const dialog = h("dialog", { "aria-labelledby": "reporte-titulo" });
  const select = h("select", { id: "reporte-frase", required: true });
  for (const scenario of app.data.scenarios) {
    const group = h("optgroup", { label: scenario.title });
    for (const phrase of core.flowPhrases(app.data, scenario.id)) {
      if (phraseEntries.has(phrase.id)) group.append(h("option", { value: phrase.id }, phrase.es_text));
    }
    if (group.children.length) select.append(group);
  }
  const listen = button("Escuchar esta frase", {
    iconName: "altavoz",
    cls: "btn btn-linea btn-chico",
    disabled: !record,
    onclick: () => record && audio.playPhrase(record.pack_id, select.value),
  });
  const reasons = core.REPORT_REASONS.map((reason, index) =>
    h(
      "label",
      { class: "casilla" },
      h("input", { type: "radio", name: "motivo", value: reason.id, required: true, checked: index === 0 }),
      h("span", null, reason.es),
    ),
  );
  const close = () => {
    audio.stop();
    dialog.close();
    dialog.remove();
  };
  const form = h(
    "form",
    {
      method: "dialog",
      onsubmit: async (event) => {
        event.preventDefault();
        const reason = form.querySelector('input[name="motivo"]:checked').value;
        const report = { pack_id: manifest.pack_id, phrase_id: select.value, reason };
        close();
        try {
          const how = await sendReport(report);
          toast(
            how === "sent"
              ? "Gracias. El reporte ya está con los guardianes del paquete."
              : how === "demo"
                ? "Esto es una demostración: aquí los reportes no se envían."
                : "Sin conexión: el reporte se enviará cuando vuelva el internet.",
          );
        } catch (error) {
          toast(error instanceof ApiError ? error.message : "No se pudo enviar el reporte.");
        }
      },
    },
    h("h2", { id: "reporte-titulo" }, "Reportar audio incorrecto"),
    h("div", { class: "campo" }, h("label", { for: "reporte-frase" }, "¿Cuál frase?"), select),
    listen,
    h("fieldset", null, h("legend", null, "¿Qué pasa con el audio?"), reasons),
    h(
      "p",
      { class: "menor" },
      "El reporte solo lleva el paquete, la frase y el motivo. No lleva texto libre para que nadie escriba datos de pacientes por error.",
    ),
    h(
      "div",
      { class: "fila" },
      button("Cancelar", { cls: "btn btn-linea btn-chico", onclick: close }),
      h("button", { class: "btn btn-chico", type: "submit" }, "Enviar reporte"),
    ),
  );
  dialog.append(form);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    close();
  });
  document.body.append(dialog);
  dialog.showModal();
}

/* ------------------------------------------------------------- Ajustes */

export async function viewSettings(app) {
  const contact = store.settings.get("contacto", { nombre: "", telefono: "", nota: "" }) || {};
  const field = (id, label, value, attrs = {}) =>
    h("div", { class: "campo" }, h("label", { for: id }, label), h("input", { id, name: id, value: value || "", autocomplete: "off", ...attrs }));
  const form = h(
    "form",
    {
      onsubmit: (event) => {
        event.preventDefault();
        const data = new FormData(form);
        const clean = (key, max) => String(data.get(key) || "").trim().slice(0, max);
        store.settings.set("contacto", { nombre: clean("contacto-nombre", 80), telefono: clean("contacto-telefono", 40), nota: clean("contacto-nota", 160) });
        toast("Contacto guardado en este teléfono.");
      },
    },
    h(
      "fieldset",
      null,
      h("legend", null, "Contacto para pedir intérprete"),
      h("p", { class: "menor" }, "Lo escribe la clínica una sola vez. Aparece en la pantalla «Pedir intérprete». Se guarda solo en este teléfono."),
      field("contacto-nombre", "Persona o servicio", contact.nombre, { maxlength: 80 }),
      field("contacto-telefono", "Teléfono o extensión", contact.telefono, { maxlength: 40, inputmode: "tel" }),
      field("contacto-nota", "Horario o indicaciones", contact.nota, { maxlength: 160 }),
      h("button", { class: "btn btn-chico", type: "submit" }, "Guardar contacto"),
    ),
  );

  const estimate = await store.storageEstimate();
  const node = h(
    "div",
    { class: "pagina" },
    h("h1", null, "Ajustes de esta clínica"),
    form,
    h(
      "fieldset",
      null,
      h("legend", null, "Este teléfono"),
      dataList([
        ["Paquetes guardados", String(app.packs.length)],
        ["Espacio usado", estimate && estimate.usage ? core.formatBytes(estimate.usage) : null],
        ["Versión de la app", app.build || "sin conexión"],
        ["Modo", app.devMode ? "Demostración (se ven paquetes de prueba)" : "Normal"],
      ]),
      button("Borrar todo lo guardado en este teléfono", {
        iconName: "borrar",
        cls: "btn btn-rojo btn-chico",
        onclick: async () => {
          const ok = await confirmDialog({
            title: "¿Borrar todo?",
            body: "Se borran los paquetes de lengua, el contacto del intérprete y los contadores pendientes. No se puede deshacer.",
            okLabel: "Borrar todo",
            danger: true,
          });
          if (!ok) return;
          await store.wipeAll();
          app.newConsultation({ silent: true });
          await app.reloadPacks();
          app.go("#/");
          toast("Listo: este teléfono quedó sin datos de Nepantla.");
        },
      }),
    ),
    h("ul", { class: "enlaces" }, h("li", null, h("a", { href: "#/admin" }, icon("ajustes"), h("span", null, "Coordinación del estudio de grabación"), icon("adelante")))),
  );
  return { title: "Ajustes", back: "#/", node };
}

/* ---------------------------------------------- Páginas de información */

const page = (title, back, ...children) => ({ title, back, node: h("div", { class: "pagina" }, h("h1", null, title), ...children) });
const list = (tag, items) => h(tag, null, items.map((item) => h("li", null, item)));

export function viewHow() {
  return page(
    "Cómo funciona",
    "#/",
    h(
      "div",
      { class: "texto" },
      list("ol", [
        "Con internet, guarde el paquete de la lengua. Después todo funciona sin conexión.",
        "Suena un saludo corto en cada variante. La persona toca la que entiende.",
        "Usted elige un escenario: urgencias, embarazo, niño enfermo, medicinas, consentimiento o señales de alarma.",
        "En cada frase usted lee el español arriba. Abajo, la persona escucha la grabación y responde tocando: sí o no, un dibujo, el cuerpo, la escala de dolor o desde cuándo.",
        "Si no entendió, toca «No entendí» y la frase se repite. Si sigue sin entender, pida intérprete.",
        "Al final hay un resumen en español para el médico y, si quiere, una tarjeta de salida con dibujos y código QR.",
      ]),
      h("h2", null, "Las dos orillas de la pantalla"),
      h("p", null, "Arriba, en blanco, está lo que lee el personal de salud. Abajo, en azul, lo que escucha y toca el paciente. El botón «Modo paciente» deja solo la parte de abajo, con botones grandes y sin texto obligatorio."),
      h("h2", null, "Modo emergencia"),
      h("p", null, "El botón rojo abre de un toque cinco preguntas críticas: falta de aire, dolor de pecho, sangrado, alergias y embarazo."),
    ),
    linkButton("Qué hace Nepantla con los datos", "#/privacidad", { iconName: "escudo", cls: "btn btn-linea btn-chico btn-ancho" }),
  );
}

export function viewPrivacy() {
  return page(
    "Privacidad",
    "#/acerca",
    h(
      "div",
      { class: "texto" },
      h("p", null, h("strong", null, "Nepantla no guarda datos de pacientes. ")),
      list("ul", [
        "No pide nombre, edad, expediente ni ningún identificador.",
        "Las respuestas viven solo en la memoria de la pantalla. Se borran al terminar la consulta, al cerrar la app o tras 30 minutos sin uso.",
        "El resumen y la tarjeta se muestran, se copian o se imprimen aquí mismo. Nunca se envían.",
        "No hay cuentas, cookies de seguimiento ni analítica de terceros. La app no carga nada de otros servidores.",
        "Lo único que sale del teléfono son conteos sueltos: «tal día, tal paquete, tal evento». Sin hora, sin IP guardada, sin dispositivo.",
        "La empresa que hospeda el servidor (hoy, Railway) anota en sus registros técnicos la IP y el navegador de cada conexión. Nepantla no guarda esos datos.",
        "Un reporte de audio incorrecto lleva solo el paquete, la frase y un motivo de una lista.",
        "No usa inteligencia artificial generativa ni reconocimiento de voz. El micrófono solo se usa en el estudio, cuando un hablante graba con su consentimiento.",
      ]),
      h("p", null, "En este teléfono se guardan los paquetes de lengua, el contacto del intérprete que escriba la clínica y los conteos pendientes de enviar. Todo se puede borrar en Ajustes."),
    ),
    linkButton("Ajustes de esta clínica", "#/ajustes", { iconName: "ajustes", cls: "btn btn-linea btn-chico btn-ancho" }),
  );
}

export function viewAbout(app) {
  return page(
    "Acerca de Nepantla",
    "#/",
    h(
      "div",
      { class: "texto" },
      h("p", null, h("em", null, "Nepantla"), " es una palabra náhuatl: «en medio», el lugar entre dos orillas. Esta app quiere ser ese lugar entre una persona que habla una lengua indígena de México y el personal de salud que la atiende."),
      h("h2", null, "Qué es"),
      h("p", null, "Una ayuda de comunicación que funciona sin internet. Usa solo audios grabados y revisados por hablantes, pictogramas, un mapa del cuerpo y una escala de dolor."),
      h("h2", null, "Qué no es"),
      list("ul", [
        "No es un traductor ni un chatbot.",
        "No diagnostica ni sugiere tratamientos.",
        "No sustituye a las personas intérpretes: el botón «Pedir intérprete» está en todas las pantallas.",
        "No usa inteligencia artificial generativa ni reconocimiento de voz.",
        "No tiene cuentas de usuario y no guarda datos de pacientes.",
      ]),
      h("h2", null, "Lo que todavía falta"),
      list("ul", [
        "Las frases en español son un borrador: falta la revisión clínica firmada.",
        "Ningún paquete de lengua real está publicado todavía. Hacen falta hablantes, intérpretes certificados y guardianes de cada comunidad.",
        "Falta una revisión legal y una prueba piloto con personal de salud y hablantes. Hasta entonces no se puede decir que «funciona».",
      ]),
      h("h2", null, "Créditos"),
      list("ul", [
        "Voces: de quienes las graban y de su comunidad. Cada paquete muestra sus créditos y su licencia en la ficha.",
        "Pictogramas de la interfaz: originales de Nepantla, licencia CC BY 4.0. Pictogramas a color: Fluent Emoji de Microsoft (licencia MIT).",
        "Mapa del cuerpo: render del modelo humano 3D de MakeHuman (licencia CC0). Sin IA generativa.",
        "Letra: Atkinson Hyperlegible, del Braille Institute (licencia SIL OFL 1.1).",
        "Código QR: biblioteca de Kazuhiko Arase (licencia MIT).",
      ]),
      h("p", { class: "menor" }, `Versión de la app: ${app.build || "sin conexión"}.`),
    ),
    h(
      "ul",
      { class: "enlaces" },
      h("li", null, h("a", { href: "#/privacidad" }, icon("escudo"), h("span", null, "Privacidad"), icon("adelante"))),
      h("li", null, h("a", { href: "#/como-funciona" }, icon("info"), h("span", null, "Cómo funciona"), icon("adelante"))),
      h("li", null, h("a", { href: "#/retirar" }, icon("escudo"), h("span", null, "Retirar mi voz"), icon("adelante"))),
    ),
  );
}
