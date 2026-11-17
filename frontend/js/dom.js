/* Nepantla: ayudas para armar la pantalla sin frameworks. */

const SVG_NS = "http://www.w3.org/2000/svg";

/** Crea un elemento. `h("button", { class: "btn", onclick: fn }, "Texto")`. */
export function h(tag, attrs, ...children) {
  const node = document.createElement(tag);
  setAttrs(node, attrs);
  append(node, children);
  return node;
}

/** Igual que `h`, pero para elementos SVG. */
export function s(tag, attrs, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  setAttrs(node, attrs);
  append(node, children);
  return node;
}

function setAttrs(node, attrs) {
  if (!attrs) return;
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2), value);
    } else if (key === "class") {
      node.setAttribute("class", Array.isArray(value) ? value.filter(Boolean).join(" ") : value);
    } else if (key === "dataset") {
      Object.assign(node.dataset, value);
    } else if (value === true) {
      node.setAttribute(key, "");
    } else {
      node.setAttribute(key, String(value));
    }
  }
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

/** Pictograma del sprite. Es decorativo: el texto vecino o `aria-label` lo nombra. */
export function icon(name, extraClass = "") {
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `#${name}`);
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", `ic${extraClass ? ` ${extraClass}` : ""}`);
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.append(use);
  return svg;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

/** Sustituye el contenido de un nodo. A diferencia de `replaceChildren`,
    ignora los valores vacíos (null, false) en lugar de escribirlos. */
export function fill(node, ...children) {
  clear(node);
  append(node, children);
  return node;
}

/** Mete el sprite de pictogramas en la página (una sola petición, queda en caché). */
export async function loadSprite(url = "./icons/pictos.svg") {
  const response = await fetch(url);
  if (!response.ok) throw new Error("No se pudieron cargar los pictogramas.");
  const doc = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
  const svg = doc.documentElement;
  if (!svg || svg.nodeName.toLowerCase() !== "svg") throw new Error("El archivo de pictogramas no es válido.");
  svg.setAttribute("class", "sprite");
  document.body.prepend(document.importNode(svg, true));
}

/* ---------- Avisos para lectores de pantalla ---------- */

let liveRegion = null;

export function announce(message) {
  if (!liveRegion) {
    liveRegion = h("div", { class: "solo-lector", "aria-live": "polite", role: "status" });
    document.body.append(liveRegion);
  }
  liveRegion.textContent = "";
  setTimeout(() => {
    liveRegion.textContent = message;
  }, 50);
}

/* ---------- Aviso flotante ---------- */

let toastTimer = null;

export function toast(message, { action = null, onAction = null, timeout = 5000 } = {}) {
  const host = document.getElementById("flotantes");
  if (!host) return;
  clearTimeout(toastTimer);
  clear(host);
  const close = () => {
    clearTimeout(toastTimer);
    clear(host);
  };
  const box = h(
    "div",
    { class: "flotante no-imprimir", role: "status" },
    h("span", null, message),
    action
      ? h(
          "button",
          {
            class: "btn btn-maiz btn-chico",
            type: "button",
            onclick: () => {
              close();
              if (onAction) onAction();
            },
          },
          action,
        )
      : null,
    h("button", { class: "icono-btn", type: "button", "aria-label": "Cerrar aviso", onclick: close }, icon("no")),
  );
  host.append(box);
  if (timeout) toastTimer = setTimeout(close, timeout);
}

/* ---------- Diálogo de confirmación ---------- */

export function confirmDialog({ title, body = "", okLabel = "Aceptar", cancelLabel = "Cancelar", danger = false }) {
  return new Promise((resolve) => {
    const dialog = h("dialog", { "aria-labelledby": "dialogo-titulo" });
    const finish = (value) => {
      dialog.close();
      dialog.remove();
      resolve(value);
    };
    dialog.append(
      h(
        "div",
        { class: "dialogo-cuerpo" },
        h("h2", { id: "dialogo-titulo" }, title),
        typeof body === "string" ? h("p", null, body) : body,
        h(
          "div",
          { class: "fila" },
          cancelLabel
            ? h("button", { class: "btn btn-linea btn-chico", type: "button", onclick: () => finish(false) }, cancelLabel)
            : null,
          h(
            "button",
            { class: `btn btn-chico ${danger ? "btn-rojo" : ""}`, type: "button", onclick: () => finish(true) },
            okLabel,
          ),
        ),
      ),
    );
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish(false);
    });
    document.body.append(dialog);
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  });
}

/** Copia texto al portapapeles; devuelve si lo logró. */
export async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* seguimos con el método de respaldo */
  }
  const area = h("textarea", { class: "solo-lector", readonly: true, "aria-hidden": "true" });
  area.value = text;
  document.body.append(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  area.remove();
  return ok;
}

/** Botón con pictograma y texto. */
export function button(label, { iconName = null, cls = "btn", ...attrs } = {}) {
  return h("button", { class: cls, type: "button", ...attrs }, iconName ? icon(iconName) : null, h("span", null, label));
}

/** Enlace con forma de botón. */
export function linkButton(label, href, { iconName = null, cls = "btn", ...attrs } = {}) {
  return h("a", { class: cls, href, ...attrs }, iconName ? icon(iconName) : null, h("span", null, label));
}

/** Lista de definiciones a partir de pares [rótulo, valor]. */
export function dataList(rows) {
  const dl = h("dl", { class: "datos" });
  for (const [label, value] of rows) {
    if (value === null || value === undefined || value === "") continue;
    dl.append(h("dt", null, label), h("dd", null, value));
  }
  return dl;
}
