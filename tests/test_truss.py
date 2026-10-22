import math

import pytest

from domeprint.frame.truss import MechanismError, Truss, solve


def tripod(h=2.0, n=3):
    feet = [(math.cos(k * math.tau / n), math.sin(k * math.tau / n), 0.0) for k in range(n)]
    nodes = [*feet, (0.0, 0.0, h)]
    bars = [(k, n) for k in range(n)]
    return Truss(nodes, bars, ea=1e6, supports=frozenset(range(n)))


@pytest.mark.parametrize("n", [3, 4, 6])  # 3 legs: statically determinate; 4 and 6: indeterminate but symmetric
def test_symmetric_legs_share_vertical_load(n):
    h, p = 2.0, 1000.0
    t = tripod(h, n)
    loads = [(0.0, 0.0, 0.0)] * n + [(0.0, 0.0, -p)]
    (r,) = solve(t, [loads])
    sin_a = h / math.hypot(1, h)
    for f in r.forces:
        assert f == pytest.approx(-p / (n * sin_a), rel=1e-9)  # compression is negative
    assert sum(rz for _, _, rz in r.reactions.values()) == pytest.approx(p)


def test_displacement_matches_hand_calculation():
    # A vertical bar pulled up at the top: δ = P·L / EA. Two horizontal bars hold the top sideways.
    t = Truss(
        [(0, 0, 0), (0, 0, 3), (1, 0, 3), (0, 1, 3)],
        [(0, 1), (1, 2), (1, 3)],
        ea=2e6,
        supports=frozenset({0, 2, 3}),
    )
    (r,) = solve(t, [[(0, 0, 0), (0, 0, 500.0), (0, 0, 0), (0, 0, 0)]])
    assert r.forces[0] == pytest.approx(500.0)
    assert r.displacements[1][2] == pytest.approx(500.0 * 3 / 2e6)


def test_equilibrium_under_random_loads():
    import random

    rng = random.Random(4)
    t = tripod(1.5, 5)
    # Brace the apex further with a second free node so the structure is indeterminate and non-symmetric.
    nodes = [*t.nodes, (0.4, 0.2, 2.5)]
    bars = [*t.bars, (5, 6), (0, 6), (2, 6)]
    t = Truss(nodes, bars, ea=[rng.uniform(1e5, 1e6) for _ in bars], supports=t.supports)
    loads = [tuple(rng.uniform(-100, 100) for _ in range(3)) for _ in nodes]
    (r,) = solve(t, [loads])
    total = [0.0, 0.0, 0.0]
    for p in loads:
        for k in range(3):
            total[k] += p[k]
    for rx in r.reactions.values():
        for k in range(3):
            total[k] += rx[k]
    assert total == pytest.approx([0, 0, 0], abs=1e-6)
    # Every free node is in equilibrium.
    for i in range(len(nodes)):
        if i in t.supports:
            continue
        s = list(loads[i])
        for (a, b), n in zip(t.bars, r.forces):
            if i in (a, b):
                j = b if i == a else a
                L = math.dist(nodes[i], nodes[j])
                for k in range(3):
                    s[k] += n * (nodes[j][k] - nodes[i][k]) / L
        assert s == pytest.approx([0, 0, 0], abs=1e-6)


def test_several_load_cases_at_once_are_independent():
    t = tripod()
    a = [(0, 0, 0)] * 3 + [(0, 0, -10.0)]
    b = [(0, 0, 0)] * 3 + [(5.0, 0, 0)]
    ra, rb = solve(t, [a, b])
    (rab,) = solve(t, [[(x + y, 0, z + w) for (x, _, z), (y, _, w) in zip(a, b)]])
    assert [x + y for x, y in zip(ra.forces, rb.forces)] == pytest.approx(rab.forces)


def test_mechanism_is_reported():
    # A free node held by two bars can swing out of their plane.
    t = Truss([(0, 0, 0), (2, 0, 0), (1, 0, 1)], [(0, 2), (1, 2)], ea=1e6, supports=frozenset({0, 1}))
    with pytest.raises(MechanismError):
        solve(t, [[(0, 0, 0), (0, 0, 0), (0, 0, -1)]])


def test_rejects_zero_length_bar():
    with pytest.raises(ValueError):
        Truss([(0, 0, 0), (0, 0, 0)], [(0, 1)], ea=1, supports=frozenset({0}))
