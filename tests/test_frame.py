import math

import pytest

from domeprint.frame import FrameInputs, analyse_dome

G = 9.81


def total(vectors):
    return [sum(v[k] for v in vectors) for k in range(3)]


@pytest.fixture(scope="module")
def hemi():
    return analyse_dome(2, 0.5, FrameInputs(radius=3.0))


@pytest.mark.parametrize("case", ["G", "S", "Sd", "W+", "W-"])
def test_reactions_balance_applied_loads(hemi, case):
    c = hemi.cases[case]
    applied = total(c.loads)
    react = total(c.reactions.values())
    assert [a + r for a, r in zip(applied, react)] == pytest.approx([0, 0, 0], abs=1e-6 * max(1, *map(abs, applied)))


def test_dead_load_is_struts_plus_cover(hemi):
    inp = hemi.inputs
    strut_mass = sum(hemi.lengths) * inp.section().area * inp.material().density
    cover = inp.cover_load * 1e3 * hemi.surface_area
    assert hemi.cases["G"].loads and total(hemi.cases["G"].loads)[2] == pytest.approx(-(strut_mass * G + cover))
    assert hemi.frame_mass == pytest.approx(strut_mass)


def test_shallow_dome_carries_full_flat_roof_snow():
    # A 6V cap cut high up: every face slopes less than 30°, so μ = 0.8 everywhere.
    r = analyse_dome(6, 0.07, FrameInputs(radius=5.0, snow_sk=1.2))
    assert max(r.face_slopes) < 30
    assert -total(r.cases["S"].loads)[2] == pytest.approx(0.8 * 1.2e3 * r.plan_area)


def test_steep_faces_shed_snow(hemi):
    assert -total(hemi.cases["S"].loads)[2] < 0.8 * hemi.inputs.snow_sk * 1e3 * hemi.plan_area
    # Drifted case: windward half at 0.5 μ, leeward at μ → less in total, but not symmetric.
    assert -total(hemi.cases["Sd"].loads)[2] < -total(hemi.cases["S"].loads)[2]


def test_wind_pushes_downwind_and_lifts(hemi):
    fx, fy, fz = total(hemi.cases["W+"].loads)
    assert fx > 0  # wind blows along +x by default
    assert abs(fy) < 1e-6 * fx
    assert fz > 0  # suction over the crown
    # Internal pressure cancels sideways but lifts the open-based shell by Δc_pi · q_p · plan area.
    gx, gy, gz = total(hemi.cases["W-"].loads)
    assert (gx, gy) == pytest.approx((fx, fy), abs=1e-6 * fx)
    assert fz - gz == pytest.approx((0.2 - -0.3) * hemi.wind.q_p * hemi.plan_area)
    assert hemi.cases["W-"].forces != pytest.approx(hemi.cases["W+"].forces)


def test_wind_direction_rotates_the_resultant():
    # 108° lies on a mirror plane of the dome (every 36°), so the drag points straight downwind.
    r = analyse_dome(2, 0.5, FrameInputs(radius=3.0, wind_direction=108))
    fx, fy, _ = total(r.cases["W+"].loads)
    along = fx * math.cos(math.radians(108)) + fy * math.sin(math.radians(108))
    across = -fx * math.sin(math.radians(108)) + fy * math.cos(math.radians(108))
    assert along > 0 and abs(across) < 1e-6 * along


def test_pentagonal_symmetry_of_wind():
    a = analyse_dome(3, 0.625, FrameInputs(radius=3.0, wind_direction=10))
    b = analyse_dome(3, 0.625, FrameInputs(radius=3.0, wind_direction=82))
    assert sorted(a.cases["W+"].forces) == pytest.approx(sorted(b.cases["W+"].forces), rel=1e-6, abs=1e-6)


def test_crown_is_in_compression_under_self_weight(hemi):
    top = [
        i
        for i, (p, q) in enumerate(hemi.edges)
        if min(hemi.vertices[p][2], hemi.vertices[q][2]) > 0.8 * hemi.inputs.radius
    ]
    assert top and all(hemi.cases["G"].forces[i] < 0 for i in top)


