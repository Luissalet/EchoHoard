import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { useApp } from "../App.jsx";
import { Chip, Empty, PageHeader } from "../components/ui.jsx";
import { KIND_LABEL, KIND_CHIP, when } from "../format.js";

export default function Fijados() {
  const { act } = useApp();
  const [clips, setClips] = useState([]);

  const refresh = useCallback(async () => {
    const { clips } = await api.clips({ pinned: 1, limit: 500 });
    const sorted = [...clips].sort((a, b) => (a.label || "").localeCompare(b.label || "", "es"));
    setClips(sorted);
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  async function copy(id) {
    await act(() => api.copyClip(id), "Copiado.");
  }
  async function unpin(id) {
    await act(() => api.updateClip(id, { pinned: false }), "Quitado de fijados.");
    refresh();
  }

  return (
    <div>
      <PageHeader title="Fijados" description="Tus copias fijadas, ordenadas por etiqueta." />
      {clips.length === 0 ? (
        <Empty title="No tienes copias fijadas">Fija una copia desde Historial para verla aquí siempre.</Empty>
      ) : (
        <div className="panel-white p-0">
          {clips.map((clip) => (
            <div key={clip.id} className="row">
              {clip.sensitive ? (
                <span className="help flex-1">Contenido oculto</span>
              ) : (
                <button type="button" className="row-main min-w-0 flex-1 text-left" onClick={() => copy(clip.id)}>
                  <div className="truncate font-medium">{clip.preview || "(vacío)"}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    <Chip className={KIND_CHIP[clip.kind]}>{KIND_LABEL[clip.kind]}</Chip>
                    {clip.label && <Chip className="chip-accent">{clip.label}</Chip>}
                    <span className="help">{when(clip.last_seen_at)}</span>
                  </div>
                </button>
              )}
              <button type="button" className="btn btn-sm" onClick={() => unpin(clip.id)}>Desfijar</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
