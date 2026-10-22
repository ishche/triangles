import { lazy, Suspense, useEffect, useState } from "react";
import { DOME_DEFAULTS, type DomeParams, FRAME_DEFAULTS, type FrameParams, type Params, paramsFromUrl } from "./api";
import { TemplateView } from "./TemplateView";

// three.js is large; load the 3D view only when it is opened.
const DomeView = lazy(() => import("./DomeView").then((m) => ({ default: m.DomeView })));

type View = "template" | "dome";

const viewFromHash = (): View => (window.location.hash === "#dome" ? "dome" : "template");

export function App() {
  const [view, setView] = useState<View>(viewFromHash);
  const [params, setParams] = useState<Params>(paramsFromUrl);
  const [domeParams, setDomeParams] = useState<DomeParams>(DOME_DEFAULTS);
  const [frameParams, setFrameParams] = useState<FrameParams>(FRAME_DEFAULTS);

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (v: View) => {
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${v === "dome" ? "#dome" : ""}`);
    setView(v);
  };

  const header = (
    <header className="brand-wrap">
      <div className="brand">
        <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden>
          <path d="M16 3 30 28H2Z" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
          <path d="M9 15.5h14M16 3 9 15.5 16 28 23 15.5Z" fill="none" stroke="currentColor" strokeWidth="1.2" strokeDasharray="2 1.5" />
        </svg>
        <div>
          <h1>domeprint</h1>
          <p>paper templates for geodesic dome triangles</p>
        </div>
      </div>
      <nav className="segmented" aria-label="View">
        <button className={view === "template" ? "on" : ""} onClick={() => go("template")}>
          Template
        </button>
        <button className={view === "dome" ? "on" : ""} onClick={() => go("dome")}>
          Dome 3D
        </button>
      </nav>
    </header>
  );

  return view === "dome" ? (
    <Suspense fallback={<div className="loading">Loading 3D view…</div>}>
      <DomeView
        params={domeParams}
        setParams={setDomeParams}
        frameParams={frameParams}
        setFrameParams={setFrameParams}
        header={header}
        onUseTriangle={([ab, bc, ca]) => {
          const r = (n: number) => Math.round(n * 1000) / 1000;
          setParams((p) => ({ ...p, ab: r(ab), bc: r(bc), ca: r(ca) }));
          go("template");
        }}
      />
    </Suspense>
  ) : (
    <TemplateView params={params} setParams={setParams} header={header} onOpenDome={() => go("dome")} />
  );
}
