/* Nepantla: service worker (modo sin internet).

   Guarda el "cascarón" de la app: HTML, JS, CSS, letras, pictogramas y las
   frases en español. Los audios de cada lengua NO pasan por aquí: los guarda
   la propia app en IndexedDB cuando alguien toca "Guardar para usar sin
   internet".

   Las llamadas a /api/ nunca se guardan ni se responden desde caché.

   `__BUILD__` lo sustituye el servidor por la huella del despliegue, así cada
   versión nueva estrena su propia caché. La lista SHELL se regenera con
   `python scripts/update_shell.py` y una prueba avisa si quedó incompleta. */

const BUILD = "__BUILD__";
const CACHE = `nepantla-${BUILD}`;

const SHELL = [
  "./",
  "./index.html",
  "./app.js",
  "./css/app.css",
  "./manifest.webmanifest",
  "./data/phrases.es.json",
  "./fonts/atkinson-hyperlegible-400.woff2",
  "./fonts/atkinson-hyperlegible-700.woff2",
  "./icons/apple-touch-icon.png",
  "./icons/favicon.svg",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./icons/pictos.svg",
  "./js/audio.js",
  "./js/bodymap.js",
  "./js/config.js",
  "./js/core.js",
  "./js/dom.js",
  "./js/net.js",
  "./js/store.js",
  "./js/views-consult.js",
  "./js/views-packs.js",
  "./js/views-studio.js",
  "./vendor/qrcode.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL.map((url) => new Request(url, { cache: "reload" })))),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("nepantla-") && key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

/* La página decide cuándo estrenar la versión nueva (nunca a media consulta). */
self.addEventListener("message", (event) => {
  if (event.data === "activar") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const path = url.pathname.slice(new URL("./", self.location).pathname.length - 1);
  if (path.startsWith("/api/") || path.startsWith("/audio/") || path === "/sw.js") return;

  if (request.mode === "navigate") {
    event.respondWith(
      caches.match("./index.html", { cacheName: CACHE }).then((cached) => cached || fetch(request)),
    );
    return;
  }
  event.respondWith(
    caches.match(request, { cacheName: CACHE, ignoreSearch: true }).then((cached) => cached || fetch(request)),
  );
});
