# Phase 10 Status — Synthetic Generic Chemistry Test

**Gate:** `PHASE10_SYNTHETIC_GENERIC_GATE = PASS`

Phase 10 adds no new absorber correlation. Its purpose is to prove that the
architecture built through Phase 9 is genuinely generic rather than a renamed
ACN/VAc-specific program.

## Synthetic case

The fixture contains only fictional entities:

- solutes: `SYN_H`, `SYN_M`
- carrier: `carrier_x`
- solvent: `solvent_q`
- random packing: `packing_z`

None of these entities exists in the locked V3 reference database.

`SYN_H` uses the supported Henry-Hpc equilibrium path. `SYN_M` uses the other
supported V4.0 path, direct linear `y*=m x`, and enters with nonzero solvent
loading (`x_in = 2e-5`). This intentionally exercises more than the original
fresh-water reference pathway.

## Full chain exercised

`Registry -> Resolver -> Onda/two-film -> Counter-current ODE -> Units/reporting -> Hydraulics -> Applicability`

The synthetic case resolves two independent components in the same column.

## Architecture audit

The generic physics/domain modules:

- `mass_transfer.py`
- `countercurrent.py`
- `hydraulics.py`
- `units.py`
- `applicability.py`

were scanned for standalone legacy identifiers `ACN`, `VAc`, `water`, and
`air`. The Phase 10 gate found **no hits**.

Reference/database modules are intentionally excluded from this audit because
legacy chemical names belong there by design.

## Synthetic baseline results

Common Onda state:

- `Re_L = 11.2255710137`
- `Re_G = 84.4765583646`
- wetting fraction `= 0.644531051890`

`SYN_H`:

- equilibrium model: `henry_pc`
- `m = 2.67391304348`
- absorption factor `A = 2.49036040517`
- `HTU_OG = 0.492662491872 m`
- `NTU_OG = 4.87148918295`
- `y_out = 6.62967003187e-05`
- removal `= 96.6851649841 %`

`SYN_M`:

- equilibrium model: `linear_m`
- `m = 0.85`
- absorption factor `A = 7.83412608275`
- `HTU_OG = 0.388257114295 m`
- `NTU_OG = 6.18147076160`
- `y_out = 2.09047852372e-05`
- removal `= 97.9095214763 %`
- nonzero liquid inlet loading is preserved by the BVP solver

Hydraulics:

- wet pressure drop `= 8.06753420819 Pa/m`
- GPDC flood velocity `= 2.20158583923 m/s`
- operating flood fraction `= 9.12549692611 %`
- GPDC range check: PASS

Multicomponent reporting:

- inlet total `= 3000 ppmv`
- outlet total `= 87.2014855559 ppmv`
- inlet `= 9904.53741620 mgVOC/Nm³`
- outlet `= 276.971850985 mgVOC/Nm³`
- captured synthetic-solute mass `= 2.46567591268 kg/h`

Pre- and post-applicability states are both `READY` with zero blocking issues.

## Regression status

- Phase 1 gate: PASS
- Phase 2 gate: PASS
- Phase 3 gate: PASS
- Phase 4 gate: PASS
- Phase 5 gate: PASS
- Phase 6 gate: PASS
- Phase 7 gate: PASS
- Phase 8 gate: PASS
- Phase 9 full V3 parity gate: PASS
- Phase 10 synthetic generic gate: PASS
- **96 automated tests PASS**
- Phase 9 still independently checks **82/82 locked V3 parity metrics**

## Interpretation

A Phase 10 PASS verifies software architecture, data routing, supported
model-path plumbing and numerical integration for chemistry that is not in the
legacy reference case. It is **not** experimental validation of a real chemical
system, because the Phase 10 property values are deliberately fictional.

Next planned phase: **Phase 11 — Property-estimation correlations**.
