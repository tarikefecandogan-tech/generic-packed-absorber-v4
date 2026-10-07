# Generic Packed Absorber Simulator V4 — Phase 16 Status

## Gate

**PHASE16_PARAMETER_SWEEP_GATE = PASS**

- Full automated regression suite: **136/136 PASS**
- Locked V3 parity: **82/82 metrics PASS**
- Phase 1–16 check scripts: **all PASS**
- Phase 14 integrated simulator and Phase 15 live audit results remain unchanged.

## Scope

Phase 16 adds **full-physics parameter sweep / sensitivity analysis**. The sweep layer does not contain a shortcut absorber equation. Every point modifies the canonical Phase 14 case and then reruns the complete verified calculation chain:

`case mutation → pre-applicability → property resolver → Onda/two-film → counter-current ODE → units/reporting → hydraulics → post-applicability`

## New module

`generic_absorber_v4/sweep.py`

Primary APIs:

- `SweepVariable`
- `SweepAxis`
- `run_parameter_sweep()`
- `apply_sweep_values()`
- `suggested_sweep_bounds()`

## Supported numerical axes

1. Temperature, °C
2. Pressure, bar abs
3. Actual gas flow, m³/h
4. Liquid mass flow, kg/h
5. Column diameter, m
6. Packed height, m
7. Feed concentration scale, × base feed

Phase 16 supports one- and two-dimensional sweeps. Categorical chemistry/solvent/packing comparison is intentionally reserved for Phase 17.

## Output retained at every successful point

Overall metrics:

- outlet mgVOC/Nm³
- outlet ppmv
- VOC-mass removal %
- captured kg/h
- % flood
- wet pressure drop, mbar/m
- total packed pressure drop, mbar
- final readiness status
- overall confidence

Per-solute metrics:

- inlet/outlet ppmv
- component removal %
- absorption factor A
- HTU_OG
- NTU_OG
- equilibrium slope m
- absorption/desorption mode

The point record also retains resolved solvent viscosity and carrier density so tests can verify that property resolution is rerun during temperature sweeps.

## Failure handling

A blocked, invalid, or numerically failed point is stored as a failed row with its status/error. It does not terminate the remainder of the sweep. The full grid therefore remains auditable.

## Safety / engineering interpretation

Phase 16 is a **sensitivity tool, not an optimizer**. A low calculated outlet is not automatically a feasible design. The corresponding applicability status, confidence, flooding and pressure drop must be inspected for the same point.

The sweep grid is limited to **225 points** to avoid accidental excessive cloud compute. Recommended Streamlit defaults are 9 points for 1D and 7×7 for 2D.

## Reference 1D verification

Using the locked ACN+VAc/water reference case and sweeping liquid flow from 1500 to 3500 kg/h:

| Liquid flow kg/h | Outlet mgVOC/Nm³ | VOC removal % | % Flood | Wet ΔP mbar/m | VAc A | VAc HTU m |
|---:|---:|---:|---:|---:|---:|---:|
| 1500 | 185.332 | 96.2934 | 6.5405 | 0.05518 | 0.70675 | 0.86826 |
| 2000 | 138.804 | 97.2239 | 6.8679 | 0.05607 | 0.94233 | 0.72820 |
| 2500 | 106.622 | 97.8676 | 7.1644 | 0.05683 | 1.17791 | 0.63799 |
| 3000 | 83.464 | 98.3307 | 7.4392 | 0.05751 | 1.41349 | 0.57431 |
| 3500 | 66.390 | 98.6722 | 7.6980 | 0.05813 | 1.64908 | 0.52659 |

The 2500 kg/h middle point reproduces the direct Phase 14 integrated result within regression tolerance.

## Streamlit

New tab: **Parameter Sweep**.

Workflow:

1. Run the baseline case under **Simulator**.
2. Open **Parameter Sweep**.
3. Select 1D or 2D.
4. Choose axis variables, bounds and point counts.
5. Run the full-physics sweep.
6. Inspect table, sensitivity curve / 2D response matrix, validity distribution and failed points.
7. Export the flattened result table as CSV if required.

### Canonical gas-flow note

A temperature or pressure sweep holds the baseline **actual gas volumetric flow** constant unless gas flow is itself selected as a sweep axis. This is explicit because the integrated case stores canonical actual flow, not the original UI flow-reference choice.
