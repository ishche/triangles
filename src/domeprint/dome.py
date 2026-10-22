"""Geodesic dome geometry: class I (alternate) subdivision of an icosahedron.

Each icosahedron face is split into frequency² triangles on an equal grid,
then every point is pushed out to the sphere ("method 1"). The icosahedron
stands on a vertex, so a pentagon sits at the zenith.

Struts are grouped by length (A = shortest) and faces by the cyclic order of
their strut letters, read counter-clockwise from outside. Mirror-image faces
(e.g. ABC vs ACB) are kept as separate types: their paper templates differ
unless the sheet is flipped. A type's sides are given in that same order as
(AB, BC, CA), matching `Triangle`, whose A, B, C run counter-clockwise on
the printed side.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

Vec3 = tuple[float, float, float]

#: Lengths closer than this (relative to the radius) are the same strut.
LENGTH_TOL = 1e-6


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def _dist(a: Vec3, b: Vec3) -> float:
    d = _sub(a, b)
    return math.sqrt(_dot(d, d))


def icosahedron() -> tuple[list[Vec3], list[tuple[int, int, int]]]:
    """Unit icosahedron with vertices at both poles; faces counter-clockwise from outside."""
    z = 1 / math.sqrt(5)
    r = 2 / math.sqrt(5)
    verts: list[Vec3] = [(0.0, 0.0, 1.0)]
    verts += [(r * math.cos(k * math.tau / 5), r * math.sin(k * math.tau / 5), z) for k in range(5)]
    verts += [(r * math.cos((k + 0.5) * math.tau / 5), r * math.sin((k + 0.5) * math.tau / 5), -z) for k in range(5)]
    verts.append((0.0, 0.0, -1.0))
    faces = []
    for k in range(5):
        u0, u1 = 1 + k, 1 + (k + 1) % 5
        l0, l1 = 6 + k, 6 + (k + 1) % 5
        faces += [(0, u0, u1), (u0, l0, u1), (u1, l0, l1), (11, l1, l0)]
    return verts, [_outward(verts, f) for f in faces]


def _outward(verts: list[Vec3], f: tuple[int, int, int]) -> tuple[int, int, int]:
    a, b, c = (verts[i] for i in f)
    n = _cross(_sub(b, a), _sub(c, a))
    centroid = (a[0] + b[0] + c[0], a[1] + b[1] + c[1], a[2] + b[2] + c[2])
    return f if _dot(n, centroid) > 0 else (f[0], f[2], f[1])


def geodesic_sphere(frequency: int) -> tuple[list[Vec3], list[tuple[int, int, int]]]:
    """Unit geodesic sphere: 10·f²+2 vertices, 20·f² faces, all counter-clockwise from outside."""
    if not isinstance(frequency, int) or frequency < 1:
        raise ValueError("frequency must be a positive integer")
    base_v, base_f = icosahedron()
    verts: list[Vec3] = []
    index: dict[tuple[int, int, int], int] = {}

    def vertex(p: Vec3) -> int:
        p = _unit(p)
        key = tuple(round(x * 1e9) for x in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(p)
        return index[key]

    faces: list[tuple[int, int, int]] = []
    n = frequency
    for ia, ib, ic in base_f:
        a, b, c = base_v[ia], base_v[ib], base_v[ic]

        def grid(i: int, j: int, a=a, b=b, c=c) -> int:
            wa, wb, wc = (n - i - j) / n, i / n, j / n
            return vertex(tuple(wa * a[k] + wb * b[k] + wc * c[k] for k in range(3)))

        for i in range(n):
            for j in range(n - i):
                faces.append((grid(i, j), grid(i + 1, j), grid(i, j + 1)))
                if i + j < n - 1:
                    faces.append((grid(i + 1, j), grid(i + 1, j + 1), grid(i, j + 1)))
    return verts, [_outward(verts, f) for f in faces]


@dataclass(frozen=True, slots=True)
class Strut:
    label: str
    length: float  # mm
    factor: float  # chord factor: length / radius
    count: int


@dataclass(frozen=True, slots=True)
class FaceType:
    label: str  # strut letters counter-clockwise from outside, e.g. "BAA"
    sides: tuple[float, float, float]  # (AB, BC, CA) in mm
    count: int
    mirror_of: str | None = None  # label of the mirror-image type, if it is in the dome too


@dataclass(frozen=True, slots=True)
class Dome:
    frequency: int
    radius: float
    portion: float  # actual fraction of the sphere's height kept
    vertices: list[Vec3]  # mm, z up
    faces: list[tuple[int, int, int]]  # counter-clockwise from outside
    face_types: list[int]  # index into types, per face
    edges: list[tuple[int, int]]
    edge_struts: list[int]  # index into struts, per edge
    struts: list[Strut]
    types: list[FaceType]

    @property
    def height(self) -> float:
        zs = [v[2] for v in self.vertices]
        return max(zs) - min(zs)

    @property
    def base_diameter(self) -> float:
        zmin = min(v[2] for v in self.vertices)
        return 2 * max(math.hypot(v[0], v[1]) for v in self.vertices if v[2] - zmin < 1e-6 * self.radius)


def _letters(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def build_dome(frequency: int, radius: float, portion: float = 0.5) -> Dome:
    """A dome of the given frequency and radius (mm), cut at the vertex row nearest `portion` of the height.

    portion=1 is the full sphere, 0.5 a hemisphere. Only whole faces are kept, so the cut follows
    the nearest row of vertices; `Dome.portion` reports where it actually landed.
    """
    if not (radius > 0 and math.isfinite(radius)):
        raise ValueError("radius must be a positive number")
    if not 0 < portion <= 1:
        raise ValueError("portion must be in (0, 1]")
    unit_v, all_faces = geodesic_sphere(frequency)

    levels = sorted({round(v[2], 9) for v in unit_v})
    target = 1 - 2 * portion
    cut = min((lv for lv in levels if lv < 1), key=lambda lv: (abs(lv - target), lv))
    faces = [f for f in all_faces if min(unit_v[i][2] for i in f) >= cut - 1e-9]

    used = sorted({i for f in faces for i in f})
    remap = {old: new for new, old in enumerate(used)}
    unit_v = [unit_v[i] for i in used]
    faces = [tuple(remap[i] for i in f) for f in faces]

    # Struts, grouped by length.
    edge_set = sorted({tuple(sorted((f[k], f[(k + 1) % 3]))) for f in faces for k in range(3)})
    lengths = [_dist(unit_v[a], unit_v[b]) for a, b in edge_set]
    classes: list[float] = []
    for length in sorted(lengths):
        if not classes or length - classes[-1] > LENGTH_TOL:
            classes.append(length)

    def strut_of(length: float) -> int:
        return min(range(len(classes)), key=lambda k: abs(classes[k] - length))

    edge_struts = [strut_of(length) for length in lengths]
    strut_counts = Counter(edge_struts)
    struts = [Strut(_letters(k), classes[k] * radius, classes[k], strut_counts[k]) for k in range(len(classes))]

    # Face types: strut letters counter-clockwise from outside, rotated to the smallest string.
    def face_key(f: tuple[int, int, int]) -> tuple[int, int, int]:
        seq = [strut_of(_dist(unit_v[f[k]], unit_v[f[(k + 1) % 3]])) for k in range(3)]
        return min(tuple(seq[k:] + seq[:k]) for k in range(3))

    keys = [face_key(f) for f in faces]
    order = sorted(set(keys), key=lambda key: (-keys.count(key), key))
    key_counts = Counter(keys)

    def label(key: tuple[int, ...]) -> str:
        return "".join(struts[k].label for k in key)

    def mirror(key: tuple[int, int, int]) -> tuple[int, int, int]:
        rev = (key[0], key[2], key[1])
        return min(tuple(rev[k:] + rev[:k]) for k in range(3))

    types = [
        FaceType(
            label(key),
            tuple(struts[k].length for k in key),
            key_counts[key],
            label(mirror(key)) if mirror(key) != key and mirror(key) in key_counts else None,
        )
        for key in order
    ]
    type_index = {key: i for i, key in enumerate(order)}

    verts = [(x * radius, y * radius, z * radius) for x, y, z in unit_v]
    return Dome(
        frequency=frequency,
        radius=radius,
        portion=(1 - cut) / 2,
        vertices=verts,
        faces=faces,
        face_types=[type_index[k] for k in keys],
        edges=edge_set,
        edge_struts=edge_struts,
        struts=struts,
        types=types,
    )
