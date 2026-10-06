# Generic Packed Absorber Simulator V4 — Phase 3 Status

**Gate:** `PHASE3_RESOLVER_GATE = PASS`

Phase 3 adds the operating-point property resolver on top of the locked Phase 1 data objects and the Phase 2 exact registry.

## Implemented

- Resolution precedence: **User Override > Registered Database > Correlation Estimate Hook > Missing**.
- `ResolvedProperty` audit object with value, unit, resolution tier, source, method, confidence and notes.
- Air operating-point viscosity from the locked Sutherland parameters.
- Air density from the same ideal-gas basis used by the reference engine.
- Water density, viscosity and surface tension from the exact locked V3 correlations.
- Exact registered ACN/VAc gas and liquid diffusivities preserved for V3 parity.
- Henry `H(T)` evaluation from registered solute–solvent equilibrium pairs.
- User operating-point overrides that do **not** mutate the registry.
- Optional estimator hooks for future Fuller / Wilke–Chang implementations.
- Explicit `MissingPropertyError` when a critical property cannot be resolved.
- Explicit blocking of unsupported equilibrium physics.

## Deliberately not implemented yet

- Fuller diffusivity equation.
- Wilke–Chang diffusivity equation.
- Onda wetted-area or film coefficients.
- Overall two-film `K_G`.
- Counter-current ODE solver.
- Pressure drop / GPDC flooding.
- Required height or generic outlet concentration.

The estimator hooks are architectural only in Phase 3. The actual engineering correlations are deferred until the planned estimation-correlation phase so that V3 regression parity can be established first.

## Locked reference parity checks at 22 °C

- Air density = `1.19739554421 kg/m³`
- Air viscosity = `1.82287646955e-5 Pa·s`
- Water density = `997.800320317 kg/m³`
- Water viscosity = `9.54775575395e-4 Pa·s`
- Water surface tension = `0.0724322704793 N/m`
- ACN `DG = 1.0e-5 m²/s`
- ACN `DL = 1.0e-9 m²/s`
- ACN `H(22 °C) = 1.03613136396 Pa·m³/mol`
- VAc `DG = 0.9e-5 m²/s`
- VAc `DL = 0.9e-9 m²/s`
- VAc `H(22 °C) = 44.4131946273 Pa·m³/mol`

## Automated tests

Phase 1 + Phase 2 + Phase 3: **23/23 PASS**.
