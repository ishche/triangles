import { type ReactNode, useEffect, useRef, useState } from "react";
import { DEFAULTS, PAPERS, type Params, type RenderResult, paramsToUrl, pdf, render, saveBlob } from "./api";
import { NumberField, Toggle } from "./controls";
import { SheetView } from "./SheetView";

type Zoom = "fit" | "actual";

type Props = {
  params: Params;
  setParams: (update: (p: Params) => Params) => void;
  header: ReactNode;
  onOpenDome: () => void;
};

export function TemplateView({ params, setParams, header, onOpenDome }: Props) {
  const [result, setResult] = useState<RenderResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [downloading, setDownloading] = useState(false);
  const ctrl = useRef<AbortController | null>(null);

  const set = <K extends keyof Params>(key: K, value: Params[K]) => setParams((p) => ({ ...p, [key]: value }));

  useEffect(() => {
    paramsToUrl(params);
    const t = setTimeout(() => {
      ctrl.current?.abort();
      const c = new AbortController();
      ctrl.current = c;
      setLoading(true);
      render(params, c.signal)
        .then((r) => {
          setResult(r);
          setError(null);
        })
        .catch((e: Error) => {
          if (e.name !== "AbortError") setError(e.message);
        })
        .finally(() => {
          if (ctrl.current === c) setLoading(false);
        });
    }, 200);
    return () => clearTimeout(t);
  }, [params]);

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      saveBlob(await pdf(params), `domeprint-${params.ab}-${params.bc}-${params.ca}.pdf`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDownloading(false);
    }
  };

  const tight = params.paper === "tight";
  const fillMode = params.count === null;

  return (
    <div className="app">
      <aside className="panel">
        {header}

        <section>
          <h2>Triangle</h2>
          <div className="row3">
            <NumberField label="AB" unit="mm" value={params.ab} min={0.1} step={0.1} onChange={(v) => set("ab", v)} />
            <NumberField label="BC" unit="mm" value={params.bc} min={0.1} step={0.1} onChange={(v) => set("bc", v)} />
            <NumberField label="CA" unit="mm" value={params.ca} min={0.1} step={0.1} onChange={(v) => set("ca", v)} />
          </div>
          <button className="link plain" onClick={onOpenDome}>
            Pick a triangle from a geodesic dome →
          </button>
        </section>

        <section>
          <h2>Glue tabs</h2>
          <div className="row2">
            <NumberField label="Width" unit="mm" value={params.tab} min={0} step={0.5} onChange={(v) => set("tab", v)} />
            <NumberField
              label="Max end angle"
              unit="°"
              value={params.max_tab_angle}
              min={1}
              max={89}
              step={1}
              onChange={(v) => set("max_tab_angle", v)}
            />
          </div>
          <Toggle label="Limit tab ends to half the corner angle" checked={params.bisector} onChange={(v) => set("bisector", v)} />
        </section>

        <section>
          <h2>Sheet</h2>
          <div className="row2">
            <label className="field">
              <span>Paper</span>
              <select value={params.paper} onChange={(e) => set("paper", e.target.value)}>
                {PAPERS.map((p) => (
                  <option key={p} value={p}>
                    {p === "tight" ? "Tight (one piece)" : p}
                  </option>
                ))}
              </select>
            </label>
            <NumberField label="Margin" unit="mm" value={params.margin} min={0} step={1} onChange={(v) => set("margin", v)} />
          </div>
          {!tight && (
            <>
              <div className="segmented" role="radiogroup" aria-label="Copies">
                <button className={fillMode ? "on" : ""} onClick={() => set("count", null)}>
                  Fill one sheet
                </button>
                <button className={!fillMode ? "on" : ""} onClick={() => set("count", params.count ?? result?.pieces ?? 1)}>
                  Exact count
                </button>
              </div>
              <div className="row2">
                {!fillMode && (
                  <NumberField
                    label="Copies"
                    value={params.count ?? 1}
                    min={1}
                    max={500}
                    step={1}
                    integer
                    onChange={(v) => set("count", v)}
                  />
                )}
                <NumberField label="Spacing" unit="mm" value={params.spacing} min={0} step={0.5} onChange={(v) => set("spacing", v)} />
              </div>
            </>
          )}
          <Toggle label="Edge labels on tabs" checked={params.labels} onChange={(v) => set("labels", v)} />
          <Toggle label="100 mm calibration ruler" checked={params.calibration} onChange={(v) => set("calibration", v)} />
        </section>

        <button className="reset" onClick={() => setParams(() => DEFAULTS)}>
          Reset to defaults
        </button>
      </aside>

      <main className="stage">
        <div className="toolbar">
          <div className="summary">
            {result && (
              <>
                <strong>{result.pieces}</strong> {result.pieces === 1 ? "piece" : "pieces"} on <strong>{result.sheets.length}</strong>{" "}
                {result.sheets.length === 1 ? "sheet" : "sheets"}
                {result.fill !== null && <span className="muted"> · paper use {Math.round(result.fill * 100)}%</span>}
              </>
            )}
            {loading && <span className="spinner" aria-label="rendering" />}
          </div>
          <div className="actions">
            <div className="segmented small">
              <button className={zoom === "fit" ? "on" : ""} onClick={() => setZoom("fit")}>
                Fit
              </button>
              <button className={zoom === "actual" ? "on" : ""} onClick={() => setZoom("actual")} title="1 mm on screen ≈ 1 mm on paper">
                Actual size
              </button>
            </div>
            <button className="primary" onClick={downloadPdf} disabled={!result || downloading || !!error}>
              {downloading ? "Preparing…" : "Download PDF"}
            </button>
          </div>
        </div>

        {error && <div className="error">{error}</div>}

        <div className={`sheets ${zoom}`}>
          {result?.sheets.map((s, i) => (
            <SheetView
              key={i}
              sheet={s}
              index={i}
              total={result.sheets.length}
              zoom={zoom}
              stale={!!error}
              filename={`domeprint-${params.ab}-${params.bc}-${params.ca}${result.sheets.length > 1 ? `-${i + 1}` : ""}.svg`}
            />
          ))}
        </div>

        {result && <Info result={result} />}
      </main>
    </div>
  );
}

