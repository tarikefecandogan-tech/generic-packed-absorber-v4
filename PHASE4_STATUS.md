# Phase 4 Status — Generic Onda Mass-Transfer Core

**Gate:** `PHASE4_MASS_TRANSFER_GATE = PASS`

Phase 4 connects the Phase 3 resolved-property layer to a chemistry-independent Onda/two-film coefficient core.

## Added

- `generic_absorber_v4/mass_transfer.py`
- canonical `AbsorberOperatingPoint`
- common Onda state calculated once per bulk case
- component-specific `ScL`, `ScG`, `kL`, `kG`, `KG`
- Henry/linear equilibrium slope handling
- absorption factor `A`
- `HTU_OG` and `NTU_OG`
- gas/liquid film-resistance fractions
- reference parity tests for ACN and VAc
- synthetic custom-solute test proving the core does not depend on ACN/VAc names

## Locked reference parity

At the locked reference operating point (22 °C, 1.01325 bar abs, D=0.5 m, Z=1.4 m, Q=117.53 m³/h actual, L=2500 kg/h, 25 mm Metal Pall Ring):

- `a_e = 108.8616313829 m²/m³`
- ACN `A = 50.4905133152`, `HTU = 0.2220933461 m`, `NTU = 6.3036557592`
- VAc `A = 1.17791131369`, `HTU = 0.6379884514 m`, `NTU = 2.1943970880`

The full kL/kG/KG intermediate coefficient set is regression-tested against the locked V3 baseline.

## Scope boundary

Phase 4 still does **not** calculate:

- counter-current ODE profiles
- outlet concentration or removal
- required packed height
- pressure drop
- GPDC flooding

Those remain later phases.
