/* Nepantla: todo lo que habla con el servidor.

   Decisiones de privacidad:
   * Al servidor solo viajan tres cosas: la descarga de paquetes, los
     contadores agregados y los reportes de audio incorrecto. Nunca una
     respuesta, un resumen ni nada escrito sobre un paciente.
   * Los contadores no se mandan en el momento del evento. Se juntan en el
     teléfono y salen en lote al abrir la app o al volver la conexión, así ni
     la hora del envío delata cuándo fue una consulta.
   * Todas las direcciones son relativas: no existe ningún otro servidor. */

import { STATIC_DEMO } from "./config.js";
import * as store from "./store.js";
import { audioSignature, audioUrl, diffManifest, packTitle, packVisible, playableEntries } from "./core.js";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function detailText(payload, fallback) {
  if (payload && typeof payload.detail === "string") return payload.detail;
  if (payload && Array.isArray(payload.detail) && payload.detail.length) {
    return "Hay un dato que no es válido. Revise lo que escribió.";
  }
  return fallback;
}

/** Petición al API. `token` va en la cabecera, nunca en la dirección. */
export async function api(path, { method = "GET", body, form, token, raw = false, timeout = 20000 } = {}) {
  const headers = { Accept: "application/json" };
  const init = { method, headers, cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (form) init.body = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  init.signal = controller.signal;

  let response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(0, "No hay conexión con el servidor.");
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    throw new ApiError(response.status, detailText(payload, `El servidor respondió con un error (${response.status}).`));
  }
  if (raw) return response;
  if (response.status === 204) return null;
  return response.json();
}

// En la demostración estática la lista de paquetes es un archivo más.
export const fetchPackList = () => api(STATIC_DEMO ? "./api/packs.json" : "./api/packs");
export const fetchManifest = (packId) => api(`./api/packs/${packId}/manifest.json`);
export const fetchHealth = () => api("./api/health");

/* Demostración estática: los audios de un paquete viajan juntos en un solo
   archivo JSON (en base64). Así funciona en cualquier hospedaje de archivos,
   aunque no sepa servir ".opus", y la descarga es una sola petición. */
async function fetchStaticAudio(packId) {
  const bundle = await api(`./api/packs/${packId}/audio.json`);
  return (bundle && bundle.audio) || {};
}

