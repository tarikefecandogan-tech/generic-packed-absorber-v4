# Phase 13 Status — VDC / Acrylonitrile

**Gate:** `PHASE13_VDC_ACN_GATE = PASS`

## Scope

Phase 13 adds liquid acrylonitrile (AN) as the second real solvent option for VDC and runs it through the generic registry → resolver → Onda/two-film → counter-current ODE → units → hydraulics → applicability chain.

This is a **screening thermodynamics** phase, not design-grade VDC/AN validation.

## Registered acrylonitrile solvent

- ID: `acrylonitrile`
- CAS: 107-13-1
- Formula: C3H3N
- MW: 53.06 g/mol
- Density at the 22 °C fixture: 803.88 kg/m³ (near-ambient interpolation)
- Dynamic viscosity: 0.34 mPa·s
- Surface tension: 27.3 mN/m
- Bulk-property confidence: B

## VDC transport path

- `DG`: Fuller correlation fallback → Confidence C
- `DL` in AN: Wilke–Chang fallback → Confidence C
- Wilke–Chang `phi=1.0` is explicitly a screening assumption; an AN-specific association-factor validation is not claimed.

Resolved fixture values:

- `DG = 9.1988490e-6 m²/s`
- `DL = 3.2275639e-9 m²/s`

## VDC / AN equilibrium treatment

No direct, traceable public VDC/AN binary VLE or infinite-dilution activity-coefficient dataset was registered in Phase 13.

Therefore the default pair is deliberately classified **Confidence D**:

`y* = m x`

with

`m = gamma_inf * Psat,VDC / P`

and the screening assumptions:

- `gamma_inf = 1.0`
- `T = 295.15 K (22 °C)`
- `P = 101325 Pa`
- VDC pure-component vapor pressure from the NIST Antoine correlation

This gives:

- `Psat,VDC = 71.567 kPa`
- `m = 0.706315367`

The registered `m` is intentionally limited to a narrow 22 °C window. It must be replaced by measured/fitted VDC/AN thermodynamics before design use.

## Solvent volatility limitation

NIST acrylonitrile vapor-pressure data give approximately:

- `Psat,AN(22 °C) = 12.867 kPa`
- `Psat/P ≈ 0.127`

V4.0 currently assumes no solvent evaporation. Therefore the Phase 13 applicability result is intentionally:

- **Final status:** `OUTSIDE_RECOMMENDED_RANGE`
- **Overall confidence:** `SCREENING`

The mathematical absorber result is shown, but it must not be interpreted as a full material-balance prediction for a volatile AN scrubber.

## Deterministic same-column fixture

Fixture basis (kept identical to Phase 12 for a controlled solvent comparison):

- Column diameter = 0.50 m
- Packed height = 1.40 m
- 25 mm Metal Pall Ring
- Gas = 117.53 actual m³/h
- Liquid = 2500 kg/h
- T = 22 °C
- P = 1 atm
- VDC inlet = 1000 ppmv
- Fresh solvent

### Phase 13 AN screening result

- Equilibrium slope `m = 0.706315367`
- Absorption factor `A = 13.7463`
- Effective wetted area `ae = 185.055 m²/m³`
- `HTU_OG = 0.140943 m`
- `NTU_OG = 9.93308`
- Outlet = `0.092713 ppmv`
- Removal = `99.99073%`
- Wet pressure drop = `5.49245 Pa/m`
- Flooding = `7.9459%`

### Controlled comparison to Phase 12 water fixture

- Water: `A = 0.02308`, removal = `2.2030%`
- Acrylonitrile screening: `A = 13.7463`, removal = `99.9907%`

The large difference is physically consistent with the much more favorable screening equilibrium slope, but the AN result is **not yet a validated solvent-design result** because its VDC/AN thermodynamics are Confidence D and AN evaporation is omitted.

## Project pilot observation

The project slide deck reports a realised VDC/AN trial with:

- Nitrogen = 300 L/h
- AN = 18 L/h
- final liquid = 93.84% AN / 6.16% VDC
- gas outlet = 1100 ppm VOC
- note that both VDC and AN liquid levels decreased

This is useful qualitative evidence that AN takes up VDC, and it also reinforces the solvent-volatility concern. It is **not used to tune Phase 13**, because the available summary does not provide a clean inlet VDC concentration, run-duration/material inventory, or solvent-loss material balance.

## Regression status

- Phase 1–13 gate scripts: PASS
- Automated tests: **115/115 PASS**
- Locked V3 full parity: **82/82 PASS**

## Required next thermodynamic upgrade

Before treating VDC/AN as design-grade, obtain at least one of:

1. measured VDC/AN VLE data near operating temperature,
2. infinite-dilution activity coefficient `gamma_inf(T)` for VDC in AN,
3. reliable NRTL/UNIQUAC/UNIFAC binary parameters validated against data,
4. a sufficiently complete pilot material balance to calibrate an effective equilibrium model.

Solvent evaporation should then be coupled into the gas/liquid flow balance rather than left as a warning only.
