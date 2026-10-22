# Geometry

Sides are named by their endpoints: `AB`, `BC`, `CA`. The triangle is placed
with `A = (0,0)`, `B = (AB, 0)` and `C` above the x-axis, so `A→B→C` runs
counter-clockwise and the outward side of every edge is its right-hand side.
Area uses Kahan's stable form of Heron's formula. Angles use
`atan2(4K, b²+c²−a²)`. Both stay accurate for very thin triangles.

**Glue tabs.** Each edge carries a trapezoidal tab of perpendicular width `w`.
Its slanted ends start exactly at the triangle corners. The angle θ between the
fold line and a tab end, at a corner with interior angle α, is

    θ = min(max_end_angle, α / 2)        (max_end_angle defaults to 45°)

Capping at α/2 (the corner's angle bisector) guarantees that the three tabs of a
triangle never collide, even when folded fully flat against its back. Folded
over, each tab stays inside the region bounded by its edge and the two
bisectors, and those regions don't overlap. `--no-bisector` turns the cap off.

If an edge is too short for a full-width trapezoid, the tab becomes a triangle
whose tip is where the two slanted ends meet. Its height is reduced and a
warning is printed. With the bisector cap this happens exactly when
`w > inradius`. All three tabs then collapse to the incenter mirrored across
their edges, and the tests check this.

**Validation.** `build_piece` checks every piece it makes against the template
constraints and raises `GeometryError` if any fail. See `geometry/validate.py`:
- fold lines are exactly the triangle edges;
- each tab is attached to its edge and lies wholly outside the triangle;
- tab width is measured perpendicular to the edge, and the tab's outer edge is parallel to it;
- tabs don't overlap each other;
- each corner keeps a gap between neighbouring tabs;
- the cut outline doesn't cross itself, and its area equals the triangle plus the tabs.

**Corner trimming: bevel, not miter.** Each tab end is a straight cut through
the vertex. A miter join would put the tab end at 180° − α/2 from the edge,
which is more than 90°. Neighbouring tabs would then overhang the vertex, share
a cut line, and collide when folded.

## Code

| Module | What it does |
|---|---|
| `geometry/vec.py` | immutable 2D vector |
| `geometry/triangle.py` | triangle from three sides, canonical placement, angles, area, inradius |
| `geometry/tabs.py` | `TabSpec` and `build_tab` (bevelled trapezoid or truncated triangle) |
| `geometry/piece.py` | `build_piece`: triangle + tabs → cut outline + fold lines, validated |
| `geometry/validate.py` | the constraint checks listed above |
| `geometry/convex.py` | convex hull, Minkowski sum, sections, offset, distance (used by layout) |
| `geometry/transform.py` | rigid rotation + translation |

Tab widths must be 0 (no tabs) or at least 1 µm; narrower widths are rejected.

## Edge labels

Each edge's name and length (e.g. `AB 120.0`) is printed on that edge's glue
tab, so it is hidden once the dome is assembled. The text runs along the fold
line with the letters pointing away from the triangle. It is centred across the
tab and between its bevelled ends, at most 60% of the tab width tall (3 mm on a
5 mm tab). If it doesn't fit, it shrinks down to 1 mm; below that, the tab
gets no label. `tests/test_labels.py` checks that every label's ink box stays on
its tab and never crosses the fold line onto the face.
