export type Params = {
  ab: number;
  bc: number;
  ca: number;
  tab: number;
  max_tab_angle: number;
  bisector: boolean;
  paper: string;
  margin: number;
  count: number | null; // null = as many as fit on one sheet
  spacing: number;
  calibration: boolean;
  labels: boolean;
};

export type Sheet = { svg: string; width: number; height: number; pieces: number };

export type RenderResult = {
  sheets: Sheet[];
  triangle: {
    sides: { ab: number; bc: number; ca: number };
    angles: { a: number; b: number; c: number };
    area: number;
    inradius: number;
    circumradius: number;
  };
  tabs: { edge: string; startAngle: number; endAngle: number; height: number }[];
  warnings: string[];
  pieces: number;
  fill: number | null;
};

export const DEFAULTS: Params = {
  ab: 61.8,
  bc: 54.7,
  ca: 54.7,
  tab: 5,
  max_tab_angle: 45,
  bisector: true,
  paper: "A4",
  margin: 10,
  count: null,
  spacing: 2,
  calibration: true,
  labels: true,
};

export const PAPERS = ["A5", "A4", "A3", "LETTER", "LEGAL", "tight"];

async function post(path: string, params: Params, signal?: AbortSignal): Promise<Response> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    signal,
  });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      message = (await res.json()).error ?? message;
    } catch {
      /* not JSON */
    }
    throw new Error(message);
  }
  return res;
}

export async function render(params: Params, signal?: AbortSignal): Promise<RenderResult> {
  return (await post("/api/render", params, signal)).json();
}

export async function pdf(params: Params): Promise<Blob> {
  return (await post("/api/pdf", params)).blob();
}

/** Read params from the URL query, falling back to defaults. */
export function paramsFromUrl(): Params {
  const q = new URLSearchParams(window.location.search);
  const p: Params = { ...DEFAULTS };
  for (const key of Object.keys(DEFAULTS) as (keyof Params)[]) {
    const raw = q.get(key);
    if (raw === null) continue;
    const def = DEFAULTS[key];
    if (typeof def === "boolean") (p as Record<string, unknown>)[key] = raw === "1" || raw === "true";
    else if (key === "paper") p.paper = raw;
    else if (key === "count") p.count = raw === "" ? null : Math.max(1, Math.round(Number(raw)) || 1);
    else if (Number.isFinite(Number(raw))) (p as Record<string, unknown>)[key] = Number(raw);
  }
  return p;
}

export function paramsToUrl(p: Params): void {
  const q = new URLSearchParams();
  for (const key of Object.keys(DEFAULTS) as (keyof Params)[]) {
    if (p[key] === DEFAULTS[key]) continue;
    const v = p[key];
    q.set(key, typeof v === "boolean" ? (v ? "1" : "0") : v === null ? "" : String(v));
  }
  const s = q.toString();
  window.history.replaceState(null, "", s ? `?${s}` : window.location.pathname);
}

export function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export type DomeParams = { frequency: number; radius: number; portion: number };

export type Dome = {
  frequency: number;
  radius: number;
  portion: number; // where the cut actually landed
  height: number;
  baseDiameter: number;
  vertices: [number, number, number][]; // mm, z up
  faces: [number, number, number][]; // counter-clockwise from outside
  faceTypes: number[];
  edges: [number, number][];
  edgeStruts: number[];
  struts: { label: string; length: number; factor: number; count: number }[];
  types: { label: string; sides: [number, number, number]; count: number; mirrorOf: string | null }[];
};

export const DOME_DEFAULTS: DomeParams = { frequency: 3, radius: 100, portion: 0.625 };

export async function dome(p: DomeParams, signal?: AbortSignal): Promise<Dome> {
  const q = new URLSearchParams({ frequency: String(p.frequency), radius: String(p.radius), portion: String(p.portion) });
  const res = await fetch(`/api/dome?${q}`, { signal });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? `${res.status} ${res.statusText}`);
  return res.json();
}

// ---------- frame loads ----------

export type FrameParams = {
  radius: number; // m, full-size dome
  material_key: string;
  section_shape: "rect" | "tube";
  section_b: number; // mm: width, or tube diameter
  section_h: number; // mm: depth, or tube wall
  cover_load: number; // kN/m²
  snow_sk: number; // kN/m²
  snow_ce: number;
  wind_vb: number; // m/s
  terrain: string;
  wind_direction: number; // degrees, the way the wind blows
};

export const FRAME_DEFAULTS: FrameParams = {
  radius: 3,
  material_key: "timber_c24",
  section_shape: "rect",
  section_b: 45,
  section_h: 95,
  cover_load: 0.15,
  snow_sk: 1,
  snow_ce: 1,
  wind_vb: 25,
  terrain: "II",
  wind_direction: 0,
};

export type CaseKey = "G" | "S" | "Sd" | "W+" | "W-";

export type FrameCase = {
  forces: number[]; // kN per strut, + tension
  total: [number, number, number]; // kN, sum of applied loads
  reactions: [number, number, number, number][]; // [node, rx, ry, rz] kN
  maxDisplacement: number; // mm
  loads: [number, number, number][]; // kN per hub
  displacements: [number, number, number][]; // mm per hub
};

export type Frame = {
  frequency: number;
  portion: number;
  radius: number;
  height: number;
  surfaceArea: number;
  planArea: number;
  frameMass: number;
  combinations: number;
  vertices: [number, number, number][]; // m
  faces: [number, number, number][];
  edges: [number, number][];
  edgeStruts: number[];
  faceCpe: number[];
  faceSnow: { S: number[]; Sd: number[] }; // kN/m² of plan, per face
  wind: { qp: number; ze: number; fd: number; hd: number; cpe: [number, number, number]; direction: number };
  cases: Record<CaseKey, FrameCase>;
  envelope: { tension: number[]; compression: number[]; utilisation: number[]; combination: string[] };
  struts: {
    label: string;
    count: number;
    length: number;
    tension: number;
    compression: number;
    tensionResistance: number;
    bucklingResistance: number;
    utilisation: number;
    combination: string;
  }[];
  supports: { node: number; down: number; uplift: number; horizontal: number }[];
};

export async function frame(dome: { frequency: number; portion: number }, p: FrameParams, signal?: AbortSignal): Promise<Frame> {
  const res = await fetch("/api/frame", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ frequency: dome.frequency, portion: dome.portion, ...p }),
    signal,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? `${res.status} ${res.statusText}`);
  return res.json();
}
