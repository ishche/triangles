import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { Dome } from "./api";
import { colorFor } from "./palette";
import { bindPointer, clearGroup, createStage, frameCamera, pointerNdc, type Stage, toThree } from "./stage";

export type ColorBy = "types" | "struts" | "loads";

type Props = {
  dome: Dome;
  colorBy: ColorBy;
  highlight: number | null; // face type or strut index, depending on colorBy
  autoRotate: boolean;
  onHover: (faceType: number | null) => void;
  onPick: (faceType: number | null) => void;
};

type Scene = Stage & { mesh?: THREE.Mesh; lines?: THREE.LineSegments };

const DIM = new THREE.Color("#9a958c");

export function DomeCanvas({ dome, colorBy, highlight, autoRotate, onHover, onPick }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const s = useRef<Scene | null>(null);
  const callbacks = useRef({ onHover, onPick });
  callbacks.current = { onHover, onPick };
  const framed = useRef(""); // radius|portion the camera was last framed for

  // One-time setup: stage and picking (hover shows a face type, a click selects it).
  useEffect(() => {
    const st: Scene = createStage(host.current!);
    s.current = st;
    framed.current = "";
    const ray = new THREE.Raycaster();
    const pick = (e: PointerEvent): number | null => {
      const mesh = st.mesh;
      if (!mesh) return null;
      ray.setFromCamera(pointerNdc(st, e), st.camera);
      const hit = ray.intersectObject(mesh)[0];
      return hit?.faceIndex != null ? (mesh.userData.faceTypes as number[])[hit.faceIndex] : null;
    };
    const unbind = bindPointer(
      st,
      (e) => callbacks.current.onHover(e ? pick(e) : null),
      (e) => callbacks.current.onPick(pick(e)),
    );
    return () => {
      unbind();
      st.dispose();
      s.current = null;
    };
  }, []);

  useEffect(() => {
    if (s.current) s.current.controls.autoRotate = autoRotate;
  }, [autoRotate]);

  // Rebuild geometry when the dome changes; reframe the camera only when its size changes.
  useEffect(() => {
    const sc = s.current!;
    clearGroup(sc.group);

    const pos: number[] = [];
    for (const f of dome.faces) for (const i of f) pos.push(...toThree(dome.vertices[i]).toArray());
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(pos.length), 3));
    geo.computeVertexNormals();
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({
        vertexColors: true,
        flatShading: true,
        side: THREE.DoubleSide,
        roughness: 0.85,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      }),
    );
    mesh.userData.faceTypes = dome.faceTypes;

    const lpos: number[] = [];
    for (const [a, b] of dome.edges) lpos.push(...toThree(dome.vertices[a]).toArray(), ...toThree(dome.vertices[b]).toArray());
    const lgeo = new THREE.BufferGeometry();
    lgeo.setAttribute("position", new THREE.Float32BufferAttribute(lpos, 3));
    lgeo.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(lpos.length), 3));
    const lines = new THREE.LineSegments(lgeo, new THREE.LineBasicMaterial({ vertexColors: true }));

    const zs = dome.vertices.map((v) => v[2]);
    const minY = Math.min(...zs);
    sc.group.add(mesh, lines, groundRing(dome.radius, minY));
    sc.mesh = mesh;
    sc.lines = lines;

    const key = `${dome.radius}|${dome.portion}`;
    if (framed.current !== key) {
      framed.current = key;
      frameCamera(sc, dome.radius, minY, Math.max(...zs));
    }
  }, [dome]);

  // Colours: faces and struts, dimming everything outside the highlighted group.
  useEffect(() => {
    const { mesh, lines } = s.current ?? {};
    if (!mesh || !lines) return;
    const fc = mesh.geometry.getAttribute("color") as THREE.BufferAttribute;
    const lc = lines.geometry.getAttribute("color") as THREE.BufferAttribute;
    const ink = new THREE.Color("#2b2824");
    const paper = new THREE.Color("#f3efe6");
    const c = new THREE.Color();

    dome.faceTypes.forEach((t, i) => {
      if (colorBy === "types") {
        c.set(colorFor(t));
        if (highlight !== null && t !== highlight) c.lerp(DIM, 0.75);
      } else c.copy(paper);
      for (let k = 0; k < 3; k++) fc.setXYZ(i * 3 + k, c.r, c.g, c.b);
    });
    dome.edgeStruts.forEach((st, i) => {
      if (colorBy === "struts") {
        c.set(colorFor(st));
        if (highlight !== null && st !== highlight) c.lerp(DIM, 0.8);
      } else c.copy(ink);
      lc.setXYZ(i * 2, c.r, c.g, c.b);
      lc.setXYZ(i * 2 + 1, c.r, c.g, c.b);
    });
    fc.needsUpdate = true;
    lc.needsUpdate = true;
  }, [dome, colorBy, highlight]);

  return <div className="canvas" ref={host} />;
}

/** A faint ring on the ground at the lowest vertex row. */
export function groundRing(radius: number, y: number): THREE.Mesh {
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(radius * 1.15, radius * 1.17, 96),
    new THREE.MeshBasicMaterial({ color: "#9a958c", transparent: true, opacity: 0.35, side: THREE.DoubleSide }),
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = y;
  return ring;
}
