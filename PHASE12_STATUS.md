# Generic Packed Absorber Simulator V4 — Phase 12 Status

## Gate

`PHASE12_VDC_WATER_GATE = PASS`

Phase 12 is the first **real, non-reference chemistry** extension of the V4 engine.  The locked ACN/VAc / Water / Air reference snapshot remains untouched.

## New chemistry

- Solute: **VDC / 1,1-dichloroethylene / vinylidene chloride**
- CAS: **75-35-4**
- Formula: **C2H2Cl2**
- MW: **96.943 g/mol**
- Solvent: **Water**
- Default carrier for this deterministic gate: **Air**

## Equilibrium dataset

Primary Phase 12 default:

- NIST Chemistry WebBook Henry compilation
- Gossett, J.M. (1987), *Measurement of Henry's Law Constants for C1 and C2 Chlorinated Hydrocarbons*, Environmental Science & Technology 21, 202–208
- Solubility-form Henry constant at 298.15 K: `kH = 0.039 mol/(kg·bar)`
- Temperature dependence: `3700 K`
- Converted V4 pressure/concentration form: `Hpc(298.15 K) = 2571.624262 Pa·m3/mol`
- Confidence: **B**

Important: published VDC/water Henry values have substantial inter-source scatter.  The Gossett/NIST value is therefore a traceable default, not a claim of negligible thermodynamic uncertainty.

## Transport-property path

No experimental VDC/air DG pair or VDC/water DL pair was inserted as if it were measured.

### Gas diffusivity

- Fuller atomic increments: C=16.5, H=1.98, Cl=19.5
- VDC Fuller volume = `75.96`
- Air Fuller volume = `20.1`
- Resolved at 22 °C / 1 atm: `DG = 9.198849015534e-06 m2/s`
- Tier: `CORRELATION_ESTIMATE`
- Confidence: **C**

### Liquid diffusivity

- Wilke–Chang
- Water association factor: `phi = 2.6`
- VDC Le Bas normal-boiling molar-volume estimate: `86.2 cm3/mol`
- Resolved at 22 °C: `DL = 1.079872929811e-09 m2/s`
- Tier: `CORRELATION_ESTIMATE`
- Confidence: **C**

## Applicability update

Phase 8 originally treated every unregistered DG/DL pair as blocking.  After Phase 11 estimators this was no longer logically complete.  Phase 12 updates the pre-solver applicability check:

- missing pair + complete Fuller/Wilke–Chang inputs → **WARNING / correlation fallback available**
- missing pair + incomplete estimator inputs → **BLOCK / insufficient data**

This preserves the rule:

`User Override > Database > Correlation Estimate > Missing`

## Deterministic Phase 12 engineering fixture

This fixture is for software/engineering verification, not plant calibration.

- D = 0.5 m
- packed height = 1.4 m
- gas flow = 117.53 actual m3/h
- water = 2500 kg/h
- T = 22 °C
- P = 101325 Pa
- VDC inlet = 1000 ppmv
- liquid inlet VDC = 0
- packing = 25 mm Metal Pall Ring

Results:

- `Hpc(22 °C) = 2266.869651 Pa·m3/mol`
- equilibrium slope `m = 1239.136953`
- absorption factor `A = 0.0230779941`
- `HTU_OG = 19.3042673 m`
- `NTU_OG = 0.0725228`
- outlet = `977.969725 ppmv`
- removal = `2.203027 %`
- outlet = `4229.831708 mgVOC/Nm3`
- wet packed-bed pressure drop = `5.683288 Pa/m`
- flooding = `7.164371 %`
- relative solute mass-balance error = `2.624e-15`

Interpretation: with the selected NIST/Gossett equilibrium dataset and the reference L/G/geometry, **water is a weak physical absorbent for VDC** (`A << 1`).  This is a screening conclusion and must be tested against equilibrium uncertainty and plant data before design decisions.

## Confidence / validity

- Pre-solver: `READY_WITH_WARNINGS`
- Final: `READY_WITH_WARNINGS`
- Thermodynamics: `MODERATE`
- Mass transfer: `SCREENING`
- Hydraulics: `MODERATE`
- Overall: `SCREENING`

The mass-transfer downgrade is caused by correlation-estimated DG and DL, not numerical instability.

## Regression status

- Automated tests: **110 / 110 PASS**
- Full V3 parity: **82 / 82 PASS**
- Phase 1–12 gate scripts: **PASS**
- `app.py` + package syntax/import compilation: **PASS**

## Project-trial note

The existing project presentation contains prior VOC-removal trials involving water and VDC-containing liquid analyses.  The slide wording does not provide a clean VDC-only gas/water equilibrium dataset, so those trials are **not used to fit or tune Phase 12**.  They should be revisited later as external validation/calibration evidence once inlet composition, outlet composition, temperature, pressure, packing and sampling basis are unambiguously reconstructed.

## Next planned phase

**Phase 13 — VDC / Acrylonitrile solvent chemistry**
