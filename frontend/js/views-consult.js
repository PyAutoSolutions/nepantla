/* Nepantla: pantallas de la consulta.

   Inicio, elegir variante por audio, escenarios, frase (con sus respuestas),
   modo emergencia, resumen para el médico, tarjeta de salida y pedir
   intérprete. Todas reciben `app` (el estado en memoria) y devuelven
   `{ title, back, node }` o `{ redirect }`. */

import qrcode from "../vendor/qrcode.js";
import * as audio from "./audio.js";
import { createBodyMap } from "./bodymap.js";
import * as core from "./core.js";
import { announce, button, confirmDialog, copyText, h, icon, linkButton, s, toast } from "./dom.js";
import { track } from "./net.js";
import { settings } from "./store.js";

const ADVANCE_MS = 750;

/* ------------------------------------------------------------------ Inicio */

export function viewHome(app) {
  const pack = app.activePack();
  const stored = app.packs.length;
  const answered = app.session.order.length;

  let language;
  if (!stored) {
    language = h(
      "div",
      { class: "aviso" },
      icon("paquete"),
      h(
        "div",
        null,
        h("strong", null, "Todavía no hay ningún paquete de lengua guardado en este teléfono."),
        " Guarde uno con internet y después todo funciona sin conexión.",
      ),
    );
  } else if (!pack) {
    language = h(
      "div",
      { class: "lengua" },
      h("a", { class: "redondo", href: "#/variante", "aria-label": "Elegir lengua por audio" }, icon("altavoz")),
      h(
        "div",
        { class: "lengua-texto" },
        h("strong", null, "Elegir lengua por audio"),
        h("span", { class: "menor" }, stored === 1 ? "1 variante guardada" : `${stored} variantes guardadas`),
      ),
    );
  } else {
    const greet = h(
      "button",
      {
        class: "redondo",
        type: "button",
        "aria-label": "Escuchar el saludo en esta lengua",
        disabled: !app.playable(core.GREETING_ID),
        onclick: async () => {
          greet.classList.add("sonando");
          await audio.playPhrase(pack.pack_id, core.GREETING_ID);
          greet.classList.remove("sonando");
        },
      },
      icon("altavoz"),
    );
    language = h(
      "div",
      { class: "lengua" },
      greet,
      h(
        "div",
        { class: "lengua-texto" },
        h("strong", null, core.packTitle(pack.manifest)),
        h("a", { href: "#/variante" }, "Cambiar de lengua"),
      ),
    );
  }

  const startHref = !stored ? "#/paquetes" : pack ? "#/escenarios" : "#/variante";
  const link = (href, iconName, label) =>
    h("li", null, h("a", { href }, icon(iconName), h("span", null, label), icon("adelante")));

  const node = h(
    "div",
    { class: "inicio" },
    h(
      "div",
      { class: "portada" },
      icon("logo"),
      h("h1", { class: "marca" }, "Nepantla"),
      h("p", { class: "lema" }, "Para entendernos en la consulta."),
    ),
    h(
      "div",
      { class: "inicio-cuerpo" },
      language,
      linkButton(!stored ? "Guardar un paquete de lengua" : answered ? "Seguir con la consulta" : "Empezar", startHref, {
        iconName: !stored ? "descargar" : "adelante",
        cls: "btn btn-grande btn-ancho",
      }),
      answered
        ? h(
            "div",
            { class: "fila" },
            linkButton(`Resumen (${answered})`, "#/resumen", { iconName: "resumen", cls: "btn btn-linea btn-chico" }),
            button("Nueva consulta", { iconName: "repetir", cls: "btn btn-linea btn-chico", onclick: () => app.newConsultation() }),
          )
        : null,
      h(
        "ul",
        { class: "enlaces" },
        link("#/como-funciona", "info", "Cómo funciona"),
        link("#/paquetes", "paquete", "Paquetes de lengua"),
        link("#/tarjeta", "tarjeta", "Tarjeta de salida"),
        link("#/acerca", "gente", "Acerca de y créditos"),
        link("#/ajustes", "ajustes", "Ajustes de esta clínica"),
      ),
      h(
        "p",
        { class: "menor" },
        "Nepantla no traduce ni diagnostica. Reproduce frases grabadas por hablantes y revisadas por dos personas. Si hace falta, pida intérprete.",
      ),
    ),
  );
  return { title: "Nepantla", back: null, node, home: true };
}

