"""Independent checks for a finished multi-sheet layout."""

from __future__ import annotations

from collections.abc import Sequence

from ..geometry.convex import convex_distance, convex_hull
from ..geometry.polygon import convex_overlap_depth
from .packing import Demand, PackOptions, printable_area
from .sheet import Sheet

_TOL = 1e-6  # mm


def layout_problems(sheets: Sequence[Sheet], demands: Sequence[Demand], options: PackOptions) -> list[str]:
    """Every rule a layout must satisfy; an empty list means valid.

    * each demand is placed exactly `count` times (matched by piece and label);
    * every cut outline lies inside the printable area (margins, ruler band);
    * any two pieces on a sheet are at least `spacing` apart (outlines' convex
      hulls are used, which can only under-estimate the true distance).
    """
    problems: list[str] = []
    placements = [(i, p) for i, s in enumerate(sheets) for p in s.placements]
    for d in demands:
        n = sum(1 for _, p in placements if p.piece == d.piece and p.label == d.label)
        if n != d.count:
            problems.append(f"{d.label or 'piece'}: placed {n}, expected {d.count}")
    known = {(d.piece, d.label) for d in demands}
    if any((p.piece, p.label) not in known for _, p in placements):
        problems.append("layout contains pieces that were not requested")

    for si, sheet in enumerate(sheets):
        area, _ = printable_area(sheet.width, sheet.height, options)
        hulls, boxes = [], []
        for pi, pl in enumerate(sheet.placements):
            bb = pl.bbox
            boxes.append(bb)
            if (
                bb.min_x < area.min_x - _TOL
                or bb.max_x > area.max_x + _TOL
                or bb.min_y < area.min_y - _TOL
                or bb.max_y > area.max_y + _TOL
            ):
                problems.append(f"sheet {si} piece {pi} is outside the printable area")
            hulls.append(convex_hull(pl.cut_outline))
        for i in range(len(hulls)):
            for j in range(i + 1, len(hulls)):
                a, b = boxes[i], boxes[j]
                gap = max(a.min_x - b.max_x, b.min_x - a.max_x, a.min_y - b.max_y, b.min_y - a.max_y)
                if gap >= options.spacing:
                    continue  # boxes already far enough apart, so the pieces are too
                if convex_overlap_depth(hulls[i], hulls[j]) > _TOL:
                    problems.append(f"sheet {si}: pieces {i} and {j} overlap")
                    continue
                dist = convex_distance(hulls[i], hulls[j])
                if dist < options.spacing - _TOL:
                    problems.append(f"sheet {si}: pieces {i} and {j} are {dist:.4f} mm apart, closer than spacing")
    return problems
