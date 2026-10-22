"""Wind on a dome, after EN 1991-1-4:2005+A1:2010 with the recommended values.

Peak velocity pressure (§4.3–4.5, flat terrain c_o = 1, k_I = 1, c_dir = c_season = 1):

    k_r   = 0.19 · (z0 / 0.05)^0.07
    c_r   = k_r · ln(z / z0)          z clamped to [z_min, 200 m]
    I_v   = 1 / ln(z / z0)
    q_p   = (1 + 7·I_v) · ½ρ · (c_r · v_b)²      ρ = 1.25 kg/m³

External pressure on a dome with circular base (§7.2.8, Figure 7.12): c_pe,10 at
the windward edge A, the crown B and the leeward edge C depends on the rise ratio
f/d and the wall ratio h/d. Between them it varies linearly along arcs parallel to
the wind and is constant on planes perpendicular to it.
"""

from __future__ import annotations

import math
from bisect import bisect_right

AIR_DENSITY = 1.25  # kg/m³, recommended value
TERRAIN = {  # category: (z0, z_min) in m, Table 4.1
    "0": (0.003, 1.0),
    "I": (0.01, 1.0),
    "II": (0.05, 2.0),
    "III": (0.3, 5.0),
    "IV": (1.0, 10.0),
}
Z_MAX = 200.0


def peak_velocity_pressure(v_b: float, terrain: str, z: float) -> float:
    """q_p(z) in Pa for basic wind velocity v_b (m/s) at height z (m)."""
    if terrain not in TERRAIN:
        raise ValueError(f"unknown terrain category {terrain!r}; use one of {', '.join(TERRAIN)}")
    if not v_b >= 0:
        raise ValueError("wind speed must be zero or more")
    z0, z_min = TERRAIN[terrain]
    z = min(max(z, z_min), Z_MAX)
    k_r = 0.19 * (z0 / 0.05) ** 0.07
    ln = math.log(z / z0)
    c_r = k_r * ln
    i_v = 1 / ln
    return (1 + 7 * i_v) * 0.5 * AIR_DENSITY * (c_r * v_b) ** 2


# Figure 7.12, digitised as (f/d, c_pe,10) corner points; flat outside the plotted range.
_A = {  # by h/d
    0.0: [(0.05, 0.13), (0.5, 0.8)],
    0.25: [(0.05, -1.4), (0.5, 0.8)],
    1.0: [(0.05, -1.4), (0.1, -1.7), (0.335, -1.4), (0.5, 0.8)],
}
_B = {0.0: [(0.05, -0.25), (0.5, -1.2)], 0.5: [(0.05, -0.5), (0.1, -0.8), (0.25, -1.2), (0.5, -1.3)]}
_C = {0.0: [(0.05, 0.0), (0.5, 0.0)], 0.5: [(0.05, -0.5), (0.5, -0.5)]}


def _interp(points: list[tuple[float, float]], x: float) -> float:
    xs = [p[0] for p in points]
    if x <= xs[0]:
        return points[0][1]
    if x >= xs[-1]:
        return points[-1][1]
    k = bisect_right(xs, x) - 1
    (x0, y0), (x1, y1) = points[k], points[k + 1]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _curve_family(family: dict[float, list[tuple[float, float]]], f_d: float, h_d: float) -> float:
    levels = sorted(family)
    return _interp([(h, _interp(family[h], f_d)) for h in levels], h_d)


def dome_cpe(f_d: float, h_d: float) -> tuple[float, float, float]:
    """c_pe,10 at (A windward edge, B crown, C leeward edge) for rise f/d and wall height h/d."""
    return _curve_family(_A, f_d, h_d), _curve_family(_B, f_d, h_d), _curve_family(_C, f_d, h_d)


def cpe_along(t: float, abc: tuple[float, float, float]) -> float:
    """c_pe at arc position t: -1 windward edge (A), 0 crown (B), +1 leeward edge (C)."""
    a, b, c = abc
    t = min(max(t, -1.0), 1.0)
    return b + (b - a) * t if t < 0 else b + (c - b) * t
