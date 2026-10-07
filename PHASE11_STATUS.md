# Phase 11 Status — Property Estimation Correlations

**Gate:** `PHASE11_PROPERTY_ESTIMATION_GATE = PASS`

Phase 11 adds controlled fallback estimates for missing binary transport properties while preserving the resolver hierarchy:

`USER OVERRIDE > DATABASE > CORRELATION ESTIMATE > MISSING`

Implemented:

- Fuller–Schettler–Giddings estimate for gas-phase binary diffusivity `DG`.
- Wilke–Chang estimate for dilute liquid-phase diffusivity `DL`.
- Every built-in estimate is tagged `CORRELATION_ESTIMATE`, `estimated=True`, `Confidence C`.
- Database pair values remain higher priority than correlations.
- User overrides remain higher priority than both database and correlations.
- Missing correlation inputs produce `MissingPropertyError`; there is no guessed fallback value.
- Built-in estimators can be explicitly disabled through `enable_builtin_estimators=False`.

## Required data

### Fuller
- solute MW
- carrier MW
- solute Fuller diffusion volume
- carrier Fuller diffusion volume
- operating T and absolute P

Equation basis used:

`D_AB[cm²/s] = 0.001 T^1.75 sqrt(1/MA + 1/MB) / (P_atm (VA^(1/3)+VB^(1/3))²)`

### Wilke–Chang
- solvent MW
- solvent viscosity at operating T
- solvent association factor `phi`
- solute molar volume at its normal boiling point
- operating T

Equation basis used:

`D_AB[cm²/s] = 7.4e-8 sqrt(phi_B M_B) T / (mu_B[cP] V_A^0.6)`

## Regression result

- `104/104` automated tests PASS.
- Phase 9 full V3 parity remains `82/82 PASS`.
- Phase 10 synthetic generic gate remains PASS.
- Locked ACN/VAc DG/DL values still resolve from the database, not from correlations.

## Phase 11 deterministic estimator fixture

For synthetic `EST_X` at 298.15 K and 101325 Pa with the separate Phase 11 synthetic carrier/solvent fixture:

- Fuller `DG = 1.024307968686e-05 m²/s`
- Wilke–Chang `DL = 1.069956635312e-09 m²/s`

These values verify software behavior only and are not a real chemical validation case.

The locked V3 Air/Water reference records are not modified with invented Fuller/Wilke–Chang metadata.
