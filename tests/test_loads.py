import math

import pytest

from domeprint.frame.members import MATERIALS, Section, buckling_reduction
from domeprint.frame.snow import snow_shape
from domeprint.frame.wind import cpe_along, dome_cpe, peak_velocity_pressure

# ---------- wind: EN 1991-1-4 ----------


def test_peak_velocity_pressure_terrain_ii_10m():
    # Hand calculation: kr = 0.19, cr = 0.19·ln(10/0.05) = 1.00668, Iv = 1/ln(200) = 0.18874,
    # ce = (1 + 7·Iv)·cr² = 2.3523, qb = ½·1.25·25² = 390.625 Pa → qp = 918.9 Pa.
    assert peak_velocity_pressure(25, "II", 10) == pytest.approx(918.9, abs=0.2)


def test_peak_velocity_pressure_below_zmin_uses_zmin():
    assert peak_velocity_pressure(25, "IV", 3) == peak_velocity_pressure(25, "IV", 10)


def test_rougher_terrain_and_lower_height_reduce_pressure():
    q = [peak_velocity_pressure(27, t, 6) for t in ("0", "I", "II", "III", "IV")]
    assert q == sorted(q, reverse=True)
    assert peak_velocity_pressure(27, "II", 4) < peak_velocity_pressure(27, "II", 8)


def test_rejects_unknown_terrain():
    with pytest.raises(ValueError):
        peak_velocity_pressure(25, "V", 5)


# Figure 7.12 read at its corner points: (f/d, h/d) -> (A, B, C)
@pytest.mark.parametrize(
    ("f_d", "h_d", "abc"),
    [
        (0.5, 0.0, (0.8, -1.2, 0.0)),  # hemisphere on the ground
        (0.5, 0.5, (0.8, -1.3, -0.5)),
        (0.5, 1.0, (0.8, -1.3, -0.5)),
        (0.1, 1.0, (-1.7, -0.8, -0.5)),
        (0.05, 0.25, (-1.4, -0.375, -0.25)),  # A from the h/d = 0.25 curve; B, C halfway between 0 and 0.5
        (0.7, 0.0, (0.8, -1.2, 0.0)),  # beyond the chart: flat
    ],
)
def test_dome_cpe_chart(f_d, h_d, abc):
    assert dome_cpe(f_d, h_d) == pytest.approx(abc, abs=0.01)


def test_dome_cpe_interpolates_along_f_d():
    a, b, _ = dome_cpe(0.3, 0.0)
    assert a == pytest.approx(0.13 + (0.3 - 0.05) / 0.45 * 0.67, abs=1e-9)
    assert b == pytest.approx(-0.25 - (0.3 - 0.05) / 0.45 * 0.95, abs=1e-9)


def test_cpe_along_arc_is_linear_between_points():
    abc = (0.8, -1.2, 0.0)
    assert cpe_along(-1, abc) == 0.8
    assert cpe_along(0, abc) == -1.2
    assert cpe_along(1, abc) == 0.0
    assert cpe_along(-0.5, abc) == pytest.approx(-0.2)
    assert cpe_along(0.25, abc) == pytest.approx(-0.9)
    assert cpe_along(1.3, abc) == 0.0  # clamped


# ---------- snow: EN 1991-1-3 ----------


@pytest.mark.parametrize(("slope", "mu"), [(0, 0.8), (20, 0.8), (30, 0.8), (45, 0.4), (60, 0.0), (80, 0.0), (120, 0.0)])
def test_snow_shape_coefficient(slope, mu):
    assert snow_shape(slope) == pytest.approx(mu)


# ---------- members ----------


@pytest.mark.parametrize(
    ("lam", "alpha", "lam0", "chi"),
    [
        (0.2, 0.49, 0.2, 1.0),
        (0.1, 0.49, 0.2, 1.0),
        (1.0, 0.49, 0.2, 0.5399),  # EN 1993-1-1 Table 6.2, curve c
        (1.0, 0.21, 0.2, 0.6656),  # curve a
        (2.0, 0.49, 0.2, 0.1962),
        (1.0, 0.2, 0.3, 0.6893),  # EN 1995-1-1 k_c, solid timber (β_c = 0.2)
    ],
)
def test_buckling_reduction(lam, alpha, lam0, chi):
    assert buckling_reduction(lam, alpha, lam0) == pytest.approx(chi, abs=1e-4)


def test_section_properties():
    r = Section.rect(45, 95)
    assert r.area == pytest.approx(45 * 95 * 1e-6)
    assert r.i_min == pytest.approx(95 * 45**3 / 12 * 1e-12)
    t = Section.tube(42.4, 2.6)
    assert t.area == pytest.approx(math.pi / 4 * (42.4**2 - 37.2**2) * 1e-6)
    assert t.i_min == pytest.approx(math.pi / 64 * (42.4**4 - 37.2**4) * 1e-12)
    with pytest.raises(ValueError, match=r"45 mm.*95 mm.*22\.5 mm"):
        Section.tube(45, 95)  # timber sizes left in after switching to a tube
    with pytest.raises(ValueError):
        Section.rect(0, 10)


def test_compression_capacity_drops_with_length_and_matches_squash_load_when_short():
    m, s = MATERIALS["steel_s235"], Section.tube(42.4, 2.6)
    short = m.compression_resistance(s, 0.01)
    assert short == pytest.approx(s.area * m.design_strength)
    capacities = [m.compression_resistance(s, length) for length in (0.5, 1, 2, 4)]
    assert capacities == sorted(capacities, reverse=True)
    # Long bars approach Euler / γM.
    euler = math.pi**2 * m.e_buckling * s.i_min / 8**2
    assert m.compression_resistance(s, 8) < euler


def test_timber_design_strength_uses_kmod_and_gamma_m():
    c24 = MATERIALS["timber_c24"]
    assert c24.design_strength == pytest.approx(0.8 * 21 / 1.3 * 1e6)
    assert c24.tension_design == pytest.approx(0.8 * 14.5 / 1.3 * 1e6)