function decodeBase64(text) {
  const binary = atob(text);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

/** "Guardar para usar sin internet": baja lo que falte y lo guarda de una vez. */
export async function downloadPack(packId, onProgress = () => {}) {
  const manifest = await fetchManifest(packId);
  const local = await store.getPack(packId);
  const have = local ? { ...local.have } : {};
  const { remove, missing } = diffManifest(have, manifest);
  const wanted = playableEntries(manifest);
  const audios = [];
  const queue = [...missing];
  let done = 0;
  onProgress(0, missing.length);
  const bundle = STATIC_DEMO && missing.length ? await fetchStaticAudio(packId) : null;

  async function fetchAudio(id) {
    if (!bundle) return (await api(audioUrl(packId, id), { raw: true })).arrayBuffer();
    if (typeof bundle[id] !== "string") throw new ApiError(0, "A la demostración le falta un audio.");
    return decodeBase64(bundle[id]);
  }

  async function worker() {
    while (queue.length) {
      const id = queue.shift();
      const entry = wanted.get(id);
      const data = await fetchAudio(id);
      if (entry.bytes && data.byteLength !== entry.bytes) {
        throw new ApiError(0, "Un audio llegó incompleto. Inténtelo otra vez.");
      }
      audios.push({ phrase_id: id, data });
      done += 1;
      onProgress(done, missing.length);
    }
  }
  await Promise.all(Array.from({ length: Math.min(4, queue.length) }, worker));

  for (const id of remove) delete have[id];
  for (const item of audios) have[item.phrase_id] = audioSignature(wanted.get(item.phrase_id));
  const record = { pack_id: packId, manifest, have, saved_at: new Date().toISOString().slice(0, 10) };
  await store.savePack(record, audios, remove);
  await store.askPersistence();
  return record;
}

/** Compara lo guardado con el servidor. Se llama al abrir la app con internet.
    * Paquete retirado -> se borra del teléfono.
    * Voz o frase retirada -> se borra ese audio en este momento.
    * Audios nuevos -> se avisa para que el personal decida cuándo actualizar. */
export async function syncPacks() {
  const list = await fetchPackList();
  const result = { devMode: Boolean(list.dev_mode), server: list.packs, removed: [], trimmed: [], updates: [] };
  const remoteById = new Map(list.packs.map((p) => [p.pack_id, p]));
  const withdrawn = new Set(list.withdrawn || []);

  for (const record of await store.listPacks()) {
    const id = record.pack_id;
    const title = packTitle(record.manifest);
    if (withdrawn.has(id)) {
      await store.deletePack(id);
      result.removed.push({ id, title, reason: "withdrawn" });
      continue;
    }
    const remote = remoteById.get(id);
    if (!remote) {
      // Un borrador o un paquete de prueba no puede quedarse en un teléfono
      // cuando el servidor ya no está en modo demostración.
      if (!packVisible(record.manifest, result.devMode)) {
        await store.deletePack(id);
        result.removed.push({ id, title, reason: "hidden" });
      }
      continue;
    }
    let manifest = record.manifest;
    if (remote.version !== manifest.version || remote.status !== manifest.status) {
      manifest = await fetchManifest(id);
    }
    const { remove, missing } = diffManifest(record.have, manifest);
    if (manifest !== record.manifest || remove.length) {
      const have = { ...record.have };
      for (const phraseId of remove) delete have[phraseId];
      await store.savePack({ ...record, manifest, have }, [], remove);
    }
    if (remove.length) result.trimmed.push({ id, title, count: remove.length });
    if (missing.length) result.updates.push({ id, title, count: missing.length });
  }
  return result;
}

/* ---------- Contadores y reportes ---------- */

let flushing = null;

/** Envía en lote lo pendiente. Si no hay red, no pasa nada: se queda guardado. */
export function flushOutbox() {
  if (STATIC_DEMO) return Promise.resolve(); // sin servidor no hay a quién enviarle nada
  if (flushing) return flushing;
  flushing = (async () => {
    if (navigator.onLine === false) return;
    try {
      for (const row of await store.listUsage()) {
        const n = Math.min(row.n, 500);
        try {
          await api("./api/usage", { method: "POST", body: { pack_id: row.pack_id, event: row.event, n } });
          await store.settleUsage(row.key, n);
        } catch (error) {
          // El paquete ya no existe o el dato no es válido: no tiene caso insistir.
          if (error.status === 404 || error.status === 422) await store.settleUsage(row.key, row.n);
          else return;
        }
      }
      for (const report of await store.listReports()) {
        try {
          await api("./api/reports", {
            method: "POST",
            body: { pack_id: report.pack_id, phrase_id: report.phrase_id, reason: report.reason },
          });
          await store.deleteReport(report.key);
        } catch (error) {
          if (error.status === 404 || error.status === 410 || error.status === 422) await store.deleteReport(report.key);
          else return;
        }
      }
    } catch {
      /* sin almacenamiento disponible: no hay nada que enviar */
    }
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}

/** Suma 1 al contador local. No hace ninguna petición de red. */
export async function track(packId, event) {
  if (!packId || STATIC_DEMO) return;
  try {
    await store.addUsage(packId, event);
  } catch {
    /* un contador perdido no debe estorbar a la consulta */
  }
}

/** Reporta un audio incorrecto; si no hay red, queda en espera. */
export async function sendReport(report) {
  if (STATIC_DEMO) return "demo";
  try {
    await api("./api/reports", { method: "POST", body: report });
    return "sent";
  } catch (error) {
    if (error.status === 0 || error.status >= 500 || error.status === 429) {
      await store.queueReport(report);
      return "queued";
    }
    throw error;
  }
}
