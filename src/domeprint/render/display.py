"""Renderer-neutral display list.

Turns a Sheet into plain drawing primitives (paths and text) in sheet
millimetres, y-up. Every renderer (SVG, PDF, ...) serializes the same list,
so all output formats draw exactly the same things in exactly the same places.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from ..geometry import GlueTab, Vec2
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


# Helvetica advance widths (1/1000 em) for printable ASCII, from the standard AFM.
# Only used to centre labels; unknown characters fall back to 556.
_HELVETICA_WIDTHS = dict(
    zip(
        " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
        [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278]
        + [556] * 10
        + [278, 278, 584, 584, 584, 556, 1015]
        + [667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833]
        + [722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611]
        + [278, 278, 278, 469, 556, 333]
        + [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833]
        + [556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500]
        + [334, 260, 334, 584],
        strict=True,
    )
)


def text_width(text: str, size: float) -> float:
    return sum(_HELVETICA_WIDTHS.get(ch, 556) for ch in text) * size / 1000.0


#: Helvetica cap height (and digit height) as a fraction of the font size.
#: Labels use only capitals, digits, '.' and spaces, so nothing descends below the baseline.
CAP_HEIGHT = 0.718
#: Labels are never set smaller than this; if even this size does not fit, the tab gets no label.
MIN_LABEL_SIZE_MM = 1.0
#: Label font size is at most this fraction of the tab height.
_LABEL_TAB_FRACTION = 0.6
_LABEL_SHRINK = 0.85


def tab_label(tab: GlueTab, text: str, style: RenderStyle) -> TextItem | None:
    """Place `text` on a glue tab (piece coordinates), or None if it cannot fit.

    The baseline runs parallel to the fold line, reading against the edge
    direction so the glyphs point outward (upright when the tab is seen from
    outside the triangle). The text is centred across the tab's height and
    between the two bevelled ends, measured at the height of the glyph tops,
    where the tab is narrowest. If it does not fit, the font shrinks; below
    MIN_LABEL_SIZE_MM the tab gets no label rather than spilling onto the face.
    """
    fold = tab.end - tab.start
    length = fold.length()
    u = fold / length
    outward = u.perp_right()
    cot_s = math.cos(tab.start_angle) / math.sin(tab.start_angle)
    cot_e = math.cos(tab.end_angle) / math.sin(tab.end_angle)
    size = min(style.label_size, _LABEL_TAB_FRACTION * tab.height)
    while size >= MIN_LABEL_SIZE_MM - 1e-12:
        cap = CAP_HEIGHT * size
        baseline = (tab.height - cap) / 2
        top = baseline + cap
        pad = 0.3 * size
        lo, hi = top * cot_s + pad, length - top * cot_e - pad  # free span along the fold line
        if text_width(text, size) <= hi - lo:
            anchor = tab.start + u * ((lo + hi) / 2) + outward * baseline
            return TextItem("label", text, anchor, (-u).angle(), size, "middle")
        size *= _LABEL_SHRINK
    return None


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
    if style.show_labels:
        # Labels go on the glue tabs, which end up hidden inside the dome.
        tf = pl.transform
        for edge, tab in zip(pl.piece.triangle.edges, pl.piece.tabs):
            item = tab_label(tab, f"{edge.name} {edge.length:.1f}", style)
            if item is not None:
                items.append(
                    TextItem(
                        item.role, item.text, tf.apply(item.position), item.angle + tf.angle, item.size, item.align
                    )
                )
    return Group(f"piece-{index}", tuple(items))


def _calibration_group(cal: CalibrationBar, style: RenderStyle) -> Group:
    o, length = cal.origin, cal.length
    steps = max(1, round(length / 10.0))
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
