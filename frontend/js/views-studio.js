/* Nepantla: estudio de grabación remoto.

   Cuatro pantallas que solo funcionan con internet:
     #/estudio  -> hablante (consentimiento y grabación), revisor o guardián,
                   según el enlace único que recibió cada persona.
     #/retirar  -> retirar una voz con el código de retiro.
     #/admin    -> coordinación: crear paquetes y enlaces.

   Decisiones de privacidad:
   * El enlace trae el permiso después del "#". Esa parte no viaja al
     servidor en la dirección; la app la lee, la quita de la barra y la manda
     en una cabecera.
   * El micrófono solo se enciende cuando el hablante toca "grabar", después
     de aceptar el consentimiento, y se apaga al terminar cada frase.
   * El token de administración se queda en la memoria de la pestaña. */

import * as audio from "./audio.js";
import * as core from "./core.js";
import { button, clear, confirmDialog, copyText, dataList, fill, h, icon, linkButton, toast } from "./dom.js";
import { ApiError, api } from "./net.js";

const SESSION_KEY = "nepantla.estudio";
const MAX_SECONDS = 30;
const ROLE_ES = { speaker: "Hablante", reviewer: "Revisor", guardian: "Guardián" };
const MINE_ES = {
  pending: "En revisión",
  approved: "Aprobada",
  rejected: "Hay que grabarla otra vez",
  superseded: "Reemplazada",
  withdrawn: "Retirada",
};
const REASON_ES = Object.fromEntries(core.REPORT_REASONS.map((r) => [r.id, r.es]));

const errorText = (error) => (error instanceof ApiError ? error.message : "Algo falló. Inténtelo otra vez.");
const shell = (title, ...children) => ({ title, back: "#/", noBar: true, node: h("div", { class: "pagina" }, h("h1", null, title), ...children) });
const absolute = (hash) => `${location.origin}${location.pathname}${hash}`;

/** Lee el token del enlace, lo guarda en la pestaña y lo quita de la barra. */
function takeToken(fromHash, key, cleanHash) {
  try {
    if (fromHash) {
      sessionStorage.setItem(key, fromHash);
      history.replaceState(null, "", `${location.pathname}${cleanHash}`);
    }
    return sessionStorage.getItem(key);
  } catch {
    return fromHash || null;
  }
}

function forgetToken(key) {
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* nada que olvidar */
  }
}

function tokenBox(value, label) {
  return h(
    "div",
    { class: "campo" },
    h("span", { class: "rotulo" }, label),
    h("div", { class: "token", tabindex: 0 }, value),
    button("Copiar", {
      iconName: "copiar",
      cls: "btn btn-linea btn-chico",
      onclick: async () => toast((await copyText(value)) ? "Copiado." : "No se pudo copiar: selecciónelo a mano."),
    }),
  );
}

async function playRemote(path, token) {
  const response = await api(path, { token, raw: true });
  return audio.playBuffer(await response.blob());
}

/* ---------------------------------------------------------------- Estudio */

export async function viewStudio(app, tokenFromHash) {
  const token = takeToken(tokenFromHash, SESSION_KEY, "#/estudio");
  if (!token) {
    const input = h("input", { id: "enlace", autocomplete: "off", required: true });
    return shell(
      "Estudio de grabación",
      h("p", null, "Aquí graban los hablantes y revisan los intérpretes. Para entrar hace falta el enlace personal que le mandó la coordinación del proyecto."),
      h(
        "form",
        {
          onsubmit: (event) => {
            event.preventDefault();
            const value = input.value.trim().split("/").pop();
            if (value) app.go(`#/estudio/${value}`);
          },
        },
        h("div", { class: "campo" }, h("label", { for: "enlace" }, "Pegue aquí su enlace o su código"), input),
        h("button", { class: "btn btn-ancho", type: "submit" }, "Entrar"),
      ),
    );
  }

  let session;
  try {
    session = await api("./api/studio/session", { token });
  } catch (error) {
    if (error.status === 401 || error.status === 403) forgetToken(SESSION_KEY);
    return shell("Estudio de grabación", h("div", { class: "aviso rojo" }, icon("alarma"), h("span", null, errorText(error))));
  }

  const head = [
    session.pack.is_test
      ? h("div", { class: "aviso" }, icon("bandera"), h("span", null, h("strong", null, "AUDIO DE PRUEBA. "), "Este paquete es de demostración."))
      : null,
    h(
      "p",
      { class: "menor" },
      `${ROLE_ES[session.role]}: ${session.alias}. Paquete: ${core.packTitle(session.pack)}.`,
    ),
  ];
  const view = { app, token, session, head, refresh: () => app.render() };
  if (session.role === "speaker") return speakerView(view);
  if (session.role === "reviewer") return reviewerView(view);
  return guardianView(view);
}

