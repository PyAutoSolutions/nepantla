// Pruebas de la lógica pura de la app (sin navegador).
//
//     node --test tests_js/core.test.mjs
//
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import * as core from "../frontend/js/core.js";

const data = JSON.parse(readFileSync(new URL("../frontend/data/phrases.es.json", import.meta.url), "utf-8"));

const entry = (id, reviewers, extra = {}) => ({
  id,
  audio: `audio/${id}.opus`,
  reviewed_by: reviewers,
  recorded_by: "Hablante Uno",
  approved_at: "2026-12-01",
  bytes: 2000,
  ...extra,
});

test("sin dos revisores distintos la frase no existe", () => {
  assert.equal(core.isDoubleReviewed(entry("urg-001", ["Ana", "Luz"])), true);
  assert.equal(core.isDoubleReviewed(entry("urg-001", ["Ana"])), false);
  assert.equal(core.isDoubleReviewed(entry("urg-001", ["Ana", " ana "])), false, "la misma persona no cuenta dos veces");
  assert.equal(core.isDoubleReviewed(entry("urg-001", [])), false);
  assert.equal(core.isDoubleReviewed(null), false);

  const manifest = {
    phrases: [entry("urg-001", ["Ana", "Luz"]), entry("urg-002", ["Ana"])],
    greeting: entry("greeting", ["Ana", "Luz"]),
  };
  assert.deepEqual([...core.playableEntries(manifest).keys()], ["urg-001", "greeting"]);
});

test("un borrador o un paquete de prueba solo se ve en modo demostración", () => {
  const approved = { status: "approved", is_test: false };
  const draft = { status: "draft", is_test: false };
  const testPack = { status: "draft", is_test: true };
  assert.equal(core.packVisible(approved, false), true);
  assert.equal(core.packVisible(draft, false), false);
  assert.equal(core.packVisible(draft, true), true);
  assert.equal(core.packVisible(testPack, false), false);
  assert.equal(core.packVisible(testPack, true), true);
  // Aunque alguien lo marcara "aprobado", el audio de prueba nunca pasa por lengua real.
  assert.equal(core.packVisible({ status: "approved", is_test: true }, false), false);
  assert.equal(core.packVisible({ status: "withdrawn", is_test: false }, true), false);
});

test("al cambiar el manifest se borra la voz retirada y se pide lo nuevo", () => {
  const first = { phrases: [entry("urg-001", ["Ana", "Luz"]), entry("urg-002", ["Ana", "Luz"])], greeting: null };
  const have = {};
  for (const [id, e] of core.playableEntries(first)) have[id] = core.audioSignature(e);
  assert.deepEqual(core.diffManifest(have, first), { remove: [], missing: [] });

  const second = {
    phrases: [
      entry("urg-002", ["Ana", "Luz"], { recorded_by: "Hablante Dos", bytes: 2100 }), // regrabada por otra persona
      entry("urg-003", ["Ana", "Luz"]), // nueva
    ],
    greeting: null,
  }; // urg-001 fue retirada
  const diff = core.diffManifest(have, second);
  assert.deepEqual(diff.remove.sort(), ["urg-001", "urg-002"]);
  assert.deepEqual(diff.missing.sort(), ["urg-002", "urg-003"]);
});

test("las versiones se comparan por números", () => {
  assert.equal(core.compareVersions("0.10.0", "0.9.9"), 1);
  assert.equal(core.compareVersions("1.0.0", "1.0.0"), 0);
  assert.equal(core.compareVersions("0.1.9", "0.2.0"), -1);
});

test("la tarjeta viaja completa en el QR y no acepta basura", () => {
  const hash = core.encodeCard({ packId: "nah-central-001", phraseIds: ["med-008", "ala-001", "med-008"], days: 3 });
  assert.equal(hash, "#/t/nah-central-001/med-008.ala-001/3");
  assert.deepEqual(core.decodeCard(hash), { packId: "nah-central-001", phraseIds: ["med-008", "ala-001"], days: 3 });
  assert.deepEqual(core.decodeCard("#/t/-/-"), { packId: null, phraseIds: [], days: null });
  assert.equal(core.decodeCard("#/t/<script>/x"), null);
  assert.equal(core.decodeCard("#/resumen"), null);
  // Nada que no sea un identificador de frase cabe en la tarjeta.
  assert.equal(core.encodeCard({ packId: null, phraseIds: ["Juan Pérez", "med-008"], days: 0 }), "#/t/-/med-008");
});

test("el modo emergencia abre cinco preguntas de sí o no", () => {
  const flow = core.flowPhrases(data, "emergencia");
  assert.equal(flow.length, 5);
  assert.ok(flow.every((p) => p.answer_type === "yes_no" && p.priority === "critica"));
  assert.equal(core.flowTitle(data, "emergencia"), "Emergencia");
  assert.equal(core.flowPhrases(data, "urgencias")[0].id, "urg-001");
});

