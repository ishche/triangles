"""No-fit polygons (NFP) for convex shapes and the exact sliding contacts derived from them.

For a fixed convex shape A and a moving convex shape B (both in their own
local coordinates), translating B by v makes the interiors overlap exactly
when v is strictly inside

    NFP(A, B) = A + (-B)        (Minkowski sum with B reflected through the origin)

A horizontal line through the NFP at height dy therefore gives the open
interval of forbidden x-offsets (lo, hi). Placing B at dx = hi puts it in
exact contact on the right of A. The same holds vertically.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..geometry import Vec2
from ..geometry.convex import minkowski_sum, negate, x_section, y_section


def no_fit_polygon(fixed: Sequence[Vec2], moving: Sequence[Vec2]) -> tuple[Vec2, ...]:
    return minkowski_sum(fixed, negate(moving))


def slide_right(fixed, moving, dy: float, nfp=None) -> float | None:
    """Smallest dx placing `moving` (shifted by dy) to the right of `fixed` without overlap.

    None when the shapes cannot overlap at this dy, so there is no constraint.
    """
    s = x_section(nfp if nfp is not None else no_fit_polygon(fixed, moving), dy)
    return None if s is None else s[1]


def slide_up(fixed, moving, dx: float, nfp=None) -> float | None:
    """Smallest dy placing `moving` (shifted by dx) above `fixed` without overlap."""
    s = y_section(nfp if nfp is not None else no_fit_polygon(fixed, moving), dx)
    return None if s is None else s[1]
