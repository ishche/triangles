"""Renderer-neutral display list.

Turns a Sheet into plain drawing primitives (paths and text) in sheet
millimetres, y-up. Every renderer (SVG, PDF, ...) serializes the same list,
so all output formats draw exactly the same things in exactly the same places.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..geometry import Vec2
from ..layout import CalibrationBar, Placement, Sheet

Role = Literal["cut", "fold", "calibration", "label"]


@dataclass(frozen=True, slots=True)
class RenderStyle:
    cut_color: str = "#000000"
    cut_width: float = 0.2  # mm
    fold_color: str = "#1f5fbf"
    fold_width: float = 0.2  # mm
    fold_dash: tuple[float, float] = (2.0, 1.0)  # mm
    label_color: str = "#777777"
    label_size: float = 3.0  # mm (font size)
    show_labels: bool = True
    decimals: int = 4  # SVG coordinate decimals (0.1 micrometre)


@dataclass(frozen=True, slots=True)
class Stroke:
    color: str
    width: float  # mm
    dash: tuple[float, ...] | None = None  # mm


@dataclass(frozen=True, slots=True)
class PathItem:
    role: Role
    subpaths: tuple[tuple[Vec2, ...], ...]
    closed: bool = False


@dataclass(frozen=True, slots=True)
class TextItem:
    role: Role
    text: str
    position: Vec2  # baseline anchor
    angle: float  # baseline direction, radians counter-clockwise
    size: float  # font size, mm
    align: Literal["start", "middle"] = "start"


@dataclass(frozen=True, slots=True)
class Group:
    id: str
    items: tuple[PathItem | TextItem, ...]


CALIBRATION_TICK_MM = 2.0
CALIBRATION_END_TICK_MM = 3.0


def stroke_for(role: Role, style: RenderStyle) -> Stroke:
    if role == "fold":
        return Stroke(style.fold_color, style.fold_width, style.fold_dash)
    return Stroke(style.cut_color, style.cut_width)


def _placement_group(index: int, pl: Placement, style: RenderStyle) -> Group:
    items: list[PathItem | TextItem] = [PathItem("cut", (pl.cut_outline,), closed=True)]
    if pl.fold_lines:
        items.append(PathItem("fold", tuple((s.start, s.end) for s in pl.fold_lines)))
    if style.show_labels and pl.piece.triangle.inradius >= 1.5 * style.label_size:
        for e in pl.edges:
            # Baseline runs along the edge, offset inward; glyphs grow toward the
            # interior because the triangle is counter-clockwise.
            anchor = e.midpoint + (-e.outward_normal) * (0.8 * style.label_size)
            items.append(
                TextItem("label", f"{e.name} {e.length:.1f}", anchor, e.direction.angle(), style.label_size, "middle")
            )
    return Group(f"piece-{index}", tuple(items))


def _calibration_group(cal: CalibrationBar, style: RenderStyle) -> Group:
    o, length = cal.origin, cal.length
    steps = max(1, int(round(length / 10.0)))
    subpaths = [(o, o + Vec2(length, 0))]
    for i in range(steps + 1):
        p = o + Vec2(i * length / steps, 0)
        h = CALIBRATION_END_TICK_MM if i in (0, steps) else CALIBRATION_TICK_MM
        subpaths.append((p, p + Vec2(0, h)))
    return Group("calibration", (PathItem("calibration", tuple(subpaths)),))


def display_list(sheet: Sheet, style: RenderStyle) -> tuple[Group, ...]:
    groups = [_placement_group(i, pl, style) for i, pl in enumerate(sheet.placements)]
    if sheet.calibration:
        groups.append(_calibration_group(sheet.calibration, style))
    return tuple(groups)


def sheet_description(sheet: Sheet) -> str:
    pieces = "; ".join(
        f"piece {i}: AB={p.piece.triangle.ab} BC={p.piece.triangle.bc} CA={p.piece.triangle.ca} mm, "
        f"tab {p.piece.tab_spec.width} mm"
        for i, p in enumerate(sheet.placements)
    )
    return "Solid = cut, dashed = fold. Units: mm. " + pieces
