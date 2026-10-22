import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { CaseKey, Frame } from "./api";
import { groundRing } from "./DomeCanvas";
import { cssColor, forceColor, netPressure, pressureColor, SNOW, utilColor, utilScale } from "./loadColors";
import { Airflow, ArrowField, groundArrow, textSprite } from "./scene3d";
import { bindPointer, clearGroup, createStage, frameCamera, pointerNdc, type Stage, toThree } from "./stage";

export type LoadView = "envelope" | CaseKey;
export type WindColour = "pressure" | "forces";

type Props = {
  frame: Frame;
  view: LoadView;
  windColour: WindColour;
  airflow: boolean;
  deflect: boolean;
  highlight: number | null; // strut type to emphasise
  hovered: number | null; // strut (edge) under the pointer
  autoRotate: boolean;
  onHover: (h: { edge: number; x: number; y: number } | null) => void;
};

type Model = {
  base: THREE.Vector3[]; // hub positions, three.js coords
  strutR: number;
  cover: THREE.Mesh;
  struts: THREE.InstancedMesh;
  radii: Float32Array; // per strut, set by the view
  windDir: THREE.Vector3;
};

type Scene = Stage & { model?: Model; overlay?: THREE.Group; anim?: (dt: number, t: number) => void };

const isWind = (v: LoadView) => v === "W+" || v === "W-";
const reduceMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/** Deflection exaggeration so the largest movement shows as 7% of the radius. */
export function deflectionScale(frame: Frame, view: CaseKey): number {
  const max = frame.cases[view].maxDisplacement / 1000;
  return max > 0 ? (frame.radius * 0.07) / max : 0;
}

