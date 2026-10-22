"""Snow on a dome, after EN 1991-1-3:2003 with the recommended values.

    s = μ · C_e · C_t · s_k        per m² of plan (horizontal projection)

μ follows each face's own slope α, as for a pitched roof (Table 5.2):
0.8 up to 30°, falling linearly to 0 at 60°. The drifted case puts 0.5·μ on the
windward half and μ on the leeward half, like the unbalanced pitched-roof case.
"""

from __future__ import annotations


def snow_shape(slope_deg: float) -> float:
    """Roof shape coefficient μ1 for a surface sloping slope_deg from horizontal."""
    if slope_deg <= 30:
        return 0.8
    if slope_deg >= 60:
        return 0.0
    return 0.8 * (60 - slope_deg) / 30