/* --- Hablante: consentimiento --- */

function consentAudioButton(session) {
  // El audio del consentimiento lo graba una persona (nunca una voz sintética).
  // Si todavía no existe, el servidor lo dice y el botón no aparece.
  if (!session.consent_audio) return null;
  const player = new Audio("./audio/consentimiento.es.opus");
  return button("Escuchar esta explicación", { iconName: "altavoz", cls: "btn btn-linea btn-ancho", onclick: () => player.play() });
}

async function consentView({ token, session, head, refresh }) {
  const pack = session.pack;
  const checks = [
    ["understands_use", "Entiendo para qué se va a usar mi voz."],
    ["understands_withdrawal", "Entiendo que puedo retirar mi voz cuando yo quiera."],
    ["accepts_license", `Acepto que mis grabaciones se compartan con esta licencia: ${pack.license || "la que defina mi comunidad"}.`],
    ["is_adult", "Soy mayor de edad."],
  ];
  const name = h("input", { id: "credito", maxlength: 80, required: true, autocomplete: "off" });
  const form = h(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        const body = { credit_name: name.value.trim() };
        for (const [key] of checks) body[key] = form.querySelector(`#c-${key}`).checked;
        if (!checks.every(([key]) => body[key])) {
          toast("Para grabar hay que marcar las cuatro casillas.");
          return;
        }
        try {
          const result = await api("./api/studio/consent", { method: "POST", token, body });
          clear(form.parentNode).append(...withdrawalKeep(result, refresh));
        } catch (error) {
          toast(errorText(error));
        }
      },
    },
    checks.map(([key, label]) => h("label", { class: "casilla" }, h("input", { type: "checkbox", id: `c-${key}` }), h("span", null, label))),
    h(
      "div",
      { class: "campo" },
      h("label", { for: "credito" }, "¿Con qué nombre quiere aparecer en los créditos?"),
      name,
      h("span", { class: "menor" }, "Puede ser su nombre, un apodo o «Anónimo»."),
    ),
    h("button", { class: "btn btn-ancho", type: "submit" }, "Acepto y quiero grabar"),
  );

  return shell(
    "Antes de grabar",
    head,
    consentAudioButton(session),
    h(
      "div",
      { class: "texto" },
      h("h2", null, "¿Quién va a usar su voz?"),
      h("p", null, `Personal de salud y personas que hablan ${pack.language}, dentro de la app Nepantla.`),
      h("h2", null, "¿Para qué?"),
      h("p", null, "Para que alguien que habla su lengua entienda las preguntas y las indicaciones en una clínica u hospital. No se usa para publicidad ni para entrenar inteligencia artificial."),
      h("h2", null, "¿Quién la revisa?"),
      h("p", null, "Dos personas escuchan cada grabación antes de que se use. Si una frase no quedó bien, se le pedirá grabarla otra vez."),
      h("h2", null, "¿Cómo la retiro?"),
      h("p", null, "Al aceptar le damos un código de retiro. Con ese código puede quitar una frase o toda su voz cuando quiera, sin dar explicaciones. Sus grabaciones se borran del servidor y, en la siguiente conexión, de los teléfonos."),
      h("h2", null, "Licencia y crédito"),
      h("p", null, `La licencia de este paquete la eligió su comunidad: ${pack.license || "todavía no está definida"}. Usted decide con qué nombre aparece.`),
    ),
    h("div", null, form),
  );
}

function withdrawalKeep(result, refresh) {
  const link = absolute(`#/retirar/${result.withdrawal_token}`);
  return [
    h("div", { class: "aviso rojo" }, icon("alarma"), h("span", null, h("strong", null, "Guarde este código ahora. "), "Es la única vez que se muestra. Tómele una foto o cópielo en un lugar seguro.")),
    tokenBox(result.withdrawal_token, "Su código de retiro"),
    tokenBox(link, "O guarde este enlace para retirar su voz"),
    button("Ya lo guardé: empezar a grabar", { iconName: "microfono", cls: "btn btn-ancho", onclick: refresh }),
  ];
}

/* --- Hablante: grabación --- */

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return null;
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return options.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

