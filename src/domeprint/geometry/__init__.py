"""Pure geometry: no rendering, no page knowledge. Units are millimetres."""

from .piece import Piece, Segment, build_piece
from .polygon import (
    BBox,
    bounding_box,
    convex_overlap_depth,
    is_convex_ccw,
    is_simple_polygon,
    point_in_convex_polygon,
    signed_area,
)
from .tabs import GlueTab, TabSpec, build_tab, tab_end_angle
from .transform import Transform2D
from .triangle import Edge, InvalidTriangleError, Triangle
from .validate import GeometryError, piece_problems, validate_piece
from .vec import Vec2, distance

__all__ = [
    "BBox",
    "Edge",
    "GeometryError",
    "GlueTab",
    "InvalidTriangleError",
    "Piece",
    "Segment",
    "TabSpec",
    "Transform2D",
    "Triangle",
    "Vec2",
    "bounding_box",
    "build_piece",
    "build_tab",
    "convex_overlap_depth",
    "distance",
    "is_convex_ccw",
    "is_simple_polygon",
    "piece_problems",
    "point_in_convex_polygon",
    "signed_area",
    "tab_end_angle",
    "validate_piece",
]
