"""Glue tab (flap) construction.

A tab is attached along one triangle edge (the fold line) and lies on the
outward side of it. Its shape is a trapezoid:

    start ----------------------------- end         <- fold line (triangle edge)
       \\ theta_s                 theta_e /
        \\                               /
         p1 --------------------------- p2          <- parallel to the edge, at distance `width`

`theta_s` / `theta_e` are the angles between the fold line and the slanted tab
ends. The slanted ends start exactly at the triangle vertices, so the outer cut
contour passes through every vertex.

Corner trimming strategy: bevel. Each tab is the outward offset strip of its
edge (width measured perpendicular to the edge) cut off at both ends by a line
through the vertex at angle theta. Tabs are separate regions; they never share
material. A miter join (offset strips meeting on a common line) is not used:
its end angle is 180deg - alpha/2 > 90deg, so tabs would overhang past the
vertex and collide as soon as they are folded.

Choice of end angle (see `tab_end_angle`): by default the end angle at a vertex
is ``min(max_end_angle, interior_angle / 2)``. With that cap, if every tab is
folded fully flat onto the back of its own triangle, the folded tabs are
bounded by the vertex angle bisectors and therefore never overlap each other,
whatever the fold angle. This is the condition that keeps neighbouring tabs from
colliding near the vertices during assembly.

If the edge is too short for a full-width trapezoid (the two slanted ends meet
before reaching `width`), the tab degrades into a triangle whose apex is the
intersection of the two slanted ends; it is then marked ``truncated``. With the
bisector cap this happens exactly when ``width > inradius`` of the triangle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .vec import Vec2

#: Smallest non-zero tab width (1 micrometre). Anything narrower is physically
#: meaningless and numerically indistinguishable from the fold line.
MIN_TAB_WIDTH_MM = 1e-3

#: Top lengths below this fraction of the edge length are treated as zero (apex).
_APEX_REL_TOL = 1e-9


@dataclass(frozen=True, slots=True)
class TabSpec:
    """How glue tabs should be generated.

    width: perpendicular width of each tab in mm (0 disables tabs).
    max_end_angle_deg: upper bound for the angle between fold line and tab end, (0, 90].
    clamp_to_bisector: also limit the end angle to half the interior vertex angle
        (recommended; guarantees that tabs of the same triangle never collide).
    """

    width: float
    max_end_angle_deg: float = 45.0
    clamp_to_bisector: bool = True

    def __post_init__(self) -> None:
        w = float(self.width)
        if not math.isfinite(w) or w < 0.0:
            raise ValueError(f"tab width must be a finite number >= 0, got {self.width!r}")
        if 0.0 < w < MIN_TAB_WIDTH_MM:
            raise ValueError(f"tab width must be 0 (no tabs) or at least {MIN_TAB_WIDTH_MM} mm, got {w!r}")
        ang = float(self.max_end_angle_deg)
        if not math.isfinite(ang) or not (0.0 < ang <= 90.0):
            raise ValueError(f"max_end_angle_deg must be in (0, 90], got {self.max_end_angle_deg!r}")
        object.__setattr__(self, "width", w)
        object.__setattr__(self, "max_end_angle_deg", ang)

    @property
    def enabled(self) -> bool:
        return self.width > 0.0

    @property
    def max_end_angle(self) -> float:
        return math.radians(self.max_end_angle_deg)


def tab_end_angle(interior_angle: float, spec: TabSpec) -> float:
    """Angle (radians) between the fold line and the tab end at a vertex."""
    angle = spec.max_end_angle
    if spec.clamp_to_bisector:
        angle = min(angle, interior_angle / 2.0)
    return angle


@dataclass(frozen=True, slots=True)
class GlueTab:
    start: Vec2  # fold line start (triangle vertex)
    end: Vec2  # fold line end (triangle vertex)
    outer: tuple[Vec2, ...]  # (p1, p2) for a trapezoid, (apex,) when truncated
    start_angle: float  # radians
    end_angle: float  # radians
    requested_width: float
    height: float  # actual perpendicular height (== requested_width unless truncated)

    @property
    def truncated(self) -> bool:
        return len(self.outer) == 1

    @property
    def fold_length(self) -> float:
        return (self.end - self.start).length()

    @property
    def top_length(self) -> float:
        """Length of the outer edge parallel to the fold line (0 when truncated)."""
        if self.truncated:
            return 0.0
        return (self.outer[1] - self.outer[0]).length()

    @property
    def polygon(self) -> tuple[Vec2, ...]:
        """Counter-clockwise tab polygon: start, outer points, end."""
        return (self.start, *self.outer, self.end)

    @property
    def area(self) -> float:
        return self.height * (self.fold_length + self.top_length) / 2.0


def build_tab(start: Vec2, end: Vec2, start_angle: float, end_angle: float, width: float) -> GlueTab:
    """Build a tab on the right-hand (outward, for a CCW polygon) side of start->end."""
    if not (width > 0.0 and math.isfinite(width)):
        raise ValueError(f"tab width must be positive and finite, got {width!r}")
    for name, ang in (("start_angle", start_angle), ("end_angle", end_angle)):
        if not (0.0 < ang <= math.pi / 2 + 1e-15):
            raise ValueError(f"{name} must be in (0, pi/2], got {ang!r}")

    d = end - start
    length = d.length()
    if length == 0.0:
        raise ValueError("tab edge has zero length")
    u = d / length
    n = u.perp_right()  # outward normal

    cot_s = math.cos(start_angle) / math.sin(start_angle)
    cot_e = math.cos(end_angle) / math.sin(end_angle)

    top = length - width * (cot_s + cot_e)
    if top > _APEX_REL_TOL * length:
        p1 = start + u * (width * cot_s) + n * width
        p2 = end - u * (width * cot_e) + n * width
        return GlueTab(start, end, (p1, p2), start_angle, end_angle, width, width)

    # Slanted ends meet below the requested width: triangular tab.
    h = length / (cot_s + cot_e)
    apex = start + u * (h * cot_s) + n * h
    return GlueTab(start, end, (apex,), start_angle, end_angle, width, h)
