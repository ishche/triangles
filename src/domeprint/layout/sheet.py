"""Renderer-independent page model.

A `Sheet` is a physical page (mm, y-up, origin at the bottom-left corner)
holding pieces placed with rigid transforms. Renderers (SVG now, PDF later)
draw a Sheet verbatim and must not move, scale or reinterpret anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..geometry import Edge, Piece, Segment, Transform2D, Vec2
from ..geometry.polygon import BBox, bounding_box

#: Portrait paper sizes, (width, height) in mm.
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "A5": (148.0, 210.0),
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "LETTER": (215.9, 279.4),
    "LEGAL": (215.9, 355.6),
}


def paper_size(name: str) -> tuple[float, float]:
    try:
        return PAPER_SIZES_MM[name.upper()]
    except KeyError:
        raise ValueError(f"unknown paper size {name!r}; known: {', '.join(PAPER_SIZES_MM)}") from None


@dataclass(frozen=True, slots=True)
class Placement:
    piece: Piece
    transform: Transform2D = field(default_factory=Transform2D.identity)
    label: str = ""

    @property
    def cut_outline(self) -> tuple[Vec2, ...]:
        return self.transform.apply_all(self.piece.cut_outline)

    @property
    def fold_lines(self) -> tuple[Segment, ...]:
        t = self.transform
        return tuple(Segment(t.apply(s.start), t.apply(s.end)) for s in self.piece.fold_lines)

    @property
    def edges(self) -> tuple[Edge, ...]:
        t = self.transform
        return tuple(
            Edge(e.name, t.apply(e.start), t.apply(e.end), e.length, e.start_angle, e.end_angle)
            for e in self.piece.triangle.edges
        )

    @property
    def bbox(self) -> BBox:
        return bounding_box(self.cut_outline)


@dataclass(frozen=True, slots=True)
class CalibrationBar:
    """A ruler of known length, used to verify the print came out at 100% scale."""

    origin: Vec2  # left end of the bar, sheet coordinates
    length: float  # mm


@dataclass(frozen=True, slots=True)
class Sheet:
    width: float
    height: float
    placements: tuple[Placement, ...] = ()
    calibration: CalibrationBar | None = None

    def __post_init__(self) -> None:
        if not (self.width > 0 and self.height > 0):
            raise ValueError("sheet dimensions must be positive")
