# Layout: packing many pieces

`pack([Demand(piece, count, label), ...], PackOptions(paper, margin, spacing))`
returns sheets holding every piece exactly once. The CLI uses it for
`--count N` (with `--spacing`, default 2 mm).

1. **Pair each triangle with a copy turned 180°.** This is the key idea.
   Triangles that are only slid (never turned) cover at most 2/3 of the paper.
   Alternating up/down copies tile a strip completely, so a row of bare
   triangles wastes nothing. Turning is a rotation, so scalene pieces keep
   their handedness.
2. **Exact contact via no-fit polygons.** For convex shapes A and B,
   B shifted by v overlaps A exactly when v is inside A + (−B). A horizontal
   slice of that polygon gives the closest legal position along the row, and a
   vertical slice gives how far to lift the next row. No sampling, and no trial
   and error. Shapes are the cut outline's convex hull grown by spacing/2 with
   bevelled corners, which proves the spacing: two grown hulls that don't
   overlap keep their pieces ≥ spacing apart.
3. **Rows.** Pieces are laid left to right, alternating up/down. Both starting
   orientations are tried, because the two gaps in a row can differ and the
   order decides whether one more piece fits.
4. **Sheets.** For each sheet, the stack of row orientations (which triangle
   edge lies on the baseline) is chosen to hold the most pieces, using exact
   row-to-row offsets. For example, a 30-40-50 triangle on 150 × 78 mm:
   two 24 mm rows plus one 30 mm row fit 16 pieces, where uniform rows fit 15.
   Portrait and landscape are both tried. The fewest sheets wins, then the
   least paper used on the last sheet.

Measured on A4 with 2 mm spacing:
- bare triangles: 1.5–2× as many per sheet as a bounding-box grid;
- 5 mm tabs: 1.15–1.35×. Facing tabs need 2 × tab + spacing between
  neighbouring edges, which limits the gain.

`layout_problems()` independently checks any layout:
- every piece is placed exactly once;
- every piece is inside the printable area;
- every pair of pieces is at least `spacing` apart.

It passes on 392 random multi-type jobs.

## Limitations

- Each row holds one triangle type. When a type runs out mid-row, the rest of
  that row stays empty rather than being filled with another type.
- Pieces are packed using their convex hull. For triangles with no angle over
  90° the cut outline is convex anyway. For obtuse triangles, the notch at the
  obtuse corner can't be used by other pieces.
- Rows grow monotonically left to right and bottom to top. A small piece is
  never placed back into a gap behind larger ones.
