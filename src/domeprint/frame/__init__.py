"""Structural loads on a full-size geodesic dome frame: truss solver, snow, wind, member checks."""

from .analysis import Case, FrameInputs, FrameResult, MemberEnvelope, StrutSummary, analyse_dome
from .members import MATERIALS, Material, Section
from .truss import MechanismError, Truss, solve

__all__ = [
    "MATERIALS",
    "Case",
    "FrameInputs",
    "FrameResult",
    "Material",
    "MechanismError",
    "MemberEnvelope",
    "Section",
    "StrutSummary",
    "Truss",
    "analyse_dome",
    "solve",
]
