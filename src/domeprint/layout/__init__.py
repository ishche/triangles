"""Page layout: placing pieces on physical sheets. No rendering here."""

from .packing import Demand, PackOptions, PackResult, fill_sheet, pack, printable_area
from .sheet import PAPER_SIZES_MM, CalibrationBar, Placement, Sheet, paper_size
from .single import CALIBRATION_BAND_MM, DoesNotFitError, single_on_paper, tight_sheet
from .validate import layout_problems

__all__ = [
    "CALIBRATION_BAND_MM",
    "PAPER_SIZES_MM",
    "CalibrationBar",
    "Demand",
    "DoesNotFitError",
    "PackOptions",
    "PackResult",
    "Placement",
    "Sheet",
    "fill_sheet",
    "layout_problems",
    "pack",
    "paper_size",
    "printable_area",
    "single_on_paper",
    "tight_sheet",
]