/* ------------------------------------------- Elegir variante por audio */

export function viewVariants(app) {
  if (!app.packs.length) return { redirect: "#/paquetes" };
  let alive = true;
  const rows = [];

  const choose = (record) => {
    app.activePackId = record.pack_id;
    const next = app.afterVariant || "#/escenarios";
    app.afterVariant = null;
    app.go(next);
  };

  const list = h("ul", { class: "variantes" });
  for (const record of app.packs) {
    const title = core.packTitle(record.manifest);
    const hasGreeting = app.playable(core.GREETING_ID, record);
    const play = h(
      "button",
      {
        class: "redondo",
        type: "button",
        disabled: !hasGreeting,
        "aria-label": hasGreeting ? `Escuchar el saludo de ${title}` : `${title} no tiene saludo grabado`,
        onclick: () => playOne(row),
      },
      icon("altavoz"),
    );
    const item = h(
      "li",
      { class: "variante", dataset: { pack: record.pack_id } },
      play,
      h(
        "div",
        { class: "variante-texto solo-personal" },
        h("strong", null, record.manifest.language),
        h("span", null, record.manifest.variant),
      ),
      h(
        "button",
        { class: "elegir", type: "button", "aria-label": `Entiende esta: elegir ${title}`, onclick: () => choose(record) },
        icon("si"),
      ),
    );
    const row = { record, item, play, hasGreeting };
    rows.push(row);
    list.append(item);
  }

  async function playOne(row) {
    for (const other of rows) {
      other.item.classList.remove("activa");
      other.play.classList.remove("sonando");
    }
    if (!row.hasGreeting) return "missing";
    row.item.classList.add("activa");
    row.play.classList.add("sonando");
    const how = await audio.playPhrase(row.record.pack_id, core.GREETING_ID);
    row.play.classList.remove("sonando");
    return how;
  }

  async function playAll() {
    for (const row of rows) {
      if (!alive) return;
      const how = await playOne(row);
      if (how === "stopped") return;
      if (alive) await new Promise((resolve) => setTimeout(resolve, 500));
    }
    for (const row of rows) row.item.classList.remove("activa");
  }

  const node = h(
    "div",
    { class: "pagina" },
    h("h1", null, "¿Cuál entiende?"),
    h(
      "p",
      { class: "menor" },
      "Suena un saludo corto en cada variante. La persona toca la palomita verde de la que entiende bien.",
    ),
    list,
    button("Repetir los saludos", { iconName: "repetir", cls: "btn btn-linea btn-ancho", onclick: playAll }),
    linkButton("No entiende ninguna: pedir intérprete", "#/interprete", { iconName: "interprete", cls: "btn btn-maiz btn-ancho" }),
  );
  setTimeout(() => alive && playAll(), 400);
  return {
    title: "Elegir lengua",
    back: "#/",
    node,
    cleanup: () => {
      alive = false;
    },
  };
}

/* ----------------------------------------------------------- Escenarios */

export function viewScenarios(app) {
  const pack = app.activePack();
  if (!pack) return { redirect: app.packs.length ? "#/variante" : "#/paquetes" };
  const tiles = app.data.scenarios.map((scenario) => {
    const phrases = core.flowPhrases(app.data, scenario.id);
    const ready = phrases.filter((p) => app.playable(p.id)).length;
    return h(
      "li",
      null,
      h(
        "a",
        { class: "tesela", href: `#/escenario/${scenario.id}` },
        icon(scenario.pictogram),
        h("span", null, scenario.title, h("small", null, `${ready} de ${phrases.length} con audio`)),
      ),
    );
  });
  const answered = app.session.order.length;
  const node = h(
    "div",
    { class: "pagina" },
    h("h1", null, "Escenarios"),
    h(
      "p",
      { class: "menor" },
      "Lengua: ",
      h("strong", null, core.packTitle(pack.manifest)),
      ". ",
      h("a", { href: "#/variante" }, "Cambiar"),
    ),
    h("ul", { class: "mosaico" }, tiles),
    h(
      "div",
      { class: "fila" },
      linkButton(answered ? `Resumen (${answered})` : "Resumen", "#/resumen", { iconName: "resumen", cls: "btn btn-linea btn-chico" }),
      linkButton("Tarjeta de salida", "#/tarjeta", { iconName: "tarjeta", cls: "btn btn-linea btn-chico" }),
    ),
  );
  return { title: "Escenarios", back: "#/", node };
}

