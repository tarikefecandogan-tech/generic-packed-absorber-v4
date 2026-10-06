# Generic Packed Absorber Simulator V4 — Phase 5 Status

## Gate

`PHASE5_COUNTERCURRENT_GATE = PASS`

Full packaged regression suite: **40/40 PASS**.

## Scope completed

Phase 5 adds a generic counter-current boundary-value solver on top of the
Phase 4 Onda/two-film coefficient layer.

Canonical coordinate and boundary convention:

- `z = 0`: gas inlet / liquid outlet (column bottom)
- `z = Z`: gas outlet / liquid inlet (column top)
- specified gas boundary: `y(0) = y_in`
- specified liquid boundary: `x(Z) = x_liquid_in`
- shooting variable: `x(0) = x_bottom`

The local model is:

- `driving force = y - m*x`
- `rate = K_G * a_e * P * (y - m*x)`
- `dy/dz = -rate/G'`
- `dx/dz = -rate/L'`

Numerical method:

- `scipy.integrate.solve_ivp`
- Brent root solve for the shooting boundary condition
- locked V3 ODE tolerances preserved for reference parity
- adaptive shooting bracket for nonzero liquid inlet loading

## Locked V3 parity

At the reference case (D=0.5 m, Z=1.4 m, Qg=117.53 actual m3/h,
L=2500 kg/h, T=22 C, P=101325 Pa, 25 mm Metal Pall Ring, fresh water):

### ACN

- `x_bottom = 6.8549417100347e-05`
- `y_out = 3.9912829105742e-06`
- `removal = 0.99796807334326`

### VAc

- `x_bottom = 2.3018167293488e-06`
- `y_out = 2.5299699106660e-05`
- `removal = 0.72236050739208`

These match the locked `REF_SCRUBBER_2026_10_06` V3 behavior within the
Phase 5 regression tolerance.

## New generic behavior verified

- nonzero solvent inlet loading `x(Z) > 0`
- desorption when `y - m*x < 0`
- no driving-force clamp
- zero shortcut only when both gas and liquid inlet solute are zero
- component gas/liquid solute mass-balance diagnostic
- boundary-condition closure diagnostic
- bed profiles for `y(z)`, `x(z)`, and `y-m*x`
- independent 1–4 solute orchestration
- no chemical-name branch in the Phase 5 physics solver

## Explicitly not in Phase 5

- total mgVOC/Nm3 / mgC/Nm3 composition conversion layer
- required-height target root solve
- generic pressure-drop model
- GPDC flooding
- applicability engine / final confidence classification
- reactive or coupled nonideal multicomponent absorption

## New runtime dependency

Phase 5 directly uses NumPy and SciPy. `requirements.txt` now includes:

- `numpy>=1.24,<3`
- `scipy>=1.11,<2`

## Next planned phase

**Phase 6 — Generic Hydraulics**: packed-bed holdup / pressure-drop screening,
packing-factor resolution, GPDC flooding capacity, percent flood, and hydraulic
regime diagnostics using resolved carrier/solvent/packing properties.
