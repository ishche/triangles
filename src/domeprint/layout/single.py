"""Layouts for a single piece. Multi-piece packing will live next to this module."""

from __future__ import annotations

import math

from ..geometry import Piece, Transform2D, Vec2
from ..geometry.polygon import bounding_box
from .sheet import CalibrationBar, Placement, Sheet, paper_size

#: Height reserved at the bottom of the printable area for the calibration bar.
CALIBRATION_BAND_MM = 8.0
_CALIBRATION_LENGTHS_MM = (100.0, 50.0, 20.0, 10.0)
_FIT_EPS = 1e-9


class DoesNotFitError(ValueError):
    """The piece cannot be placed on the requested paper in any orientation."""


def _candidate_rotations(piece: Piece) -> list[float]:
    """Identity first, then each edge horizontal, then each of those turned 90 degrees."""
    base = [0.0] + [-e.direction.angle() for e in piece.triangle.edges]
    return base + [a + math.pi / 2 for a in base]


def _calibration_length(available: float) -> float | None:
    for length in _CALIBRATION_LENGTHS_MM:
        if length <= available + _FIT_EPS:
            return length
    return None


def _place(piece: Piece, angle: float, target_min: Vec2) -> Placement:
    rot = Transform2D.rotation(angle)
    bb = bounding_box(rot.apply_all(piece.cut_outline))
    shift = target_min - bb.min
    return Placement(piece, rot.then(Transform2D(0.0, shift)))


def tight_sheet(piece: Piece, margin: float = 10.0, calibration: bool = True) -> Sheet:
    """A page exactly as large as the piece plus margins (and calibration band)."""
    if margin < 0:
        raise ValueError("margin must be >= 0")
    bb = piece.bbox
    band = CALIBRATION_BAND_MM if calibration else 0.0
    cal_len = (100.0 if bb.width >= 100.0 else 50.0) if calibration else None
    width = max(bb.width, cal_len or 0.0) + 2 * margin
    height = bb.height + 2 * margin + band
    placement = _place(piece, 0.0, Vec2((width - bb.width) / 2, margin + band))
    cal = CalibrationBar(Vec2(margin, margin), cal_len) if cal_len else None
    return Sheet(width, height, (placement,), cal)


def single_on_paper(
    piece: Piece, paper: str = "A4", margin: float = 10.0, calibration: bool = True
) -> Sheet:
    """Center one piece on a standard paper size, rotating it if needed to fit."""
    width, height = paper_size(paper)
    usable_w = width - 2 * margin
    cal_len = _calibration_length(usable_w) if calibration else None
    band = CALIBRATION_BAND_MM if cal_len else 0.0
    usable_h = height - 2 * margin - band
    if usable_w <= 0 or usable_h <= 0:
        raise ValueError("margins leave no printable area")

    for angle in _candidate_rotations(piece):
        bb = bounding_box(Transform2D.rotation(angle).apply_all(piece.cut_outline))
        if bb.width <= usable_w + _FIT_EPS and bb.height <= usable_h + _FIT_EPS:
            target = Vec2(
                margin + (usable_w - bb.width) / 2,
                margin + band + (usable_h - bb.height) / 2,
            )
            placement = _place(piece, angle, target)
            cal = CalibrationBar(Vec2(margin, margin), cal_len) if cal_len else None
            return Sheet(width, height, (placement,), cal)

    bb = piece.bbox
    raise DoesNotFitError(
        f"piece ({bb.width:.1f} x {bb.height:.1f} mm) does not fit on {paper} "
        f"(printable {usable_w:.1f} x {usable_h:.1f} mm) in any orientation"
    )
