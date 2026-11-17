/* Nepantla: lo que se guarda en el teléfono.

   Decisión de privacidad: aquí solo se guardan cuatro cosas, y ninguna es
   del paciente:
     1. Paquetes de lengua (manifest y audios), para trabajar sin internet.
     2. Contadores de uso pendientes de enviar ("tal paquete, tal evento, N").
     3. Reportes de audio incorrecto pendientes de enviar (paquete, frase y un
        motivo de lista cerrada).
     4. Ajustes de la clínica (contacto del intérprete).
   Las respuestas de una consulta NO pasan por este archivo: viven en la
   memoria de la pantalla y desaparecen al cerrar o al iniciar otra consulta. */

const DB_NAME = "nepantla";
const DB_VERSION = 1;
const PREFIX = "nepantla.";

let dbPromise = null;

function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    if (!("indexedDB" in globalThis)) {
      reject(new Error("Este navegador no permite guardar paquetes."));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("packs")) db.createObjectStore("packs", { keyPath: "pack_id" });
      if (!db.objectStoreNames.contains("audio")) {
        const audio = db.createObjectStore("audio", { keyPath: "key" });
        audio.createIndex("pack_id", "pack_id");
      }
      if (!db.objectStoreNames.contains("usage")) db.createObjectStore("usage", { keyPath: "key" });
      if (!db.objectStoreNames.contains("reports")) db.createObjectStore("reports", { autoIncrement: true });
    };
    request.onsuccess = () => {
      request.result.onversionchange = () => request.result.close();
      resolve(request.result);
    };
    request.onerror = () => reject(request.error || new Error("No se pudo abrir el almacenamiento."));
    request.onblocked = () => reject(new Error("El almacenamiento está ocupado por otra pestaña."));
  }).catch((error) => {
    dbPromise = null;
    throw error;
  });
  return dbPromise;
}

const wrap = (request) =>
  new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

/** Ejecuta `work` dentro de una transacción y espera a que termine entera. */
async function tx(stores, mode, work) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(stores, mode);
    let result;
    transaction.oncomplete = () => resolve(result);
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error || new Error("No se pudo guardar."));
    try {
      result = work(transaction);
    } catch (error) {
      transaction.abort();
      reject(error);
    }
  });
}

const audioKey = (packId, phraseId) => `${packId}/${phraseId}`;

/* ---------- Paquetes ---------- */

export async function listPacks() {
  const db = await openDb();
  return wrap(db.transaction("packs").objectStore("packs").getAll());
}

export async function getPack(packId) {
  const db = await openDb();
  return (await wrap(db.transaction("packs").objectStore("packs").get(packId))) || null;
}

/** Guarda el paquete y sus audios de una sola vez: o entra todo o no entra nada. */
export function savePack(record, audios = [], removeIds = []) {
  return tx(["packs", "audio"], "readwrite", (t) => {
    const audioStore = t.objectStore("audio");
    for (const id of removeIds) audioStore.delete(audioKey(record.pack_id, id));
    for (const item of audios) {
      audioStore.put({ key: audioKey(record.pack_id, item.phrase_id), pack_id: record.pack_id, phrase_id: item.phrase_id, data: item.data });
    }
    t.objectStore("packs").put(record);
  });
}

export function deletePack(packId) {
  return tx(["packs", "audio"], "readwrite", (t) => {
    t.objectStore("packs").delete(packId);
    const index = t.objectStore("audio").index("pack_id");
    const cursorRequest = index.openKeyCursor(IDBKeyRange.only(packId));
    cursorRequest.onsuccess = () => {
      const cursor = cursorRequest.result;
      if (cursor) {
        t.objectStore("audio").delete(cursor.primaryKey);
        cursor.continue();
      }
    };
  });
}

export async function getAudio(packId, phraseId) {
  const db = await openDb();
  const row = await wrap(db.transaction("audio").objectStore("audio").get(audioKey(packId, phraseId)));
  return row ? row.data : null;
}

/* ---------- Contadores de uso (se envían en lote cuando hay red) ---------- */

export function addUsage(packId, event) {
  const key = `${packId}|${event}`;
  return tx(["usage"], "readwrite", (t) => {
    const store = t.objectStore("usage");
    const request = store.get(key);
    request.onsuccess = () => {
      const row = request.result || { key, pack_id: packId, event, n: 0 };
      row.n += 1;
      store.put(row);
    };
  });
}

export async function listUsage() {
  const db = await openDb();
  return wrap(db.transaction("usage").objectStore("usage").getAll());
}

/** Resta lo que ya se envió (puede haber llegado un conteo nuevo mientras tanto). */
export function settleUsage(key, sent) {
  return tx(["usage"], "readwrite", (t) => {
    const store = t.objectStore("usage");
    const request = store.get(key);
    request.onsuccess = () => {
      const row = request.result;
      if (!row) return;
      row.n -= sent;
      if (row.n > 0) store.put(row);
      else store.delete(key);
    };
  });
}

/* ---------- Reportes pendientes ---------- */

export function queueReport(report) {
  return tx(["reports"], "readwrite", (t) => {
    t.objectStore("reports").add({ pack_id: report.pack_id, phrase_id: report.phrase_id, reason: report.reason });
  });
}

export async function listReports() {
  const db = await openDb();
  const t = db.transaction("reports");
  const [keys, values] = await Promise.all([wrap(t.objectStore("reports").getAllKeys()), wrap(t.objectStore("reports").getAll())]);
  return keys.map((key, i) => ({ key, ...values[i] }));
}

export function deleteReport(key) {
  return tx(["reports"], "readwrite", (t) => {
    t.objectStore("reports").delete(key);
  });
}

/* ---------- Ajustes pequeños ---------- */

export const settings = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem(PREFIX + key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(PREFIX + key, JSON.stringify(value));
      return true;
    } catch {
      return false;
    }
  },
  remove(key) {
    try {
      localStorage.removeItem(PREFIX + key);
    } catch {
      /* sin almacenamiento local no hay nada que borrar */
    }
  },
};

/** Pide al navegador que no borre los paquetes cuando falte espacio. */
export async function askPersistence() {
  try {
    if (navigator.storage && navigator.storage.persist) return await navigator.storage.persist();
  } catch {
    /* el navegador decide; no es un error de la app */
  }
  return false;
}

export async function storageEstimate() {
  try {
    if (navigator.storage && navigator.storage.estimate) return await navigator.storage.estimate();
  } catch {
    /* sin estimación */
  }
  return null;
}

/** Borra TODO lo que Nepantla guardó en este teléfono. */
export async function wipeAll() {
  try {
    const db = await openDb();
    db.close();
  } catch {
    /* si no abría, igual intentamos borrarla */
  }
  dbPromise = null;
  await new Promise((resolve) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = request.onerror = request.onblocked = () => resolve();
  });
  try {
    for (const key of Object.keys(localStorage)) if (key.startsWith(PREFIX)) localStorage.removeItem(key);
    for (const key of Object.keys(sessionStorage)) if (key.startsWith(PREFIX)) sessionStorage.removeItem(key);
  } catch {
    /* nada más que limpiar */
  }
}
