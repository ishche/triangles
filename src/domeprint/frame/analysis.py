"""Loads on a geodesic dome frame: dead, snow and wind, combined per EN 1990.

The dome is a pin-jointed space truss (struts meet at hubs) pinned at every
vertex of its open bottom edge. The cover is assumed closed and spans each
triangle; a face's load goes one third to each of its three hubs.

Load cases (characteristic):
  G    self-weight of the struts + cover dead load
  S    snow, balanced (μ by face slope)
  Sd   snow, drifted: 0.5·μ on the windward half, μ on the leeward half
  W+   wind with internal pressure c_pi = +0.2
  W-   wind with internal pressure c_pi = -0.3

Ultimate limit state combinations (EN 1990 eq. 6.10, ψ0 snow 0.5, wind 0.6),
each with every wind direction in a 36° sector (the dome repeats every 72° and
is mirror-symmetric) plus the chosen one:
  1.35·G
  1.35·G + 1.5·S
  1.35·G + 1.5·S + 0.9·W
  1.35·G + 1.5·W + 0.75·S
  1.0·G  + 1.5·W                     (uplift)
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from ..dome import build_dome
from .members import MATERIALS, Material, Section
from .snow import snow_shape
from .truss import Truss, TrussResult, Vec3, solve
from .wind import TERRAIN, cpe_along, dome_cpe, peak_velocity_pressure

GRAVITY = 9.81
CPI = {"W+": 0.2, "W-": -0.3}  # EN 1991-1-4 §7.2.9(6) note 2: the more onerous of +0.2 and -0.3
GAMMA_G, GAMMA_G_FAV, GAMMA_Q = 1.35, 1.0, 1.5
PSI0_SNOW, PSI0_WIND = 0.5, 0.6
ENVELOPE_DIRECTIONS = tuple(range(0, 37, 6))  # degrees


@dataclass(frozen=True, slots=True)
class FrameInputs:
    radius: float = 3.0  # m, the full-size dome
    material_key: str = "timber_c24"
    section_shape: str = "rect"  # "rect" (b × h) or "tube" (diameter b, wall h)
    section_b: float = 45.0  # mm
    section_h: float = 95.0  # mm
    cover_load: float = 0.15  # kN/m² of surface, dead load of cover, insulation, hubs
    snow_sk: float = 1.0  # kN/m², characteristic ground snow load
    snow_ce: float = 1.0  # exposure: 0.8 windswept, 1.0 normal, 1.2 sheltered
    wind_vb: float = 25.0  # m/s, basic wind velocity
    terrain: str = "II"
    wind_direction: float = 0.0  # degrees in plan, the direction the wind blows towards

    def material(self) -> Material:
        if self.material_key not in MATERIALS:
            raise ValueError(f"unknown material {self.material_key!r}; use one of {', '.join(MATERIALS)}")
        return MATERIALS[self.material_key]

    def section(self) -> Section:
        if self.section_shape == "rect":
            return Section.rect(self.section_b, self.section_h)
        if self.section_shape == "tube":
            return Section.tube(self.section_b, self.section_h)
        raise ValueError("section shape must be 'rect' or 'tube'")

    def validate(self) -> None:
        if not (self.radius > 0 and math.isfinite(self.radius)):
            raise ValueError("radius must be a positive number")
        for name in ("cover_load", "snow_sk", "wind_vb"):
            v = getattr(self, name)
            if not (v >= 0 and math.isfinite(v)):
                raise ValueError(f"{name} must be zero or more")
        if not self.snow_ce > 0:
            raise ValueError("snow exposure factor must be positive")
        if self.terrain not in TERRAIN:
            raise ValueError(f"unknown terrain category {self.terrain!r}; use one of {', '.join(TERRAIN)}")
        self.material()
        self.section()


@dataclass(frozen=True)
class Case:
    name: str
    loads: list[Vec3]  # N per node
    forces: list[float]  # N per strut, + tension
    reactions: dict[int, Vec3]  # N per support, force from the foundation on the dome
    max_displacement: float  # m
    displacements: list[Vec3]  # m per node


@dataclass(frozen=True, slots=True)
class MemberEnvelope:
    tension: float  # N, ≥ 0, largest over all combinations
    compression: float  # N, ≤ 0
    utilisation: float  # max(tension / N_t,Rd, |compression| / N_b,Rd)
    combination: str  # the governing one


@dataclass(frozen=True, slots=True)
class StrutSummary:
    label: str
    count: int
    length: float  # m
    tension: float
    compression: float
    tension_resistance: float  # N_t,Rd
    buckling_resistance: float  # N_b,Rd
    utilisation: float
    combination: str


@dataclass(frozen=True, slots=True)
class SupportEnvelope:
    node: int
    down: float  # N, largest push into the foundation
    uplift: float  # N, largest pull out of it (≥ 0)
    horizontal: float  # N, largest outward/sideways thrust


@dataclass(frozen=True, slots=True)
class WindInfo:
    q_p: float  # Pa
    z_e: float  # m, reference height
    f_d: float
    h_d: float
    cpe: tuple[float, float, float]  # A, B, C


@dataclass(frozen=True)
class FrameResult:
    inputs: FrameInputs
    frequency: int
    portion: float
    vertices: list[Vec3]
    faces: list[tuple[int, int, int]]
    edges: list[tuple[int, int]]
    edge_struts: list[int]
    strut_labels: list[str]
    lengths: list[float]
    supports: list[int]
    face_slopes: list[float]  # degrees
    face_cpe: list[float]  # c_pe,10 per face for the chosen wind direction
    face_snow: dict[str, list[float]]  # "S", "Sd": N per m² of plan, per face (chosen wind direction)
    surface_area: float  # m²
    plan_area: float  # m²
    height: float  # m
    frame_mass: float  # kg
    wind: WindInfo
    cases: dict[str, Case]
    envelope: list[MemberEnvelope]
    strut_summary: list[StrutSummary]
    support_envelope: list[SupportEnvelope]
    combinations: int = field(default=0)


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _wind_geometry(verts: list[Vec3], supports: list[int], radius: float) -> tuple[float, float, float, float]:
    """(f/d, h/d, z_e, half-width a) for Figure 7.12. Below the equator the dome counts as a wall + hemisphere."""
    z_top = max(v[2] for v in verts)
    z_base = min(verts[i][2] for i in supports)
    height = z_top - z_base
    if z_base < -1e-9 * radius:
        d, f, h = 2 * radius, radius, -z_base
    else:
        d = 2 * max(math.hypot(verts[i][0], verts[i][1]) for i in supports)
        f, h = height, 0.0
    return f / d, h / d, h + f, d / 2


def analyse_dome(frequency: int, portion: float, inputs: FrameInputs) -> FrameResult:
    """Build the full-size dome and analyse it. Raises ValueError for bad input or a dome without a base."""
    inputs.validate()
    if portion >= 1:
        raise ValueError("a full sphere has no base to stand on; choose a portion below 1")
    dome = build_dome(frequency, inputs.radius, portion)
    verts, faces, edges = dome.vertices, dome.faces, dome.edges
    material, section = inputs.material(), inputs.section()
    R = inputs.radius

    # Supports: every vertex on the open bottom edge (edges used by one face only).
    edge_use = Counter(tuple(sorted((f[k], f[(k + 1) % 3]))) for f in faces for k in range(3))
    supports = sorted({i for e, n in edge_use.items() if n == 1 for i in e})
    if not supports:
        raise ValueError("this dome has no open base to stand on")

    # Faces: area, outward unit normal, centroid, slope.
    areas, normals, centroids, slopes = [], [], [], []
    for a, b, c in faces:
        n = _cross(_sub(verts[b], verts[a]), _sub(verts[c], verts[a]))
        nn = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        areas.append(nn / 2)
        normals.append((n[0] / nn, n[1] / nn, n[2] / nn))
        centroids.append(tuple((verts[a][k] + verts[b][k] + verts[c][k]) / 3 for k in range(3)))
        slopes.append(math.degrees(math.acos(max(-1.0, min(1.0, normals[-1][2])))))
    surface_area = sum(areas)
    plan_area = sum(ar * max(0.0, n[2]) for ar, n in zip(areas, normals))

    lengths = [math.dist(verts[a], verts[b]) for a, b in edges]
    nv = len(verts)

    def from_faces(face_force) -> list[Vec3]:
        loads = [[0.0, 0.0, 0.0] for _ in range(nv)]
        for i, f in enumerate(faces):
            fx, fy, fz = face_force(i)
            for v in f:
                loads[v][0] += fx / 3
                loads[v][1] += fy / 3
                loads[v][2] += fz / 3
        return [tuple(p) for p in loads]

    # Dead load: struts (half to each end) + cover.
    strut_weight = [L * section.area * material.density * GRAVITY for L in lengths]
    cover = inputs.cover_load * 1e3
    dead = [list(p) for p in from_faces(lambda i: (0.0, 0.0, -cover * areas[i]))]
    for (a, b), w in zip(edges, strut_weight):
        dead[a][2] -= w / 2
        dead[b][2] -= w / 2
    dead_loads = [tuple(p) for p in dead]

    # Snow: per m² of plan, so the vertical force on a face is s · area · cos(slope).
    s_ground = inputs.snow_ce * inputs.snow_sk * 1e3

    def snow(i: int, factor: float = 1.0) -> Vec3:
        mu = snow_shape(slopes[i])
        return (0.0, 0.0, -factor * mu * s_ground * areas[i] * max(0.0, normals[i][2]))

    def drift_factor(i: int, direction: float) -> float:
        return 0.5 if along(i, direction) < 0 else 1.0

    # Wind.
    f_d, h_d, z_e, half_width = _wind_geometry(verts, supports, R)
    q_p = peak_velocity_pressure(inputs.wind_vb, inputs.terrain, z_e)
    abc = dome_cpe(f_d, h_d)
    phi_max = math.asin(min(1.0, half_width / R))

    def along(i: int, direction: float) -> float:
        """Arc position of face i along the wind: -1 windward edge, 0 crown, +1 leeward edge."""
        w = math.radians(direction)
        x = centroids[i][0] * math.cos(w) + centroids[i][1] * math.sin(w)
        return math.asin(max(-1.0, min(1.0, x / R))) / phi_max

    def wind_loads(direction: float, cpi: float) -> list[Vec3]:
        def force(i: int) -> Vec3:
            p = (cpe_along(along(i, direction), abc) - cpi) * q_p * areas[i]  # + pushes inward
            n = normals[i]
            return (-p * n[0], -p * n[1], -p * n[2])

        return from_faces(force)

    def drift_loads(direction: float) -> list[Vec3]:
        return from_faces(lambda i: snow(i, drift_factor(i, direction)))

    # Basic load cases: G, S, then per wind direction Sd, W+, W-.
    user_dir = inputs.wind_direction % 360
    directions = [user_dir, *(d for d in ENVELOPE_DIRECTIONS if d != user_dir)]
    rhs: list[list[Vec3]] = [dead_loads, from_faces(snow)]
    for d in directions:
        rhs += [drift_loads(d), wind_loads(d, CPI["W+"]), wind_loads(d, CPI["W-"])]

    truss = Truss(verts, edges, ea=material.e_mean * section.area, supports=frozenset(supports))
    results: list[TrussResult] = solve(truss, rhs)

    def case(name: str, k: int) -> Case:
        r = results[k]
        disp = max(math.sqrt(sum(c * c for c in u)) for u in r.displacements)
        return Case(name, rhs[k], r.forces, r.reactions, disp, r.displacements)

    cases = {name: case(name, k) for k, name in enumerate(["G", "S", "Sd", "W+", "W-"])}

    # Combinations: (label, [(factor, result index)]).
    combos: list[tuple[str, list[tuple[float, int]]]] = [
        ("1.35G", [(GAMMA_G, 0)]),
        ("1.35G + 1.5S", [(GAMMA_G, 0), (GAMMA_Q, 1)]),
    ]
    for j, d in enumerate(directions):
        sd, wp, wm = 2 + 3 * j, 3 + 3 * j, 4 + 3 * j
        tag = f"{d:g}°"
        combos.append((f"1.35G + 1.5Sd({tag})", [(GAMMA_G, 0), (GAMMA_Q, sd)]))
        for wname, w in (("W+", wp), ("W-", wm)):
            wl = f"{wname}({tag})"
            combos.append((f"1.0G + 1.5{wl}", [(GAMMA_G_FAV, 0), (GAMMA_Q, w)]))
            for sname, s in (("S", 1), (f"Sd({tag})", sd)):
                fw, fs = GAMMA_Q * PSI0_WIND, GAMMA_Q * PSI0_SNOW
                combos.append((f"1.35G + 1.5{sname} + {fw:g}{wl}", [(GAMMA_G, 0), (GAMMA_Q, s), (fw, w)]))
                combos.append((f"1.35G + 1.5{wl} + {fs:g}{sname}", [(GAMMA_G, 0), (GAMMA_Q, w), (fs, s)]))

    ne = len(edges)
    t_max, t_by = [0.0] * ne, [""] * ne
    c_min, c_by = [0.0] * ne, [""] * ne
    sup_down = dict.fromkeys(supports, 0.0)
    sup_up = dict.fromkeys(supports, 0.0)
    sup_h = dict.fromkeys(supports, 0.0)
    for label, terms in combos:
        forces = [0.0] * ne
        for factor, k in terms:
            fk = results[k].forces
            forces = [x + factor * y for x, y in zip(forces, fk)]
        for i, f in enumerate(forces):
            if f > t_max[i]:
                t_max[i], t_by[i] = f, label
            elif f < c_min[i]:
                c_min[i], c_by[i] = f, label
        for n in supports:
            rx = ry = rz = 0.0
            for factor, k in terms:
                x, y, z = results[k].reactions[n]
                rx, ry, rz = rx + factor * x, ry + factor * y, rz + factor * z
            sup_down[n] = max(sup_down[n], rz)
            sup_up[n] = max(sup_up[n], -rz)
            sup_h[n] = max(sup_h[n], math.hypot(rx, ry))

    n_t = material.tension_resistance(section)
    n_b_by_strut = {}
    envelope = []
    for i in range(ne):
        n_b = material.compression_resistance(section, lengths[i])
        n_b_by_strut.setdefault(dome.edge_struts[i], n_b)
        ut, uc = t_max[i] / n_t, -c_min[i] / n_b
        envelope.append(MemberEnvelope(t_max[i], c_min[i], max(ut, uc), t_by[i] if ut >= uc else c_by[i]))

    summary = []
    for k, strut in enumerate(dome.struts):
        idx = [i for i, s in enumerate(dome.edge_struts) if s == k]
        worst = max(idx, key=lambda i: envelope[i].utilisation)
        summary.append(
            StrutSummary(
                label=strut.label,
                count=len(idx),
                length=lengths[idx[0]],
                tension=max(envelope[i].tension for i in idx),
                compression=min(envelope[i].compression for i in idx),
                tension_resistance=n_t,
                buckling_resistance=n_b_by_strut[k],
                utilisation=envelope[worst].utilisation,
                combination=envelope[worst].combination,
            )
        )

    return FrameResult(
        inputs=inputs,
        frequency=frequency,
        portion=dome.portion,
        vertices=verts,
        faces=faces,
        edges=edges,
        edge_struts=dome.edge_struts,
        strut_labels=[s.label for s in dome.struts],
        lengths=lengths,
        supports=supports,
        face_slopes=slopes,
        face_cpe=[cpe_along(along(i, user_dir), abc) for i in range(len(faces))],
        face_snow={
            "S": [snow_shape(slopes[i]) * s_ground for i in range(len(faces))],
            "Sd": [snow_shape(slopes[i]) * s_ground * drift_factor(i, user_dir) for i in range(len(faces))],
        },
        surface_area=surface_area,
        plan_area=plan_area,
        height=dome.height,
        frame_mass=sum(lengths) * section.area * material.density,
        wind=WindInfo(q_p, z_e, f_d, h_d, abc),
        cases=cases,
        envelope=envelope,
        strut_summary=summary,
        support_envelope=[SupportEnvelope(n, sup_down[n], sup_up[n], sup_h[n]) for n in supports],
        combinations=len(combos),
    )
