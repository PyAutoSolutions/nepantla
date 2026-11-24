/* Nepantla: mapa corporal con un cuerpo humano realista.

   Las imágenes son renders del modelo 3D de MakeHuman (CC0), de mujer y de
   hombre, de frente, de espalda y la cara de cerca. Las zonas salen del mismo
   modelo 3D, así que todo el cuerpo queda cubierto: toque donde toque, hay
   una zona. Cada zona es un botón de verdad: se puede usar con teclado y un
   lector de pantalla dice su nombre. La zona elegida cambia de color Y recibe
   una palomita, para no depender solo del color. */

import { BODY_ZONES, zoneLabel } from "./core.js";
import { CUERPOS } from "./cuerpo-datos.js";
import { h, s } from "./dom.js";

const VIEWS = [
  ["frente", "Frente", "Cuerpo de frente"],
  ["espalda", "Espalda", "Cuerpo de espalda"],
  ["cara", "Cara", "La cara de cerca"],
];
const BODIES = [
  ["mujer", "Mujer"],
  ["hombre", "Hombre"],
];
const WHOLE_BODY = "todo-cuerpo";

/* Solo en memoria mientras la app está abierta: no se guarda en el teléfono. */
let lastBody = "mujer";

function viewFor(selected) {
  const zones = selected.filter((id) => id !== WHOLE_BODY);
  if (zones.length && zones.every((id) => id.startsWith("e-"))) return "espalda";
  if (zones.length && zones.every((id) => id.startsWith("c-"))) return "cara";
  return "frente";
}

function thumb(src) {
  return h("img", { class: "cuerpo-mini", src, alt: "", width: 40, height: 52, decoding: "async", draggable: "false" });
}

/** Crea el mapa. `selected` es la lista de zonas ya elegidas. */
export function createBodyMap({ selected = [], onChange = () => {} } = {}) {
  const chosen = new Set(selected.filter((id) => id in BODY_ZONES));
  let view = viewFor([...chosen]);
  let body = lastBody;

  const canvas = h("div", { class: "cuerpo-lienzo" });
  const chips = h("div", { class: "cuerpo-elegidas", "aria-live": "polite" });
  const viewButtons = {};
  const bodyButtons = {};
  const groups = new Map();

  const changed = () => {
    drawChips();
    onChange([...chosen]);
  };

  function toggle(id) {
    if (chosen.has(id)) chosen.delete(id);
    else chosen.add(id);
    const group = groups.get(id);
    if (group) paint(group);
    wholeButton.setAttribute("aria-pressed", chosen.has(WHOLE_BODY) ? "true" : "false");
    changed();
  }

  function paint(group) {
    const on = chosen.has(group.dataset.zona);
    group.setAttribute("aria-pressed", on ? "true" : "false");
    group.querySelector(".zona").classList.toggle("elegida", on);
    for (const old of group.querySelectorAll(".zona-palomita, .zona-palomita-fondo")) old.remove();
    if (on) {
      const [x, y] = group._mark;
      const d = `M${x - 8} ${y}l5.5 6.5 11-13`;
      group.append(s("path", { class: "zona-palomita-fondo", d }), s("path", { class: "zona-palomita", d }));
    }
  }

  function draw() {
    const data = CUERPOS[body][view];
    const what = view === "cara" ? "Cara vista de cerca" : `Cuerpo de ${body} visto ${view === "frente" ? "de frente" : "de espalda"}`;
    const svg = s("svg", {
      viewBox: `0 0 ${data.w} ${data.h}`,
      role: "group",
      "aria-label": `${what}. Toque donde le duele.`,
      dataset: { cuerpo: body, vista: view },
    });
    svg.append(s("image", { href: data.img, x: 0, y: 0, width: data.w, height: data.h, class: "cuerpo-foto", "aria-hidden": "true" }));
    groups.clear();
    for (const [id, d, x, y] of data.zonas) {
      const group = s(
        "g",
        { role: "button", tabindex: 0, "aria-label": zoneLabel(id), "aria-pressed": "false", dataset: { zona: id } },
        s("path", { class: "zona", d }),
      );
      group._mark = [x, y];
      group.addEventListener("click", () => toggle(id));
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggle(id);
        }
      });
      groups.set(id, group);
      svg.append(group);
      paint(group);
    }
    canvas.replaceChildren(svg);
    for (const [name, node] of Object.entries(viewButtons)) {
      node.setAttribute("aria-pressed", name === view ? "true" : "false");
      node.querySelector("img").src = CUERPOS[body][name].img;
    }
    for (const [name, node] of Object.entries(bodyButtons)) node.setAttribute("aria-pressed", name === body ? "true" : "false");
    wholeButton.querySelector("img").src = CUERPOS[body].frente.img;
  }

  function drawChips() {
    chips.replaceChildren(
      ...[...chosen].map((id) =>
        h(
          "button",
          {
            class: "chip chip-quitar",
            type: "button",
            "aria-label": `Quitar: ${zoneLabel(id)}`,
            onclick: () => {
              toggle(id);
              chips.querySelector("button")?.focus();
            },
          },
          zoneLabel(id),
          h("span", { "aria-hidden": "true" }, " ×"),
        ),
      ),
    );
  }

  for (const [name, label, longLabel] of VIEWS) {
    viewButtons[name] = h(
      "button",
      {
        class: "opcion",
        type: "button",
        "aria-pressed": "false",
        "aria-label": longLabel,
        dataset: { lado: name },
        onclick: () => {
          view = name;
          draw();
        },
      },
      thumb(CUERPOS[body][name].img),
      h("span", { class: "etiqueta-opcion" }, label),
    );
  }
  for (const [name, label] of BODIES) {
    bodyButtons[name] = h(
      "button",
      {
        class: "opcion",
        type: "button",
        "aria-pressed": "false",
        "aria-label": label,
        dataset: { tipo: name },
        onclick: () => {
          body = name;
          lastBody = name;
          draw();
        },
      },
      thumb(CUERPOS[name].frente.img),
      h("span", { class: "etiqueta-opcion" }, label),
    );
  }

  const wholeButton = h(
    "button",
    {
      class: "opcion cuerpo-todo",
      type: "button",
      "aria-pressed": chosen.has(WHOLE_BODY) ? "true" : "false",
      "aria-label": BODY_ZONES[WHOLE_BODY],
      dataset: { zona: WHOLE_BODY },
      onclick: () => toggle(WHOLE_BODY),
    },
    thumb(CUERPOS[body].frente.img),
    h("span", { class: "etiqueta-opcion" }, "Me duele todo el cuerpo"),
  );

  const node = h(
    "div",
    { class: "cuerpo" },
    h(
      "div",
      { class: "cuerpo-controles" },
      h("div", { class: "cuerpo-tipo", role: "group", "aria-label": "Cuerpo" }, ...Object.values(bodyButtons)),
      h("div", { class: "cuerpo-lados", role: "group", "aria-label": "Vista" }, ...Object.values(viewButtons)),
    ),
    canvas,
    wholeButton,
    chips,
  );
  draw();
  drawChips();
  return { node, getSelected: () => [...chosen] };
}
