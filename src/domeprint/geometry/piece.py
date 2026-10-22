"""A printable piece: one triangle plus its glue tabs, as cut and fold geometry.

This is the boundary between geometry and everything else: layout and
renderers consume `Piece` and never recompute dimensions themselves.
"""

from __future__ import annotations

from dataclasses import dataclass

from .polygon import BBox, bounding_box
from .tabs import GlueTab, TabSpec, build_tab, tab_end_angle
from .triangle import Triangle
from .vec import Vec2


@dataclass(frozen=True, slots=True)
class Segment:
    start: Vec2
    end: Vec2

    @property
    def length(self) -> float:
        return (self.end - self.start).length()


@dataclass(frozen=True, slots=True)
class Piece:
    triangle: Triangle
    tab_spec: TabSpec
    tabs: tuple[GlueTab, ...]  # one per edge AB, BC, CA (empty if tabs disabled)
    cut_outline: tuple[Vec2, ...]  # closed CCW polygon (cut line)
    fold_lines: tuple[Segment, ...]  # triangle edges that carry a tab

    @property
    def vertices(self) -> tuple[Vec2, Vec2, Vec2]:
        return self.triangle.vertices

    @property
    def bbox(self) -> BBox:
        return bounding_box(self.cut_outline)

    @property
    def warnings(self) -> tuple[str, ...]:
        out = []
        for edge, tab in zip(self.triangle.edges, self.tabs):
            if tab.truncated:
                out.append(
                    f"tab on edge {edge.name} truncated to a triangle: height "
                    f"{tab.height:.3f} mm < requested {tab.requested_width:.3f} mm"
                )
        return tuple(out)


def build_piece(triangle: Triangle, tab_spec: TabSpec, validate: bool = True) -> Piece:
    """Triangle + one glue tab per edge. Raises GeometryError if any constraint fails."""
    piece = _construct(triangle, tab_spec)
    if validate:
        from .validate import validate_piece  # local import: validate depends on this module

        validate_piece(piece)
    return piece


def _construct(triangle: Triangle, tab_spec: TabSpec) -> Piece:
    edges = triangle.edges
    if not tab_spec.enabled:
        outline = tuple(e.start for e in edges)
        return Piece(triangle, tab_spec, (), outline, ())

    tabs: list[GlueTab] = []
    outline: list[Vec2] = []
    for edge in edges:
        tab = build_tab(
            edge.start,
            edge.end,
            tab_end_angle(edge.start_angle, tab_spec),
            tab_end_angle(edge.end_angle, tab_spec),
            tab_spec.width,
        )
        tabs.append(tab)
        outline.append(edge.start)
        outline.extend(tab.outer)
    fold_lines = tuple(Segment(e.start, e.end) for e in edges)
    return Piece(triangle, tab_spec, tuple(tabs), tuple(outline), fold_lines)
