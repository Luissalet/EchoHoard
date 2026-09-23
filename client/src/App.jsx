import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import { Toast } from "./components/ui.jsx";
import Historial from "./pages/Historial.jsx";
import Fijados from "./pages/Fijados.jsx";
import Estado from "./pages/Estado.jsx";

const PAGES = [
  { path: "historial", label: "Historial", icon: "M4 5h16v4H4zM4 11h16v8H4zM8 15h8", component: Historial },
  { path: "fijados", label: "Fijados", icon: "M12 2l2.5 6.5L21 9l-5 4.5L17.5 21 12 17.5 6.5 21 8 13.5 3 9l6.5-.5z", component: Fijados },
  { path: "estado", label: "Estado", icon: "M4 20V10m5 10V4m5 16v-8m5 8V7", component: Estado },
];

const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

function useHashRoute() {
  const read = () => {
    const parts = window.location.hash.replace(/^#\/?/, "").split("/");
    return { page: parts[0] || "historial", param: parts[1] || null };
  };
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const onChange = () => setRoute(read());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

function Icon({ d }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export default function App() {
  const route = useHashRoute();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const refreshStatus = useCallback(async () => {
    try {
      const s = await api.status();
      setStatus(s);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    refreshStatus();
    const timer = setInterval(refreshStatus, 5000);
    return () => clearInterval(timer);
  }, [refreshStatus]);

  const notify = useCallback((message) => setToast(message), []);
  const act = useCallback(
    async (fn, okMessage) => {
      try {
        const result = await fn();
        if (okMessage) setToast(okMessage);
        await refreshStatus();
        return result;
      } catch (e) {
        setToast(e.message);
        throw e;
      }
    },
    [refreshStatus],
  );

  const togglePause = useCallback(async () => {
    await act(() => (status?.paused ? api.resume() : api.pause()), status?.paused ? "Vigilando el portapapeles de nuevo." : "Portapapeles en pausa.");
  }, [act, status]);

  const value = useMemo(() => ({ status, refreshStatus, notify, act }), [status, refreshStatus, notify, act]);

  const page = PAGES.find((p) => p.path === route.page) || PAGES[0];
  const Component = page.component;

  return (
    <AppContext.Provider value={value}>
      <div className="min-h-dvh md:grid md:grid-cols-[224px_minmax(0,1fr)]">
        <aside className="sticky top-0 z-10 border-b md:h-dvh md:border-b-0 md:border-r" style={{ background: "var(--sidebar)", borderColor: "var(--line)" }}>
          <div className="flex items-center gap-2 px-4 py-3 md:px-5 md:py-5">
            <span className="grid h-8 w-8 place-items-center rounded-md text-[15px] font-bold text-white" style={{ background: "var(--accent)" }}>E</span>
            <div className="leading-tight">
              <div className="text-[15px] font-semibold">Echo's Hoard</div>
              <div className="help text-[11px]">Portapapeles</div>
            </div>
          </div>
          <nav aria-label="Secciones" className="flex gap-1 overflow-x-auto px-3 pb-2 md:flex-col md:px-3">
            {PAGES.map((p) => (
              <a key={p.path} href={`#/${p.path}`} className="nav-link shrink-0 text-[13px]" aria-current={p.path === page.path ? "page" : undefined}>
                <Icon d={p.icon} />
                {p.label}
              </a>
            ))}
          </nav>
          {status && (
            <div className="hidden px-5 pt-4 md:block">
              <div className="help text-[11px]">{status.paused ? "En pausa" : "Vigilando"}</div>
              <button type="button" className="btn btn-sm mt-2 w-full" onClick={togglePause}>
                {status.paused ? "Reanudar" : "Pausar"}
              </button>
              <div className="help mt-3 text-[11px]">
                <span className="num font-semibold">{status.clips_count}</span> copias · <span className="num">{status.pinned_count}</span> fijadas
              </div>
            </div>
          )}
        </aside>
        <main className="min-w-0 px-4 py-4 md:px-10 md:py-8">
          {error && (
            <div className="mb-4 rounded-md border p-4 text-[13px]" style={{ background: "var(--danger-bg)", color: "var(--danger-ink)", borderColor: "var(--danger-line)" }} role="alert">
              No se pudo contactar con Echo: {error}. <button type="button" className="btn-link" onClick={refreshStatus}>Reintentar</button>
            </div>
          )}
          <Component param={route.param} />
        </main>
      </div>
      <Toast message={toast} onClose={() => setToast(null)} />
    </AppContext.Provider>
  );
}
