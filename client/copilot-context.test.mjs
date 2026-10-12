import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildContext, changedFields, clipPatch, collectEditors, installCopilot, onTurnEnd, parseRoute, rebaseForm, setRefreshHandler,
} from "./src/copilot-context.js";

const clips = {
  7: { id: 7, kind: "url", text: "https://example.com/very/long", preview: "https://example.com", chars: 29, source_app: "chrome.exe", pinned: true, label: "docs", tags: ["a"], times: 2, sensitive: false, deleted_at: null },
  8: { id: 8, kind: "text", text: "[oculto: contraseña]", preview: "[oculto: contraseña]", sensitive: true, deleted_at: null },
  9: { id: 9, kind: "text", text: "gone", preview: "gone", sensitive: false, deleted_at: 123 },
};
const getClip = async (id) => { if (!clips[id]) throw new Error("not found"); return clips[id]; };
const editor = (id, fields = { label: "x" }, dirty = true) => ({ kind: "clip-label", object_id: id, dirty, fields });

test("only changed fields are sent, including a manual clear", () => {
  assert.deepEqual(changedFields({ label: "a" }, { label: "a" }), {});
  assert.deepEqual(changedFields({ label: "a" }, { label: "" }), { label: "" });
  assert.deepEqual(clipPatch({ label: "" }), { label: "" });
  assert.deepEqual(clipPatch({}), {});
});

test("a reload keeps what the user typed and updates the rest", () => {
  assert.deepEqual(rebaseForm({ label: "old" }, { label: "agent" }, { label: "old" }), { label: "agent" });
  assert.deepEqual(rebaseForm({ label: "old" }, { label: "agent" }, { label: "typed" }), { label: "typed" });
});

test("route parsing", () => {
  assert.equal(parseRoute("#/fijados").page, "fijados");
  assert.equal(parseRoute("").page, "");
});

test("an open label editor yields the real clip, without its full text", async () => {
  const ctx = await buildContext({ hash: "#/historial", editors: [editor("7")], getClip });
  assert.equal(ctx.view.page, "history");
  assert.deepEqual(ctx.active_objects.map((o) => `${o.kind}:${o.object_id}`), ["clip:7"]);
  const o = ctx.active_objects[0];
  assert.equal(o.clip_kind, "url");
  assert.equal(o.preview, "https://example.com");
  assert.equal(o.pinned, true);
  assert.equal(JSON.stringify(ctx).includes("very/long"), false);
  assert.deepEqual(ctx.view.editor.fields, { label: "x" });
});

test("sensitive, deleted, unknown and creation ids yield no object and never throw", async () => {
  for (const id of ["8", "9", "404", "new", null]) {
    const ctx = await buildContext({ hash: "", editors: [editor(id)], getClip });
    assert.deepEqual(ctx.active_objects, [], String(id));
  }
  const bad = await buildContext({ hash: "#/estado", editors: [], getClip: () => { throw new Error("boom"); } });
  assert.deepEqual(bad.active_objects, []);
  assert.equal(bad.view.page, "status");
});

test("the list view reports filters and visible ids only for its own page", async () => {
  const view = { page: "history", filters: { kind: "url" }, ids: [1, 2, 3] };
  const ctx = await buildContext({ hash: "", editors: [], view, getClip });
  assert.deepEqual(ctx.view.filters, { kind: "url" });
  assert.deepEqual(ctx.view.visible_clip_ids, [1, 2, 3]);
  const other = await buildContext({ hash: "#/fijados", editors: [], view, getClip });
  assert.equal(other.view.visible_clip_ids, undefined);
});

test("editors are collected through echo:context-request", () => {
  const target = new EventTarget();
  target.addEventListener("echo:context-request", (e) => e.detail.provide(editor("7")));
  assert.equal(collectEditors(target).length, 1);
  assert.deepEqual(collectEditors(new EventTarget()), []);
});

test("the window event and onTurnEnd trigger one debounced refresh", async () => {
  const target = new EventTarget();
  installCopilot(target);
  installCopilot(target);
  assert.equal(typeof target.hoardCopilot.context, "function");
  let calls = 0;
  const off = setRefreshHandler(() => { calls += 1; });
  target.dispatchEvent(new Event("hoard:copilot-turn-end"));
  target.hoardCopilot.onTurnEnd();
  onTurnEnd();
  await new Promise((r) => setTimeout(r, 400));
  assert.equal(calls, 1);
  off();
});
