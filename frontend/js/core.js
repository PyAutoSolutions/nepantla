/* Nepantla: lógica pura.
   Aquí no hay pantalla, ni red, ni almacenamiento: solo reglas. Por eso este
   archivo se puede probar con `node --test` sin abrir un navegador. */

export const GREETING_ID = "greeting";

export const DURATIONS = [
  { id: "hoy", es: "Hoy", icon: "hoy" },
  { id: "dias", es: "Hace días", icon: "dias" },
  { id: "semanas", es: "Hace semanas", icon: "semanas" },
];

export const YES_NO = [
  { id: "si", es: "Sí", icon: "si" },
  { id: "no", es: "No", icon: "no" },
  { id: "nose", es: "No sabe", icon: "duda" },
];

/* Motivos cerrados para reportar un audio. No hay texto libre a propósito:
   un campo abierto es donde terminan escribiéndose datos de pacientes. */
export const REPORT_REASONS = [
  { id: "wrong_meaning", es: "Dice otra cosa" },
  { id: "wrong_variant", es: "Es de otra variante o aquí no se entiende" },
  { id: "bad_audio", es: "Se oye mal, cortado o con ruido" },
  { id: "offensive", es: "Resulta ofensivo o inapropiado" },
  { id: "other", es: "Otro problema" },
];

/* Zonas del mapa corporal. "f-" es de frente y "e-" es de espalda.
   Derecha e izquierda son las del paciente, no las de quien mira. */
export const BODY_ZONES = {
  "f-cabeza": "Cabeza",
  "f-cuello": "Cuello",
  "f-pecho": "Pecho",
  "f-abdomen-alto": "Boca del estómago",
  "f-abdomen-bajo": "Vientre",
  "f-brazo-der": "Brazo derecho",
  "f-brazo-izq": "Brazo izquierdo",
  "f-mano-der": "Mano derecha",
  "f-mano-izq": "Mano izquierda",
  "f-pierna-der": "Pierna derecha",
  "f-pierna-izq": "Pierna izquierda",
  "f-pie-der": "Pie derecho",
  "f-pie-izq": "Pie izquierdo",
  "e-cabeza": "Cabeza (atrás)",
  "e-nuca": "Nuca",
  "e-espalda-alta": "Espalda alta",
  "e-espalda-baja": "Espalda baja (cintura)",
  "e-cadera": "Cadera y glúteos",
  "e-brazo-izq": "Brazo izquierdo (atrás)",
  "e-brazo-der": "Brazo derecho (atrás)",
  "e-mano-izq": "Mano izquierda (dorso)",
  "e-mano-der": "Mano derecha (dorso)",
  "e-pierna-izq": "Pierna izquierda (atrás)",
  "e-pierna-der": "Pierna derecha (atrás)",
  "e-pie-izq": "Talón izquierdo",
  "e-pie-der": "Talón derecho",
};

const norm = (name) => String(name).trim().replace(/\s+/g, " ").toLowerCase();

/** Revisores distintos (sin contar dos veces a la misma persona). */
export function distinctReviewers(list) {
  const seen = new Map();
  for (const name of Array.isArray(list) ? list : []) {
    if (typeof name === "string" && name.trim()) {
      if (!seen.has(norm(name))) seen.set(norm(name), name.trim());
    }
  }
  return [...seen.values()];
}

/** Regla dura del proyecto: sin dos revisores distintos, la frase no existe. */
export function isDoubleReviewed(entry) {
  return Boolean(entry) && distinctReviewers(entry.reviewed_by).length >= 2;
}

/** Entradas del manifest que la app puede usar, saludo incluido. */
export function playableEntries(manifest) {
  const out = new Map();
  if (!manifest) return out;
  for (const entry of manifest.phrases || []) {
    if (entry && typeof entry.id === "string" && isDoubleReviewed(entry)) out.set(entry.id, entry);
  }
  if (isDoubleReviewed(manifest.greeting)) out.set(GREETING_ID, manifest.greeting);
  return out;
}

/** Un paquete en borrador (o de prueba) solo existe en modo demostración. */
export function packVisible(pack, devMode) {
  if (!pack || pack.status === "withdrawn") return false;
  if (pack.is_test) return Boolean(devMode) && pack.status === "draft";
  if (pack.status === "approved") return true;
  return Boolean(devMode) && pack.status === "draft";
}