export function viewScenario(app, scenarioId) {
  const scenario = core.scenarioById(app.data, scenarioId);
  if (!scenario) return { redirect: "#/escenarios" };
  const pack = app.activePack();
  if (!pack) {
    app.afterVariant = `#/escenario/${scenarioId}`;
    return { redirect: app.packs.length ? "#/variante" : "#/paquetes" };
  }
  if (!app.session.scenariosOpened.includes(scenarioId)) {
    app.session.scenariosOpened.push(scenarioId);
    track(pack.pack_id, "scenario_opened");
  }

  const phrases = core.flowPhrases(app.data, scenarioId);
  let firstOpen = phrases.findIndex((p) => app.playable(p.id) && !core.isAnswered(app.session.answers[p.id]));
  if (firstOpen < 0) firstOpen = Math.max(0, phrases.findIndex((p) => app.playable(p.id)));

  const items = phrases.map((phrase, index) => {
    const answer = app.session.answers[phrase.id];
    const done = core.isAnswered(answer) || (answer && answer.understood !== null);
    const chips = [];
    if (done) chips.push(h("span", { class: "chip listo" }, core.answerText(phrase, answer, app.data)));
    if (answer && answer.understood === false) chips.push(h("span", { class: "chip critica" }, "no entendió"));
    if (!app.playable(phrase.id)) chips.push(h("span", { class: "chip apagado" }, "sin audio"));
    if (phrase.priority === "critica") chips.push(h("span", { class: "chip critica" }, "crítica"));
    return h(
      "li",
      null,
      h(
        "a",
        { href: `#/frase/${scenarioId}/${index + 1}` },
        icon(phrase.pictogram),
        h(
          "span",
          { class: "frases-texto" },
          phrase.es_text,
          chips.length ? h("span", { class: "etiquetas" }, chips) : null,
        ),
        done ? icon("ok", "marca-ok") : null,
      ),
    );
  });

  const ready = phrases.filter((p) => app.playable(p.id)).length;
  const node = h(
    "div",
    { class: "pagina" },
    h("h1", null, scenario.title),
    scenario.notice ? h("div", { class: "aviso" }, icon("alarma"), h("span", null, scenario.notice)) : null,
    ready
      ? linkButton("Empezar", `#/frase/${scenarioId}/${firstOpen + 1}`, { iconName: "adelante", cls: "btn btn-ancho" })
      : h(
          "div",
          { class: "aviso rojo" },
          icon("alarma"),
          h("span", null, "Esta variante todavía no tiene audios revisados para este escenario. Pida intérprete."),
        ),
    h("p", { class: "menor" }, `${ready} de ${phrases.length} frases tienen audio revisado en esta variante.`),
    h("ul", { class: "frases" }, items),
  );
  return { title: scenario.title, back: "#/escenarios", node };
}

/* ---------------------------------------------------------------- Frase */

export function viewEmergency(app) {
  const target = "#/frase/emergencia/1";
  if (!app.activePack()) {
    if (app.packs.length === 1) app.activePackId = app.packs[0].pack_id;
    else {
      app.afterVariant = target;
      return { redirect: app.packs.length ? "#/variante" : "#/interprete" };
    }
  }
  return { redirect: target };
}

