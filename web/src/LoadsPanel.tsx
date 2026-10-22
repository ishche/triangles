import type React from "react";
import { useRef } from "react";
import type { CaseKey, Frame, FrameParams } from "./api";
import { NumberField } from "./controls";
import { deflectionScale, type LoadView, type WindColour } from "./FrameCanvas";
import { CRITICAL, FORCE_RAMP, netPressure, PRESSURE_RAMP, SNOW, UTIL_RAMP, utilScale } from "./loadColors";
import { colorFor } from "./palette";

// Same keys as domeprint.frame.members.MATERIALS.
const MATERIALS = [
  { key: "timber_c24", name: "Timber C24", shape: "rect" as const, b: 45, h: 95 },
  { key: "steel_s235", name: "Steel S235 tube", shape: "tube" as const, b: 33.7, h: 2.6 },
  { key: "alu_6060", name: "Aluminium 6060-T6 tube", shape: "tube" as const, b: 40, h: 3 },
];

const TERRAINS = [
  { key: "0", name: "0 · sea, coast" },
  { key: "I", name: "I · lakes, open flat land" },
  { key: "II", name: "II · grass, isolated trees" },
  { key: "III", name: "III · villages, suburbs, forest" },
  { key: "IV", name: "IV · city, ≥15% built up" },
];

export type CaseTab = "envelope" | "G" | "S" | "Sd" | "W";

export const CASES: { key: CaseTab; label: string; title: string }[] = [
  { key: "envelope", label: "Design check", title: "Utilisation over all ULS combinations" },
  { key: "G", label: "Dead", title: "G · self-weight of struts + cover" },
  { key: "S", label: "Snow", title: "S · balanced snow" },
  { key: "Sd", label: "Drift", title: "Sd · drifted snow, more on the lee side" },
  { key: "W", label: "Wind", title: "W · wind pressure and suction on the cover" },
];

export const CASE_TITLES: Record<string, string> = {
  G: "Dead load · struts + cover",
  S: "Snow · balanced",
  Sd: "Snow · drifted to the lee side",
  "W+": "Wind · inside overpressure (c_pi +0.2)",
  "W-": "Wind · inside suction (c_pi −0.3)",
};

const kn = (x: number) => `${x.toFixed(2)}`;
const pct = (u: number) => `${Math.round(u * 100)}%`;

type InputsProps = { params: FrameParams; set: <K extends keyof FrameParams>(k: K, v: FrameParams[K]) => void };

type Shape = FrameParams["section_shape"];
const SHAPE_DEFAULTS: Record<Shape, [number, number]> = { rect: [45, 95], tube: [42.4, 2.6] };

