"""Strut materials, cross-sections and axial resistance.

Each strut is a pin-ended bar of length L (buckling length = L). Compression
resistance uses the Perry–Robertson buckling curve shared by EN 1993-1-1 §6.3.1
(steel, λ0 = 0.2) and EN 1995-1-1 §6.3.2 (timber, λ0 = 0.3, β_c as α):

    N_cr = π²·E·I / L²              λ̄ = √(A·f_k / N_cr)
    Φ    = ½·(1 + α·(λ̄ − λ0) + λ̄²)   χ = 1 / (Φ + √(Φ² − λ̄²)) ≤ 1
    N_b,Rd = χ · A · f_d

f_d = k_mod·f_k/γ_M. Joints (hubs, bolts) are not checked here and often govern.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def buckling_reduction(slenderness: float, alpha: float, plateau: float) -> float:
    """χ for relative slenderness λ̄, imperfection factor α and plateau λ0."""
    if slenderness <= plateau:
        return 1.0
    phi = 0.5 * (1 + alpha * (slenderness - plateau) + slenderness**2)
    return min(1.0, 1 / (phi + math.sqrt(phi**2 - slenderness**2)))


@dataclass(frozen=True, slots=True)
class Section:
    shape: str  # "rect" or "tube"
    b: float  # mm: width, or outside diameter for a tube
    h: float  # mm: depth, or wall thickness for a tube

    @staticmethod
    def rect(b: float, h: float) -> Section:
        if not (b > 0 and h > 0):
            raise ValueError("section width and depth must be positive")
        return Section("rect", b, h)

    @staticmethod
    def tube(d: float, t: float) -> Section:
        if not d > 0:
            raise ValueError(f"tube diameter must be positive (got {d:g} mm)")
        if not 0 < t < d / 2:
            raise ValueError(
                f"tube wall must be thinner than half the diameter: {d:g} mm diameter, {t:g} mm wall (max {d / 2:g} mm)"
            )
        return Section("tube", d, t)

    @property
    def area(self) -> float:  # m²
        if self.shape == "rect":
            return self.b * self.h * 1e-6
        d, t = self.b, self.h
        return math.pi / 4 * (d**2 - (d - 2 * t) ** 2) * 1e-6

    @property
    def i_min(self) -> float:  # m⁴, about the weak axis
        if self.shape == "rect":
            lo, hi = sorted((self.b, self.h))
            return hi * lo**3 / 12 * 1e-12
        d, t = self.b, self.h
        return math.pi / 64 * (d**4 - (d - 2 * t) ** 4) * 1e-12


@dataclass(frozen=True, slots=True)
class Material:
    name: str
    e_mean: float  # Pa, for the stiffness analysis
    e_buckling: float  # Pa, for N_cr (E_0.05 for timber)
    f_c: float  # Pa, characteristic compression strength (f_y for metals)
    f_t: float  # Pa, characteristic tension strength
    density: float  # kg/m³
    gamma_m: float
    k_mod: float  # timber load-duration factor (1 for metals)
    alpha: float  # imperfection factor (β_c for timber)
    plateau: float  # λ0

    @property
    def design_strength(self) -> float:
        return self.k_mod * self.f_c / self.gamma_m

    @property
    def tension_design(self) -> float:
        return self.k_mod * self.f_t / self.gamma_m

    def tension_resistance(self, s: Section) -> float:  # N
        return s.area * self.tension_design

    def euler_load(self, s: Section, length: float) -> float:  # N
        return math.pi**2 * self.e_buckling * s.i_min / length**2

    def compression_resistance(self, s: Section, length: float) -> float:  # N
        lam = math.sqrt(s.area * self.f_c / self.euler_load(s, length))
        return buckling_reduction(lam, self.alpha, self.plateau) * s.area * self.design_strength


MPa = 1e6
MATERIALS = {
    # EN 338 C24; k_mod 0.8 = medium-term load (snow), service class 1–2; γ_M 1.3 solid timber.
    "timber_c24": Material("Timber C24", 11000 * MPa, 7400 * MPa, 21 * MPa, 14.5 * MPa, 420, 1.3, 0.8, 0.2, 0.3),
    # S235 cold-formed hollow section: buckling curve c.
    "steel_s235": Material("Steel S235", 210000 * MPa, 210000 * MPa, 235 * MPa, 235 * MPa, 7850, 1.0, 1.0, 0.49, 0.2),
    # EN AW-6060 T6 extrusion (EN 1999-1-1 class A curve: α 0.2, λ0 0.1, γ_M1 1.1).
    "alu_6060": Material("Aluminium 6060-T6", 70000 * MPa, 70000 * MPa, 140 * MPa, 140 * MPa, 2700, 1.1, 1.0, 0.2, 0.1),
}