export function FrameCanvas({ frame, view, windColour, airflow, deflect, highlight, hovered, autoRotate, onHover }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const hudArrow = useRef<SVGGElement>(null);
  const s = useRef<Scene | null>(null);
  const cb = useRef(onHover);
  cb.current = onHover;
  const framed = useRef("");

  useEffect(() => {
    const st: Scene = createStage(host.current!);
    s.current = st;
    framed.current = "";
    const ray = new THREE.Raycaster();
    const hover = (e: PointerEvent | null) => {
      const struts = st.model?.struts;
      if (!e || !struts) return cb.current(null);
      ray.setFromCamera(pointerNdc(st, e), st.camera);
      const hit = ray.intersectObject(struts)[0];
      const r = st.renderer.domElement.getBoundingClientRect();
      cb.current(hit?.instanceId != null ? { edge: hit.instanceId, x: e.clientX - r.left, y: e.clientY - r.top } : null);
    };
    const unbind = bindPointer(st, hover, () => {});
    // Keep the wind badge's arrow pointing the way the wind goes on screen.
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    const hud = () => {
      const el = hudArrow.current;
      const dir = st.model?.windDir;
      if (!el || !dir) return;
      a.copy(st.controls.target).project(st.camera);
      b.copy(st.controls.target).add(dir).project(st.camera);
      const deg = (Math.atan2(-(b.y - a.y) / st.camera.aspect, b.x - a.x) * 180) / Math.PI;
      if (!Number.isFinite(deg)) return;
      el.setAttribute("transform", `rotate(${deg.toFixed(1)} 16 16)`);
    };
    st.onFrame.add(hud);
    return () => {
      unbind();
      st.dispose();
      s.current = null;
    };
  }, []);

  useEffect(() => {
    if (s.current) s.current.controls.autoRotate = autoRotate;
  }, [autoRotate]);

  // Model: cover, strut tubes, supports. Rebuilt when the analysis changes.
  useEffect(() => {
    const sc = s.current!;
    clearGroup(sc.group);
    const R = frame.radius;
    const strutR = Math.max(R * 0.008, 0.004);
    const base = frame.vertices.map(toThree);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array(frame.faces.length * 9), 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(frame.faces.length * 9), 3));
    const cover = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, side: THREE.DoubleSide, roughness: 0.9, transparent: true }),
    );
    cover.renderOrder = 1;

    const struts = new THREE.InstancedMesh(
      new THREE.CylinderGeometry(1, 1, 1, 10),
      new THREE.MeshStandardMaterial({ roughness: 0.5 }),
      frame.edges.length,
    );
    struts.setColorAt(0, new THREE.Color());

    const supports = new THREE.Group();
    const supportGeo = new THREE.BoxGeometry(strutR * 5, strutR * 2.5, strutR * 5);
    const supportMat = new THREE.MeshStandardMaterial({ color: "#3b3732", roughness: 0.8 });
    for (const sp of frame.supports) {
      const m = new THREE.Mesh(supportGeo, supportMat);
      m.position.copy(base[sp.node]).add(new THREE.Vector3(0, -strutR * 1.5, 0));
      supports.add(m);
    }

    const minY = Math.min(...base.map((v) => v.y));
    const overlay = new THREE.Group();
    sc.group.add(cover, struts, supports, overlay, groundRing(R, minY - strutR * 2.75));
    const w = (frame.wind.direction * Math.PI) / 180;
    const windDir = new THREE.Vector3(Math.cos(w), 0, -Math.sin(w));
    sc.model = { base, strutR, cover, struts, radii: new Float32Array(frame.edges.length).fill(strutR), windDir };
    sc.overlay = overlay;

    const key = `${R}|${frame.portion}`;
    if (framed.current !== key) {
      framed.current = key;
      // From a little upwind and above: wind at 0° blows left to right, and the windward face shows.
      frameCamera(sc, R, minY, Math.max(...base.map((v) => v.y)), 5.4, [-0.42, 0.36, 0.83]);
    }
  }, [frame]);

  // View: colours, thickness, overlays, animation.
  useEffect(() => {
    const sc = s.current;
    const model = sc?.model;
    if (!sc || !model || !sc.overlay) return;
    const { base, strutR, cover, struts, radii } = model;
    const overlay = sc.overlay;
    const R = frame.radius;
    const ink = cssColor("--ink", "#1d1b18");
    const muted = cssColor("--muted", "#6f695f");
    const paper = new THREE.Color("#ece7dc");
    const c = new THREE.Color();
    const wind = isWind(view);
    const pressureMode = wind && windColour === "pressure";
    const caseView = view === "envelope" ? null : frame.cases[view];
    const showDeflection = deflect && caseView !== null;

    // Cover colour and opacity.
    const fc = cover.geometry.getAttribute("color") as THREE.BufferAttribute;
    const pnet = wind ? netPressure(frame.faceCpe, frame.wind.qp, view) : [];
    const pmax = Math.max(1e-9, ...pnet.map(Math.abs));
    frame.faces.forEach((_, i) => {
      if (pressureMode) pressureColor(pnet[i], pmax, c);
      else c.copy(paper);
      for (let k = 0; k < 3; k++) fc.setXYZ(i * 3 + k, c.r, c.g, c.b);
    });
    fc.needsUpdate = true;
    const coverMat = cover.material as THREE.MeshStandardMaterial;
    coverMat.opacity = pressureMode ? 0.96 : 0.32;
    coverMat.depthWrite = pressureMode;

    // Struts: colour and thickness.
    const values = view === "envelope" ? frame.envelope.utilisation : frame.cases[view].forces;
    const fmax = Math.max(1e-9, ...values.map(Math.abs));
    const uScale = utilScale(frame.envelope.utilisation);
    frame.edges.forEach((_, i) => {
      const v = values[i];
      const mag = view === "envelope" ? Math.min(1, v / uScale) : Math.abs(v) / fmax;
      if (pressureMode) {
        c.copy(ink).lerp(muted, 0.35);
        radii[i] = strutR * 0.55;
      } else {
        if (view === "envelope") utilColor(v, uScale, c);
        else forceColor(v, fmax, c);
        radii[i] = strutR * (0.5 + 0.9 * mag);
      }
      if (highlight !== null && frame.edgeStruts[i] !== highlight) c.lerp(muted, 0.75);
      if (i === hovered) radii[i] *= 1.7;
      struts.setColorAt(i, c);
    });
    if (struts.instanceColor) struts.instanceColor.needsUpdate = true;

    // Shape: hubs moved by k × exaggerated displacement.
    const disp = caseView ? caseView.displacements.map((d) => toThree([d[0] / 1000, d[1] / 1000, d[2] / 1000])) : [];
    const exaggerate = caseView ? deflectionScale(frame, view as CaseKey) : 0;
    const pts = base.map((p) => p.clone());
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    const d = new THREE.Vector3();
    const mid = new THREE.Vector3();
    const layout = (k: number) => {
      for (let i = 0; i < base.length; i++) {
        pts[i].copy(base[i]);
        if (k && disp.length) pts[i].addScaledVector(disp[i], k * exaggerate);
      }
      const pos = cover.geometry.getAttribute("position") as THREE.BufferAttribute;
      const shrink = 1 - strutR / R; // keep the cover just inside the tubes
      frame.faces.forEach((f, i) => f.forEach((v, k2) => pos.setXYZ(i * 3 + k2, pts[v].x * shrink, pts[v].y * shrink, pts[v].z * shrink)));
      pos.needsUpdate = true;
      cover.geometry.computeVertexNormals();
      frame.edges.forEach(([a, b], i) => {
        d.subVectors(pts[b], pts[a]);
        const len = d.length();
        q.setFromUnitVectors(up, d.normalize());
        m.compose(mid.addVectors(pts[a], pts[b]).multiplyScalar(0.5), q, new THREE.Vector3(radii[i], len, radii[i]));
        struts.setMatrixAt(i, m);
      });
      struts.instanceMatrix.needsUpdate = true;
      struts.computeBoundingSphere();
    };

    // Overlays.
    clearGroup(overlay);
    if (sc.anim) sc.onFrame.delete(sc.anim);
    sc.anim = undefined;
    const minY = Math.min(...base.map((p) => p.y));
    const maxY = Math.max(...base.map((p) => p.y));
    const windDir = model.windDir;
    const arrowMat = () => new THREE.MeshStandardMaterial({ color: ink, roughness: 0.6 });

    if (wind || view === "Sd") {
      // A broad arrow on the ground through the dome's footprint, pointing downwind.
      const g = groundArrow(windDir, R * 2.9, R * 0.9, minY - strutR * 2.7, ink, 0.1);
      g.position.addScaledVector(windDir, -R * 1.45);
      overlay.add(g);
    }

    if (showDeflection) {
      // Ghost of the unloaded shape.
      const lpos: number[] = [];
      for (const [a, b] of frame.edges) lpos.push(...base[a].toArray(), ...base[b].toArray());
      const lg = new THREE.BufferGeometry();
      lg.setAttribute("position", new THREE.Float32BufferAttribute(lpos, 3));
      overlay.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: muted, transparent: true, opacity: 0.45 })));
    } else if (view === "G") {
      const loads = frame.cases.G.loads;
      const lmax = Math.max(1e-9, ...loads.map((l) => Math.hypot(...l)));
      const f = new ArrowField(loads.length, arrowMat());
      loads.forEach((l, i) => {
        const len = (R * 0.22 * Math.hypot(...l)) / lmax;
        if (len < R * 0.01) return;
        f.add(base[i].clone().add(new THREE.Vector3(0, len + strutR * 2, 0)), new THREE.Vector3(0, -1, 0), len, strutR * 0.35);
      });
      overlay.add(f.done().group);
    } else if (view === "S" || view === "Sd") {
      // Snow layer: each face's snow as a slab raised above it, thickness ∝ load per m² of plan.
      const snow = frame.faceSnow[view];
      const smax = Math.max(1e-9, ...snow);
      const spos: number[] = [];
      frame.faces.forEach((face, i) => {
        if (snow[i] <= 0) return;
        const t = (R * 0.08 * snow[i]) / smax;
        const ctr = face.map((v) => base[v]).reduce((a, b) => a.clone().add(b)).multiplyScalar(1 / 3);
        for (const v of face) spos.push(...base[v].clone().lerp(ctr, 0.06).add(new THREE.Vector3(0, t + strutR, 0)).toArray());
      });
      const sg = new THREE.BufferGeometry();
      sg.setAttribute("position", new THREE.Float32BufferAttribute(spos, 3));
      sg.computeVertexNormals();
      overlay.add(new THREE.Mesh(sg, new THREE.MeshStandardMaterial({ color: SNOW, roughness: 1, side: THREE.DoubleSide, flatShading: true })));
    } else if (wind) {
      // Push/pull arrows on the cover: inward = pressure, outward = suction.
      const f = new ArrowField(frame.faces.length, arrowMat());
      frame.faces.forEach((face, i) => {
        const [a, b, cc] = face.map((v) => base[v]);
        const n = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(cc, a)).normalize();
        const ctr = a.clone().add(b).add(cc).multiplyScalar(1 / 3);
        const len = (R * 0.17 * Math.abs(pnet[i])) / pmax;
        if (len < R * 0.025) return;
        if (pnet[i] > 0) f.add(ctr.clone().addScaledVector(n, len + strutR * 2), n.clone().negate(), len, strutR * 0.5);
        else f.add(ctr.clone().addScaledVector(n, strutR * 2), n, len, strutR * 0.5);
      });
      overlay.add(f.done().group);
    }

    if (wind && airflow) {
      const flow = new Airflow(R, minY, maxY, windDir, 520, ink, reduceMotion());
      overlay.add(flow.lines);
      if (!reduceMotion()) sc.anim = flow.tick;
    }

    // Foundation reactions: arrows ending at the base hubs.
    if (caseView && !showDeflection) {
      const rs = caseView.reactions;
      const rmax = Math.max(1e-9, ...rs.map(([, x, y, z]) => Math.hypot(x, y, z)));
      const f = new ArrowField(rs.length, new THREE.MeshStandardMaterial({ color: muted, roughness: 0.7 }));
      for (const [node, x, y, z] of rs) {
        const v = toThree([x, y, z]);
        const len = (R * 0.35 * v.length()) / rmax;
        if (len < R * 0.015) continue;
        const dir = v.normalize();
        const tip = base[node].clone().add(new THREE.Vector3(0, -strutR * 2.8, 0));
        f.add(tip.clone().addScaledVector(dir, -len), dir, len, strutR * 0.45);
      }
      overlay.add(f.done().group);
    }

    // The worst strut, labelled.
    if (view === "envelope") {
      const u = frame.envelope.utilisation;
      const worst = u.indexOf(Math.max(...u));
      const [a, b] = frame.edges[worst];
      const at = base[a].clone().add(base[b]).multiplyScalar(0.5);
      const label = textSprite(
        `${u[worst] > 1 ? "⚠ " : ""}max ${Math.round(u[worst] * 100)}% · strut ${frame.struts[frame.edgeStruts[worst]].label}`,
        R * 0.11,
        "#ffffff",
        u[worst] > 1 ? "#d03b3b" : "#1c5cab",
      );
      label.position.copy(at).add(at.clone().setY(0).normalize().multiplyScalar(R * 0.25)).add(new THREE.Vector3(0, R * 0.12, 0));
      overlay.add(label);
      const stem = new THREE.BufferGeometry().setFromPoints([at, label.position.clone().add(new THREE.Vector3(0, -R * 0.05, 0))]);
      overlay.add(new THREE.Line(stem, new THREE.LineBasicMaterial({ color: "#1c5cab" })));
    }

    // Deflection: the loaded shape, held still, over the grey ghost of the unloaded one.
    layout(showDeflection ? 1 : 0);
    if (sc.anim) sc.onFrame.add(sc.anim);
  }, [frame, view, windColour, airflow, deflect, highlight, hovered]);

  const windy = isWind(view) || view === "Sd";
  return (
    <>
      <div className="canvas" ref={host} />
      <div className={`wind-hud ${windy ? "" : "hidden"}`} aria-hidden={!windy}>
        <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden>
          <g ref={hudArrow}>
            <path d="M4 16h20M18 9l7 7-7 7" />
          </g>
        </svg>
        <div>
          <b>Wind {frame.wind.direction}°</b>
          <div className="muted">
            q_p {(frame.wind.qp / 1000).toFixed(2)} kN/m² at {frame.wind.ze.toFixed(1)} m
          </div>
        </div>
      </div>
    </>
  );
}
