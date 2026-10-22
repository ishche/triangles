import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

/** Renderer, camera, lights, orbit controls and a render loop inside `el`. */
export type Stage = {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  group: THREE.Group; // everything that changes with the model
  onFrame: Set<(dt: number, t: number) => void>; // called every frame with seconds
  dispose: () => void;
};

// Dome data is z-up; three.js is y-up.
export const toThree = ([x, y, z]: [number, number, number]) => new THREE.Vector3(x, z, -y);

export function createStage(el: HTMLElement): Stage {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  el.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.autoRotateSpeed = 1.2;

  scene.add(new THREE.HemisphereLight("#ffffff", "#5a5248", 1.6));
  const sun = new THREE.DirectionalLight("#ffffff", 1.6);
  sun.position.set(1, 1.6, 0.8);
  scene.add(sun);
  const group = new THREE.Group();
  scene.add(group);

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = el;
    renderer.setSize(w, h);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(el);
  resize();

  let frame = 0;
  const onFrame = new Set<(dt: number, t: number) => void>();
  const clock = new THREE.Clock();
  const tick = () => {
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;
    for (const f of onFrame) f(dt, t);
    controls.update();
    renderer.render(scene, camera);
    frame = requestAnimationFrame(tick);
  };
  tick();

  const stage: Stage = {
    renderer,
    scene,
    camera,
    controls,
    group,
    onFrame,
    dispose: () => {
      onFrame.clear();
      cancelAnimationFrame(frame);
      ro.disconnect();
      controls.dispose();
      clearGroup(group);
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
  return stage;
}

/** Point the camera at a model of the given size (z-up bounds). */
export function frameCamera(st: Stage, radius: number, minZ: number, maxZ: number, distance = 4.2, view: [number, number, number] = [0.75, 0.45, 0.55]): void {
  const midY = (minZ + maxZ) / 2;
  st.controls.target.set(0, midY, 0);
  const d = radius * distance;
  st.camera.position.set(d * view[0], midY + d * view[1], d * view[2]);
  st.camera.near = radius / 100;
  st.camera.far = radius * 100;
  st.camera.updateProjectionMatrix();
  st.controls.minDistance = radius * 1.2;
  st.controls.maxDistance = radius * 12;
}

/** Remove and free everything in the group. */
export function clearGroup(group: THREE.Group): void {
  for (const obj of [...group.children]) {
    group.remove(obj);
    obj.traverse((o) => {
      const m = o as THREE.Mesh;
      m.geometry?.dispose();
      const mat = m.material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
      else mat?.dispose();
    });
  }
}

/** Normalised device coordinates of a pointer event over the canvas. */
export function pointerNdc(st: Stage, e: PointerEvent): THREE.Vector2 {
  const r = st.renderer.domElement.getBoundingClientRect();
  return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
}

/** Calls onHover on move, onPick on a click that was not a drag. Returns an unsubscribe function. */
export function bindPointer(st: Stage, onHover: (e: PointerEvent | null) => void, onPick: (e: PointerEvent) => void): () => void {
  const c = st.renderer.domElement;
  let down: { x: number; y: number } | null = null;
  const move = (e: PointerEvent) => onHover(e);
  const press = (e: PointerEvent) => (down = { x: e.clientX, y: e.clientY });
  const up = (e: PointerEvent) => {
    if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 4) onPick(e);
    down = null;
  };
  const leave = () => onHover(null);
  c.addEventListener("pointermove", move);
  c.addEventListener("pointerdown", press);
  c.addEventListener("pointerup", up);
  c.addEventListener("pointerleave", leave);
  return () => {
    c.removeEventListener("pointermove", move);
    c.removeEventListener("pointerdown", press);
    c.removeEventListener("pointerup", up);
    c.removeEventListener("pointerleave", leave);
  };
}
