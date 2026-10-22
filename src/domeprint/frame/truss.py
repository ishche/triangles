"""Linear-elastic pin-jointed space truss, solved by the direct stiffness method.

Every bar carries axial force only (hubs are pins, loads act at nodes). The global
stiffness K = Σ (EA/L)·[e·eᵀ  -e·eᵀ; -e·eᵀ  e·eᵀ] is assembled for the free
degrees of freedom, ordered by reverse Cuthill–McKee to keep the profile narrow,
and factorised once with a skyline Cholesky. Each load case is then a cheap
forward/back substitution.

Units are whatever you give it, consistently (the frame package uses m and N).
Bar force is positive in tension.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from operator import mul

Vec3 = tuple[float, float, float]

#: A pivot smaller than this fraction of the largest diagonal means the truss is a mechanism.
PIVOT_TOL = 1e-10


class MechanismError(ValueError):
    """The truss can move without straining a bar, so it cannot carry the load."""


@dataclass(frozen=True)
class Truss:
    nodes: Sequence[Vec3]
    bars: Sequence[tuple[int, int]]
    ea: float | Sequence[float]  # axial stiffness E·A per bar, or one value for all
    supports: frozenset[int]  # pinned nodes: all three translations fixed
    lengths: list[float] = field(init=False, repr=False)
    dirs: list[Vec3] = field(init=False, repr=False)  # unit vector from bar start to end

    def __post_init__(self) -> None:
        lengths, dirs = [], []
        for a, b in self.bars:
            d = [self.nodes[b][k] - self.nodes[a][k] for k in range(3)]
            n = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
            if not n > 0:
                raise ValueError(f"bar {a}-{b} has zero length")
            lengths.append(n)
            dirs.append((d[0] / n, d[1] / n, d[2] / n))
        object.__setattr__(self, "lengths", lengths)
        object.__setattr__(self, "dirs", dirs)

    def bar_ea(self, i: int) -> float:
        return self.ea if isinstance(self.ea, int | float) else self.ea[i]


@dataclass(frozen=True)
class TrussResult:
    displacements: list[Vec3]
    forces: list[float]  # per bar, + tension
    reactions: dict[int, Vec3]  # per support node


def _rcm_order(n_nodes: int, bars: Sequence[tuple[int, int]], free: list[int]) -> list[int]:
    """Free nodes in reverse Cuthill–McKee order (small bandwidth)."""
    free_set = set(free)
    adj: dict[int, set[int]] = {i: set() for i in free}
    for a, b in bars:
        if a in free_set and b in free_set:
            adj[a].add(b)
            adj[b].add(a)
    seen: set[int] = set()
    order: list[int] = []
    for start in sorted(free, key=lambda i: (len(adj[i]), i)):
        if start in seen:
            continue
        seen.add(start)
        q = deque([start])
        while q:
            i = q.popleft()
            order.append(i)
            for j in sorted(adj[i] - seen, key=lambda j: (len(adj[j]), j)):
                seen.add(j)
                q.append(j)
    order.reverse()
    return order


class _Skyline:
    """Symmetric matrix stored row by row from the first non-zero column to the diagonal."""

    def __init__(self, first: list[int]):
        self.first = first
        self.rows = [[0.0] * (i - f + 1) for i, f in enumerate(first)]

    def add(self, i: int, j: int, v: float) -> None:
        if j > i:
            i, j = j, i
        self.rows[i][j - self.first[i]] += v

    def cholesky(self) -> None:
        """In place: rows become L with A = L·Lᵀ."""
        first, rows = self.first, self.rows
        dmax = max((r[-1] for r in rows), default=0.0)
        if not dmax > 0:
            raise MechanismError("structure has no stiffness")
        for i, row in enumerate(rows):
            fi = first[i]
            for j in range(fi, i):
                rj = rows[j]
                fj = first[j]
                lo = max(fi, fj)
                s = sum(map(mul, row[lo - fi : j - fi], rj[lo - fj : j - fj]))
                row[j - fi] = (row[j - fi] - s) / rj[-1]
            d = row[-1] - sum(map(mul, row[:-1], row[:-1]))
            if d <= PIVOT_TOL * dmax:
                raise MechanismError("the structure is a mechanism: some node can move without loading a bar")
            row[-1] = math.sqrt(d)

    def solve(self, b: list[float]) -> list[float]:
        first, rows = self.first, self.rows
        y = b[:]
        for i, row in enumerate(rows):  # L·y = b
            fi = first[i]
            y[i] = (y[i] - sum(map(mul, row[:-1], y[fi:i]))) / row[-1]
        for i in range(len(rows) - 1, -1, -1):  # Lᵀ·x = y
            row = rows[i]
            y[i] /= row[-1]
            xi = y[i]
            fi = first[i]
            for k, lik in enumerate(row[:-1]):
                y[fi + k] -= lik * xi
        return y


def solve(truss: Truss, load_cases: Sequence[Sequence[Vec3]]) -> list[TrussResult]:
    """Solve the truss for each load case (one force per node). Raises MechanismError if unstable."""
    nodes = truss.nodes
    for case in load_cases:
        if len(case) != len(nodes):
            raise ValueError("each load case needs one force vector per node")

    free = [i for i in range(len(nodes)) if i not in truss.supports]
    order = _rcm_order(len(nodes), truss.bars, free)
    slot = {node: k for k, node in enumerate(order)}  # node -> position among free nodes
    ndof = 3 * len(order)

    # Profile: first non-zero column in each row (a node's own 3×3 block, then its lowest neighbour).
    first = [3 * (i // 3) for i in range(ndof)]
    for a, b in truss.bars:
        if a in slot and b in slot:
            lo, hi = sorted((slot[a], slot[b]))
            for k in range(3):
                first[3 * hi + k] = min(first[3 * hi + k], 3 * lo)
    K = _Skyline(first)

    for i, (a, b) in enumerate(truss.bars):
        k = truss.bar_ea(i) / truss.lengths[i]
        e = truss.dirs[i]
        sa, sb = slot.get(a), slot.get(b)
        for p in range(3):
            for q in range(3):
                v = k * e[p] * e[q]
                if sa is not None and p >= q:
                    K.add(3 * sa + p, 3 * sa + q, v)
                if sb is not None and p >= q:
                    K.add(3 * sb + p, 3 * sb + q, v)
                if sa is not None and sb is not None:
                    hi, lo = (sa, sb) if sa > sb else (sb, sa)
                    K.add(3 * hi + p, 3 * lo + q, -v)
    K.cholesky()

    results = []
    for case in load_cases:
        rhs = [case[n][k] for n in order for k in range(3)]
        x = K.solve(rhs) if ndof else []
        disp: list[Vec3] = [(0.0, 0.0, 0.0)] * len(nodes)
        for n, s in slot.items():
            disp[n] = (x[3 * s], x[3 * s + 1], x[3 * s + 2])
        forces = []
        for i, (a, b) in enumerate(truss.bars):
            e = truss.dirs[i]
            elong = sum((disp[b][k] - disp[a][k]) * e[k] for k in range(3))
            forces.append(truss.bar_ea(i) / truss.lengths[i] * elong)
        reactions = {n: (-case[n][0], -case[n][1], -case[n][2]) for n in truss.supports}
        for i, (a, b) in enumerate(truss.bars):
            e, f = truss.dirs[i], forces[i]
            if a in reactions:  # tension pulls a towards b; the support pushes back
                reactions[a] = tuple(reactions[a][k] - f * e[k] for k in range(3))
            if b in reactions:
                reactions[b] = tuple(reactions[b][k] + f * e[k] for k in range(3))
        results.append(TrussResult(disp, forces, reactions))
    return results
