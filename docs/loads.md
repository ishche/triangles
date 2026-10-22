# Frame loads

The **Loads** mode of the Dome 3D view checks a full-size dome frame (same
frequency and cut as the model, at a radius you choose) under dead load, snow
and wind. It is a first sizing tool, not a substitute for a structural engineer
signing off a building.

## In the viewer

- **Design check:** struts coloured by utilisation (scale fitted to the worst strut,
  ⚠ red over 100%), thicker = higher; the worst strut is labelled.
- **Dead / Snow / Drift:** strut force, red compression ↔ blue tension, thicker =
  larger. Arrows show the weight on each hub (dead) or a snow layer whose
  thickness follows the load per m² (snow); grey arrows at the base are the
  foundation reactions.
- **Wind:** colour the cover by net pressure (red pushes in, blue pulls out) or
  colour the struts by force. Arrows on each face point in for pressure and out
  for suction. Streaks follow potential flow around a sphere with a log-law
  ground profile: they speed up over the crown, which is where the suction is.
  This flow is an illustration; the loads come from the Eurocode coefficients.
- **Deflection:** the deformed shape, drawn still over a grey ghost of the
  unloaded one, exaggerated so the largest movement is 7% of the radius.
- Respects "reduce motion": the airflow is drawn still.

## Structural model

- **Pin-jointed space truss.** Struts carry axial force only; hubs are pins.
  Solved by the direct stiffness method, K·u = F, with K = Σ (EA/L)·[e·eᵀ …].
  Pure Python: reverse Cuthill–McKee ordering + skyline Cholesky. A 12V dome
  with ~30 load cases takes about half a second.
- **Supports:** every vertex on the open bottom edge, pinned (x, y, z fixed).
  The 3V 5/8 dome's base is stepped (two heights); that's handled the same way.
- **Loads to hubs:** a face's load goes ⅓ to each corner hub; strut self-weight
  goes ½ to each end.

## Load cases (characteristic)

| Case | What | Rule |
|---|---|---|
| G | struts + cover dead load | ρ·A·L·g per strut; cover kN/m² × surface area |
| S | balanced snow | s = μ₁(α)·Cₑ·C_t·s_k per m² of plan; μ₁ = 0.8 to 30°, linear to 0 at 60° (EN 1991-1-3 Table 5.2), α = each face's slope |
| Sd | drifted snow | 0.5·μ₁ windward half, μ₁ leeward half (pitched-roof unbalanced case, applied to the dome) |
| W+ / W− | wind, c_pi = +0.2 / −0.3 | w = q_p(z_e)·(c_pe − c_pi), normal to each face |

### Wind (EN 1991-1-4, recommended values)

- q_p(z) = (1 + 7·I_v)·½ρ·(c_r·v_b)², c_r = k_r·ln(z/z₀), k_r = 0.19·(z₀/0.05)^0.07,
  I_v = 1/ln(z/z₀), ρ = 1.25 kg/m³, z clamped to [z_min, 200 m] (§4.3–4.5, Table 4.1).
- Reference height z_e = h + f = dome height.
- c_pe,10 for a dome with circular base from **Figure 7.12**, digitised at its
  corner points (`frame/wind.py`), interpolated in f/d and h/d. Values at the
  windward edge A, crown B and leeward edge C; linear between them along arcs
  parallel to the wind (by arc angle), constant on planes across the wind.
- Domes taller than a hemisphere are treated as a hemisphere (f = R, d = 2R)
  on a wall of height h = the part below the equator.
- Internal pressure: the more onerous of +0.2 and −0.3 (§7.2.9), so both are run.
  The base is open, so internal pressure lifts the shell by Δc_pi·q_p·plan area.

## Combinations (EN 1990 eq. 6.10)

γ_G = 1.35 (1.0 when favourable), γ_Q = 1.5, ψ₀ = 0.5 snow, 0.6 wind:

```
1.35G
1.35G + 1.5S              (S or Sd)
1.35G + 1.5S + 0.9W
1.35G + 1.5W + 0.75S
1.0G  + 1.5W              uplift
```

Wind (and drift) are run for every 6° from 0° to 36° plus the direction you
choose. The dome repeats every 72° and is mirror-symmetric, so that covers all
directions. 79 combinations in total.

## Member check

Pin-ended, buckling length = strut length.

- Tension: N_t,Rd = A·f_t,d.
- Compression (EN 1993-1-1 §6.3.1 / EN 1995-1-1 §6.3.2, same form):
  λ̄ = √(A·f_k/N_cr), N_cr = π²EI/L², Φ = ½(1 + α(λ̄ − λ₀) + λ̄²),
  χ = 1/(Φ + √(Φ² − λ̄²)), N_b,Rd = χ·A·f_d.
- Utilisation = max(N_t/N_t,Rd, |N_c|/N_b,Rd) over all combinations.

| Material | f_k MPa | E for buckling | γ_M | k_mod | α, λ₀ |
|---|---|---|---|---|---|
| Timber C24 | 21 (c), 14.5 (t) | E₀.₀₅ 7400 | 1.3 | 0.8 | 0.2, 0.3 |
| Steel S235 tube | 235 | 210000 | 1.0 | – | 0.49, 0.2 (cold-formed, curve c) |
| Aluminium 6060-T6 tube | 140 | 70000 | 1.1 | – | 0.2, 0.1 |

## Not covered

- **Hubs, bolts, plates and anchors.** In real domes these usually fail first.
- Bending in struts from loads between hubs, and hub rotational stiffness.
- Joint slip (real deflections are larger than shown).
- Global (snap-through) buckling of the shell; local cladding pressures (c_pe,1);
  wind on an uncovered frame; snow drift against obstacles; national annex values.
- Seismic, imposed (maintenance) loads, and hanging loads.