async function speakerView(view) {
  const { app, token, session, head } = view;
  if (!session.consent.signed) return consentView(view);

  let phrases;
  try {
    phrases = (await api("./api/studio/phrases", { token })).phrases;
  } catch (error) {
    return shell("Grabar frases", head, h("div", { class: "aviso rojo" }, icon("alarma"), h("span", null, errorText(error))));
  }

  const needsWork = (p) => !p.mine || p.mine === "rejected" || p.mine === "withdrawn" || p.mine === "superseded";
  let index = Math.max(0, phrases.findIndex(needsWork));
  let recorder = null;
  let stream = null;
  let take = null;
  let ticker = null;
  let alive = true;
  const stage = h("div", { class: "pagina-seccion" });
  const mime = pickMimeType();

  function stopStream() {
    if (stream) for (const track of stream.getTracks()) track.stop();
    stream = null;
  }

  function draw() {
    clearInterval(ticker);
    const phrase = phrases[index];
    const done = phrases.filter((p) => p.mine === "pending" || p.mine === "approved").length;
    const scenario = core.scenarioById(app.data, phrase.scenario);
    const clock = h("div", { class: "reloj", "aria-live": "off" }, "0:00");
    const recordBtn = h("button", { class: "btn-audio", type: "button", "aria-label": "Grabar" }, icon("microfono"));
    const after = h("div", { class: "fila" });

    function setRecording(on) {
      recordBtn.classList.toggle("grabando", on);
      recordBtn.setAttribute("aria-label", on ? "Detener la grabación" : "Grabar");
      recordBtn.replaceChildren(icon(on ? "detener" : "microfono"));
    }

    function showTake() {
      after.replaceChildren(
        button("Escuchar", { iconName: "altavoz", cls: "btn btn-claro btn-chico", onclick: () => audio.playBuffer(take) }),
        button("Grabar otra vez", { iconName: "repetir", cls: "btn btn-claro btn-chico", onclick: () => { take = null; after.replaceChildren(); clock.textContent = "0:00"; } }),
        button("Guardar y seguir", { iconName: "ok", cls: "btn btn-maiz btn-chico", onclick: upload }),
      );
    }

    async function start() {
      audio.stop();
      take = null;
      after.replaceChildren();
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
      } catch {
        toast("No se pudo usar el micrófono. Revise que le dio permiso al navegador.");
        return;
      }
      const chunks = [];
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorder.ondataavailable = (event) => event.data && event.data.size && chunks.push(event.data);
      recorder.onstop = () => {
        clearInterval(ticker);
        stopStream();
        setRecording(false);
        take = new Blob(chunks, { type: recorder.mimeType || mime || "audio/webm" });
        recorder = null;
        if (alive) showTake();
      };
      const startedAt = Date.now();
      recorder.start();
      setRecording(true);
      ticker = setInterval(() => {
        const seconds = Math.floor((Date.now() - startedAt) / 1000);
        clock.textContent = `0:${String(seconds).padStart(2, "0")}`;
        if (seconds >= MAX_SECONDS && recorder) recorder.stop();
      }, 250);
    }

    async function upload() {
      if (!take) return;
      const form = new FormData();
      form.append("phrase_id", phrase.id);
      form.append("audio", take, take.type.includes("mp4") ? "grabacion.m4a" : "grabacion.webm");
      for (const node of after.querySelectorAll("button")) node.disabled = true;
      try {
        const saved = await api("./api/studio/recordings", { method: "POST", token, form, timeout: 60000 });
        phrase.mine = "pending";
        phrase.recording_id = saved.recording_id;
        phrase.note = "";
        take = null;
        toast("Grabación guardada. Pasa a revisión.");
        const next = phrases.findIndex((p, i) => i > index && needsWork(p));
        index = next >= 0 ? next : Math.min(index + 1, phrases.length - 1);
        draw();
      } catch (error) {
        toast(errorText(error));
        showTake();
      }
    }

    recordBtn.addEventListener("click", () => (recorder ? recorder.stop() : start()));

    fill(
      stage,
      h("p", { class: "menor" }, `${done} de ${phrases.length} frases grabadas`),
      h("div", { class: "avance", role: "img", "aria-label": `${done} de ${phrases.length} frases grabadas` }, h("span", { dataset: { ancho: String(Math.round((done / phrases.length) * 100)) } })),
      h(
        "div",
        { class: "frase-meta" },
        h("span", null, `${scenario ? scenario.title : "Saludo"} · ${index + 1} de ${phrases.length}`),
        phrase.mine ? h("span", { class: `chip ${phrase.mine === "approved" ? "listo" : phrase.mine === "rejected" ? "critica" : ""}`.trim() }, MINE_ES[phrase.mine] || phrase.mine) : h("span", { class: "chip apagado" }, "Sin grabar"),
      ),
      h("h2", { class: "frase-texto" }, phrase.es_text),
      phrase.mine === "rejected" && phrase.note ? h("div", { class: "aviso" }, icon("info"), h("span", null, `Nota de quien revisó: ${phrase.note}`)) : null,
      phrase.id === core.GREETING_ID
        ? h("p", { class: "menor" }, "Este saludo sirve para que el paciente reconozca su variante. Dígalo como saludaría a alguien de su comunidad.")
        : h("p", { class: "menor" }, "Dígalo en su lengua como se lo diría a un familiar: claro, sin prisa y con sus propias palabras."),
      h("div", { class: "grabadora" }, recordBtn, clock, after),
      h(
        "div",
        { class: "frase-nav" },
        button("Anterior", { iconName: "atras", cls: "btn btn-linea btn-chico", disabled: index === 0, onclick: () => { index -= 1; draw(); } }),
        button("Siguiente", { iconName: "adelante", cls: "btn btn-linea btn-chico", disabled: index >= phrases.length - 1, onclick: () => { index += 1; draw(); } }),
      ),
    );
    const bar = stage.querySelector(".avance span");
    bar.style.width = `${bar.dataset.ancho}%`;
  }

  const blockers = [];
  if (!session.recording_available) blockers.push("El servidor no puede guardar grabaciones en este momento (falta ffmpeg). Avise a la coordinación.");
  if (mime === null || !navigator.mediaDevices) blockers.push("Este navegador no puede grabar audio. Pruebe con Chrome o Firefox actualizados.");

  const result = shell(
    "Grabar frases",
    head,
    h(
      "div",
      { class: "aviso calma" },
      icon("microfono"),
      h("span", null, h("strong", null, "Para que se oiga bien: "), "busque un lugar silencioso, ponga el teléfono a un palmo de la boca y apague música, radio y televisión."),
    ),
    blockers.length ? h("div", { class: "aviso rojo" }, icon("alarma"), h("span", null, blockers.join(" "))) : stage,
    h("p", { class: "menor" }, "¿Quiere quitar una grabación o toda su voz? ", h("a", { href: "#/retirar" }, "Retirar mi voz"), "."),
  );
  if (!blockers.length) draw();
  result.cleanup = () => {
    alive = false;
    clearInterval(ticker);
    if (recorder) recorder.stop();
    stopStream();
  };
  return result;
}

