import math

import pytest

from domeprint.dome import build_dome, geodesic_sphere
from domeprint.geometry import Triangle


@pytest.mark.parametrize("f", [1, 2, 3, 4, 5, 6])
def test_sphere_counts_and_orientation(f):
    verts, faces = geodesic_sphere(f)
    assert len(verts) == 10 * f * f + 2
    assert len(faces) == 20 * f * f
    for v in verts:
        assert math.isclose(math.dist(v, (0, 0, 0)), 1, abs_tol=1e-12)
    for a, b, c in faces:  # counter-clockwise from outside
        pa, pb, pc = verts[a], verts[b], verts[c]
        u = [pb[i] - pa[i] for i in range(3)]
        w = [pc[i] - pa[i] for i in range(3)]
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        assert sum(n[i] * (pa[i] + pb[i] + pc[i]) for i in range(3)) > 0


@pytest.mark.parametrize(
    ("f", "portion", "struts"),
    [
        (2, 0.5, {"A": (0.54653, 30), "B": (0.61803, 35)}),
        (3, 0.625, {"A": (0.34862, 30), "B": (0.40355, 55), "C": (0.41241, 80)}),
        (
            4,
            0.5,
            {
                "A": (0.25318, 30),
                "B": (0.29453, 60),
                "C": (0.29524, 30),
                "D": (0.29859, 30),
                "E": (0.31287, 70),
                "F": (0.32492, 30),
            },
        ),
    ],
)
def test_published_chord_factors(f, portion, struts):
    d = build_dome(f, 1.0, portion)
    assert {s.label: (round(s.factor, 5), s.count) for s in d.struts} == struts


def test_2v_hemisphere_types():
    d = build_dome(2, 100, 0.5)
    assert [(t.label, t.count) for t in d.types] == [("AAB", 30), ("BBB", 10)]
    assert math.isclose(d.height, 100) and math.isclose(d.base_diameter, 200)
    assert sum(t.count for t in d.types) == len(d.faces) == len(d.face_types)


def test_mirror_types_and_sides_are_valid_triangles():
    d = build_dome(4, 150, 0.5)
    mirrored = {t.label: t.mirror_of for t in d.types if t.mirror_of}
    assert mirrored == {"BDE": "BED", "BED": "BDE"}
    by_label = {s.label: s.length for s in d.struts}
    for t in d.types:
        assert t.sides == tuple(by_label[c] for c in t.label)
        Triangle(*t.sides)  # does not raise


def test_portion_snaps_to_vertex_row():
    assert build_dome(3, 1, 0.5).portion != 0.5  # 3V has no row on the equator
    assert build_dome(3, 1, 1).portion == 1


@pytest.mark.parametrize(("f", "r", "p"), [(0, 1, 0.5), (2, 0, 0.5), (2, 1, 0), (2, 1, 1.5)])
def test_rejects_bad_input(f, r, p):
    with pytest.raises(ValueError):
        build_dome(f, r, p)