export function LoadsInputs({ params, set }: InputsProps) {
  const tube = params.section_shape === "tube";
  // Each shape keeps its own last size, so switching never turns 45 × 95 timber into a 95 mm tube wall.
  const lastSize = useRef<Record<Shape, [number, number]>>({ ...SHAPE_DEFAULTS });
  lastSize.current[params.section_shape] = [params.section_b, params.section_h];
  const switchShape = (shape: Shape, size = lastSize.current[shape]) => {
    if (shape === params.section_shape) return;
    set("section_shape", shape);
    set("section_b", size[0]);
    set("section_h", size[1]);
  };
  return (
    <>
      <section>
        <h2>Full-size frame</h2>
        <small className="muted">Same frequency and cut as above, built at this size.</small>
        <NumberField label="Radius" unit="m" value={params.radius} min={0.5} max={50} step={0.5} onChange={(v) => set("radius", v)} />
        <label className="field">
          <span>Strut material</span>
          <select
            value={params.material_key}
            onChange={(e) => {
              const m = MATERIALS.find((x) => x.key === e.target.value)!;
              set("material_key", m.key);
              switchShape(m.shape, [m.b, m.h]);
            }}
          >
            {MATERIALS.map((m) => (
              <option key={m.key} value={m.key}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <div className="segmented small">
          <button className={!tube ? "on" : ""} onClick={() => switchShape("rect")}>
            Rectangular
          </button>
          <button className={tube ? "on" : ""} onClick={() => switchShape("tube")}>
            Round tube
          </button>
        </div>
        <div className="row2">
          <NumberField label={tube ? "Diameter" : "Width"} unit="mm" value={params.section_b} min={1} max={1000} step={1} onChange={(v) => set("section_b", v)} />
          <NumberField
            label={tube ? "Wall" : "Depth"}
            unit="mm"
            value={params.section_h}
            min={0.1}
            max={tube ? Math.round(params.section_b * 5 - 1) / 10 : 1000}
            step={tube ? 0.1 : 1}
            onChange={(v) => set("section_h", v)}
          />
        </div>
        <NumberField label="Cover, hubs, insulation" unit="kN/m²" value={params.cover_load} min={0} max={10} step={0.05} onChange={(v) => set("cover_load", v)} />
      </section>

      <section>
        <h2>Snow</h2>
        <div className="row2">
          <NumberField label="Ground snow sₖ" unit="kN/m²" value={params.snow_sk} min={0} max={20} step={0.1} onChange={(v) => set("snow_sk", v)} />
          <label className="field">
            <span>Exposure Cₑ</span>
            <select value={params.snow_ce} onChange={(e) => set("snow_ce", Number(e.target.value))}>
              <option value={0.8}>0.8 windswept</option>
              <option value={1}>1.0 normal</option>
              <option value={1.2}>1.2 sheltered</option>
            </select>
          </label>
        </div>
      </section>

      <section>
        <h2>Wind</h2>
        <div className="row2">
          <NumberField label="Basic speed v_b" unit="m/s" value={params.wind_vb} min={0} max={80} step={1} onChange={(v) => set("wind_vb", v)} />
          <label className="field">
            <span>Terrain</span>
            <select value={params.terrain} onChange={(e) => set("terrain", e.target.value)}>
              {TERRAINS.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="field dial-field">
          <span>Direction shown</span>
          <div className="dial-row">
            <WindDial value={params.wind_direction} onChange={(v) => set("wind_direction", v)} />
            <div>
              <b className="num">{params.wind_direction}°</b>
              <div className="muted small">Drag the arrow. The design check covers every direction.</div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

const grad = (stops: string[]) => ({ background: `linear-gradient(90deg, ${stops.join(", ")})` });

function Cue({ icon, children }: { icon: "arrow-down" | "arrow-in" | "streak" | "snow" | "ghost" | "reaction"; children: React.ReactNode }) {
  const paths: Record<string, React.ReactNode> = {
    "arrow-down": <path d="M9 2v10M5 9l4 4 4-4" />,
    "arrow-in": (
      <>
        <path d="M2 9h8M7 5l4 4-4 4" />
        <path d="M14 3v12" strokeWidth="2.4" />
      </>
    ),
    streak: <path d="M1 6c4 0 6 2 10 2s4-2 6-2M1 12c4 0 6 2 10 2" strokeDasharray="0" opacity="0.8" />,
    snow: <rect x="2" y="6" width="14" height="6" rx="2" fill={SNOW} />,
    ghost: <path d="M2 14 9 3l7 11Z" strokeWidth="1" opacity="0.6" />,
    reaction: <path d="M9 16V6M5 9l4-4 4 4M3 17h12" />,
  };
  return (
    <div className="legend-row">
      <svg viewBox="0 0 18 18" width="18" height="18" className="cue" aria-hidden>
        {paths[icon]}
      </svg>
      <span>{children}</span>
    </div>
  );
}

type LegendProps = { frame: Frame; view: LoadView; windColour: WindColour; airflow: boolean; deflect: boolean };

/** Key for colours, thickness and the visual cues in the current view. */
export function LoadsLegend({ frame, view, windColour, airflow, deflect }: LegendProps) {
  if (view === "envelope") {
    const scale = utilScale(frame.envelope.utilisation);
    return (
      <div className="legend">
        <div className="legend-title">Utilisation · thicker = higher</div>
        <div className="ramp" style={grad(UTIL_RAMP)} />
        <div className="ramp-labels">
          <span>0%</span>
          <span>{pct(scale / 2)}</span>
          <span>{pct(scale)}</span>
        </div>
        <div className="legend-row">
          <i className="swatch" style={{ background: CRITICAL }} /> ⚠ over 100% of capacity
        </div>
      </div>
    );
  }
  const wind = view === "W+" || view === "W-";
  const deflecting = deflect;
  const fmax = Math.max(...frame.cases[view].forces.map(Math.abs));
  const pnet = wind ? netPressure(frame.faceCpe, frame.wind.qp, view) : [];
  const pmax = wind ? Math.max(...pnet.map(Math.abs)) : 0;
  return (
    <div className="legend">
      {wind && windColour === "pressure" ? (
        <>
          <div className="legend-title">Net wind on the cover, kN/m²</div>
          <div className="ramp" style={grad(PRESSURE_RAMP)} />
          <div className="ramp-labels">
            <span>−{pmax.toFixed(2)}</span>
            <span>0</span>
            <span>+{pmax.toFixed(2)}</span>
          </div>
          <div className="ramp-labels names">
            <span>suction (pulls out)</span>
            <span>pressure (pushes in)</span>
          </div>
        </>
      ) : (
        <>
          <div className="legend-title">Strut force, kN · thicker = larger</div>
          <div className="ramp" style={grad(FORCE_RAMP)} />
          <div className="ramp-labels">
            <span>−{fmax.toFixed(1)}</span>
            <span>0</span>
            <span>+{fmax.toFixed(1)}</span>
          </div>
          <div className="ramp-labels names">
            <span>compression</span>
            <span>tension</span>
          </div>
        </>
      )}
      {deflecting ? (
        <Cue icon="ghost">
          Deflection ×{Math.round(deflectionScale(frame, view))}; thin grey = unloaded
        </Cue>
      ) : (
        <>
          {view === "G" && <Cue icon="arrow-down">Weight on each hub</Cue>}
          {(view === "S" || view === "Sd") && <Cue icon="snow">Snow layer, thicker = more per m²</Cue>}
          {wind && <Cue icon="arrow-in">Arrows: in = pressure, out = suction</Cue>}
          <Cue icon="reaction">Foundation reactions at the base</Cue>
        </>
      )}
      {wind && airflow && <Cue icon="streak">Airflow; faster over the crown = suction</Cue>}
    </div>
  );
}

/** Plan-view dial: the arrow points where the wind blows to. */
function WindDial({ value, onChange }: { value: number; onChange: (deg: number) => void }) {
  const size = 76;
  const c = size / 2;
  const rad = (value * Math.PI) / 180;
  const tip = [c + Math.cos(rad) * 28, c - Math.sin(rad) * 28];
  const tail = [c - Math.cos(rad) * 28, c + Math.sin(rad) * 28];
  const setFrom = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left - r.width / 2;
    const y = e.clientY - r.top - r.height / 2;
    onChange((Math.round(((Math.atan2(-y, x) * 180) / Math.PI + 360) / 5) * 5) % 360);
  };
  return (
    <svg
      className="dial"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="slider"
      tabIndex={0}
      aria-label="Wind direction"
      aria-valuemin={0}
      aria-valuemax={359}
      aria-valuenow={value}
      aria-valuetext={`${value} degrees`}
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId);
        setFrom(e);
      }}
      onPointerMove={(e) => e.buttons && setFrom(e)}
      onKeyDown={(e) => {
        const step = e.key === "ArrowLeft" || e.key === "ArrowDown" ? -5 : e.key === "ArrowRight" || e.key === "ArrowUp" ? 5 : 0;
        if (step) {
          e.preventDefault();
          onChange((value + step + 360) % 360);
        }
      }}
    >
      <circle cx={c} cy={c} r={c - 2} className="dial-face" />
      {[0, 90, 180, 270].map((a) => (
        <line key={a} x1={c + Math.cos((a * Math.PI) / 180) * (c - 8)} y1={c - Math.sin((a * Math.PI) / 180) * (c - 8)} x2={c + Math.cos((a * Math.PI) / 180) * (c - 3)} y2={c - Math.sin((a * Math.PI) / 180) * (c - 3)} className="dial-tick" />
      ))}
      <circle cx={c} cy={c} r={9} className="dial-dome" />
      <line x1={tail[0]} y1={tail[1]} x2={tip[0]} y2={tip[1]} className="dial-arrow" />
      <polygon
        points={`${tip[0]},${tip[1]} ${tip[0] - Math.cos(rad - 0.45) * 10},${tip[1] + Math.sin(rad - 0.45) * 10} ${tip[0] - Math.cos(rad + 0.45) * 10},${tip[1] + Math.sin(rad + 0.45) * 10}`}
        className="dial-head"
      />
    </svg>
  );
}

export function StrutTooltip({ frame, view, edge, x, y }: { frame: Frame; view: LoadView; edge: number; x: number; y: number }) {
  const s = frame.struts[frame.edgeStruts[edge]];
  const env = frame.envelope;
  const f = view === "envelope" ? null : frame.cases[view].forces[edge];
  return (
    <div className="tooltip" style={{ left: x + 14, top: y + 14 }}>
      <b>
        Strut {s.label}
        <span className="muted"> · {(s.length * 1000).toFixed(0)} mm</span>
      </b>
      {f !== null && (
        <div>
          {CASE_TITLES[view].split(" · ")[0]}: <b className="num">{kn(Math.abs(f))} kN</b> {f < 0 ? "compression" : "tension"}
        </div>
      )}
      <div>
        Design: <span className="num">{kn(-env.compression[edge])}</span> C / <span className="num">{kn(env.tension[edge])}</span> T kN
      </div>
      <div>
        Utilisation <b className="num">{pct(env.utilisation[edge])}</b>
        {env.utilisation[edge] > 1 && " ⚠"}
      </div>
      <div className="muted small">{env.combination[edge]}</div>
    </div>
  );
}

type ResultsProps = {
  frame: Frame;
  view: LoadView;
  highlight: number | null;
  rowProps: (i: number) => object;
};

export function LoadsResults({ frame, view, rowProps }: ResultsProps) {
  const worst = frame.struts.reduce((a, b) => (b.utilisation > a.utilisation ? b : a));
  const ok = worst.utilisation <= 1;
  const sup = frame.supports;
  const maxDown = Math.max(...sup.map((s) => s.down));
  const maxUp = Math.max(...sup.map((s) => s.uplift));
  const maxH = Math.max(...sup.map((s) => s.horizontal));
  const c = view === "envelope" ? null : frame.cases[view];

  return (
    <>
      <div className={`card verdict ${ok ? "ok" : "bad"}`}>
        <div className="verdict-head">
          <span className="verdict-icon" aria-hidden>
            {ok ? "✓" : "⚠"}
          </span>
          <div>
            <div className="verdict-num num">{pct(worst.utilisation)}</div>
            <div>{ok ? "Struts OK · highest utilisation" : "Struts overloaded"}</div>
          </div>
        </div>
        <p className="muted small">
          Strut {worst.label}, {worst.combination}. {frame.combinations} combinations checked over every wind direction. Hubs, bolts
          and anchors are not checked.
        </p>
        <dl>
          <dt>Frame mass</dt>
          <dd>{Math.round(frame.frameMass)} kg</dd>
          <dt>Cover area</dt>
          <dd>{frame.surfaceArea.toFixed(1)} m²</dd>
          <dt>Height</dt>
          <dd>{frame.height.toFixed(2)} m</dd>
        </dl>
      </div>

      {c && (
        <div className="card">
          <h3>{CASE_TITLES[view]}</h3>
          <dl>
            <dt>Total load</dt>
            <dd>
              {view.startsWith("W")
                ? `${Math.hypot(c.total[0], c.total[1]).toFixed(2)} kN sideways, ${c.total[2].toFixed(2)} kN up`
                : `${(-c.total[2]).toFixed(2)} kN down`}
            </dd>
            <dt>Strut forces</dt>
            <dd>
              {kn(-Math.min(0, ...c.forces))} C · {kn(Math.max(0, ...c.forces))} T kN
            </dd>
            <dt>Largest movement</dt>
            <dd>{c.maxDisplacement.toFixed(2)} mm</dd>
          </dl>
          <small className="muted">Characteristic values (unfactored), struts only — joint slip adds to movement.</small>
        </div>
      )}

      <div className="card">
        <h3>Struts</h3>
        <table className="pick">
          <thead>
            <tr>
              <th />
              <th>Type</th>
              <th>Qty</th>
              <th title="Largest design compression / buckling resistance">C / N_b,Rd kN</th>
              <th title="Largest design tension">T kN</th>
              <th>Use</th>
            </tr>
          </thead>
          <tbody>
            {frame.struts.map((s, i) => (
              <tr key={s.label} {...rowProps(i)}>
                <td>
                  <i className="swatch" style={{ background: colorFor(i) }} />
                </td>
                <td>
                  {s.label} <small className="muted">{(s.length * 1000).toFixed(0)} mm</small>
                </td>
                <td>{s.count}</td>
                <td>
                  {kn(-s.compression)} <small className="muted">/ {kn(s.bucklingResistance)}</small>
                </td>
                <td>{kn(s.tension)}</td>
                <td>
                  <UtilBar u={s.utilisation} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <WindCard frame={frame} />

      <div className="card">
        <h3>Foundation, per support</h3>
        <dl>
          <dt>Push down</dt>
          <dd>{kn(maxDown)} kN</dd>
          <dt>Uplift</dt>
          <dd>{maxUp > 0 ? `${kn(maxUp)} kN — anchor it` : "none"}</dd>
          <dt>Sideways</dt>
          <dd>{kn(maxH)} kN</dd>
          <dt>Supports</dt>
          <dd>{sup.length} base hubs, pinned</dd>
        </dl>
        <small className="muted">Design values (factored), worst over all combinations.</small>
      </div>
    </>
  );
}

function UtilBar({ u }: { u: number }) {
  const over = u > 1;
  return (
    <span className="util" title={`${pct(u)} of capacity`}>
      <span className="util-track">
        <span className="util-fill" style={{ width: `${Math.min(100, u * 100)}%`, background: over ? CRITICAL : UTIL_RAMP[3] }} />
      </span>
      <span className="num">
        {pct(u)}
        {over && " ⚠"}
      </span>
    </span>
  );
}

/** c_pe along the arc in the wind direction: windward edge A, crown B, leeward edge C. */
function WindCard({ frame }: { frame: Frame }) {
  const { qp, ze, fd, hd, cpe } = frame.wind;
  const W = 300;
  const H = 120;
  const pad = { l: 34, r: 40, t: 14, b: 22 };
  const lo = -1.8;
  const hi = 1.0;
  const x = (t: number) => pad.l + ((t + 1) / 2) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + ((hi - v) / (hi - lo)) * (H - pad.t - pad.b);
  const pts = cpe.map((v, i) => [x(i - 1), y(v)] as const);
  return (
    <div className="card">
      <h3>Wind on the cover</h3>
      <svg className="cpe-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`c_pe: A ${cpe[0].toFixed(2)}, B ${cpe[1].toFixed(2)}, C ${cpe[2].toFixed(2)}`}>
        {[-1.5, -1, -0.5, 0, 0.5].map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} className={v === 0 ? "axis" : "grid"} />
            <text x={pad.l - 6} y={y(v) + 4} textAnchor="end" className="tick">
              {v > 0 ? `+${v}` : v}
            </text>
          </g>
        ))}
        <text x={x(-0.5)} y={y(0.75)} textAnchor="middle" className="tick">
          ↓ pressure
        </text>
        <text x={x(-0.5)} y={y(-1.62)} textAnchor="middle" className="tick">
          ↑ suction
        </text>
        <polyline points={pts.map((p) => p.join(",")).join(" ")} className="line" />
        {pts.map(([px, py], i) => (
          <g key={i}>
            <circle cx={px} cy={py} r={4.5} className="dot">
              <title>{`${"ABC"[i]}: c_pe ${cpe[i].toFixed(2)}`}</title>
            </circle>
            <text x={px} y={H - 6} textAnchor={["start", "middle", "end"][i] as "start"} dx={[-10, 0, 10][i]} className="tick strong">
              {["A windward", "B crown", "C leeward"][i]}
            </text>
            <text x={px + 8} y={py + (i === 1 ? 14 : -8)} textAnchor="start" className="tick">
              {cpe[i].toFixed(2)}
            </text>
          </g>
        ))}
      </svg>
      <dl>
        <dt>Peak pressure q_p</dt>
        <dd>
          {(qp / 1000).toFixed(3)} kN/m² <small className="muted">at {ze.toFixed(1)} m</small>
        </dd>
        <dt>Shape</dt>
        <dd>
          f/d {fd.toFixed(2)} · h/d {hd.toFixed(2)}
        </dd>
      </dl>
      <small className="muted">EN 1991-1-4 Fig. 7.12, c_pe,10. Linear between A, B, C along the wind; constant across it.</small>
    </div>
  );
}

export type { CaseKey };
