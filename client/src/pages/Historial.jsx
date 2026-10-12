import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { changedFields, clipPatch, rebaseForm, setRefreshHandler, setViewState } from "../copilot-context.js";
import { useApp } from "../App.jsx";
import { Chip, Empty, PageHeader } from "../components/ui.jsx";
import { KIND_LABEL, KIND_CHIP, when, dayKey } from "../format.js";

const KIND_FILTERS = ["", "text", "url", "email", "path", "code", "number", "image"];

function groupByDay(clips) {
  const groups = [];
  let current = null;
  for (const clip of clips) {
    const key = dayKey(clip.last_seen_at);
    if (!current || current.key !== key) {
      current = { key, clips: [] };
      groups.push(current);
    }
    current.clips.push(clip);
  }
  return groups;
}

function LockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 018 0v3" />
    </svg>
  );
}

function ClipRow({ clip, onCopy, onPin, onDelete, onLabel }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(clip.label || "");
  // What the field was loaded with: a reload that changes the label (an assistant edit) only moves an untouched field.
  const baseRef = useRef({ label: clip.label || "" });
  const labelRef = useRef(label);
  labelRef.current = label;
  useEffect(() => {
    const next = { label: clip.label || "" };
    const merged = rebaseForm(baseRef.current, next, { label: labelRef.current });
    baseRef.current = next;
    if (merged.label !== labelRef.current) setLabel(merged.label);
  }, [clip.label]);
  // The open label editor answers the copilot context request with what has been typed.
  useEffect(() => {
    if (!editing) return undefined;
    const onRequest = (e) => e.detail?.provide?.({
      kind: "clip-label", object_id: String(clip.id), dirty: labelRef.current !== baseRef.current.label, fields: { label: labelRef.current },
    });
    window.addEventListener("echo:context-request", onRequest);
    return () => window.removeEventListener("echo:context-request", onRequest);
  }, [editing, clip.id]);
  // Saving sends only what changed from the loaded label, so an assistant edit made meanwhile is not overwritten.
  const save = () => {
    setEditing(false);
    const patch = clipPatch(changedFields(baseRef.current, { label: labelRef.current }));
    if ("label" in patch) onLabel(clip.id, patch.label);
  };

  if (clip.sensitive) {
    return (
      <div className="hidden-row">
        <LockIcon />
        <span className="flex-1 text-[13px]">Contenido oculto</span>
        <span className="help">{when(clip.last_seen_at)}</span>
        <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(clip.id)}>Eliminar</button>
      </div>
    );
  }

  return (
    <div className="row" title={`${clip.source_app || "origen desconocido"} · ${when(clip.last_seen_at)} · copiado ${clip.times}×`}>
      {clip.kind === "image" && <img src={api.imageUrl(clip.id)} alt="" className="h-10 w-10 shrink-0 rounded object-cover" />}
      <button type="button" className="row-main min-w-0 flex-1 text-left" onClick={() => onCopy(clip.id)}>
        <div className="truncate font-medium">{clip.preview || "(vacío)"}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          <Chip className={KIND_CHIP[clip.kind]}>{KIND_LABEL[clip.kind]}</Chip>
          {clip.source_app && <span className="help">{clip.source_app}</span>}
          <span className="help">{when(clip.last_seen_at)}</span>
          {clip.times > 1 && <span className="help">×{clip.times}</span>}
          {clip.label && <Chip className="chip-accent">{clip.label}</Chip>}
        </div>
      </button>
      {editing ? (
        <input
          className="field w-40"
          value={label}
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => { if (e.key === "Enter") save(); }}
        />
      ) : (
        <button type="button" className="btn btn-sm" onClick={() => setEditing(true)}>Etiquetar</button>
      )}
      <button type="button" className="btn btn-sm" onClick={() => onPin(clip)}>{clip.pinned ? "Desfijar" : "Fijar"}</button>
      <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(clip.id)}>Eliminar</button>
    </div>
  );
}

export default function Historial() {
  const { act } = useApp();
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [clips, setClips] = useState([]);
  const [lastDeleted, setLastDeleted] = useState(null);

  const refresh = useCallback(async () => {
    if (q.trim()) {
      const { hits } = await api.search({ q, kind: kind || undefined, limit: 200 });
      setClips(hits);
    } else {
      const { clips } = await api.clips({ kind: kind || undefined, limit: 200 });
      setClips(clips);
    }
  }, [kind, q]);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => setRefreshHandler(refresh), [refresh]);
  useEffect(() => setViewState({
    page: "history",
    filters: { ...(kind ? { kind } : {}), ...(q.trim() ? { q: q.trim() } : {}) },
    ids: clips.filter((c) => !c.sensitive).map((c) => c.id),
  }), [kind, q, clips]);

  async function copy(id) {
    await act(() => api.copyClip(id), "Copiado.");
    refresh();
  }
  async function pin(clip) {
    await act(() => api.updateClip(clip.id, { pinned: !clip.pinned }), clip.pinned ? "Quitado de fijados." : "Fijado.");
    refresh();
  }
  async function label(id, value) {
    await act(() => api.updateClip(id, { label: value }));
    refresh();
  }
  async function remove(id) {
    await act(() => api.removeClip(id), "Eliminado.");
    setLastDeleted(id);
    refresh();
  }
  async function undo() {
    if (!lastDeleted) return;
    await act(() => api.restoreClip(lastDeleted), "Recuperado.");
    setLastDeleted(null);
    refresh();
  }

  const groups = groupByDay(clips);

  return (
    <div>
      <PageHeader title="Historial" description="Todo lo que has copiado, de más reciente a más antiguo.">
        {lastDeleted && <button type="button" className="btn btn-sm" onClick={undo}>Deshacer</button>}
      </PageHeader>

      <div className="panel-white mb-5 grid gap-3 md:grid-cols-[2fr_3fr]">
        <input className="field" placeholder="Buscar en el portapapeles…" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="seg">
          {KIND_FILTERS.map((k) => (
            <button key={k || "todos"} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>
              {k ? KIND_LABEL[k] : "Todo"}
            </button>
          ))}
        </div>
      </div>

      {clips.length === 0 ? (
        <Empty title="Nada por aquí todavía">Copia algo y aparecerá en este historial.</Empty>
      ) : (
        groups.map((group) => (
          <div key={group.key} className="mb-5">
            <div className="help mb-2">{group.key}</div>
            <div className="panel-white p-0">
              {group.clips.map((clip) => (
                <ClipRow key={clip.id} clip={clip} onCopy={copy} onPin={pin} onDelete={remove} onLabel={label} />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
