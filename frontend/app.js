/* Nepantla: arranque, estado en memoria y navegación.

   Decisión de privacidad más importante de la app: las respuestas de una
   consulta viven en `app.session`, que es una variable en memoria. No se
   escriben en el teléfono ni salen de él. Se borran al tocar "Terminar
   consulta", al cerrar la app o después de 30 minutos sin tocar la pantalla. */

import * as audio from "./js/audio.js";
import { STATIC_BUILD, STATIC_DEMO } from "./js/config.js";
import * as core from "./js/core.js";
import { clear, confirmDialog, h, icon, loadSprite, toast } from "./js/dom.js";
import { flushOutbox, syncPacks } from "./js/net.js";
import * as store from "./js/store.js";
import * as consult from "./js/views-consult.js";
import * as packs from "./js/views-packs.js";

const IDLE_MS = 30 * 60 * 1000;
const FLUSH_EVERY_MS = 6 * 60 * 60 * 1000;

const root = document.getElementById("app");
const main = document.getElementById("contenido");
const topBar = document.getElementById("tope");
const ribbons = document.getElementById("cintas");
const bottomBar = document.getElementById("barra");

/* El estudio de grabación se carga solo cuando hace falta, y necesita servidor. */
const studio = (name) => async (...args) => {
  if (STATIC_DEMO) {
    return {
      title: "Estudio de grabación",
      back: "#/",
      node: h(
        "div",
        { class: "pagina" },
        h("h1", null, "Esto es una demostración"),
        h("p", null, "El estudio de grabación, la revisión y el retiro de voces necesitan el servidor de Nepantla. Esta versión de muestra solo trae la app de consulta con audios de prueba."),
        h("a", { class: "btn btn-ancho", href: "#/" }, "Ir al inicio"),
      ),
    };
  }
  return (await import("./js/views-studio.js"))[name](...args);
};