/* --- Revisor --- */

async function reviewerView({ token, session, head, refresh }) {
  let queue;
  try {
    queue = (await api("./api/studio/queue", { token })).queue;
  } catch (error) {
    return shell("Revisar grabaciones", head, h("div", { class: "aviso rojo" }, icon("alarma"), h("span", null, errorText(error))));
  }
  const stage = h("div", { class: "pagina-seccion" });

  function draw() {
    if (!queue.length) {
      stage.replaceChildren(
        h("div", { class: "aviso calma" }, icon("ok"), h("span", null, "No hay grabaciones esperando su revisión. Gracias.")),
        button("Buscar nuevas", { iconName: "repetir", cls: "btn btn-linea btn-ancho", onclick: refresh }),
      );
      return;
    }
    const item = queue[0];
    const note = h("textarea", { id: "nota", maxlength: 300 });
    const send = async (verdict) => {
      if (verdict === "reject" && !note.value.trim()) {
        toast("Escriba una nota corta para que el hablante sepa qué corregir.");
        note.focus();
        return;
      }
      try {
        const result = await api("./api/studio/reviews", { method: "POST", token, body: { recording_id: item.recording_id, verdict, note: note.value.trim() } });
        toast(
          result.status === "approved"
            ? "Aprobada: ya tiene doble revisión y entra al paquete."
            : result.status === "rejected"
              ? "Rechazada: el hablante la grabará otra vez."
              : result.needs_interpreter
                ? "Registrada. Falta la aprobación de una persona intérprete."
                : "Registrada. Falta una segunda revisión.",
        );
      } catch (error) {
        toast(errorText(error));
      }
      audio.stop();
      queue.shift();
      draw();
    };
    stage.replaceChildren(
      h("p", { class: "menor" }, `Quedan ${queue.length} por revisar. Esta lleva ${item.approvals} aprobación(es).`),
      h("h2", { class: "frase-texto" }, item.es_text),
      button("Escuchar la grabación", {
        iconName: "altavoz",
        cls: "btn btn-maiz btn-ancho",
        onclick: () => playRemote(`./api/studio/recordings/${item.recording_id}/audio`, token).catch((error) => toast(errorText(error))),
      }),
      h("div", { class: "campo" }, h("label", { for: "nota" }, "Nota para quien grabó (obligatoria si rechaza)"), note),
      h(
        "div",
        { class: "fila" },
        button("Rechazar", { iconName: "no", cls: "btn btn-linea", onclick: () => send("reject") }),
        button("Aprobar", { iconName: "si", cls: "btn", onclick: () => send("approve") }),
      ),
    );
  }
  draw();
  return shell(
    "Revisar grabaciones",
    head,
    h(
      "div",
      { class: "aviso calma" },
      icon("doble-revision"),
      h(
        "span",
        null,
        session.is_interpreter ? "Usted revisa como intérprete de esta lengua. " : "Usted revisa como personal de salud. ",
        "Apruebe solo si la grabación dice lo mismo que el texto, se oye clara y suena natural en esta variante. No escriba datos de pacientes en la nota.",
      ),
    ),
    stage,
  );
}

