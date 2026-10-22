"""SVG renderer.

The document is sized in millimetres (width="210mm") with a viewBox in the
same numbers, so one user unit is exactly 1 mm. Geometry is in a y-up frame;
it is converted point by point with y_svg = sheet.height - y. That is a change
of coordinate frame, not a mirror of the shape: the piece looks the same as in
the geometry frame, so scalene triangles keep their handedness.

Styling uses presentation attributes (not CSS) for compatibility with cutting
machine software. Stroke centres lie exactly on the geometry.
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

from ..geometry import Vec2
from ..layout import Sheet
from .display import PathItem, RenderStyle, TextItem, display_list, sheet_description, stroke_for

#: Backwards-compatible name.
SvgStyle = RenderStyle


def _num(v: float, decimals: int) -> str:
    s = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def render_svg(sheet: Sheet, style: RenderStyle | None = None, title: str = "domeprint template") -> str:
    style = style or RenderStyle()

    def n(v: float) -> str:
        return _num(v, style.decimals)

    def pt(p: Vec2) -> str:
        return f"{n(p.x)} {n(sheet.height - p.y)}"

    def path(item: PathItem) -> str:
        st = stroke_for(item.role, style)
        d = " ".join("M " + " L ".join(pt(p) for p in sub) for sub in item.subpaths)
        if item.closed:
            d += " Z"
        dash = f' stroke-dasharray="{" ".join(n(x) for x in st.dash)}"' if st.dash else ""
        return (
            f'    <path class="{item.role}" d="{d}" fill="none" stroke="{st.color}" '
            f'stroke-width="{n(st.width)}" stroke-linejoin="miter" stroke-miterlimit="10"{dash}/>'
        )

    def text(item: TextItem) -> str:
        x, y = n(item.position.x), n(sheet.height - item.position.y)
        rot = ""
        if item.angle:
            # SVG rotation is clockwise in its y-down frame.
            rot = f' transform="rotate({n(-math.degrees(item.angle))} {x} {y})"'
        anchor = ' text-anchor="middle"' if item.align == "middle" else ""
        return (
            f'    <text class="{item.role}" x="{x}" y="{y}"{rot}{anchor} font-family="Helvetica, Arial, sans-serif" '
            f'font-size="{n(item.size)}" fill="{style.label_color}">{escape(item.text)}</text>'
        )

    wd, ht = n(sheet.width), n(sheet.height)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{wd}mm" height="{ht}mm" viewBox="0 0 {wd} {ht}">',
        f"  <title>{escape(title)}</title>",
        f"  <desc>{escape(sheet_description(sheet))}</desc>",
    ]
    for group in display_list(sheet, style):
        lines.append(f'  <g id="{group.id}">')
        for item in group.items:
            lines.append(path(item) if isinstance(item, PathItem) else text(item))
        lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


__all__ = ["SvgStyle", "render_svg"]
