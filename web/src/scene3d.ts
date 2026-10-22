import * as THREE from "three";

const UP = new THREE.Vector3(0, 1, 0);

/** Many arrows in two draw calls: instanced shafts and heads. */
export class ArrowField {
  readonly group = new THREE.Group();
  private shafts: THREE.InstancedMesh;
  private heads: THREE.InstancedMesh;
  private n = 0;
  private m = new THREE.Matrix4();
  private q = new THREE.Quaternion();

  constructor(capacity: number, material: THREE.Material) {
    const shaft = new THREE.CylinderGeometry(1, 1, 1, 8).translate(0, 0.5, 0);
    const head = new THREE.ConeGeometry(1, 1, 12).translate(0, 0.5, 0);
    this.shafts = new THREE.InstancedMesh(shaft, material, Math.max(1, capacity));
    this.heads = new THREE.InstancedMesh(head, material, Math.max(1, capacity));
    this.shafts.count = this.heads.count = 0;
    this.group.add(this.shafts, this.heads);
  }

  /** Arrow from `from` along unit `dir`, total length `len`, shaft radius `r`. */
  add(from: THREE.Vector3, dir: THREE.Vector3, len: number, r: number, color?: THREE.Color): void {
    const i = this.n++;
    const headLen = Math.min(len * 0.4, r * 7);
    const shaftLen = Math.max(len - headLen, 1e-6);
    this.q.setFromUnitVectors(UP, dir);
    this.m.compose(from, this.q, new THREE.Vector3(r, shaftLen, r));
    this.shafts.setMatrixAt(i, this.m);
    const tip = from.clone().addScaledVector(dir, shaftLen);
    this.m.compose(tip, this.q, new THREE.Vector3(r * 2.6, headLen, r * 2.6));
    this.heads.setMatrixAt(i, this.m);
    if (color) {
      this.shafts.setColorAt(i, color);
      this.heads.setColorAt(i, color);
    }
  }

  done(): this {
    for (const im of [this.shafts, this.heads]) {
      im.count = this.n;
      im.instanceMatrix.needsUpdate = true;
      if (im.instanceColor) im.instanceColor.needsUpdate = true;
      im.computeBoundingSphere();
    }
    return this;
  }
}

/** Text that always faces the camera; height in world units. */
export function textSprite(text: string, height: number, color: string, background?: string): THREE.Sprite {
  const pad = 14;
  const px = 52;
  const c = document.createElement("canvas");
  const ctx = c.getContext("2d")!;
  ctx.font = `600 ${px}px system-ui, -apple-system, sans-serif`;
  c.width = Math.ceil(ctx.measureText(text).width) + pad * 2;
  c.height = px + pad * 2;
  ctx.font = `600 ${px}px system-ui, -apple-system, sans-serif`;
  if (background) {
    ctx.fillStyle = background;
    ctx.beginPath();
    ctx.roundRect(0, 0, c.width, c.height, 18);
    ctx.fill();
  }
  ctx.fillStyle = color;
  ctx.textBaseline = "middle";
  ctx.fillText(text, pad, c.height / 2 + 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  sprite.scale.set((height * c.width) / c.height, height, 1);
  sprite.renderOrder = 10;
  return sprite;
}

/** A flat arrow lying on the ground, pointing along `dir` (three.js coords, y = 0). */
export function groundArrow(dir: THREE.Vector3, length: number, width: number, y: number, color: THREE.Color, opacity: number) {
  const s = new THREE.Shape();
  const h = width / 2;
  const head = length * 0.32;
  s.moveTo(0, -h * 0.45);
  s.lineTo(length - head, -h * 0.45);
  s.lineTo(length - head, -h);
  s.lineTo(length, 0);
  s.lineTo(length - head, h);
  s.lineTo(length - head, h * 0.45);
  s.lineTo(0, h * 0.45);
  s.closePath();
  const mesh = new THREE.Mesh(
    new THREE.ShapeGeometry(s),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false }),
  );
  mesh.rotation.x = -Math.PI / 2; // shape x → world x, shape y → world -z
  mesh.rotation.z = Math.atan2(-dir.z, dir.x);
  mesh.position.y = y;
  const g = new THREE.Group();
  g.add(mesh);
  return g;
}

/**
 * Wind streaks: tracers carried by potential flow around a sphere of radius R at the origin
 * (three.js coords, y up), slowed near the ground by a log-law profile. Faster over the crown
 * = suction there; slower in front = pressure.
 */
