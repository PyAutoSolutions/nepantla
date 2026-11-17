/* Nepantla: mapa corporal (frente y espalda).

   El paciente toca dónde le duele. Cada zona es un botón de verdad: se puede
   usar con teclado y un lector de pantalla dice su nombre. La zona elegida
   cambia de color Y recibe una palomita, para no depender solo del color. */

import { BODY_ZONES } from "./core.js";
import { h, s } from "./dom.js";

const VIEW_BOX = "0 0 200 424";

/* Formas compartidas por las dos vistas. `c` es el centro para la palomita. */
const SHAPES = {
  cabeza: { tag: "circle", attrs: { cx: 100, cy: 34, r: 28 }, c: [100, 34] },
  tronco1: { tag: "path", attrs: { d: "M60 82h80a12 12 0 0 1 12 12v42H48V94a12 12 0 0 1 12-12z" }, c: [100, 110] },
  tronco2: { tag: "rect", attrs: { x: 52, y: 140, width: 96, height: 44, rx: 4 }, c: [100, 162] },
  tronco3: { tag: "path", attrs: { d: "M52 188h96v32a22 22 0 0 1-22 22H74a22 22 0 0 1-22-22z" }, c: [100, 214] },
  cuello: { tag: "rect", attrs: { x: 85, y: 60, width: 30, height: 22, rx: 5 }, c: [100, 71] },
  brazoA: { tag: "rect", attrs: { x: 14, y: 86, width: 30, height: 126, rx: 15 }, c: [29, 150] },
  brazoB: { tag: "rect", attrs: { x: 156, y: 86, width: 30, height: 126, rx: 15 }, c: [171, 150] },
  manoA: { tag: "ellipse", attrs: { cx: 29, cy: 236, rx: 16, ry: 19 }, c: [29, 236] },
  manoB: { tag: "ellipse", attrs: { cx: 171, cy: 236, rx: 16, ry: 19 }, c: [171, 236] },
  piernaA: { tag: "rect", attrs: { x: 52, y: 246, width: 44, height: 138, rx: 16 }, c: [74, 314] },
  piernaB: { tag: "rect", attrs: { x: 104, y: 246, width: 44, height: 138, rx: 16 }, c: [126, 314] },
  pieA: { tag: "rect", attrs: { x: 42, y: 390, width: 54, height: 28, rx: 14 }, c: [69, 404] },
  pieB: { tag: "rect", attrs: { x: 104, y: 390, width: 54, height: 28, rx: 14 }, c: [131, 404] },
};

/* "A" es el lado izquierdo de la pantalla. De frente, ahí queda el lado
   DERECHO del paciente; de espalda, su lado IZQUIERDO. */
const VIEWS = {
  frente: [
    ["f-cabeza", "cabeza"], ["f-pecho", "tronco1"], ["f-abdomen-alto", "tronco2"], ["f-abdomen-bajo", "tronco3"],
    ["f-brazo-der", "brazoA"], ["f-brazo-izq", "brazoB"], ["f-mano-der", "manoA"], ["f-mano-izq", "manoB"],
    ["f-pierna-der", "piernaA"], ["f-pierna-izq", "piernaB"], ["f-pie-der", "pieA"], ["f-pie-izq", "pieB"],
    ["f-cuello", "cuello"],
  ],
  espalda: [
    ["e-cabeza", "cabeza"], ["e-espalda-alta", "tronco1"], ["e-espalda-baja", "tronco2"], ["e-cadera", "tronco3"],
    ["e-brazo-izq", "brazoA"], ["e-brazo-der", "brazoB"], ["e-mano-izq", "manoA"], ["e-mano-der", "manoB"],
    ["e-pierna-izq", "piernaA"], ["e-pierna-der", "piernaB"], ["e-pie-izq", "pieA"], ["e-pie-der", "pieB"],
    ["e-nuca", "cuello"],
  ],
};

/* Rasgos que distinguen el frente de la espalda sin usar texto. */
const DETAILS = {
  frente: ["M89 30v.5M111 30v.5", "M90 44c6 5 14 5 20 0"],
  espalda: ["M74 24c8-12 44-12 52 0", "M100 86v150"],
};