export function compareVersions(a, b) {
  const parse = (v) => String(v || "0").split(".").map((x) => parseInt(x, 10) || 0);
  const [x, y] = [parse(a), parse(b)];
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    const d = (x[i] || 0) - (y[i] || 0);
    if (d !== 0) return d > 0 ? 1 : -1;
  }
  return 0;
}

/** Huella de una grabación: si cambia, el audio guardado ya no sirve. */
export function audioSignature(entry) {
  return [entry.bytes, entry.approved_at, entry.recorded_by, distinctReviewers(entry.reviewed_by).join("+")].join("|");
}

/** Compara lo guardado en el teléfono con el manifest nuevo del servidor.
    `remove`: audios que hay que borrar ya (voz retirada o regrabada).
    `missing`: audios que faltan por descargar. */
export function diffManifest(have, manifest) {
  const wanted = playableEntries(manifest);
  const remove = [];
  const missing = [];
  for (const id of Object.keys(have || {})) {
    const entry = wanted.get(id);
    if (!entry || audioSignature(entry) !== have[id]) remove.push(id);
  }
  for (const [id, entry] of wanted) {
    if (!have || have[id] !== audioSignature(entry)) missing.push(id);
  }
  return { remove, missing };
}

export function audioUrl(packId, phraseId) {
  return phraseId === GREETING_ID
    ? `./api/packs/${packId}/greeting.opus`
    : `./api/packs/${packId}/audio/${phraseId}.opus`;
}