/* --- Guardián --- */

async function withdrawWithConfirm(token, body, question) {
  const preview = await api("./api/withdraw", { method: "POST", body: { ...body, token, dry_run: true } });
  const ok = await confirmDialog({
    title: question,
    body: `Se borrarán ${preview.recordings} grabación(es) del servidor. Los teléfonos las borran en su siguiente conexión. No se puede deshacer.`,
    okLabel: "Retirar",
    danger: true,
  });
  if (!ok) return null;
  return api("./api/withdraw", { method: "POST", body: { ...body, token, dry_run: false } });
}

async function guardianView({ token, head, refresh }) {
  let data;
  try {
    data = await api("./api/studio/pack", { token });
  } catch (error) {
    return shell("Guardianes del paquete", head, h("div", { class: "aviso rojo" }, icon("alarma"), h("span", null, errorText(error))));
  }
  const { pack, coverage } = data;
  const act = async (work, okMessage) => {
    try {
      const result = await work();
      if (result === null) return;
      toast(okMessage);
      refresh();
    } catch (error) {
      toast(errorText(error));
    }
  };

  const approvedRows = data.approved.map((entry) =>
    h(
      "tr",
      null,
      h("td", null, h("strong", null, entry.es_text || entry.id), h("br"), h("span", { class: "menor" }, `Grabó: ${entry.recorded_by}. Revisó: ${entry.reviewed_by.join(", ")}.`)),
      h(
        "td",
        null,
        h(
          "div",
          { class: "fila" },
          entry.recording_id
            ? h("button", { class: "icono-btn", type: "button", "aria-label": `Escuchar: ${entry.es_text}`, onclick: () => playRemote(`./api/studio/recordings/${entry.recording_id}/audio`, token).catch((e) => toast(errorText(e))) }, icon("altavoz"))
            : null,
          h("button", { class: "icono-btn", type: "button", "aria-label": `Retirar la frase: ${entry.es_text}`, onclick: () => act(() => withdrawWithConfirm(token, { scope: "phrase", phrase_id: entry.id }, "¿Retirar esta frase del paquete?"), "Frase retirada.") }, icon("borrar")),
        ),
      ),
    ),
  );

  const reportRows = data.reports.map((report) =>
    h(
      "tr",
      null,
      h("td", null, report.phrase_id),
      h("td", null, REASON_ES[report.reason] || report.reason),
      h("td", null, report.created_at),
      h(
        "td",
        null,
        report.status === "open"
          ? h(
              "div",
              { class: "fila" },
              button("Atendido", { cls: "btn btn-chico", onclick: () => act(() => api(`./api/studio/reports/${report.report_id}`, { method: "POST", token, body: { status: "resolved" } }), "Reporte marcado como atendido.") }),
              button("Descartar", { cls: "btn btn-linea btn-chico", onclick: () => act(() => api(`./api/studio/reports/${report.report_id}`, { method: "POST", token, body: { status: "dismissed" } }), "Reporte descartado.") }),
            )
          : report.status === "resolved" ? "Atendido" : "Descartado",
      ),
    ),
  );

  const percent = coverage.total_phrases ? Math.round((coverage.approved / coverage.total_phrases) * 100) : 0;
  const bar = h("span");
  bar.style.width = `${percent}%`;

  return shell(
    "Guardianes del paquete",
    head,
    dataList([
      ["Estado", pack.status === "approved" ? "Publicado" : pack.status === "withdrawn" ? "Retirado" : "Borrador (todavía no se publica)"],
      ["Versión", pack.version],
      ["Licencia", pack.license || "Sin definir"],
      ["Frases con doble revisión", `${coverage.approved} de ${coverage.total_phrases}`],
      ["En revisión", String(coverage.pending)],
      ["Saludo", coverage.has_greeting ? "Grabado y revisado" : "Falta"],
    ]),
    h("div", { class: "avance", role: "img", "aria-label": `${percent} por ciento del paquete tiene doble revisión` }, bar),
    pack.status === "draft" && !pack.is_test
      ? button("Aprobar y publicar el paquete", {
          iconName: "ok",
          cls: "btn btn-ancho",
          disabled: coverage.approved === 0,
          onclick: async () => {
            const ok = await confirmDialog({
              title: "¿Publicar este paquete?",
              body: `Las clínicas podrán descargar las ${coverage.approved} frases que ya tienen doble revisión. Podrá retirarlo cuando quiera.`,
              okLabel: "Publicar",
            });
            if (ok) act(() => api("./api/studio/pack/approve", { method: "POST", token }), "Paquete publicado.");
          },
        })
      : null,
    h("h2", null, `Reportes de audio incorrecto (${data.reports.filter((r) => r.status === "open").length} abiertos)`),
    reportRows.length
      ? h("div", { class: "desliza" }, h("table", { class: "tabla" }, h("thead", null, h("tr", null, h("th", null, "Frase"), h("th", null, "Motivo"), h("th", null, "Día"), h("th", null, "Estado"))), h("tbody", null, reportRows)))
      : h("p", { class: "menor" }, "No hay reportes."),
    h("h2", null, `Frases en el paquete (${data.approved.length})`),
    approvedRows.length
      ? h("div", { class: "desliza" }, h("table", { class: "tabla" }, h("tbody", null, approvedRows)))
      : h("p", { class: "menor" }, "Todavía no hay frases con doble revisión."),
    data.missing.length ? h("details", null, h("summary", null, `Frases que faltan (${data.missing.length})`), h("ul", null, data.missing.map((m) => h("li", null, m.es_text)))) : null,
    h("h2", null, "Retirar el paquete"),
    h("p", { class: "menor" }, "Si la comunidad decide que este paquete ya no debe usarse, se borra del servidor y de los teléfonos en su siguiente conexión."),
    button("Retirar el paquete completo", {
      iconName: "borrar",
      cls: "btn btn-rojo btn-chico",
      disabled: pack.status === "withdrawn",
      onclick: () => act(() => withdrawWithConfirm(token, { scope: "pack" }, "¿Retirar el paquete completo?"), "Paquete retirado."),
    }),
  );
}