function Info({ result }: { result: RenderResult }) {
  const t = result.triangle;
  const f = (n: number, d = 2) => n.toFixed(d);
  return (
    <div className="info">
      <div className="card">
        <h3>Angles</h3>
        <dl>
          <dt>A</dt>
          <dd>{f(t.angles.a, 3)}°</dd>
          <dt>B</dt>
          <dd>{f(t.angles.b, 3)}°</dd>
          <dt>C</dt>
          <dd>{f(t.angles.c, 3)}°</dd>
        </dl>
      </div>
      <div className="card">
        <h3>Size</h3>
        <dl>
          <dt>Area</dt>
          <dd>{f(t.area, 1)} mm²</dd>
          <dt>Inradius</dt>
          <dd>{f(t.inradius, 3)} mm</dd>
          <dt>Circumradius</dt>
          <dd>{f(t.circumradius, 3)} mm</dd>
        </dl>
      </div>
      <div className="card wide">
        <h3>Tabs</h3>
        <table>
          <thead>
            <tr>
              <th>Edge</th>
              <th>Start</th>
              <th>End</th>
              <th>Height</th>
            </tr>
          </thead>
          <tbody>
            {result.tabs.map((tab) => (
              <tr key={tab.edge}>
                <td>{tab.edge}</td>
                <td>{f(tab.startAngle)}°</td>
                <td>{f(tab.endAngle)}°</td>
                <td>{f(tab.height, 3)} mm</td>
              </tr>
            ))}
            {result.tabs.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  No tabs
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {result.warnings.length > 0 && (
        <div className="card wide warn">
          <h3>Warnings</h3>
          <ul>
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
