import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { useApp } from "../App.jsx";
import { PageHeader, StatTile, Switch } from "../components/ui.jsx";
import { bytes, when } from "../format.js";

export default function Estado() {
  const { act, notify } = useApp();
  const [status, setStatus] = useState(null);
  const [before, setBefore] = useState("");

  const refresh = useCallback(async () => {
    setStatus(await api.status());
  }, []);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function togglePause() {
    await act(() => (status.paused ? api.resume() : api.pause()), status.paused ? "Vigilando el portapapeles de nuevo." : "Portapapeles en pausa.");
    refresh();
  }

  async function purge() {
    if (!before) return;
    if (!window.confirm(`¿Purgar permanentemente todo lo no fijado anterior a ${before}? Esta acción no se puede deshacer.`)) return;
    const iso = new Date(before).toISOString();
    const result = await act(() => api.purgeBefore(iso));
    notify(`Purgadas ${result.deleted} copias.`);
    setBefore("");
  }

  if (!status) return null;

  return (
    <div>
      <PageHeader title="Estado" description="Vigilancia del portapapeles, contadores y limpieza." />

      <div className="panel-white mb-5 flex items-center justify-between gap-3">
        <div>
          <div className="font-semibold">{status.paused ? "En pausa" : "Vigilando"}</div>
          <div className="help mt-1">
            Backend: {status.backend}. Última copia: {when(status.last_capture_at)}.
          </div>
        </div>
        <Switch checked={!status.paused} onChange={togglePause} label="Vigilar el portapapeles" />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Copias" value={status.clips_count} />
        <StatTile label="Fijadas" value={status.pinned_count} />
        <StatTile label="Ocultas" value={status.sensitive_count} />
        <StatTile label="Imágenes" value={bytes(status.images_bytes)} />
      </div>

      <div className="panel-white mt-5">
        <div className="help">Retención</div>
        <p className="mt-1">
          Se conserva todo <span className="num font-semibold">{status.retention_days}</span> días (lo fijado no caduca nunca);
          como máximo <span className="num font-semibold">{status.max_clips}</span> copias guardadas; imágenes hasta{" "}
          <span className="num font-semibold">{status.max_image_mb}</span> MB en total.
        </p>
      </div>

      <div className="panel-white mt-5">
        <div className="help">Aplicaciones excluidas</div>
        <p className="mt-1">{status.exclude_apps.length ? status.exclude_apps.join(", ") : "Ninguna"}</p>
      </div>

      <div className="panel-white mt-5">
        <div className="label">Purgar anteriores a…</div>
        <div className="mt-2 flex flex-wrap gap-2">
          <input type="datetime-local" className="field w-auto" value={before} onChange={(e) => setBefore(e.target.value)} />
          <button type="button" className="btn btn-danger" onClick={purge} disabled={!before}>Purgar</button>
        </div>
        <p className="help mt-2">Elimina permanentemente lo no fijado anterior a esa fecha. No se puede deshacer.</p>
      </div>
    </div>
  );
}