export function viewPhrase(app, flowId, position) {
  const phrases = core.flowPhrases(app.data, flowId);
  const index = parseInt(position, 10) - 1;
  if (!phrases.length || !(index >= 0 && index < phrases.length)) return { redirect: "#/escenarios" };
  const pack = app.activePack();
  if (!pack) {
    app.afterVariant = `#/frase/${flowId}/${index + 1}`;
    return { redirect: app.packs.length ? "#/variante" : "#/paquetes" };
  }

  const phrase = phrases[index];
  const canPlay = app.playable(phrase.id);
  const listHref = flowId === "emergencia" ? "#/escenarios" : `#/escenario/${flowId}`;
  const nextHref = index + 1 < phrases.length ? `#/frase/${flowId}/${index + 2}` : "#/resumen";
  const prevHref = index > 0 ? `#/frase/${flowId}/${index}` : listHref;
  const saved = () => app.session.answers[phrase.id] || { value: null, understood: null, plays: 0, notUnderstood: 0 };
  let timer = null;
  let alive = true;

  const advance = () => {
    clearTimeout(timer);
    timer = setTimeout(() => alive && app.go(nextHref), ADVANCE_MS);
  };

  /* --- Audio --- */
  const audioBtn = h(
    "button",
    { class: "btn-audio", type: "button", disabled: !canPlay, "aria-label": "Escuchar la frase en la lengua del paciente" },
    icon("altavoz"),
  );
  async function playNow() {
    if (!canPlay) return;
    clearTimeout(timer);
    core.recordAnswer(app.session, phrase.id, { plays: saved().plays + 1 });
    audioBtn.classList.add("sonando");
    const how = await audio.playPhrase(pack.pack_id, phrase.id);
    audioBtn.classList.remove("sonando");
    if (alive && (how === "error" || how === "missing")) toast("No se pudo reproducir este audio. Pida intérprete.");
  }
  audioBtn.addEventListener("click", playNow);

  /* --- Respuestas --- */
  const setAnswer = (value) => core.recordAnswer(app.session, phrase.id, { value });

  function choiceGroup(cls, options, { multiple = false } = {}) {
    const current = saved().value;
    const picked = new Set(multiple ? (Array.isArray(current) ? current : []) : current === null ? [] : [current]);
    const buttons = options.map((option) => {
      const node = h(
        "button",
        {
          class: `opcion ${option.cls || ""}`.trim(),
          type: "button",
          "aria-pressed": picked.has(option.id) ? "true" : "false",
          "aria-label": option.es,
          dataset: { valor: String(option.id) },
          onclick: () => {
            if (multiple) {
              if (picked.has(option.id)) picked.delete(option.id);
              else picked.add(option.id);
              setAnswer([...picked]);
            } else {
              picked.clear();
              picked.add(option.id);
              setAnswer(option.id);
              announce(`Respuesta: ${option.es}`);
              advance();
            }
            for (const [other, otherNode] of pairs) otherNode.setAttribute("aria-pressed", picked.has(other.id) ? "true" : "false");
          },
        },
        option.numeral !== undefined ? h("span", { class: "numeral", "aria-hidden": "true" }, String(option.numeral)) : null,
        option.icon ? icon(option.icon) : null,
        option.visible ? h("span", { "aria-hidden": "true" }, option.visible) : h("span", { class: "etiqueta-opcion" }, option.es),
      );
      return [option, node];
    });
    const pairs = buttons;
    return h("div", { class: cls }, buttons.map(([, node]) => node));
  }

  const doneButton = () =>
    button("Listo", { iconName: "ok", cls: "btn btn-maiz btn-ancho", onclick: () => app.go(nextHref) });

  let answerArea = null;
  if (phrase.answer_type === "yes_no") {
    answerArea = choiceGroup(
      "sino",
      core.YES_NO.map((o) => ({ ...o, cls: o.id === "nose" ? "nose" : o.id })),
    );
  } else if (phrase.answer_type === "pictogram") {
    const options = phrase.options.map((id) => {
      const option = app.data.options[id];
      return { id, es: option.es, icon: option.pictogram, numeral: option.numeral };
    });
    answerArea = h(
      "div",
      { class: "respuesta" },
      choiceGroup("opciones", options, { multiple: Boolean(phrase.multiple) }),
      phrase.multiple ? doneButton() : null,
    );
  } else if (phrase.answer_type === "body_map") {
    const map = createBodyMap({ selected: Array.isArray(saved().value) ? saved().value : [], onChange: setAnswer });
    answerArea = h("div", { class: "respuesta" }, map.node, doneButton());
  } else if (phrase.answer_type === "pain_scale") {
    const options = Array.from({ length: 11 }, (_, n) => ({ id: n, es: `${n} de 10`, icon: core.painFace(n), visible: String(n) }));
    answerArea = choiceGroup("dolor", options);
  } else if (phrase.answer_type === "duration") {
    answerArea = choiceGroup("duracion", core.DURATIONS);
  }

  /* --- Entendí / No entendí --- */
  const understoodBtn = h(
    "button",
    { class: "opcion si", type: "button", "aria-label": "Entendí", "aria-pressed": saved().understood === true ? "true" : "false" },
    icon("entendi"),
    h("span", { class: "etiqueta-opcion" }, "Entendí"),
  );
  const lostBtn = h(
    "button",
    { class: "opcion no", type: "button", "aria-label": "No entendí", "aria-pressed": saved().understood === false ? "true" : "false" },
    icon("no-entendi"),
    h("span", { class: "etiqueta-opcion" }, "No entendí"),
  );
  understoodBtn.addEventListener("click", () => {
    core.recordAnswer(app.session, phrase.id, { understood: true });
    understoodBtn.setAttribute("aria-pressed", "true");
    lostBtn.setAttribute("aria-pressed", "false");
    if (phrase.answer_type === "none") advance();
  });
  lostBtn.addEventListener("click", async () => {
    const times = saved().notUnderstood + 1;
    core.recordAnswer(app.session, phrase.id, { understood: false, notUnderstood: times });
    lostBtn.setAttribute("aria-pressed", "true");
    understoodBtn.setAttribute("aria-pressed", "false");
    if (times >= 2) {
      clearTimeout(timer);
      const ask = await confirmDialog({
        title: "No entendió esta frase",
        body: "Ya la escuchó más de una vez y sigue sin entenderla. Lo más seguro es pedir intérprete.",
        okLabel: "Pedir intérprete",
        cancelLabel: "Seguir aquí",
      });
      if (ask && alive) app.go("#/interprete");
      return;
    }
    playNow();
  });

  /* --- Las dos orillas --- */
  const meta = h(
    "div",
    { class: "frase-meta" },
    h("span", null, `${core.flowTitle(app.data, flowId)} · ${index + 1} de ${phrases.length}`),
    phrase.priority === "critica" ? h("span", { class: "chip critica" }, "crítica") : null,
    canPlay ? null : h("span", { class: "chip apagado" }, "sin audio"),
  );

  const node = h(
    "section",
    { class: "frase", "aria-label": "Frase" },
    h(
      "div",
      { class: "zona-personal" },
      meta,
      h("h1", { class: "frase-texto", lang: "es" }, phrase.es_text),
      h(
        "div",
        { class: "frase-nav" },
        h("a", { class: "btn btn-linea btn-chico angosto", href: prevHref, "aria-label": "Frase anterior" }, icon("atras")),
        button("Modo paciente", {
          iconName: "paciente",
          cls: "btn btn-linea btn-chico",
          onclick: () => {
            app.setPatientMode(true);
            playNow();
          },
        }),
        h("a", { class: "btn btn-linea btn-chico angosto", href: nextHref, "aria-label": index + 1 < phrases.length ? "Frase siguiente" : "Ir al resumen" }, icon("adelante")),
      ),
    ),
    h(
      "div",
      { class: "zona-paciente" },
      h(
        "button",
        { class: "btn btn-claro btn-chico volver-personal", type: "button", "aria-label": "Volver al modo del personal de salud", onclick: () => app.setPatientMode(false) },
        icon("personal"),
      ),
      h("div", { class: "escucha" }, icon(phrase.pictogram, "picto"), audioBtn),
      canPlay
        ? null
        : h(
            "p",
            { class: "sin-audio solo-personal" },
            "Esta frase todavía no tiene una grabación revisada en esta variante. Nepantla no la reproduce: pida intérprete.",
          ),
      answerArea,
      h("div", { class: "entendio" }, understoodBtn, lostBtn),
    ),
  );

  if (app.patientMode && canPlay) setTimeout(() => alive && playNow(), 350);

  return {
    title: core.flowTitle(app.data, flowId),
    back: listHref,
    node,
    phrase: true,
    cleanup: () => {
      alive = false;
      clearTimeout(timer);
    },
  };
}