/* ------------------------------------------------------- Retirar mi voz */

export function viewWithdraw(app, tokenFromHash) {
  const token = takeToken(tokenFromHash, "nepantla.retiro", "#/retirar") || "";
  const input = h("input", { id: "codigo", value: token, autocomplete: "off", required: true });
  const stage = h("div", { class: "pagina-seccion", "aria-live": "polite" });
  const phraseSelect = h(
    "select",
    { id: "retiro-frase" },
    h("option", { value: core.GREETING_ID }, "El saludo"),
    app.data.phrases.map((p) => h("option", { value: p.id }, p.es_text)),
  );

  async function run(scope) {
    const body = { token: input.value.trim(), scope };
    if (scope === "phrase") body.phrase_id = phraseSelect.value;
    try {
      const preview = await api("./api/withdraw", { method: "POST", body: { ...body, dry_run: true } });
      if (!preview.recordings) {
        toast(scope === "phrase" ? "No hay grabaciones suyas de esa frase." : "Ya no hay grabaciones suyas que retirar.");
        return;
      }
      const ok = await confirmDialog({
        title: scope === "voice" ? "¿Retirar toda su voz?" : "¿Retirar esta frase?",
        body: `Se borrarán ${preview.recordings} grabación(es) del servidor. Los teléfonos las borran en su siguiente conexión. No se puede deshacer.`,
        okLabel: "Retirar",
        danger: true,
      });
      if (!ok) return;
      const result = await api("./api/withdraw", { method: "POST", body: { ...body, dry_run: false } });
      if (scope === "voice") forgetToken("nepantla.retiro");
      stage.replaceChildren(
        h("div", { class: "aviso calma" }, icon("ok"), h("span", null, h("strong", null, "Listo. "), `Se borraron ${result.recordings} grabación(es). Gracias por haber participado.`)),
      );
    } catch (error) {
      toast(error.status === 404 ? "No reconocemos ese código. Revise que esté completo." : errorText(error));
    }
  }

  stage.append(
    h("div", { class: "campo" }, h("label", { for: "codigo" }, "Su código de retiro"), input),
    button("Retirar toda mi voz", { iconName: "borrar", cls: "btn btn-rojo btn-ancho", onclick: () => run("voice") }),
    h(
      "fieldset",
      null,
      h("legend", null, "O retirar solo una frase"),
      h("div", { class: "campo" }, h("label", { for: "retiro-frase" }, "Frase"), phraseSelect),
      button("Retirar esta frase", { iconName: "borrar", cls: "btn btn-linea btn-chico", onclick: () => run("phrase") }),
    ),
  );
  return shell(
    "Retirar mi voz",
    h("p", null, "Su voz es suya. Con el código que recibió al aceptar el consentimiento puede retirarla cuando quiera, sin dar explicaciones."),
    stage,
    h("p", { class: "menor" }, "¿Perdió su código? Escriba a la coordinación del proyecto o a los guardianes de su paquete: ellos también pueden retirar sus frases."),
  );
}

