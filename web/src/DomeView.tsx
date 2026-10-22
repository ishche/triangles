import { type ReactNode, useEffect, useState } from "react";
import { type Dome, DOME_DEFAULTS, type DomeParams, type Frame, type FrameParams, dome as fetchDome, frame as fetchFrame } from "./api";
import { type ColorBy, DomeCanvas } from "./DomeCanvas";
import { NumberField, Toggle } from "./controls";
import { FrameCanvas, type LoadView, type WindColour } from "./FrameCanvas";
import { CASES, type CaseTab, LoadsInputs, LoadsLegend, LoadsResults, StrutTooltip } from "./LoadsPanel";
import { colorFor } from "./palette";

type Props = {
  params: DomeParams;
  setParams: (update: (p: DomeParams) => DomeParams) => void;
  frameParams: FrameParams;
  setFrameParams: (update: (p: FrameParams) => FrameParams) => void;
  header: ReactNode;
  onUseTriangle: (sides: [number, number, number]) => void;
};

const PORTIONS = [
  { label: "3/8", value: 0.375 },
  { label: "1/2", value: 0.5 },
  { label: "5/8", value: 0.625 },
  { label: "Sphere", value: 1 },
];

export function DomeView({ params, setParams, frameParams, setFrameParams, header, onUseTriangle }: Props) {
  const [dome, setDome] = useState<Dome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [colorBy, setColorBy] = useState<ColorBy>("types");
  const [selected, setSelected] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [autoRotate, setAutoRotate] = useState(true);
  const [frame, setFrame] = useState<Frame | null>(null);
  const [frameError, setFrameError] = useState<string | null>(null);
  const [caseTab, setCaseTab] = useState<CaseTab>("envelope");
  const [inside, setInside] = useState<"W+" | "W-">("W+");
  const [windColour, setWindColour] = useState<WindColour>("pressure");
  const [airflow, setAirflow] = useState(true);
  const [deflect, setDeflect] = useState(false);
  const loadView: LoadView = caseTab === "W" ? inside : caseTab;
  const [tip, setTip] = useState<{ edge: number; x: number; y: number } | null>(null);
  const loads = colorBy === "loads";
  const setFrameParam = <K extends keyof FrameParams>(key: K, value: FrameParams[K]) =>
    setFrameParams((p) => ({ ...p, [key]: value }));

  const set = <K extends keyof DomeParams>(key: K, value: DomeParams[K]) => setParams((p) => ({ ...p, [key]: value }));

  useEffect(() => {
    const c = new AbortController();
    const t = setTimeout(() => {
      fetchDome(params, c.signal)
        .then((d) => {
          setDome(d);
          setError(null);
        })
        .catch((e: Error) => e.name !== "AbortError" && setError(e.message));
    }, 120);
    return () => {
      clearTimeout(t);
      c.abort();
    };
  }, [params]);

  useEffect(() => {
    if (!loads) return;
    const c = new AbortController();
    const t = setTimeout(() => {
      fetchFrame({ frequency: params.frequency, portion: params.portion }, frameParams, c.signal)
        .then((f) => {
          setFrame(f);
          setFrameError(null);
        })
        .catch((e: Error) => e.name !== "AbortError" && setFrameError(e.message));
    }, 200);
    return () => {
      clearTimeout(t);
      c.abort();
    };
  }, [loads, params.frequency, params.portion, frameParams]);

  // Type and strut indices mean something else once the dome changes.
  useEffect(() => {
    setSelected(null);
    setHovered(null);
  }, [params.frequency, params.portion, colorBy]);

  const highlight = hovered ?? selected;
  const toggle = (i: number) => setSelected((s) => (s === i ? null : i));
  const rowProps = (i: number) => ({
    className: `${highlight === i ? "hl" : ""} ${selected === i ? "sel" : ""}`,
    onMouseEnter: () => setHovered(i),
    onMouseLeave: () => setHovered(null),
    onClick: () => toggle(i),
  });

  return (
    <div className="app">
      <aside className="panel">
        {header}

        <section>
          <h2>Dome</h2>
          <div className="row2">
            <label className="field">
              <span>Frequency</span>
              <select value={params.frequency} onChange={(e) => set("frequency", Number(e.target.value))}>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((f) => (
                  <option key={f} value={f}>
                    {f}V
                  </option>
                ))}
              </select>
            </label>
            <NumberField label="Radius" unit="mm" value={params.radius} min={1} max={100000} step={10} onChange={(v) => set("radius", v)} />
          </div>
          <div className="field">
            <span>Portion of the sphere</span>
            <div className="segmented small">
              {PORTIONS.map((p) => (
                <button key={p.label} className={params.portion === p.value ? "on" : ""} onClick={() => set("portion", p.value)}>
                  {p.label}
                </button>
              ))}
            </div>
            <input
              type="range"
              min={0.1}
              max={1}
              step={0.025}
              value={params.portion}
              onChange={(e) => set("portion", Number(e.target.value))}
            />
            {dome && (
              <small className="muted">
                Cut at the nearest row of vertices: {Math.round(dome.portion * 1000) / 10}% of the height
              </small>
            )}
          </div>
          <button className="link plain" onClick={() => setParams(() => DOME_DEFAULTS)}>
            Reset to 3V 5/8
          </button>
        </section>

        <section>
          <h2>View</h2>
          <div className="segmented small">
            <button className={colorBy === "types" ? "on" : ""} onClick={() => setColorBy("types")}>
              Triangles
            </button>
            <button className={colorBy === "struts" ? "on" : ""} onClick={() => setColorBy("struts")}>
              Struts
            </button>
            <button className={colorBy === "loads" ? "on" : ""} onClick={() => setColorBy("loads")}>
              Loads
            </button>
          </div>
          <Toggle label="Rotate" checked={autoRotate} onChange={setAutoRotate} />
        </section>

        {loads && <LoadsInputs params={frameParams} set={setFrameParam} />}

        {dome && !loads && (
          <section>
            <h2>Size</h2>
            <dl>
              <dt>Triangles</dt>
              <dd>{dome.faces.length}</dd>
              <dt>Struts</dt>
              <dd>{dome.edges.length}</dd>
              <dt>Vertices</dt>
              <dd>{dome.vertices.length}</dd>
              <dt>Height</dt>
              <dd>{dome.height.toFixed(1)} mm</dd>
              {dome.portion < 1 && (
                <>
                  <dt>Base Ø</dt>
                  <dd>{dome.baseDiameter.toFixed(1)} mm</dd>
                </>
              )}
            </dl>
          </section>
        )}
      </aside>

      {loads ? (
        <main className="dome-stage">
          {frameError && <div className="error floating">{frameError}</div>}
          <div className={`dome-canvas ${frameError ? "stale" : ""}`}>
            {frame && (
              <FrameCanvas
                frame={frame}
                view={loadView}
                windColour={windColour}
                airflow={airflow}
                deflect={deflect}
                highlight={highlight}
                hovered={tip?.edge ?? null}
                autoRotate={autoRotate && highlight === null && tip === null}
                onHover={setTip}
              />
            )}
            <div className="case-bar" role="toolbar" aria-label="Load case">
              <div className="segmented small">
                {CASES.map((c) => (
                  <button key={c.key} className={caseTab === c.key ? "on" : ""} title={c.title} onClick={() => setCaseTab(c.key)}>
                    {c.label}
                  </button>
                ))}
              </div>
              {caseTab === "W" && (
                <>
                  <div className="segmented small" aria-label="Inside pressure">
                    <button className={inside === "W+" ? "on" : ""} title="Openings on the windward side: c_pi +0.2" onClick={() => setInside("W+")}>
                      Inside +0.2
                    </button>
                    <button className={inside === "W-" ? "on" : ""} title="Openings on the lee side: c_pi −0.3" onClick={() => setInside("W-")}>
                      Inside −0.3
                    </button>
                  </div>
                  <div className="segmented small" aria-label="Colour by">
                    <button className={windColour === "pressure" ? "on" : ""} onClick={() => setWindColour("pressure")}>
                      Pressure
                    </button>
                    <button className={windColour === "forces" ? "on" : ""} onClick={() => setWindColour("forces")}>
                      Strut forces
                    </button>
                  </div>
                  <Toggle label="Airflow" checked={airflow} onChange={setAirflow} />
                </>
              )}
              {caseTab !== "envelope" && <Toggle label="Deflection" checked={deflect} onChange={setDeflect} />}
            </div>
            {frame && <LoadsLegend frame={frame} view={loadView} windColour={windColour} airflow={airflow} deflect={deflect && caseTab !== "envelope"} />}
            {frame && tip && <StrutTooltip frame={frame} view={loadView} {...tip} />}
            {!frame && !frameError && <div className="loading">Analysing frame…</div>}
            <p className="hint">Drag to orbit · scroll to zoom · hover a strut for its forces</p>
          </div>
          {frame && (
            <div className="dome-tables">
              <LoadsResults frame={frame} view={loadView} highlight={highlight} rowProps={rowProps} />
            </div>
          )}
        </main>
      ) : (
        <main className="dome-stage">
          {error && <div className="error floating">{error}</div>}
          <div className={`dome-canvas ${error ? "stale" : ""}`}>
            {dome && (
              <DomeCanvas
                dome={dome}
                colorBy={colorBy}
                highlight={highlight}
                autoRotate={autoRotate && highlight === null}
                onHover={(t) => colorBy === "types" && setHovered(t)}
                onPick={(t) => colorBy === "types" && setSelected(t)}
              />
            )}
            <p className="hint">Drag to orbit · scroll to zoom · click a triangle to pick its type</p>
          </div>

          {dome && (
            <div className="dome-tables">
              {colorBy === "types" ? (
                <div className="card">
                  <h3>Triangle types</h3>
                  <table className="pick">
                    <thead>
                      <tr>
                        <th />
                        <th>Type</th>
                        <th>AB · BC · CA, mm</th>
                        <th>Qty</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {dome.types.map((t, i) => (
                        <tr key={t.label} {...rowProps(i)}>
                          <td>
                            <i className="swatch" style={{ background: colorFor(i) }} />
                          </td>
                          <td>
                            {t.label}
                            {t.mirrorOf && <small className="muted"> mirror of {t.mirrorOf}</small>}
                          </td>
                          <td>{t.sides.map((x) => x.toFixed(1)).join(" · ")}</td>
                          <td>{t.count}</td>
                          <td>
                            <button
                              className="link plain"
                              onClick={(e) => {
                                e.stopPropagation();
                                onUseTriangle(t.sides);
                              }}
                            >
                              Template →
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="card">
                  <h3>Struts</h3>
                  <table className="pick">
                    <thead>
                      <tr>
                        <th />
                        <th>Strut</th>
                        <th>Length, mm</th>
                        <th>Chord factor</th>
                        <th>Qty</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dome.struts.map((s, i) => (
                        <tr key={s.label} {...rowProps(i)}>
                          <td>
                            <i className="swatch" style={{ background: colorFor(i) }} />
                          </td>
                          <td>{s.label}</td>
                          <td>{s.length.toFixed(2)}</td>
                          <td>{s.factor.toFixed(5)}</td>
                          <td>{s.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </main>
      )}
    </div>
  );
}