/* -------------------------------------------------------------- Resumen */

function summaryBlocks(summary) {
  return [
    h("p", { class: "leyenda" }, summary.legend),
    h("div", { class: "texto menor" }, summary.header.map((line) => h("p", null, line))),
    summary.lines.length
      ? h(
          "ol",
          { class: "resumen" },
          summary.lines.map((line) =>
            h(
              "li",
              null,
              h("span", { class: "pregunta" }, line.question),
              h("span", { class: "dicho" }, line.answer),
              line.note ? h("span", { class: `nota ${line.alert ? "alerta" : ""}`.trim() }, line.note) : null,
            ),
          ),
        )
      : h("div", { class: "aviso calma" }, icon("info"), h("span", null, "Todavía no hay respuestas en esta consulta.")),
    h("div", { class: "texto menor" }, summary.footer.map((line) => h("p", null, line))),
  ];
}

export function viewSummary(app) {
  const pack = app.activePack();
  const summary = core.buildSummary({ data: app.data, pack: pack ? pack.manifest : null, session: app.session });
  if (summary.lines.length && pack && !app.session.summaryCounted) {
    app.session.summaryCounted = true;
    track(pack.pack_id, "summary_generated");
  }

  function fullScreen() {
    const overlay = h(
      "div",
      { class: "pantalla-completa", role: "dialog", "aria-modal": "true", "aria-label": "Resumen en pantalla completa" },
      button("Cerrar", {
        iconName: "no",
        cls: "btn btn-linea btn-chico no-imprimir",
        onclick: () => {
          if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(() => {});
          overlay.remove();
        },
      }),
      h("h1", null, "Resumen para el médico"),
      summaryBlocks(summary),
    );
    document.body.append(overlay);
    if (overlay.requestFullscreen) overlay.requestFullscreen().catch(() => {});
    overlay.querySelector("button").focus();
  }

  const node = h(
    "div",
    { class: "pagina" },
    h("h1", null, "Resumen para el médico"),
    summaryBlocks(summary),
    h(
      "div",
      { class: "fila no-imprimir" },
      button("Copiar", {
        iconName: "copiar",
        cls: "btn btn-chico",
        onclick: async () => toast((await copyText(summary.text)) ? "Resumen copiado." : "No se pudo copiar. Use pantalla completa."),
      }),
      button("Pantalla completa", { iconName: "pantalla", cls: "btn btn-linea btn-chico", onclick: fullScreen }),
      button("Imprimir", { iconName: "imprimir", cls: "btn btn-linea btn-chico", onclick: () => window.print() }),
    ),
    h(
      "div",
      { class: "fila no-imprimir" },
      linkButton("Más preguntas", "#/escenarios", { iconName: "lista", cls: "btn btn-linea btn-chico" }),
      linkButton("Tarjeta de salida", "#/tarjeta", { iconName: "tarjeta", cls: "btn btn-linea btn-chico" }),
    ),
    button("Terminar consulta y borrar respuestas", {
      iconName: "borrar",
      cls: "btn btn-rojo btn-chico btn-ancho no-imprimir",
      onclick: () => app.newConsultation(),
    }),
    h(
      "p",
      { class: "menor no-imprimir" },
      "Este resumen vive solo en la memoria de esta pantalla. No se guarda en el teléfono ni se envía a ningún lado.",
    ),
  );
  return { title: "Resumen", back: "#/escenarios", node };
}

