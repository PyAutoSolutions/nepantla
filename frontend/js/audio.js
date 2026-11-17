/* Nepantla: reproducción de audio.

   Regla del proyecto: aquí solo suenan grabaciones guardadas en el teléfono
   (o, en el estudio, la grabación que se está revisando). No existe ninguna
   voz sintética ni lectura automática de texto. */

import * as store from "./store.js";

const player = new Audio();
player.preload = "auto";

let currentUrl = null;
let settle = null;

function release() {
  if (currentUrl) {
    URL.revokeObjectURL(currentUrl);
    currentUrl = null;
  }
}

/** Detiene lo que esté sonando. */
export function stop() {
  player.pause();
  if (settle) settle("stopped");
}

/** ¿Este navegador puede reproducir Opus dentro de Ogg? */
export function canPlayOpus() {
  return player.canPlayType('audio/ogg; codecs="opus"') !== "";
}

/** Reproduce un audio desde memoria y avisa cuando termina.
    Resuelve con "ended", "stopped" o "error". */
export function playBuffer(data, type = "audio/ogg") {
  stop();
  release();
  return new Promise((resolve) => {
    const done = (how) => {
      if (settle !== done) return;
      settle = null;
      player.removeEventListener("ended", onEnded);
      player.removeEventListener("error", onError);
      resolve(how);
    };
    const onEnded = () => done("ended");
    const onError = () => done("error");
    settle = done;
    currentUrl = URL.createObjectURL(data instanceof Blob ? data : new Blob([data], { type }));
    player.addEventListener("ended", onEnded);
    player.addEventListener("error", onError);
    player.src = currentUrl;
    const started = player.play();
    if (started && typeof started.catch === "function") started.catch(() => done("error"));
  });
}

/** Reproduce una frase de un paquete guardado. Devuelve "missing" si no está. */
export async function playPhrase(packId, phraseId) {
  let data = null;
  try {
    data = await store.getAudio(packId, phraseId);
  } catch {
    data = null;
  }
  if (!data) return "missing";
  return playBuffer(data);
}

/** Para las pruebas automáticas: saber si algo está sonando. */
export function isPlaying() {
  return !player.paused && !player.ended;
}