export function formatBytes(n) {
  const bytes = Number(n) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function packTitle(pack) {
  if (!pack) return "";
  return pack.variant ? `${pack.language}: ${pack.variant}` : pack.language;
}

/* ---------- Frases y recorridos ---------- */

export function indexPhrases(data) {
  const byId = new Map();
  for (const phrase of data.phrases) byId.set(phrase.id, phrase);
  return byId;
}

export function scenarioById(data, id) {
  return data.scenarios.find((s) => s.id === id) || null;
}

/** Lista ordenada de frases de un recorrido ("emergencia" o un escenario). */
export function flowPhrases(data, flowId) {
  if (flowId === "emergencia") {
    const byId = indexPhrases(data);
    return data.emergency.map((id) => byId.get(id)).filter(Boolean);
  }
  return data.phrases.filter((p) => p.scenario === flowId);
}

export function flowTitle(data, flowId) {
  if (flowId === "emergencia") return "Emergencia";
  const scenario = scenarioById(data, flowId);
  return scenario ? scenario.title : "";
}

/** Indicaciones (frases sin respuesta) que pueden ir en la tarjeta de salida. */
export function cardPhrases(data) {
  const pick = (scenario) => data.phrases.filter((p) => p.scenario === scenario && p.answer_type === "none");
  return { medicina: pick("medicinas"), alarma: pick("alarma") };
}

/* ---------- Respuestas y resumen ---------- */

export function isAnswered(answer) {
  if (!answer) return false;
  const v = answer.value;
  return Array.isArray(v) ? v.length > 0 : v !== null && v !== undefined && v !== "";
}

/** Texto en español de una respuesta, para el personal de salud. */
export function answerText(phrase, answer, data) {
  if (!isAnswered(answer)) {
    return phrase.answer_type === "none" ? "Indicación reproducida" : "Sin respuesta";
  }
  const v = answer.value;
  switch (phrase.answer_type) {
    case "yes_no":
      return (YES_NO.find((o) => o.id === v) || { es: "Sin respuesta" }).es;
    case "pictogram":
      return (Array.isArray(v) ? v : [v]).map((id) => (data.options[id] ? data.options[id].es : id)).join(", ");
    case "body_map":
      return (Array.isArray(v) ? v : [v]).map((id) => BODY_ZONES[id] || id).join(", ");
    case "pain_scale":
      return `${Number(v)} de 10`;
    case "duration":
      return (DURATIONS.find((d) => d.id === v) || { es: String(v) }).es;
    default:
      return "Indicación reproducida";
  }
}

export function newSession() {
  return { answers: {}, order: [], interpreterRequested: false, summaryCounted: false, scenariosOpened: [] };
}

/** Guarda o cambia una respuesta sin perder el orden en que se preguntó. */
export function recordAnswer(session, phraseId, patch) {
  const current = session.answers[phraseId] || { value: null, understood: null, plays: 0, notUnderstood: 0 };
  session.answers[phraseId] = { ...current, ...patch };
  if (!session.order.includes(phraseId)) session.order.push(phraseId);
  return session.answers[phraseId];
}

function pad(n) {
  return String(n).padStart(2, "0");
}

export function formatDateTime(date) {
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export const LEGEND = "Comunicación asistida, no es diagnóstico.";

/** Resumen para el médico: preguntas y respuestas en español.
    Solo incluye lo que de verdad pasó en la pantalla: una frase aparece si se
    respondió, si se marcó "entendí / no entendí" o si se reprodujo. */
export function buildSummary({ data, pack, session, now = new Date() }) {
  const byId = indexPhrases(data);
  const lines = [];
  for (const id of session.order) {
    const phrase = byId.get(id);
    const answer = session.answers[id];
    if (!phrase || !answer) continue;
    const touched = isAnswered(answer) || answer.understood !== null || answer.plays > 0;
    if (!touched) continue;
    let note = "";
    let alert = false;
    if (answer.understood === false) {
      note = "Marcó «No entendí». Conviene confirmar con intérprete.";
      alert = true;
    } else if (answer.understood === true) {
      note = "Marcó «Entendí».";
    }
    lines.push({ id, question: phrase.es_text, answer: answerText(phrase, answer, data), note, alert });
  }

  const header = [];
  if (pack) {
    header.push(`Lengua: ${packTitle(pack)} (paquete ${pack.pack_id}, versión ${pack.version})`);
    if (pack.is_test) header.push("ATENCIÓN: se usó un paquete de AUDIO DE PRUEBA. No es una lengua real.");
  }
  header.push(`Intérprete solicitado durante la consulta: ${session.interpreterRequested ? "sí" : "no"}`);

  const footer = [
    "Las respuestas se dieron tocando la pantalla después de escuchar audios grabados por hablantes y revisados por dos personas.",
    "Las frases en español todavía no tienen revisión clínica firmada.",
    "Nepantla ayuda a comunicarse: no sustituye a un intérprete ni hace valoraciones clínicas.",
  ];

  const text = [
    LEGEND.toUpperCase(),
    `Resumen de Nepantla, ${formatDateTime(now)}`,
    ...header,
    "",
    ...(lines.length
      ? lines.map((l, i) => `${i + 1}. ${l.question} R: ${l.answer}${l.note ? ` [${l.note}]` : ""}`)
      : ["(Todavía no hay respuestas.)"]),
    "",
    ...footer,
  ].join("\n");

  return { legend: LEGEND, header, lines, footer, text };
}

/* ---------- Tarjeta de salida y su QR ---------- */

const CARD_ID = /^[a-z]{3}-\d{3}$/;
const PACK_ID = /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/;

/** La tarjeta viaja en la parte de la dirección que va después de "#".
    Esa parte nunca se envía al servidor: el QR no le cuenta nada a nadie. */
export function encodeCard({ packId, phraseIds, days }) {
  const ids = [...new Set(phraseIds)].filter((id) => CARD_ID.test(id)).slice(0, 20);
  const pack = packId && PACK_ID.test(packId) ? packId : "-";
  const tail = Number.isInteger(days) && days >= 1 && days <= 90 ? `/${days}` : "";
  return `#/t/${pack}/${ids.join(".") || "-"}${tail}`;
}

export function decodeCard(hash) {
  const match = /^#\/t\/([a-z0-9-]+)\/([a-z0-9.-]+)(?:\/(\d{1,2}))?$/.exec(String(hash || ""));
  if (!match) return null;
  const [, pack, list, days] = match;
  const phraseIds = list === "-" ? [] : list.split(".").filter((id) => CARD_ID.test(id)).slice(0, 20);
  const n = days ? parseInt(days, 10) : null;
  return {
    packId: pack !== "-" && PACK_ID.test(pack) ? pack : null,
    phraseIds: [...new Set(phraseIds)],
    days: n && n >= 1 && n <= 90 ? n : null,
  };
}

/** Cara de la escala de dolor que acompaña a cada número (0 a 10). */
export function painFace(n) {
  return `cara-${Math.ceil(Math.max(0, Math.min(10, n)) / 2)}`;
}