def test_supports_are_the_open_boundary():
    r = analyse_dome(3, 0.625, FrameInputs(radius=3.0))
    # 3V 5/8 has a stepped base: 15 boundary vertices at two heights.
    assert len(r.supports) == 15
    assert len({round(r.vertices[i][2], 6) for i in r.supports}) == 2


def test_sphere_has_no_base():
    with pytest.raises(ValueError, match="base"):
        analyse_dome(2, 1.0, FrameInputs(radius=3.0))


def test_wind_geometry_parameters():
    hemi = analyse_dome(4, 0.5, FrameInputs(radius=3.0))
    assert hemi.wind.f_d == pytest.approx(0.5) and hemi.wind.h_d == pytest.approx(0)
    assert hemi.wind.cpe == pytest.approx((0.8, -1.2, 0.0), abs=0.01)
    assert hemi.wind.z_e == pytest.approx(3.0)
    # Taller than a hemisphere: the part below the equator counts as the wall height h.
    tall = analyse_dome(4, 0.75, FrameInputs(radius=3.0))
    assert tall.wind.f_d == pytest.approx(0.5)
    assert tall.wind.h_d == pytest.approx((tall.height - 3.0) / 6.0)


def test_envelope_and_utilisation(hemi):
    env = hemi.envelope
    assert len(env) == len(hemi.edges)
    m, s = hemi.inputs.material(), hemi.inputs.section()
    for e, length in zip(env, hemi.lengths):
        assert e.tension >= 0 >= e.compression
        expected = max(e.tension / m.tension_resistance(s), -e.compression / m.compression_resistance(s, length))
        assert e.utilisation == pytest.approx(expected)
    worst = max(env, key=lambda e: e.utilisation)
    assert worst.combination  # names the governing combination


def test_envelope_is_at_least_each_factored_case(hemi):
    # 1.35·G alone is one of the combinations, so the envelope must cover it.
    for e, g in zip(hemi.envelope, hemi.cases["G"].forces):
        assert e.compression <= min(0, 1.35 * g) + 1e-9
        assert e.tension >= max(0, 1.35 * g) - 1e-9


def test_bigger_section_lowers_utilisation():
    small = analyse_dome(3, 0.625, FrameInputs(radius=3.0, section_b=35, section_h=70))
    big = analyse_dome(3, 0.625, FrameInputs(radius=3.0, section_b=70, section_h=140))
    assert max(e.utilisation for e in big.envelope) < max(e.utilisation for e in small.envelope)


def test_strut_type_summary(hemi):
    by_label = {s.label: s for s in hemi.strut_summary}
    assert set(by_label) == {"A", "B"}
    for k, s in enumerate(hemi.strut_summary):
        idx = [i for i, sk in enumerate(hemi.edge_struts) if sk == k]
        assert s.count == len(idx)
        assert s.length == pytest.approx(hemi.lengths[idx[0]])
        assert s.utilisation == pytest.approx(max(hemi.envelope[i].utilisation for i in idx))
        assert s.compression == pytest.approx(min(hemi.envelope[i].compression for i in idx))
        assert s.tension == pytest.approx(max(hemi.envelope[i].tension for i in idx))


def test_rejects_bad_inputs():
    with pytest.raises(ValueError):
        analyse_dome(2, 0.5, FrameInputs(radius=-1))
    with pytest.raises(ValueError):
        analyse_dome(2, 0.5, FrameInputs(radius=3, material_key="unobtainium"))
    with pytest.raises(ValueError):
        analyse_dome(2, 0.5, FrameInputs(radius=3, terrain="VII"))


def test_face_snow_per_plan_area(hemi):
    from domeprint.frame.snow import snow_shape

    s_ground = hemi.inputs.snow_sk * hemi.inputs.snow_ce * 1e3
    for slope, s in zip(hemi.face_slopes, hemi.face_snow["S"]):
        assert s == pytest.approx(snow_shape(slope) * s_ground)
    drift = hemi.face_snow["Sd"]
    assert all(d in (pytest.approx(s), pytest.approx(s / 2)) for d, s in zip(drift, hemi.face_snow["S"]))
    assert any(d < s for d, s in zip(drift, hemi.face_snow["S"]))
