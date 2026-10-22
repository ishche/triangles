"""Runtime verification of a Piece against the template constraints.

`build_piece` runs this on every piece it creates, so a template that breaks
any constraint can never reach layout or rendering. Tolerances are relative to
the piece size (default 1e-9, i.e. 1 nm on a 1 m triangle).

Constraints checked:
 1. Triangle dimensions are preserved: fold lines are the exact triangle edges.
 2. Each tab is attached to its edge: its base is exactly that edge.
 3. Tab width is perpendicular: outer points sit at exactly `height` from the
    edge line, on the outward side, and the outer edge is parallel to it.
    `height` equals the requested width unless the tab is truncated.
 4. Tabs are convex and lie entirely in the outward half-plane of their edge,
    so they never cover the triangle.
 5. Tabs do not overlap each other (they may touch only at a shared vertex).
 6. Corner trimming: the tab ends at each vertex leave a gap angle > 0.
 7. The cut outline is a simple (non-self-intersecting) CCW polygon whose area
    is exactly the triangle plus all tabs.
"""

from __future__ import annotations

import math

from .piece import Piece
from .polygon import convex_overlap_depth, is_convex_ccw, is_simple_polygon, signed_area
from .vec import distance


class GeometryError(ValueError):
    """A piece violates one of the template constraints."""


def _line_distance(p, a, b) -> float:
    """Signed distance of p from line a->b, positive on the left (inside)."""
    d = b - a
    return d.cross(p - a) / d.length()


def piece_problems(piece: Piece, rel_tol: float = 1e-9) -> list[str]:
    """All constraint violations of `piece` (empty list means valid)."""
    t = piece.triangle
    scale = max(t.sides)
    eps = rel_tol * scale
    problems: list[str] = []
    edges = t.edges

    # 1. fold lines == triangle edges
    if piece.tab_spec.enabled:
        if len(piece.fold_lines) != 3:
            problems.append(f"expected 3 fold lines, got {len(piece.fold_lines)}")
        for seg, e in zip(piece.fold_lines, edges):
            if distance(seg.start, e.start) > eps or distance(seg.end, e.end) > eps:
                problems.append(f"fold line {e.name} is not on the triangle edge")
            if abs(seg.length - e.length) > eps:
                problems.append(f"fold line {e.name} length {seg.length} != side {e.length}")
        if len(piece.tabs) != 3:
            problems.append(f"expected 3 tabs, got {len(piece.tabs)}")
    elif piece.tabs or piece.fold_lines:
        problems.append("tabs disabled but piece has tabs or fold lines")

    for e, tab in zip(edges, piece.tabs):
        # 2. attached to the edge
        if distance(tab.start, e.start) > eps or distance(tab.end, e.end) > eps:
            problems.append(f"tab {e.name} is not attached to its edge")
        # 3. perpendicular width, parallel outer edge
        for o in tab.outer:
            h = -_line_distance(o, e.start, e.end)
            if abs(h - tab.height) > eps:
                problems.append(f"tab {e.name} outer point at {h} mm, expected {tab.height} mm")
        if tab.height > tab.requested_width + eps:
            problems.append(f"tab {e.name} is wider than requested")
        if not tab.truncated and abs(tab.height - tab.requested_width) > eps:
            problems.append(f"tab {e.name} height {tab.height} != width {tab.requested_width}")
        # 4. convex and on the outward side
        if not is_convex_ccw(tab.polygon, eps):
            problems.append(f"tab {e.name} is not a convex CCW polygon")
        if any(_line_distance(p, e.start, e.end) > eps for p in tab.polygon):
            problems.append(f"tab {e.name} reaches inside the triangle")

    # 5. tabs pairwise disjoint
    tabs = piece.tabs
    for i in range(len(tabs)):
        for j in range(i + 1, len(tabs)):
            if convex_overlap_depth(tabs[i].polygon, tabs[j].polygon) > eps:
                problems.append(f"tabs {edges[i].name} and {edges[j].name} overlap")

    # 6. corner gap between the two tabs meeting at each vertex
    if len(tabs) == 3:
        for k, e in enumerate(edges):
            prev_tab = tabs[k - 1]  # ends at e.start
            gap = 2 * math.pi - e.start_angle - prev_tab.end_angle - tabs[k].start_angle
            if gap <= 0:
                problems.append(f"tabs at vertex {e.name[0]} leave no corner gap")

    # 7. outline
    outline = piece.cut_outline
    if not is_simple_polygon(outline, eps):
        problems.append("cut outline self-intersects")
    area = signed_area(outline)
    expected = t.area + sum(tab.area for tab in tabs)
    if area <= 0:
        problems.append("cut outline is not counter-clockwise")
    elif abs(area - expected) > rel_tol * 10 * expected:
        problems.append(f"cut outline area {area} != triangle + tabs {expected}")
    return problems


def validate_piece(piece: Piece, rel_tol: float = 1e-9) -> Piece:
    problems = piece_problems(piece, rel_tol)
    if problems:
        raise GeometryError("; ".join(problems))
    return piece
