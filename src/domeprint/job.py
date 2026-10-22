"""One print job: the options the CLI and the web server share, turned into sheets."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import Piece, TabSpec, Triangle, build_piece
from .layout import Demand, PackOptions, Sheet, fill_sheet, pack, single_on_paper, tight_sheet


@dataclass(frozen=True, slots=True)
class JobOptions:
    ab: float
    bc: float
    ca: float
    tab: float = 5.0
    max_tab_angle: float = 45.0
    bisector: bool = True
    paper: str = "A4"
    margin: float = 10.0
    count: int | None = None  # None = as many as fit on one sheet
    spacing: float = 2.0
    calibration: bool = True

    @property
    def tight(self) -> bool:
        return self.paper.lower() == "tight"


@dataclass(frozen=True, slots=True)
class JobResult:
    triangle: Triangle
    piece: Piece
    sheets: list[Sheet]
    fill: float | None = None  # paper use, only for multi-sheet packing


def run_job(o: JobOptions) -> JobResult:
    """Build the piece and lay it out. Raises InvalidTriangleError, DoesNotFitError or ValueError."""
    triangle = Triangle(o.ab, o.bc, o.ca)
    piece = build_piece(triangle, TabSpec(o.tab, o.max_tab_angle, clamp_to_bisector=o.bisector))
    if o.count is not None and o.count < 1:
        raise ValueError("--count must be at least 1")
    if o.tight and o.count not in (None, 1):
        raise ValueError("--paper tight holds a single piece; choose a paper size to print several")
    if o.tight:
        return JobResult(triangle, piece, [tight_sheet(piece, o.margin, calibration=o.calibration)])
    opts = PackOptions(o.paper, o.margin, o.spacing, o.calibration)
    if o.count is None:
        return JobResult(triangle, piece, [fill_sheet(piece, opts)])
    if o.count == 1:
        return JobResult(triangle, piece, [single_on_paper(piece, o.paper, o.margin, calibration=o.calibration)])
    result = pack([Demand(piece, o.count)], opts)
    return JobResult(triangle, piece, list(result.sheets), result.fill_ratio)
