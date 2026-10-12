// What the shared copilot launcher asks this app for: the real objects open in the current view and the unsaved form fields,
// plus a way to refresh the open view when the assistant finishes a turn. Nothing here renders anything.
import { api } from "./api.js";

const PAGE_NAMES = { "": "history", historial: "history", fijados: "pinned", estado: "status" };
const MAX_VISIBLE_IDS = 20;

// Fields of `draft` whose value differs from `initial` (compared as JSON, so arrays and "" clears count).
export function changedFields(initial, draft) {
  const base = initial || {};
  return Object.fromEntries(Object.entries(draft || {}).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(base[key])));
}

// A refreshed baseline arrives while the user is editing: fields the user did not touch follow the new baseline, touched ones stay.
export function rebaseForm(previousBase, nextBase, form) {
  const out = { ...nextBase };
  for (const key of Object.keys(form)) {
    if (JSON.stringify(form[key]) !== JSON.stringify(previousBase?.[key])) out[key] = form[key];
  }
  return out;
}

// The PATCH /api/clips/{id} body for the fields the user changed (only label is editable in a form).
export function clipPatch(changed) {
  const patch = {};
  if ("label" in changed) patch.label = String(changed.label ?? "");
  return patch;
}

export function parseRoute(hash) {
  const [path, query = ""] = String(hash || "").replace(/^#\/?/, "").split("?");
  const parts = path.split("/").filter(Boolean).map((p) => { try { return decodeURIComponent(p); } catch { return p; } });
  return { page: parts[0] || "", param: parts[1] || null, query: new URLSearchParams(query) };
}

// Every open form answers this event with a snapshot of what the user has typed: { kind, object_id, dirty, fields }.
export function collectEditors(target = globalThis.window) {
  const found = [];
  if (!target?.dispatchEvent) return found;
  target.dispatchEvent(new CustomEvent("echo:context-request", { detail: { provide: (snapshot) => { if (snapshot) found.push(snapshot); } } }));
  return found;
}

// The open list view publishes what it shows (filters and the ids on screen) so the context can name them.
let viewState = null;
export function setViewState(state) {
  viewState = state;
  return () => { if (viewState === state) viewState = null; };
}
export const getViewState = () => viewState;

const clipObject = (c) => ({
  kind: "clip",
  object_id: String(c.id),
  title: c.label || c.preview || `clip ${c.id}`,
  ...(c.clip_kind ? { clip_kind: c.clip_kind } : {}),
  ...Object.fromEntries(["source_app", "last_seen_at", "times", "pinned", "label", "tags", "chars"]
    .filter((k) => c[k] !== undefined && c[k] !== null && c[k] !== "" && !(Array.isArray(c[k]) && !c[k].length)).map((k) => [k, c[k]])),
  ...(c.preview ? { preview: String(c.preview).slice(0, 200) } : {}),
});

async function safe(fn) {
  try { return await fn(); } catch { return null; }
}

// Pure core (dependencies injected so it can be tested): never throws; unknown or "new" ids yield no object.
// Clips flagged sensitive or deleted are never included, and the full clip text is never sent (only a short preview).
export async function buildContext({ hash, editors = [], view = null, getClip }) {
  const route = parseRoute(hash);
  const page = PAGE_NAMES[route.page] || route.page || "history";
  const active = [];
  const seen = new Set();
  for (const e of editors) {
    const id = e?.object_id;
    if (e?.kind !== "clip-label" || !id || id === "new" || seen.has(String(id))) continue;
    seen.add(String(id));
    const clip = await safe(() => getClip(id));
    if (clip?.id && !clip.sensitive && !clip.deleted_at) {
      const { kind, ...rest } = clip;
      active.push(clipObject({ ...rest, clip_kind: kind }));
    }
  }
  const out = { view: { page }, active_objects: active };
  if (view && view.page === page) {
    if (view.filters && Object.keys(view.filters).length) out.view.filters = view.filters;
    if (view.ids?.length) out.view.visible_clip_ids = view.ids.slice(0, MAX_VISIBLE_IDS);
  }
  const editor = editors.find((e) => e?.dirty) || editors[0];
  if (editor) out.view.editor = editor;
  if (editors.length > 1) out.view.editors = editors;
  return out;
}

export function context() {
  return buildContext({
    hash: globalThis.window?.location?.hash,
    editors: collectEditors(),
    view: getViewState(),
    getClip: (id) => api.clip(id),
  });
}

// ---- refresh when the assistant finishes a turn -------------------------------------------------------------------------
const handlers = new Set();
let timer = null;

function scheduleRefresh() {
  clearTimeout(timer);
  timer = setTimeout(() => {
    for (const fn of [...handlers]) { try { fn(); } catch { /* a refresh must never break the page */ } }
  }, 250);
}

// A view registers what "reload what is on screen" means (it keeps the forms the user is editing untouched).
export function setRefreshHandler(fn) {
  handlers.add(fn);
  return () => handlers.delete(fn);
}

export const onTurnEnd = () => scheduleRefresh();

// Once at start: the object the launcher looks for, and the window event it dispatches on turn end (the debounce merges the two).
export function installCopilot(target = globalThis.window) {
  if (!target || target.hoardCopilot) return;
  target.hoardCopilot = { context, onTurnEnd };
  target.addEventListener("hoard:copilot-turn-end", scheduleRefresh);
}