/* ----------------------------------------------------- Pedir intérprete */

export function viewInterpreter(app) {
  const pack = app.activePack();
  if (!app.session.interpreterRequested) {
    app.session.interpreterRequested = true;
    if (pack) track(pack.pack_id, "interpreter_requested");
  }
  const contact = settings.get("contacto", null);
  const hasContact = contact && (contact.nombre || contact.telefono || contact.nota);
  const askPhrase = "con-012";

  const message = pack
    ? h("h1", { class: "pide" }, "Se solicita intérprete de ", h("span", null, pack.manifest.language), pack.manifest.variant ? `, variante ${pack.manifest.variant}.` : ".")
    : h("h1", { class: "pide" }, "Se solicita intérprete. Falta identificar la lengua.");

  const tell = pack && app.playable(askPhrase)
    ? (() => {
        const node = button("Avisar al paciente con audio", {
          iconName: "altavoz",
          cls: "btn btn-ancho",
          onclick: async () => {
            node.classList.add("sonando");
            await audio.playPhrase(pack.pack_id, askPhrase);
            node.classList.remove("sonando");
          },
        });
        return node;
      })()
    : null;

  const node = h(
    "div",
    { class: "interprete" },
    h(
      "div",
      { class: "pagina" },
      icon("interprete", "picto-grande"),
      message,
      h("p", null, "Muestre esta pantalla a quien pueda llamar a una persona intérprete. Mientras llega, puede seguir usando las frases con audio."),
      h(
        "div",
        { class: "contacto" },
        h("h2", null, "Contacto de esta clínica"),
        hasContact
          ? [
              contact.nombre ? h("p", null, contact.nombre) : null,
              contact.telefono
                ? h("a", { class: "telefono", href: `tel:${contact.telefono.replace(/[^\d+]/g, "")}` }, contact.telefono)
                : null,
              contact.nota ? h("p", { class: "menor" }, contact.nota) : null,
            ]
          : h("p", null, "Aún no hay un contacto configurado. ", h("a", { href: "#/ajustes" }, "Escribir el contacto del intérprete"), "."),
      ),
      tell,
      pack ? null : linkButton("Identificar la lengua por audio", "#/variante", { iconName: "altavoz", cls: "btn btn-ancho" }),
      linkButton("Volver a las frases", pack ? "#/escenarios" : "#/", { iconName: "atras", cls: "btn btn-linea btn-ancho" }),
    ),
  );
  return { title: "Pedir intérprete", back: pack ? "#/escenarios" : "#/", node };
}