const ROUTES = [
  [/^#\/?$/, consult.viewHome],
  [/^#\/variante$/, consult.viewVariants],
  [/^#\/escenarios$/, consult.viewScenarios],
  [/^#\/escenario\/([a-z]+)$/, consult.viewScenario],
  [/^#\/frase\/([a-z]+)\/(\d{1,3})$/, consult.viewPhrase],
  [/^#\/emergencia$/, consult.viewEmergency],
  [/^#\/resumen$/, consult.viewSummary],
  [/^#\/interprete$/, consult.viewInterpreter],
  [/^#\/tarjeta$/, consult.viewCardBuilder],
  [/^#\/tarjeta\/ver$/, consult.viewCard],
  [/^#\/t\/.+$/, consult.viewCardFromQr],
  [/^#\/paquetes$/, packs.viewPacks],
  [/^#\/paquete\/([a-z0-9-]+)$/, packs.viewPack],
  [/^#\/ajustes$/, packs.viewSettings],
  [/^#\/como-funciona$/, packs.viewHow],
  [/^#\/privacidad$/, packs.viewPrivacy],
  [/^#\/acerca$/, packs.viewAbout],
  [/^#\/estudio(?:\/([A-Za-z0-9_-]+))?$/, studio("viewStudio")],
  [/^#\/retirar(?:\/([A-Za-z0-9_-]+))?$/, studio("viewWithdraw")],
  [/^#\/admin$/, studio("viewAdmin")],
];

const playableCache = new WeakMap();

export const app = {
  data: null,
  packs: [],
  serverPacks: null,
  devMode: store.settings.get("demo", false) === true,
  online: navigator.onLine !== false,
  build: STATIC_BUILD || null,
  activePackId: null,
  afterVariant: null,
  patientMode: false,
  session: core.newSession(),
  card: { ids: [], days: 0 },

  go(hash) {
    if (location.hash === hash) render();
    else location.hash = hash;
  },
  render: () => render(),

  activePack() {
    return this.packs.find((record) => record.pack_id === this.activePackId) || null;
  },

  /** Frases que este teléfono puede reproducir: doble revisión Y audio guardado. */
  playableSet(record) {
    if (!record) return new Set();
    if (!playableCache.has(record)) {
      const entries = core.playableEntries(record.manifest);
      const set = new Set();
      for (const [id, entry] of entries) if (record.have[id] === core.audioSignature(entry)) set.add(id);
      playableCache.set(record, set);
    }
    return playableCache.get(record);
  },

  playable(phraseId, record = this.activePack()) {
    return this.playableSet(record).has(phraseId);
  },

  async reloadPacks() {
    let records = [];
    try {
      records = await store.listPacks();
    } catch {
      records = [];
    }
    this.packs = records
      .filter((record) => core.packVisible(record.manifest, this.devMode))
      .sort((a, b) => core.packTitle(a.manifest).localeCompare(core.packTitle(b.manifest), "es"));
    if (this.activePackId && !this.activePack()) this.activePackId = null;
    drawRibbons();
  },

  /** Compara con el servidor: borra lo retirado y avisa de actualizaciones. */
  async sync({ quiet = false } = {}) {
    const result = await syncPacks();
    this.devMode = result.devMode;
    this.serverPacks = result.server;
    store.settings.set("demo", result.devMode);
    await this.reloadPacks();
    if (!quiet || result.removed.length) {
      for (const gone of result.removed) {
        toast(
          gone.reason === "withdrawn"
            ? `Sus guardianes retiraron «${gone.title}». Ya se borró de este teléfono.`
            : `«${gone.title}» ya no está publicado y se borró de este teléfono.`,
          { timeout: 12000 },
        );
      }
    }
    if (!quiet && !result.removed.length && result.updates.length) {
      const first = result.updates[0];
      toast(`Hay audios nuevos para «${first.title}».`, { action: "Ver", onAction: () => this.go("#/paquetes"), timeout: 12000 });
    }
    return result;
  },

  setPatientMode(on) {
    this.patientMode = Boolean(on);
    root.classList.toggle("modo-paciente", this.patientMode && root.dataset.vista === "frase");
  },

  /** Termina la consulta: borra respuestas, tarjeta y lengua elegida. */
  async newConsultation({ silent = false } = {}) {
    if (!silent && (this.session.order.length || this.card.ids.length)) {
      const ok = await confirmDialog({
        title: "¿Terminar esta consulta?",
        body: "Se borran las respuestas y la tarjeta. No se pueden recuperar.",
        okLabel: "Terminar y borrar",
        danger: true,
      });
      if (!ok) return false;
    }
    audio.stop();
    this.session = core.newSession();
    this.card = { ids: [], days: 0 };
    this.activePackId = null;
    this.afterVariant = null;
    this.setPatientMode(false);
    if (!silent) {
      toast("Consulta terminada. Las respuestas se borraron.");
      this.go("#/");
    }
    return true;
  },
};

/* ---------------------------------------------------------------- Pantalla */

function drawRibbons() {
  clear(ribbons);
  const active = app.activePack();
  if (active && active.manifest.is_test) {
    ribbons.append(
      h("div", { class: "cinta no-imprimir", role: "note" }, icon("bandera"), h("span", null, "AUDIO DE PRUEBA. No es una lengua real.")),
    );
  } else if (app.devMode) {
    ribbons.append(
      h("div", { class: "cinta no-imprimir", role: "note" }, icon("bandera"), h("span", null, "MODO DEMOSTRACIÓN: este servidor muestra paquetes de prueba.")),
    );
  }
  if (!audio.canPlayOpus()) {
    // Mejor decirlo claro que dejar que un botón de audio no haga nada.
    ribbons.append(
      h("div", { class: "cinta sin-red no-imprimir", role: "alert" }, icon("alarma"), h("span", null, "Este navegador no puede reproducir los audios. Use Chrome o Firefox actualizados.")),
    );
  }
  if (!app.online) {
    ribbons.append(
      h("div", { class: "cinta sin-red no-imprimir", role: "status" }, icon("sin-red"), h("span", null, "Sin internet. Todo sigue funcionando con lo guardado.")),
    );
  }
}

function drawTopBar(view) {
  clear(topBar);
  topBar.hidden = Boolean(view.home);
  if (view.home) return;
  topBar.append(
    view.back ? h("a", { class: "icono-btn", href: view.back, "aria-label": "Atrás" }, icon("atras")) : null,
    h("span", { class: "tope-titulo" }, view.title),
    h("a", { class: "icono-btn", href: "#/", "aria-label": "Ir al inicio" }, icon("inicio")),
  );
}

let cleanup = null;
let renderId = 0;

async function render() {
  const id = (renderId += 1);
  const hash = location.hash || "#/";
  audio.stop();
  if (cleanup) {
    try {
      cleanup();
    } catch {
      /* una pantalla que ya no existe no debe frenar a la siguiente */
    }
    cleanup = null;
  }
  for (const overlay of document.querySelectorAll(".pantalla-completa, dialog")) overlay.remove();

  let view;
  const route = ROUTES.find(([pattern]) => pattern.test(hash));
  try {
    view = route ? await route[1](app, ...hash.match(route[0]).slice(1)) : { redirect: "#/" };
  } catch (error) {
    console.error(error);
    view = {
      title: "Algo falló",
      back: "#/",
      node: h(
        "div",
        { class: "pagina" },
        h("h1", null, "Esta pantalla no se pudo abrir"),
        h("p", null, "Vuelva al inicio. Si necesita comunicarse ahora, pida intérprete."),
        h("a", { class: "btn btn-ancho", href: "#/" }, "Ir al inicio"),
      ),
    };
  }
  if (id !== renderId) return;
  if (view.redirect) {
    location.replace(`${location.pathname}${location.search}${view.redirect}`);
    return;
  }

  cleanup = view.cleanup || null;
  root.dataset.vista = view.phrase ? "frase" : view.home ? "inicio" : "pagina";
  root.classList.toggle("modo-paciente", app.patientMode && Boolean(view.phrase));
  drawRibbons();
  drawTopBar(view);
  bottomBar.hidden = Boolean(view.noBar);
  main.replaceChildren(view.node);
  document.title = view.home ? "Nepantla" : `${view.title} · Nepantla`;
  window.scrollTo(0, 0);
  main.focus({ preventScroll: true });
}

/* --------------------------------------------------- Red, reposo y arranque */

async function goOnline() {
  if (!app.online) return;
  try {
    const result = await app.sync();
    if (result.removed.length) render();
  } catch {
    /* sin servidor: la app sigue con lo guardado */
  }
  flushOutbox();
}

function watchNetwork() {
  window.addEventListener("online", () => {
    app.online = true;
    drawRibbons();
    goOnline();
  });
  window.addEventListener("offline", () => {
    app.online = false;
    drawRibbons();
  });
  setInterval(() => app.online && flushOutbox(), FLUSH_EVERY_MS);
}

/** Si nadie toca la pantalla en 30 minutos, la consulta se borra sola. */
function watchIdle() {
  let timer = null;
  const reset = () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (!app.session.order.length && !app.card.ids.length && !app.activePackId) return;
      await app.newConsultation({ silent: true });
      toast("Por privacidad se borraron las respuestas de la consulta anterior.", { timeout: 15000 });
      app.go("#/");
    }, IDLE_MS);
  };
  for (const type of ["pointerdown", "keydown"]) window.addEventListener(type, reset, { passive: true });
  reset();
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  try {
    const registration = await navigator.serviceWorker.register("./sw.js");
    const offer = (worker) => {
      if (!worker || !navigator.serviceWorker.controller) return;
      toast("Hay una versión nueva de Nepantla.", {
        action: "Actualizar",
        timeout: 0,
        onAction: () => {
          navigator.serviceWorker.addEventListener("controllerchange", () => location.reload(), { once: true });
          worker.postMessage("activar");
        },
      });
    };
    if (registration.waiting) offer(registration.waiting);
    registration.addEventListener("updatefound", () => {
      const worker = registration.installing;
      if (!worker) return;
      worker.addEventListener("statechange", () => worker.state === "installed" && offer(worker));
    });
  } catch {
    /* sin service worker la app funciona, pero solo con internet */
  }
}

async function boot() {
  // Pictogramas y frases se piden al mismo tiempo: una vuelta menos en redes lentas.
  const [, data] = await Promise.all([
    loadSprite().catch(() => null), // sin pictogramas la app sigue siendo utilizable por el personal
    fetch("./data/phrases.es.json")
      .then((response) => (response.ok ? response.json() : null))
      .catch(() => null),
  ]);
  if (!data) {
    main.replaceChildren(
      h(
        "div",
        { class: "pagina" },
        h("h1", null, "Nepantla no pudo abrir"),
        h("p", null, "Falta conexión para la primera carga. Conéctese a internet una vez y vuelva a abrir la app."),
      ),
    );
    return;
  }
  app.data = data;
  await app.reloadPacks();
  window.addEventListener("hashchange", render);
  watchNetwork();
  watchIdle();
  await render();
  registerServiceWorker();
  if (app.online && !STATIC_DEMO) {
    fetch("./api/health", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((health) => {
        if (health) app.build = health.build;
      })
      .catch(() => {});
  }
  goOnline();
}

// Asa para las pruebas automáticas (e2e/): permite preguntar si suena un audio.
window.nepantla = { app, audio };
boot();
