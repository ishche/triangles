import * as THREE from "three";

// Strut forces: diverging, compression red ↔ grey ↔ tension blue.
// Wind on the cover: diverging, pressure red ↔ light neutral ↔ suction blue (shown with struts in ink, never both at once).
// Utilisation: one blue ramp, auto-scaled; over capacity is the reserved critical red with a ⚠ label.
export const TENSION = "#2a78d6";
export const COMPRESSION = "#e34948";
export const CRITICAL = "#d03b3b";
export const FORCE_RAMP = ["#9b1c1c", COMPRESSION, "#8f8a82", TENSION, "#0d366b"];
export const PRESSURE_RAMP = ["#104281", "#5598e7", "#b7d3f6", "#eeece7", "#f5b3a8", "#e34948", "#9b1c1c"]; // suction … pressure
export const UTIL_RAMP = ["#b7d3f6", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"];
export const SNOW = "#f4f8fc";

function ramp(stops: string[], t: number, out: THREE.Color): THREE.Color {
  const x = Math.max(0, Math.min(1, t)) * (stops.length - 1);
  const k = Math.min(stops.length - 2, Math.floor(x));
  return out.set(stops[k]).lerp(new THREE.Color(stops[k + 1]), x - k);
}

/** Force f (kN, + tension) on a symmetric scale of ±fmax. */
export function forceColor(f: number, fmax: number, out = new THREE.Color()): THREE.Color {
  return ramp(FORCE_RAMP, fmax > 0 ? 0.5 + f / fmax / 2 : 0.5, out);
}

/** Net wind pressure p (kN/m², + pushes in) on a symmetric scale of ±pmax. */
export function pressureColor(p: number, pmax: number, out = new THREE.Color()): THREE.Color {
  return ramp(PRESSURE_RAMP, pmax > 0 ? 0.5 + p / pmax / 2 : 0.5, out);
}

/** Utilisation u on a 0…scale ramp; critical red above 100%. */
export function utilColor(u: number, scale: number, out = new THREE.Color()): THREE.Color {
  if (u > 1) return out.set(CRITICAL);
  return ramp(UTIL_RAMP, u / scale, out);
}

/** Round up to 1, 2, 2.5 or 5 × 10ⁿ. */
export function niceMax(x: number): number {
  if (!(x > 0)) return 1;
  const e = 10 ** Math.floor(Math.log10(x));
  return [1, 2, 2.5, 5, 10].map((m) => m * e).find((v) => v >= x * 0.999)!;
}

/** Scale top for the utilisation ramp: fitted to the worst strut, never above 100%. */
export const utilScale = (utils: number[]) => Math.min(1, niceMax(Math.max(...utils)));

export const CPI: Record<string, number> = { "W+": 0.2, "W-": -0.3 };

/** Net pressure per face in kN/m² for a wind case (+ pushes the cover in). */
export function netPressure(faceCpe: number[], qp: number, view: string): number[] {
  return faceCpe.map((c) => ((c - CPI[view]) * qp) / 1000);
}

/** A CSS custom property as a three.js colour (follows light/dark mode). */
export function cssColor(name: string, fallback: string): THREE.Color {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return new THREE.Color(v || fallback);
}