test("las respuestas se dicen en español sencillo", () => {
  const byId = core.indexPhrases(data);
  assert.equal(core.answerText(byId.get("urg-001"), { value: "si" }, data), "Sí");
  assert.equal(core.answerText(byId.get("urg-001"), { value: "nose" }, data), "No sabe");
  assert.equal(core.answerText(byId.get("urg-004"), { value: ["sintoma-dolor", "sintoma-tos"] }, data), "Dolor, Tos");
  assert.equal(core.answerText(byId.get("urg-005"), { value: ["f-pecho", "e-espalda-baja"] }, data), "Centro del pecho, Espalda baja (cintura)");
  assert.equal(core.answerText(byId.get("urg-006"), { value: 0 }, data), "0 de 10");
  assert.equal(core.answerText(byId.get("urg-007"), { value: "semanas" }, data), "Hace semanas");
  assert.equal(core.answerText(byId.get("urg-001"), { value: null }, data), "Sin respuesta");
  assert.equal(core.answerText(byId.get("ala-008"), { value: null }, data), "Indicación reproducida");
});

test("el resumen lleva la leyenda, el orden y los avisos", () => {
  const session = core.newSession();
  core.recordAnswer(session, "urg-002", { value: "no" });
  core.recordAnswer(session, "urg-001", { value: "si", understood: true });
  core.recordAnswer(session, "urg-008", { understood: false, notUnderstood: 1 });
  core.recordAnswer(session, "urg-002", { value: "si" }); // corrige sin cambiar el orden
  session.interpreterRequested = true;
  const pack = { pack_id: "nah-central-001", language: "Náhuatl", variant: "Centro", version: "1.2.0", is_test: false };
  const summary = core.buildSummary({ data, pack, session, now: new Date(2026, 10, 13, 9, 5) });

  assert.equal(summary.legend, "Comunicación asistida, no es diagnóstico.");
  assert.deepEqual(summary.lines.map((l) => [l.question, l.answer]), [
    ["¿Le duele el pecho?", "Sí"],
    ["¿Le falta el aire?", "Sí"],
    ["¿Se desmayó?", "Sin respuesta"],
  ]);
  assert.equal(summary.lines[2].alert, true);
  assert.ok(summary.text.startsWith("COMUNICACIÓN ASISTIDA, NO ES DIAGNÓSTICO."));
  assert.ok(summary.text.includes("13/11/2026 09:05"));
  assert.ok(summary.text.includes("Lengua: Náhuatl: Centro (paquete nah-central-001, versión 1.2.0)"));
  assert.ok(summary.text.includes("Intérprete solicitado durante la consulta: sí"));
  assert.ok(!summary.text.includes("AUDIO DE PRUEBA"));

  const testSummary = core.buildSummary({ data, pack: { ...pack, is_test: true }, session });
  assert.ok(testSummary.text.includes("AUDIO DE PRUEBA"));
});

test("la escala de dolor usa seis caritas para once números", () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(core.painFace), [
    "cara-0", "cara-1", "cara-1", "cara-2", "cara-2", "cara-3", "cara-3", "cara-4", "cara-4", "cara-5", "cara-5",
  ]);
});

test("cada zona del cuerpo tiene nombre y el lado es el del paciente", async () => {
  const { CUERPOS } = await import("../frontend/js/cuerpo-datos.js");
  assert.equal(Object.keys(core.BODY_ZONES).length, 82);
  assert.equal(core.BODY_ZONES["f-brazo-der"], "Brazo derecho");
  assert.equal(core.BODY_ZONES["e-brazo-izq"], "Brazo izquierdo (atrás)");
  assert.equal(core.zoneLabel("e-cadera"), "Cadera y glúteos"); // respuestas de la versión anterior
  const onMap = new Set(["todo-cuerpo"]);
  for (const [body, views] of Object.entries(CUERPOS)) {
    for (const [view, data] of Object.entries(views)) {
      for (const [id, d, x] of data.zonas) {
        onMap.add(id);
        assert.ok(core.BODY_ZONES[id], `${body}/${view}: ${id} no tiene nombre`);
        assert.ok(d.startsWith("M") && d.endsWith("z"), `${body}/${view}: ${id}`);
        // De frente, la derecha del paciente queda a la izquierda de quien mira; de espalda, al revés.
        const left = x < data.w / 2;
        if (id.endsWith("-der")) assert.equal(left, view !== "espalda", `${body}/${view}: ${id}`);
        if (id.endsWith("-izq")) assert.equal(left, view === "espalda", `${body}/${view}: ${id}`);
      }
    }
  }
  assert.deepEqual([...onMap].sort(), Object.keys(core.BODY_ZONES).sort());
});
