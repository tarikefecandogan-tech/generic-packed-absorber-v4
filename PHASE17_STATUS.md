# Generic Packed Absorber Simulator V4 — Phase 17 Status

## Gate

**PHASE17_COMPARISON_GATE = PASS**

- Full automated regression suite: **144/144 PASS**
- Locked V3 parity: **82/82 metrics PASS**
- Phase 1–17 check scripts: **all PASS**
- `app.py` package export check: **86/86 imports available**
- Locked 25 mm Metal Pall Ring reference values and Phase 9 outputs remain unchanged.

## Scope

Phase 17 adds **engineering comparison tools**. Each alternative is evaluated by rerunning the same verified integrated V4 calculation chain:

`case alternative → pre-applicability → property resolver → Onda/two-film → counter-current ODE → units/reporting → hydraulics → post-applicability`

There is no shortcut comparison equation and no hidden composite "best" score.

## New modules

- `generic_absorber_v4/comparison.py`
- `generic_absorber_v4/packing_catalog.py`

Primary APIs:

- `compare_packings()`
- `compare_solvents()`
- `compare_named_cases()`
- `EngineeringComparisonResult`
- `ComparisonAlternativeResult`
- `NamedCase`

## Packing comparison catalog

Phase 1 intentionally locked only the selected `25mm_metal_pall_ring` for parity. Phase 17 adds the remaining **legacy V3 random-packing records** as comparison alternatives without modifying the locked Phase 1 bundle:

- 38 mm Metal Pall Ring
- IMTP #25
- IMTP #40
- CMR #2
- CMR #3
- 13 mm Super Raschig
- 16 mm Super Raschig
- 25 mm Super Raschig
- 38 mm Super Raschig

These records retain explicit provenance from the legacy V3 packing table and are **engineering-screening data unless independently checked against a current vendor datasheet**.

Packings with no empirical `Fp` retain the existing geometric `a/eps^3` fallback and remain visibly screening-level in hydraulics/applicability.

## Comparison modes

### Packing comparison

Holds constant:

- solutes and gas feed
- carrier gas
- solvent and solvent inlet loading
- temperature and pressure
- gas and liquid flow
- column diameter and packed height

Only `packing_id` changes.

### Solvent comparison

Holds constant:

- solutes and gas feed
- carrier gas
- packing
- geometry
- gas/liquid flow basis
- temperature and pressure

Only `solvent_id` changes. Unsupported solute-solvent chemistry is retained as a failed alternative with a reason rather than silently removed.

Acrylonitrile is automatically flagged as materially volatile in the product UI because V4.0 does not model solvent evaporation.

### Named scenario comparison API

`compare_named_cases()` can compare complete named `GenericAbsorberCase` objects for programmatic studies. This does not force unlike scenarios into a hidden score.

## Outputs per successful alternative

Overall:

- outlet mgVOC/Nm³
- outlet ppmv
- VOC-mass removal %
- captured kg/h
- % flood
- wet pressure drop, mbar/m
- total pressure drop, mbar
- final readiness status
- overall confidence

Per solute:

- inlet/outlet ppmv
- component removal %
- absorption factor A
- HTU_OG
- NTU_OG
- equilibrium slope m
- absorption/desorption mode

## No automatic winner

Phase 17 intentionally does **not** calculate a composite design score. A high-removal alternative can still be poor because of:

- pressure drop
- flooding margin
- low thermodynamic confidence
- correlation estimates
- unsupported solvent evaporation
- extrapolated/screening packing data

Decision-making therefore remains multi-criteria and auditable.

## Reference packing comparison example

Locked ACN+VAc / Water case, same operating basis:

| Packing | Outlet mgVOC/Nm³ | VOC removal % | % Flood | Wet ΔP mbar/m | Status | Confidence |
|---|---:|---:|---:|---:|---|---|
| 25mm Metal Pall Ring | 106.622 | 97.8676 | 7.164 | 0.05683 | READY_WITH_WARNINGS | MODERATE |
| 38mm Metal Pall Ring | 213.957 | 95.7209 | 5.202 | 0.03056 | READY_WITH_WARNINGS | MODERATE |
| IMTP #25 | 110.078 | 97.7984 | 6.520 | 0.05453 | OUTSIDE_RECOMMENDED_RANGE | MODERATE |
| IMTP #40 | 275.041 | 94.4992 | 4.752 | 0.02781 | READY_WITH_WARNINGS | MODERATE |
| CMR #2 | 103.153 | 97.9369 | 8.469 | 0.04072 | READY_WITH_WARNINGS | SCREENING |

This table is illustrative only. It demonstrates why removal, hydraulics and confidence must be reviewed together.

## VDC solvent comparison example

Same VDC feed/column/flow basis:

| Solvent | Outlet ppmv | Removal % | % Flood | Wet ΔP mbar/m | Status | Confidence |
|---|---:|---:|---:|---:|---|---|
| Water | 977.970 | 2.2030 | 7.164 | 0.05683 | READY_WITH_WARNINGS | SCREENING |
| Acrylonitrile | 0.0927 | 99.9907 | 7.946 | 0.05492 | OUTSIDE_RECOMMENDED_RANGE | SCREENING |

The AN result remains a screening result because VDC/AN equilibrium is Confidence D and solvent evaporation is not modelled.

## Streamlit

New product tab: **Comparison**.

Workflow:

1. Run a baseline under **Simulator**.
2. Open **Comparison**.
3. Choose **Packing alternatives** or **Solvent alternatives**.
4. Select alternatives.
5. Run the full-physics comparison.
6. Inspect performance, hydraulics, readiness/confidence, failed alternatives and property provenance.
7. Export the flattened table as CSV.

The comparison chart is a visualization of one selected metric only; it is not an automatic ranking score.

## Milestone status

Phase 17 completes the originally planned **Milestone C** product sequence:

- integrated product UI
- live Methods & Assumptions
- parameter sweeps
- comparison tools

Further work should be treated as a new roadmap/release cycle rather than silently extending the original Phase 0–17 migration plan.