export class Airflow {
  readonly lines: THREE.LineSegments;
  private pos: Float32Array; // tails: particles × TAIL points × 3
  private alive: Float32Array;
  private readonly TAIL = 22;
  private readonly speed: number;
  private wind: THREE.Vector3;
  private side: THREE.Vector3;
  private v = new THREE.Vector3();
  private p = new THREE.Vector3();

  constructor(
    private R: number,
    private ground: number,
    private top: number,
    dir: THREE.Vector3,
    private count: number,
    color: THREE.Color,
    reduceMotion: boolean,
  ) {
    this.wind = dir.clone().normalize();
    this.side = new THREE.Vector3(0, 1, 0).cross(this.wind).normalize();
    this.speed = R * 0.9; // world units per second, for the eye
    const segs = count * (this.TAIL - 1);
    this.pos = new Float32Array(count * this.TAIL * 3);
    this.alive = new Float32Array(count);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(segs * 2 * 3), 3));
    const col = new Float32Array(segs * 2 * 4);
    for (let i = 0; i < count; i++)
      for (let k = 0; k < this.TAIL - 1; k++) {
        const s = (i * (this.TAIL - 1) + k) * 2;
        const a0 = 1 - k / (this.TAIL - 1);
        const a1 = 1 - (k + 1) / (this.TAIL - 1);
        col.set([color.r, color.g, color.b, a0 * 0.6, color.r, color.g, color.b, a1 * 0.6], s * 4);
      }
    geo.setAttribute("color", new THREE.BufferAttribute(col, 4));
    this.lines = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false }));
    this.lines.frustumCulled = false;
    for (let i = 0; i < count; i++) this.spawn(i, true);
    if (reduceMotion) for (let k = 0; k < 400; k++) this.step(1 / 30); // settle into a still picture
    this.write();
  }

  private velocity(p: THREE.Vector3, out: THREE.Vector3): THREE.Vector3 {
    const r = Math.max(p.length(), this.R * 1.001);
    const x = p.dot(this.wind);
    const k = this.R ** 3 / 2;
    out.copy(this.wind).multiplyScalar(1 + k / r ** 3).addScaledVector(p, (-3 * k * x) / r ** 5);
    const h = Math.max(p.y - this.ground, 0.02 * this.R);
    const profile = Math.log(h / (0.05 * this.R) + 1) / Math.log((this.top - this.ground) / (0.05 * this.R) + 1);
    return out.multiplyScalar(this.speed * Math.min(1.25, Math.max(0.25, profile)));
  }

  private spawn(i: number, anywhere: boolean): void {
    const span = this.R * 1.4;
    const along = anywhere ? (Math.random() * 2 - 1) * this.R * 3 : -this.R * 3;
    const across = (Math.random() * 2 - 1) * span;
    const up = this.ground + Math.random() * (this.top - this.ground) * 1.15;
    this.p.copy(this.wind).multiplyScalar(along).addScaledVector(this.side, across).setY(up);
    if (this.p.length() < this.R * 1.05) this.p.addScaledVector(this.side, this.R * 1.2 * Math.sign(across || 1));
    for (let k = 0; k < this.TAIL; k++) this.pos.set([this.p.x, this.p.y, this.p.z], (i * this.TAIL + k) * 3);
    this.alive[i] = 0;
  }

  step(dt: number): void {
    const T = this.TAIL;
    for (let i = 0; i < this.count; i++) {
      const o = i * T * 3;
      this.pos.copyWithin(o + 3, o, o + (T - 1) * 3); // shift the tail
      this.p.fromArray(this.pos, o);
      this.velocity(this.p, this.v);
      this.p.addScaledVector(this.v, dt);
      if (this.p.y < this.ground) this.p.y = this.ground;
      this.p.toArray(this.pos, o);
      this.alive[i] += dt;
      if (this.p.dot(this.wind) > this.R * 3 || this.p.length() < this.R * 0.98) this.spawn(i, false);
    }
  }

  write(): void {
    const T = this.TAIL;
    const out = (this.lines.geometry.getAttribute("position") as THREE.BufferAttribute).array as Float32Array;
    let w = 0;
    for (let i = 0; i < this.count; i++) {
      const o = i * T * 3;
      for (let k = 0; k < T - 1; k++) {
        for (let c = 0; c < 6; c++) out[w++] = this.pos[o + k * 3 + c];
      }
    }
    this.lines.geometry.getAttribute("position").needsUpdate = true;
  }

  tick = (dt: number) => {
    this.step(dt);
    this.write();
  };
}