function miniFigure(view) {
  const svg = s("svg", { class: "ic", viewBox: "0 0 48 48", "aria-hidden": "true", focusable: "false" });
  const stroke = { fill: "none", stroke: "currentColor", "stroke-width": 3, "stroke-linecap": "round", "stroke-linejoin": "round" };
  svg.append(
    s("circle", { cx: 24, cy: 10, r: 6.5, ...stroke }),
    s("path", { d: "M12 44V27a7 7 0 0 1 7-7h10a7 7 0 0 1 7 7v17", ...stroke }),
    view === "frente"
      ? s("path", { d: "M21.500 9.500v.5M26.500 9.500v.5M19 30h10", ...stroke })
      : s("path", { d: "M24 22v20M18 6.500c4-3 8-3 12 0", ...stroke }),
  );
  return svg;
}

/** Crea el mapa. `selected` es la lista de zonas ya elegidas. */
export function createBodyMap({ selected = [], onChange = () => {} } = {}) {
  const chosen = new Set(selected);
  let view = selected.length && selected.every((id) => id.startsWith("e-")) ? "espalda" : "frente";

  const canvas = h("div", { class: "cuerpo-lienzo" });
  const chips = h("div", { class: "cuerpo-elegidas", "aria-live": "polite" });
  const sideButtons = {};

  function drawChips() {
    chips.replaceChildren(
      ...[...chosen].map((id) => h("span", { class: "chip" }, BODY_ZONES[id] || id)),
    );
  }

  function toggle(id, group, shapeNode, c) {
    if (chosen.has(id)) chosen.delete(id);
    else chosen.add(id);
    paint(id, group, shapeNode, c);
    drawChips();
    onChange([...chosen]);
  }

  function paint(id, group, shapeNode, c) {
    const on = chosen.has(id);
    group.setAttribute("aria-pressed", on ? "true" : "false");
    shapeNode.classList.toggle("elegida", on);
    const old = group.querySelector(".zona-palomita");
    if (old) old.remove();
    if (on) group.append(s("path", { class: "zona-palomita", d: `M${c[0] - 9} ${c[1]}l6 7 12-14` }));
  }

  function draw() {
    const svg = s("svg", {
      viewBox: VIEW_BOX,
      role: "group",
      "aria-label": view === "frente" ? "Cuerpo visto de frente. Toque donde le duele." : "Cuerpo visto de espalda. Toque donde le duele.",
    });
    for (const [id, shapeName] of VIEWS[view]) {
      const shape = SHAPES[shapeName];
      const visible = s(shape.tag, { class: "zona", ...shape.attrs });
      const touch = s(shape.tag, { class: "zona-toque", ...shape.attrs });
      const group = s("g", { role: "button", tabindex: 0, "aria-label": BODY_ZONES[id], "aria-pressed": "false", dataset: { zona: id } }, visible, touch);
      const act = () => toggle(id, group, visible, shape.c);
      group.addEventListener("click", act);
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          act();
        }
      });
      svg.append(group);
      paint(id, group, visible, shape.c);
    }
    for (const d of DETAILS[view]) svg.append(s("path", { class: "zona-detalle", d }));
    canvas.replaceChildren(svg);
    for (const [name, node] of Object.entries(sideButtons)) node.setAttribute("aria-pressed", name === view ? "true" : "false");
  }

  function sideButton(name, label) {
    const node = h(
      "button",
      {
        class: "opcion",
        type: "button",
        "aria-pressed": "false",
        "aria-label": label,
        dataset: { lado: name },
        onclick: () => {
          view = name;
          draw();
        },
      },
      miniFigure(name),
      h("span", { class: "etiqueta-opcion" }, label),
    );
    sideButtons[name] = node;
    return node;
  }

  const node = h(
    "div",
    { class: "cuerpo" },
    h("div", { class: "cuerpo-lados" }, sideButton("frente", "De frente"), sideButton("espalda", "De espalda")),
    canvas,
    chips,
  );
  draw();
  drawChips();
  return { node, getSelected: () => [...chosen] };
}
