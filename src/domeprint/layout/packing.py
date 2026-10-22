"""Pack many triangle pieces onto as few sheets as possible.

Algorithm
---------
1. Orientations: each piece type is turned so one triangle edge is horizontal,
   either apex up (U) or turned a further 180 degrees (D). Only rotations are
   used, so scalene triangles keep their handedness.
2. Shapes: the packing shape is the convex hull of the cut outline, grown by
   spacing/2 (`offset_convex`). Two grown hulls that do not overlap guarantee
   at least `spacing` between the pieces.
3. Rows: pieces are laid left to right, alternating U and D, every piece
   bottom-aligned on the row baseline. Each one slides left into exact
   contact with the row so far, using cached no-fit polygons (see nfp.py).
   Rows starting with U and with D are both tried (the two gaps in a row can
   differ). For bare triangles this tiles the strip with zero waste.
4. Sheets: types are placed largest first. For each sheet, `_plan_rows`
   chooses the stack of row orientations (which edge lies on the baseline)
   that holds the most pieces, using exact row-to-row offsets
   (`_row_pitches`). Every row is still lifted against everything already on
   the sheet before it is placed, so a plan can never cause an overlap.
5. Page: portrait and landscape are both packed. Fewest sheets wins, then
   the least height used on the last sheet, then portrait.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..geometry import Piece, Transform2D, Vec2
from ..geometry.convex import convex_hull, offset_convex
from ..geometry.polygon import BBox, bounding_box, signed_area
from .nfp import no_fit_polygon, slide_right, slide_up
from .sheet import CalibrationBar, Placement, Sheet, paper_size
from .single import CALIBRATION_BAND_MM, DoesNotFitError, calibration_length

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class Demand:
    piece: Piece
    count: int
    label: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.count, int) or self.count < 0:
            raise ValueError(f"count must be a non-negative integer, got {self.count!r}")


@dataclass(frozen=True, slots=True)
class PackOptions:
    paper: str | tuple[float, float] = "A4"
    margin: float = 10.0  # mm, all four sides
    spacing: float = 2.0  # mm, minimum distance between pieces
    calibration: bool = True  # 100 mm ruler in a band at the bottom of each sheet
    allow_landscape: bool = True

    def __post_init__(self) -> None:
        if not (self.margin >= 0 and math.isfinite(self.margin)):
            raise ValueError("margin must be >= 0")
        if not (self.spacing >= 0 and math.isfinite(self.spacing)):
            raise ValueError("spacing must be >= 0")

    def page_sizes(self) -> list[tuple[float, float]]:
        w, h = paper_size(self.paper) if isinstance(self.paper, str) else map(float, self.paper)
        sizes = [(w, h)]
        if self.allow_landscape and w != h:
            sizes.append((h, w))
        return sizes


def printable_area(width: float, height: float, options: PackOptions) -> tuple[BBox, float | None]:
    """Area available to pieces on a sheet, and the calibration ruler length (if any)."""
    m = options.margin
    cal = calibration_length(width - 2 * m) if options.calibration else None
    band = CALIBRATION_BAND_MM if cal else 0.0
    area = BBox(m, m + band, width - m, height - m)
    if area.width <= 0 or area.height <= 0:
        raise ValueError("margins leave no printable area")
    return area, cal


# ---------------------------------------------------------------- shapes
@dataclass(frozen=True, slots=True)
class OrientedShape:
    piece: Piece
    edge: int
    up: bool
    local_transform: Transform2D  # piece coords -> local coords (outline bbox at origin)
    width: float
    height: float
    hull: tuple[Vec2, ...]  # convex hull grown by spacing/2, local coords
    key: tuple = field(default=(), compare=False)


def orient(piece: Piece, edge: int, up: bool, spacing: float = 0.0, key: tuple = ()) -> OrientedShape:
    e = piece.triangle.edges[edge]
    angle = -e.direction.angle() + (0.0 if up else math.pi)
    rotated = Transform2D.rotation(angle).apply_all(piece.cut_outline)
    bb = bounding_box(rotated)
    local = Transform2D(angle, -bb.min)
    outline = local.apply_all(piece.cut_outline)
    hull = offset_convex(convex_hull(outline), spacing / 2.0)
    return OrientedShape(piece, edge, up, local, bb.width, bb.height, hull, key)


class _NfpCache:
    def __init__(self) -> None:
        self._cache: dict[tuple, tuple[Vec2, ...]] = {}

    def get(self, a: OrientedShape, b: OrientedShape) -> tuple[Vec2, ...]:
        k = (a.key, b.key)
        nfp = self._cache.get(k)
        if nfp is None:
            nfp = self._cache[k] = no_fit_polygon(a.hull, b.hull)
        return nfp


def row_area_per_piece(piece: Piece, edge: int, spacing: float, alternate: bool = True) -> float:
    """Sheet area used per piece in an endless field of identical rows.

    Horizontal period P: alternate U, D, U, ... (or U, U, ... when alternate=False).
    Vertical pitch: lowest lift of an identical row that clears the one below.
    """
    u = orient(piece, edge, True, spacing, key=("u",))
    d = orient(piece, edge, False, spacing, key=("d",))
    seq = [u, d] if alternate else [u]
    xs = [0.0]
    for i in range(1, 2 * len(seq) + 1):
        prev, cur = seq[(i - 1) % len(seq)], seq[i % len(seq)]
        xs.append(xs[-1] + slide_right(prev.hull, cur.hull, 0.0))
    period = xs[len(seq)]
    # Base row spanning several periods on both sides.
    base = [(seq[i % len(seq)], xs[i % len(seq)] + k * period) for k in range(-3, 4) for i in range(len(seq))]
    pitch = 0.0
    for y_shape, y_x in base:
        if not (0 <= y_x < period):
            continue
        for x_shape, x_x in base:
            dy = slide_up(x_shape.hull, y_shape.hull, y_x - x_x)
            if dy is not None:
                pitch = max(pitch, dy)
    return pitch * period / len(seq)


# ---------------------------------------------------------------- packing
@dataclass(frozen=True, slots=True)
class PackResult:
    sheets: tuple[Sheet, ...]
    fill_ratio: float  # cut-outline area / printable area over all sheets


@dataclass(slots=True)
class _Placed:
    shape: OrientedShape
    x: float
    y: float
    label: str


def _build_row(queue, shapes, area: BBox, cache: _NfpCache) -> list[tuple[OrientedShape, float, str]]:
    """Best of the rows starting apex-up and apex-down.

    The two gaps in an alternating row generally differ, so which piece comes
    first decides whether one more piece fits at the end.
    """
    rows = [_fill_row(queue, shapes, area, cache, start_up) for start_up in (True, False)]
    return min(rows, key=lambda r: (-len(r), r[-1][1] + r[-1][0].width if r else 0.0))


def _fill_row(queue, shapes, area: BBox, cache: _NfpCache, start_up: bool) -> list[tuple[OrientedShape, float, str]]:
    row: list[tuple[OrientedShape, float, str]] = []
    for type_idx, label in queue:
        up_shape, down_shape = shapes[type_idx]
        if not row:
            candidates = [up_shape, down_shape] if start_up else [down_shape, up_shape]
        else:
            last_up = row[-1][0].up
            candidates = [down_shape, up_shape] if last_up else [up_shape, down_shape]
        placed = False
        for cand in candidates:
            x = area.min_x
            for other, ox, _ in row:
                dx = slide_right(None, None, 0.0, nfp=cache.get(other, cand))
                if dx is not None:
                    x = max(x, ox + dx)
            if x + cand.width <= area.max_x + _EPS:
                row.append((cand, x, label))
                placed = True
                break
        if not placed:
            break
    return row


def _lift(row, current: list[_Placed], area: BBox, spacing: float, cache: _NfpCache) -> float:
    y = area.min_y
    for shape, x, _ in row:
        for a in current:
            if x > a.x + a.shape.width + spacing + _EPS or x + shape.width < a.x - spacing - _EPS:
                continue  # padded boxes do not overlap horizontally
            dy = slide_up(None, None, x - a.x, nfp=cache.get(a.shape, shape))
            if dy is not None:
                y = max(y, a.y + dy)
    return y


@dataclass(frozen=True, slots=True)
class _RowOption:
    edge: int
    height: float
    template: tuple[tuple[OrientedShape, float], ...]  # a full row: shapes and x positions
    pad_top: float  # how far padded hulls reach above the row's boxes
    pad_bottom: float  # how far padded hulls reach below the row's boxes


def _row_options(
    type_idx: int, piece: Piece, label: str, spacing: float, area: BBox, cache: _NfpCache
) -> list[_RowOption]:
    """One full-width row per distinct orientation of the piece."""
    options = []
    for edge in _distinct_edges(piece, spacing):
        u = orient(piece, edge, True, spacing, key=(type_idx, edge, True))
        d = orient(piece, edge, False, spacing, key=(type_idx, edge, False))
        if u.width > area.width + _EPS or u.height > area.height + _EPS:
            continue
        # Pieces can nest in pairs, so a row holds at most ~2 * width / piece width.
        bound = int(2 * area.width / u.width) + 2
        row = _build_row([(type_idx, label)] * bound, {type_idx: (u, d)}, area, cache)
        pad_top = max(max(p.y for p in sh.hull) - sh.height for sh in (u, d))
        pad_bottom = max(-min(p.y for p in sh.hull) for sh in (u, d))
        options.append(_RowOption(edge, u.height, tuple((shape, x) for shape, x, _ in row), pad_top, pad_bottom))
    return options


def _plan_rows(
    heights: Sequence[float],
    pieces: Sequence[int],
    first: Sequence[float],
    pitch: Sequence[Sequence[float]],
    top_limit: float,
    remaining: int,
) -> list[int]:
    """Best stack of rows (option indices, bottom to top) under `top_limit`.

    first[o]    baseline of a row of option o placed first
    pitch[a][b] baseline step from a row of option a to a row of option b above it
    Rows are grouped in blocks of one option; every block order and every count
    is tried (at most 3 options, so this stays small). Maximises
    min(pieces, remaining), then minimises the top of the stack.
    """
    n = len(heights)
    best_key: tuple[int, float] = (0, 0.0)
    best: list[int] = []

    def dfs(perm, pos, last, y_last, count, seq):
        nonlocal best_key, best
        if seq:
            key = (min(count, remaining), -(y_last + heights[last]))
            if key > best_key:
                best_key, best = key, list(seq)
        if count >= remaining or pos == len(perm):
            return
        o = perm[pos]
        ys = []
        y = first[o] if last is None else y_last + pitch[last][o]
        while y + heights[o] <= top_limit + _EPS and count + len(ys) * pieces[o] < remaining:
            ys.append(y)
            y += pitch[o][o]
        for k in range(len(ys), -1, -1):
            if k == 0:
                dfs(perm, pos + 1, last, y_last, count, seq)
            else:
                dfs(perm, pos + 1, o, ys[k - 1], count + k * pieces[o], seq + [o] * k)

    for perm in itertools.permutations(range(n)):
        dfs(perm, 0, None, 0.0, 0, [])
    return best


def _best_rows(options: Sequence[tuple[float, int]], budget: float, spacing: float, remaining: int) -> list[int]:
    """_plan_rows for flat rows: each row is `height` tall, `spacing` between rows."""
    heights = [h for h, _ in options]
    pitch = [[ha + spacing for _ in options] for ha in heights]
    return _plan_rows(heights, [c for _, c in options], [0.0] * len(options), pitch, budget, remaining)


def _row_pitches(opts: Sequence[_RowOption], area: BBox, spacing: float, cache: _NfpCache) -> list[list[float]]:
    """Exact baseline step between full rows of each pair of options (NFP lift)."""
    unbounded = BBox(area.min_x, -math.inf, area.max_x, area.max_y)
    pitch = []
    for a in opts:
        below = [_Placed(shape, x, 0.0, "") for shape, x in a.template]
        row_pitch = []
        for b in opts:
            lift = _lift([(shape, x, "") for shape, x in b.template], below, unbounded, spacing, cache)
            row_pitch.append(lift if math.isfinite(lift) else a.height + spacing)
        pitch.append(row_pitch)
    return pitch


def _pack_variant(
    demands: Sequence[Demand], area: BBox, spacing: float, cache: _NfpCache
) -> list[list[_Placed]] | None:
    """Fill sheets type by type (largest pieces first). For each sheet, plan the
    stack of row orientations that holds the most pieces, using exact row-to-row
    offsets; every row is still checked against everything already placed."""
    row_opts = [_row_options(i, d.piece, d.label, spacing, area, cache) for i, d in enumerate(demands)]
    if any(not opts or not opts[0].template for opts in row_opts):
        return None
    pitches = [_row_pitches(opts, area, spacing, cache) for opts in row_opts]
    remaining = [d.count for d in demands]
    order = sorted(range(len(demands)), key=lambda i: (-signed_area(demands[i].piece.cut_outline), i))
    sheets: list[list[_Placed]] = []
    while any(remaining):
        placed: list[_Placed] = []
        for t in order:
            opts, label = row_opts[t], demands[t].label
            progress = True
            while remaining[t] > 0 and progress:
                progress = False
                first = [_lift([(sh, x, label) for sh, x in o.template], placed, area, spacing, cache) for o in opts]
                plan = _plan_rows(
                    [o.height for o in opts],
                    [len(o.template) for o in opts],
                    first,
                    pitches[t],
                    area.max_y,
                    remaining[t],
                )
                for oi in plan:
                    opt = opts[oi]
                    k = min(len(opt.template), remaining[t])
                    row = [(shape, x, label) for shape, x in opt.template[:k]]
                    lift = _lift(row, placed, area, spacing, cache)
                    if lift + opt.height > area.max_y + _EPS:
                        break  # an older row interferes more than planned: re-plan
                    placed.extend(_Placed(shape, x, lift, lbl) for shape, x, lbl in row)
                    remaining[t] -= k
                    progress = True
        if not placed:
            return None
        sheets.append(placed)
    return sheets


def _distinct_edges(piece: Piece, spacing: float) -> list[int]:
    """Edges giving distinct shapes, best row density first."""
    scored = []
    seen = set()
    for edge in range(3):
        u = orient(piece, edge, True, spacing)
        # Merge only truly identical shapes (e.g. the three edges of an equilateral
        # triangle). Equal bounding boxes are not enough: the legs of an isosceles
        # triangle give mirror-image shapes that pack differently.
        outline = u.local_transform.apply_all(piece.cut_outline)
        sig = tuple(sorted((round(p.x, 6), round(p.y, 6)) for p in outline))
        if sig in seen:
            continue
        seen.add(sig)
        scored.append((row_area_per_piece(piece, edge, spacing), edge))
    scored.sort()
    return [edge for _, edge in scored]


def pack(demands: Sequence[Demand], options: PackOptions | None = None) -> PackResult:
    options = options or PackOptions()
    demands = [d for d in demands if d.count > 0]
    if not demands:
        return PackResult((), 0.0)

    cache = _NfpCache()  # NFPs depend only on the shape pair, so all variants share them
    best = None
    for page_index, (pw, ph) in enumerate(options.page_sizes()):
        area, cal = printable_area(pw, ph, options)
        sheets = _pack_variant(demands, area, options.spacing, cache)
        if sheets is None:
            continue
        last_top = max(p.y + p.shape.height for p in sheets[-1])
        score = (len(sheets), (last_top - area.min_y) / area.height, page_index)
        if best is None or score < best[0]:
            best = (score, sheets, pw, ph, area, cal)

    if best is None:
        raise DoesNotFitError("a piece does not fit on the printable area in any orientation")
    _, placed_sheets, pw, ph, area, cal = best
    sheets = []
    used = 0.0
    for placed in placed_sheets:
        placements = tuple(
            Placement(p.shape.piece, p.shape.local_transform.then(Transform2D(0.0, Vec2(p.x, p.y))), p.label)
            for p in placed
        )
        used += sum(signed_area(p.shape.piece.cut_outline) for p in placed)
        calibration = CalibrationBar(Vec2(options.margin, options.margin), cal) if cal else None
        sheets.append(Sheet(pw, ph, placements, calibration))
    fill = used / (len(sheets) * area.width * area.height)
    return PackResult(tuple(sheets), fill)
