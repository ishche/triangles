"""PDF renderer (standard library only).

Physical size:
  * Each page's MediaBox is the sheet size converted to points (1 pt = 1/72 in,
    so 1 mm = 72 / 25.4 pt exactly). A4 is 595.2756 x 841.8898 pt.
  * The content stream starts with one `cm` that scales user space to
    millimetres, so all coordinates, line widths and dash lengths in the file
    are written directly in mm, at 1 nm resolution.
  * PDF user space is y-up with its origin at the bottom-left, the same as the
    sheet frame, so no flip is needed and handedness is preserved.
  * The catalog sets /PrintScaling /None, telling viewers to default to
    "actual size" rather than "fit to page" in the print dialog.

Each Sheet becomes one page, so a multi-sheet layout becomes a multi-page PDF.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from ..geometry import Vec2
from ..layout import Sheet
from .display import PathItem, RenderStyle, TextItem, display_list, sheet_description, stroke_for, text_width

MM_TO_PT = 72.0 / 25.4


def _n(v: float, decimals: int = 6) -> str:
    s = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _n_floor(v: float, decimals: int = 6) -> str:
    """Round down, so a page box never exceeds the paper.

    Exact metric sizes are irrational in points (A4 = 595.27559055... pt), and
    rasterisers round page pixels up: rounding the box up by even 1e-6 pt makes
    an A4 page 2101 px wide at 10 px/mm instead of 2100. Rounding down costs
    < 0.4 nm.
    """
    q = 10**decimals
    return _n(math.floor(v * q) / q, decimals)


def _rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _pdf_string(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _content_stream(sheet: Sheet, style: RenderStyle) -> bytes:
    out: list[str] = ["q", f"{_n(MM_TO_PT, 9)} 0 0 {_n(MM_TO_PT, 9)} 0 0 cm", "0 J 0 j 10 M"]

    def color(op: str, hex_color: str) -> str:
        return " ".join(_n(c, 4) for c in _rgb(hex_color)) + f" {op}"

    for group in display_list(sheet, style):
        out.append(f"% {group.id}")
        for item in group.items:
            if isinstance(item, PathItem):
                st = stroke_for(item.role, style)
                out.append(color("RG", st.color))
                out.append(f"{_n(st.width)} w")
                out.append(f"[{' '.join(_n(d) for d in st.dash)}] 0 d" if st.dash else "[] 0 d")
                for sub in item.subpaths:
                    out.append(f"{_n(sub[0].x)} {_n(sub[0].y)} m")
                    out.extend(f"{_n(p.x)} {_n(p.y)} l" for p in sub[1:])
                    if item.closed:
                        out.append("h")
                out.append("S")
            else:
                out.append(_text_ops(item, style, color))
    out.append("Q")
    return ("\n".join(out) + "\n").encode("latin-1")


def _text_ops(item: TextItem, style: RenderStyle, color) -> str:
    c, s = math.cos(item.angle), math.sin(item.angle)
    pos = item.position
    if item.align == "middle":
        half = text_width(item.text, item.size) / 2
        pos = Vec2(pos.x - c * half, pos.y - s * half)
    tm = " ".join(_n(v) for v in (c, s, -s, c, pos.x, pos.y))
    return (
        f"BT /F1 {_n(item.size)} Tf {color('rg', style.label_color)} {tm} Tm "
        + _pdf_string(item.text).decode("latin-1")
        + " Tj ET"
    )


def render_pdf(
    sheets: Sheet | Sequence[Sheet], style: RenderStyle | None = None, title: str = "domeprint template"
) -> bytes:
    style = style or RenderStyle()
    pages = [sheets] if isinstance(sheets, Sheet) else list(sheets)
    if not pages:
        raise ValueError("render_pdf needs at least one sheet")

    # Object numbers: 1 catalog, 2 page tree, 3 font, 4 info, then (page, content) pairs.
    page_ids = [5 + 2 * i for i in range(len(pages))]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R /ViewerPreferences << /PrintScaling /None >> >>",
        2: (f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {len(pages)} >>").encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Title "
        + _pdf_string(title)
        + b" /Subject "
        + _pdf_string(" | ".join(sheet_description(s) for s in pages))
        + b" /Producer (domeprint) >>",
    }
    for page_id, sheet in zip(page_ids, pages):
        w, h = _n_floor(sheet.width * MM_TO_PT), _n_floor(sheet.height * MM_TO_PT)
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] /CropBox [0 0 {w} {h}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>"
        ).encode()
        stream = _content_stream(sheet, style)
        objects[page_id + 1] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream"

    buf = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = len(buf)
        buf += b"%d 0 obj\n" % num + objects[num] + b"\nendobj\n"
    xref = len(buf)
    size = max(objects) + 1
    buf += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for num in range(1, size):
        buf += b"%010d 00000 n \n" % offsets[num]
    buf += b"trailer\n<< /Size %d /Root 1 0 R /Info 4 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return bytes(buf)


__all__ = ["MM_TO_PT", "render_pdf", "text_width"]