/* --------------------------------------------------- Tarjeta de salida */

function qrSvg(text) {
  const code = qrcode(0, "M");
  code.addData(text);
  code.make();
  const count = code.getModuleCount();
  const quiet = 4;
  const size = count + quiet * 2;
  let d = "";
  for (let row = 0; row < count; row += 1) {
    for (let col = 0; col < count; col += 1) {
      if (code.isDark(row, col)) d += `M${col + quiet} ${row + quiet}h1v1h-1z`;
    }
  }
  return s(
    "svg",
    { viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": "Código QR para abrir esta tarjeta en otro teléfono", "shape-rendering": "crispEdges" },
    s("rect", { width: size, height: size, fill: "#ffffff" }),
    s("path", { d, fill: "#000000" }),
  );
}

export function viewCardBuilder(app) {
  const groups = core.cardPhrases(app.data);
  const card = app.card;
  const output = h("output", { "aria-live": "polite" }, String(card.days));

  const toggles = (phrases) =>
    h(
      "div",
      { class: "alternar" },
      phrases.map((phrase) => {
        const node = h(
          "button",
          {
            class: "opcion",
            type: "button",
            "aria-pressed": card.ids.includes(phrase.id) ? "true" : "false",
            onclick: () => {
              if (card.ids.includes(phrase.id)) card.ids = card.ids.filter((id) => id !== phrase.id);
              else card.ids.push(phrase.id);
              node.setAttribute("aria-pressed", card.ids.includes(phrase.id) ? "true" : "false");
            },
          },
          icon(phrase.pictogram),
          h("span", null, phrase.es_text),
        );
        return node;
      }),
    );

  const step = (delta) => {
    card.days = Math.max(0, Math.min(90, card.days + delta));
    output.textContent = String(card.days);
  };

  const node = h(
    "div",
    { class: "pagina" },
    h("h1", null, "Tarjeta de salida"),
    h(
      "p",
      { class: "menor" },
      "Usted elige las indicaciones; la app solo las muestra con pictogramas. Lo que marque aquí no se guarda ni se envía.",
    ),
    h("fieldset", null, h("legend", null, "Medicina"), toggles(groups.medicina)),
    h("fieldset", null, h("legend", null, "Cuándo regresar de inmediato"), toggles(groups.alarma)),
    h(
      "fieldset",
      null,
      h("legend", null, "Regresar a consulta en… días"),
      h(
        "div",
        { class: "paso" },
        h("button", { class: "icono-btn", type: "button", "aria-label": "Un día menos", onclick: () => step(-1) }, icon("menos")),
        output,
        h("button", { class: "icono-btn", type: "button", "aria-label": "Un día más", onclick: () => step(1) }, icon("mas")),
        h("span", { class: "menor" }, "0 = no indicar"),
      ),
    ),
    linkButton("Ver tarjeta", "#/tarjeta/ver", { iconName: "tarjeta", cls: "btn btn-ancho" }),
  );
  return { title: "Tarjeta de salida", back: app.activePack() ? "#/escenarios" : "#/", node };
}

function cardNode(app, { record, phraseIds, days, qrText }) {
  const byId = core.indexPhrases(app.data);
  const phrases = phraseIds.map((id) => byId.get(id)).filter((p) => p && p.answer_type === "none");
  const medicine = phrases.filter((p) => p.scenario === "medicinas");
  const alarm = phrases.filter((p) => p.scenario !== "medicinas");
  const contact = settings.get("contacto", null);

  const item = (phrase) => {
    const canPlay = record && app.playable(phrase.id, record);
    let play = null;
    if (canPlay) {
      play = h(
        "button",
        {
          class: "redondo no-imprimir",
          type: "button",
          "aria-label": `Escuchar: ${phrase.es_text}`,
          onclick: async () => {
            play.classList.add("sonando");
            await audio.playPhrase(record.pack_id, phrase.id);
            play.classList.remove("sonando");
          },
        },
        icon("altavoz"),
      );
    }
    return h("li", null, icon(phrase.pictogram), h("span", null, phrase.es_text), play);
  };

  return h(
    "article",
    { class: "tarjeta", "aria-label": "Tarjeta de salida" },
    h("div", { class: "tarjeta-cabeza" }, icon("logo"), h("span", null, "Indicaciones para llevar a casa")),
    medicine.length
      ? h(
          "div",
          { class: "tarjeta-seccion" },
          h("h2", null, "Medicina"),
          h("ul", { class: "tarjeta-pictos" }, medicine.map(item)),
          h("div", { class: "tarjeta-renglon" }, h("span", null, "Medicina:"), h("span", null)),
        )
      : null,
    alarm.length
      ? h("div", { class: "tarjeta-seccion" }, h("h2", null, "Cuándo regresar"), h("ul", { class: "tarjeta-pictos" }, alarm.map(item)))
      : null,
    days
      ? h(
          "div",
          { class: "tarjeta-seccion" },
          h("h2", null, "Regresar a consulta"),
          h(
            "ul",
            { class: "tarjeta-pictos" },
            h("li", null, h("span", { class: "numero" }, String(days)), h("span", null, days === 1 ? "día" : "días")),
            h("li", null, icon("cita"), h("span", null, "Regrese a consulta")),
          ),
          h("div", { class: "tarjeta-renglon" }, h("span", null, "Fecha:"), h("span", null)),
        )
      : null,
    !phrases.length && !days ? h("p", null, "Esta tarjeta no tiene indicaciones marcadas.") : null,
    h(
      "div",
      { class: "tarjeta-pie" },
      qrText ? h("div", { class: "qr" }, qrSvg(qrText)) : null,
      h(
        "div",
        null,
        qrText ? h("p", null, "Escanee el código para volver a ver y escuchar estas indicaciones.") : null,
        contact && (contact.nombre || contact.telefono)
          ? h("p", null, [contact.nombre, contact.telefono].filter(Boolean).join(" · "))
          : null,
        h("p", null, "Comunicación asistida: no sustituye las indicaciones de su personal de salud."),
        record && record.manifest.is_test ? h("p", null, h("strong", null, "AUDIO DE PRUEBA: no es una lengua real.")) : null,
      ),
    ),
  );
}

export function viewCard(app) {
  const record = app.activePack();
  const card = app.card;
  const hash = core.encodeCard({ packId: record ? record.pack_id : null, phraseIds: card.ids, days: card.days || null });
  const qrText = `${location.origin}${location.pathname}${hash}`;
  const node = h(
    "div",
    { class: "pagina" },
    h("h1", { class: "solo-lector" }, "Tarjeta de salida"),
    cardNode(app, { record, phraseIds: card.ids, days: card.days, qrText }),
    h(
      "div",
      { class: "fila no-imprimir" },
      button("Imprimir", { iconName: "imprimir", cls: "btn btn-chico", onclick: () => window.print() }),
      linkButton("Cambiar", "#/tarjeta", { iconName: "atras", cls: "btn btn-linea btn-chico" }),
    ),
    h(
      "p",
      { class: "menor no-imprimir" },
      "El código QR solo lleva la lista de indicaciones. No lleva nombre ni ningún dato de la persona, y lo que contiene no se envía al servidor.",
    ),
  );
  return { title: "Tarjeta de salida", back: "#/tarjeta", node };
}

/** Tarjeta abierta desde el código QR, en el teléfono de la familia. */
export function viewCardFromQr(app) {
  const card = core.decodeCard(location.hash);
  if (!card) return { redirect: "#/" };
  const record = card.packId ? app.packs.find((p) => p.pack_id === card.packId) || null : null;
  const node = h(
    "div",
    { class: "pagina" },
    h("h1", { class: "solo-lector" }, "Indicaciones para llevar a casa"),
    cardNode(app, { record, phraseIds: card.phraseIds, days: card.days, qrText: null }),
    record
      ? h("p", { class: "menor no-imprimir" }, "Toque el altavoz amarillo de cada indicación para escucharla.")
      : h(
          "div",
          { class: "aviso calma no-imprimir" },
          icon("paquete"),
          h(
            "span",
            null,
            "Para escuchar estas indicaciones hace falta guardar el paquete de la lengua en este teléfono. ",
            h("a", { href: "#/paquetes" }, "Ver paquetes"),
            ".",
          ),
        ),
  );
  return { title: "Indicaciones", back: "#/", node };
}
