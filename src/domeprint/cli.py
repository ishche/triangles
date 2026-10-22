"""Command line: domeprint AB BC CA --tab 5 -o piece.svg|piece.pdf"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from .geometry import InvalidTriangleError, TabSpec, Triangle, build_piece
from .layout import PAPER_SIZES_MM, DoesNotFitError, single_on_paper, tight_sheet
from .render import RenderStyle, render_pdf, render_svg


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="domeprint",
        description="Create a print-ready SVG or PDF template (cut + fold lines, glue tabs) for one triangle.",
    )
    p.add_argument("ab", type=float, help="side AB in mm (base)")
    p.add_argument("bc", type=float, help="side BC in mm")
    p.add_argument("ca", type=float, help="side CA in mm")
    p.add_argument("--tab", type=float, default=5.0, help="glue tab width in mm (default 5, 0 = none)")
    p.add_argument(
        "--max-tab-angle", type=float, default=45.0, help="max angle of tab ends in degrees (default 45)"
    )
    p.add_argument(
        "--no-bisector",
        action="store_true",
        help="do not limit tab end angles to half the corner angle (tabs may collide when folded flat)",
    )
    p.add_argument(
        "--paper",
        default="tight",
        help=f"'tight' (page fits the piece) or one of: {', '.join(PAPER_SIZES_MM)} (default tight)",
    )
    p.add_argument("--margin", type=float, default=10.0, help="page margin in mm (default 10)")
    p.add_argument("--no-labels", action="store_true", help="omit edge labels")
    p.add_argument("--no-calibration", action="store_true", help="omit the calibration ruler")
    p.add_argument("-o", "--output", type=Path, help="output .svg or .pdf file (default: SVG on stdout)")
    p.add_argument(
        "--format", choices=["svg", "pdf"], help="output format (default: from the output file extension, else svg)"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        triangle = Triangle(args.ab, args.bc, args.ca)
        spec = TabSpec(args.tab, args.max_tab_angle, clamp_to_bisector=not args.no_bisector)
        piece = build_piece(triangle, spec)
        if args.paper.lower() == "tight":
            sheet = tight_sheet(piece, args.margin, calibration=not args.no_calibration)
        else:
            sheet = single_on_paper(piece, args.paper, args.margin, calibration=not args.no_calibration)
    except (InvalidTriangleError, DoesNotFitError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    fmt = args.format or ("pdf" if args.output and args.output.suffix.lower() == ".pdf" else "svg")
    style = RenderStyle(show_labels=not args.no_labels)
    data = render_pdf(sheet, style) if fmt == "pdf" else render_svg(sheet, style).encode("utf-8")
    if args.output:
        args.output.write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
        sys.stdout.flush()

    a, b, c = triangle.angles_deg
    info = [
        f"triangle AB={triangle.ab:g} BC={triangle.bc:g} CA={triangle.ca:g} mm",
        f"angles A={a:.4f} B={b:.4f} C={c:.4f} deg; inradius {triangle.inradius:.3f} mm",
        f"sheet {sheet.width:.2f} x {sheet.height:.2f} mm",
    ]
    for tab, edge in zip(piece.tabs, triangle.edges):
        info.append(
            f"tab {edge.name}: ends {math.degrees(tab.start_angle):.2f}/{math.degrees(tab.end_angle):.2f} deg, "
            f"height {tab.height:.3f} mm"
        )
    info += [f"warning: {w}" for w in piece.warnings]
    if args.output:
        info.append(f"wrote {args.output} - print at 100% scale (no 'fit to page')")
    print("\n".join(info), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