/* ---------------------------------------------------------- Coordinación */

let adminToken = "";

export async function viewAdmin(app) {
  if (!adminToken) {
    const input = h("input", { id: "admin-token", type: "password", autocomplete: "off", required: true });
    return shell(
      "Coordinación del estudio",
      h("p", null, "Esta pantalla es para quien coordina el proyecto: crea paquetes y manda enlaces a hablantes, revisores y guardianes."),
      h(
        "form",
        {
          onsubmit: (event) => {
            event.preventDefault();
            adminToken = input.value.trim();
            app.render();
          },
        },
        h("div", { class: "campo" }, h("label", { for: "admin-token" }, "Token de administración"), input, h("span", { class: "menor" }, "Es el valor de NEPANTLA_ADMIN_TOKEN en el servidor. No se guarda en este navegador.")),
        h("button", { class: "btn btn-ancho", type: "submit" }, "Entrar"),
      ),
    );
  }

  let overview;
  try {
    overview = await api("./api/studio/admin/overview", { token: adminToken });
  } catch (error) {
    adminToken = "";
    return shell("Coordinación del estudio", h("div", { class: "aviso rojo" }, icon("alarma"), h("span", null, errorText(error))), linkButton("Intentar otra vez", "#/admin", { cls: "btn btn-linea btn-ancho", onclick: () => setTimeout(() => app.render()) }));
  }
  const post = async (path, body, okMessage) => {
    try {
      const result = await api(path, { method: "POST", token: adminToken, body });
      if (okMessage) toast(okMessage);
      return result;
    } catch (error) {
      toast(errorText(error));
      return null;
    }
  };
  const field = (id, label, attrs = {}) => h("div", { class: "campo" }, h("label", { for: id }, label), h("input", { id, name: id, autocomplete: "off", ...attrs }));

  const packForm = h(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        const data = new FormData(packForm);
        const text = (key) => String(data.get(key) || "").trim();
        const created = await post(
          "./api/studio/packs",
          {
            pack_id: text("p-id"),
            language: text("p-lengua"),
            variant: text("p-variante"),
            community: text("p-comunidad"),
            region: text("p-region"),
            license: text("p-licencia"),
            community_label: text("p-etiqueta") || null,
            guardians: text("p-guardianes").split(",").map((x) => x.trim()).filter(Boolean),
          },
          "Paquete creado en borrador.",
        );
        if (created) app.render();
      },
    },
    h(
      "fieldset",
      null,
      h("legend", null, "Crear paquete"),
      field("p-id", "Código (minúsculas, números y guiones)", { required: true, pattern: "[a-z0-9][a-z0-9\\-]{1,62}[a-z0-9]", placeholder: "nah-central-001" }),
      field("p-lengua", "Lengua", { required: true, maxlength: 80 }),
      field("p-variante", "Variante", { required: true, maxlength: 80 }),
      field("p-comunidad", "Comunidad", { maxlength: 120 }),
      field("p-region", "Región donde se habla (municipio, estado o región)", { maxlength: 120 }),
      field("p-licencia", "Licencia elegida por la comunidad", { maxlength: 120 }),
      field("p-etiqueta", "Etiqueta comunitaria (opcional)", { maxlength: 120 }),
      field("p-guardianes", "Guardianes (nombres o seudónimos, separados por comas)"),
      h("button", { class: "btn btn-chico", type: "submit" }, "Crear paquete"),
    ),
  );

  const packCards = overview.packs.map((pack) => {
    const out = h("div", { "aria-live": "polite" });
    const linkForm = h(
      "form",
      {
        onsubmit: async (event) => {
          event.preventDefault();
          const data = new FormData(linkForm);
          const created = await post("./api/studio/session", {
            pack_id: pack.pack_id,
            role: data.get("rol"),
            alias: String(data.get("alias") || "").trim(),
            is_interpreter: data.get("interprete") === "on",
            days: parseInt(data.get("dias"), 10) || 30,
          });
          if (created) {
            out.replaceChildren(
              h("div", { class: "aviso" }, icon("enlace"), h("span", null, `Enlace para ${created.alias}. Mándelo por un medio privado: solo se muestra esta vez.`)),
              tokenBox(absolute(`#/estudio/${created.token}`), "Enlace personal"),
            );
            linkForm.reset();
          }
        },
      },
      h(
        "fieldset",
        null,
        h("legend", null, "Crear enlace personal"),
        h(
          "div",
          { class: "campo" },
          h("label", { for: `rol-${pack.pack_id}` }, "Para"),
          h("select", { id: `rol-${pack.pack_id}`, name: "rol" }, h("option", { value: "speaker" }, "Hablante (graba)"), h("option", { value: "reviewer" }, "Revisor (aprueba o rechaza)"), h("option", { value: "guardian" }, "Guardián del paquete")),
        ),
        h("div", { class: "campo" }, h("label", { for: `alias-${pack.pack_id}` }, "Nombre o seudónimo"), h("input", { id: `alias-${pack.pack_id}`, name: "alias", required: true, maxlength: 80, autocomplete: "off" })),
        h("label", { class: "casilla" }, h("input", { type: "checkbox", name: "interprete" }), h("span", null, "Es intérprete de esta lengua (solo para revisores)")),
        h("div", { class: "campo" }, h("label", { for: `dias-${pack.pack_id}` }, "Días de vigencia"), h("input", { id: `dias-${pack.pack_id}`, name: "dias", type: "number", min: 1, max: 180, value: 30 })),
        h("button", { class: "btn btn-chico", type: "submit" }, "Crear enlace"),
      ),
    );
    const sessions = pack.sessions.map((sessionRow) =>
      h(
        "tr",
        null,
        h("td", null, sessionRow.alias),
        h("td", null, `${ROLE_ES[sessionRow.role]}${sessionRow.is_interpreter ? " (intérprete)" : ""}`),
        h("td", null, sessionRow.revoked ? "Revocado" : `Vence ${sessionRow.expires_at.slice(0, 10)}`),
        h(
          "td",
          null,
          sessionRow.revoked
            ? null
            : button("Revocar", {
                cls: "btn btn-linea btn-chico",
                onclick: async () => {
                  if (await post(`./api/studio/session/${sessionRow.session_id}/revoke`, undefined, "Enlace revocado.")) app.render();
                },
              }),
        ),
      ),
    );
    return h(
      "li",
      { class: `paquete ${pack.is_test ? "prueba" : ""}`.trim() },
      h("div", { class: "paquete-cabeza" }, icon("paquete"), h("h2", null, core.packTitle(pack))),
      dataList([
        ["Código", pack.pack_id],
        ["Estado", pack.status === "approved" ? "Publicado" : pack.status === "withdrawn" ? "Retirado" : "Borrador"],
        ["Versión", pack.version],
        ["Doble revisión", `${pack.coverage.approved} de ${pack.coverage.total_phrases}`],
        ["En revisión", String(pack.coverage.pending)],
        ["Reportes abiertos", String(pack.open_reports)],
      ]),
      sessions.length ? h("div", { class: "desliza" }, h("table", { class: "tabla" }, h("thead", null, h("tr", null, h("th", null, "Persona"), h("th", null, "Papel"), h("th", null, "Enlace"), h("th", null, ""))), h("tbody", null, sessions))) : null,
      pack.status === "withdrawn" ? null : linkForm,
      out,
    );
  });

  const usageRows = overview.usage.map((row) => h("tr", null, h("td", null, row.day), h("td", null, row.pack_id), h("td", null, row.event), h("td", null, String(row.n))));

  return shell(
    "Coordinación del estudio",
    dataList([
      ["Modo del servidor", overview.dev_mode ? "Demostración (se ven paquetes de prueba)" : "Normal"],
      ["Conversión de audio", overview.ffmpeg ? "Lista (ffmpeg instalado)" : "Falta ffmpeg: no se puede grabar"],
    ]),
    packForm,
    h("h2", null, "Paquetes"),
    packCards.length ? h("ul", { class: "paquetes" }, packCards) : h("p", { class: "menor" }, "Todavía no hay paquetes."),
    h("h2", null, "Uso (solo conteos por día)"),
    usageRows.length
      ? h("div", { class: "desliza" }, h("table", { class: "tabla" }, h("thead", null, h("tr", null, h("th", null, "Día"), h("th", null, "Paquete"), h("th", null, "Evento"), h("th", null, "Veces"))), h("tbody", null, usageRows)))
      : h("p", { class: "menor" }, "Sin conteos todavía."),
    button("Salir de coordinación", { cls: "btn btn-linea btn-chico", onclick: () => { adminToken = ""; app.go("#/"); } }),
  );
}
