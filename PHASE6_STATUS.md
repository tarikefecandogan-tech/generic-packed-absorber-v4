# Phase 6 Status — Generic Hydraulics

**Reference:** `REF_SCRUBBER_2026_10_06`

## Gate

`PHASE6_HYDRAULICS_GATE = PASS`

Full regression suite: **48/48 PASS**.

## Added in Phase 6

- `generic_absorber_v4/hydraulics.py`
- generic liquid-holdup screening correlation
- dry and wet packed-bed pressure drop
- empirical/literature GPDC packing factor with visible geometric fallback
- GPDC flood-velocity root solve
- percent flood and hydraulic-regime classification
- Kister–Gill pressure-drop-at-flood diagnostic
- solute-independent resolver orchestration
- Streamlit **Hydraulics** tab

## Locked V3 parity — reference case

Operating case: 25 mm Metal Pall Ring, D=0.5 m, Z=1.4 m,
Qg=117.53 actual m3/h, L=2500 kg/h, T=22 °C, P=101325 Pa.

| Quantity | Phase 6 / locked reference |
|---|---:|
| liquid holdup hL | 0.0571305669135 |
| dry pressure drop | 4.72968506728 Pa/m |
| wet pressure drop | 5.68328828670 Pa/m |
| wet pressure drop | 0.0568328828670 mbar/m |
| total packed pressure drop | 7.95660360138 Pa |
| GPDC flood velocity | 2.32080296670 m/s |
| F_LV at flood | 0.0440888436631 |
| CP at flood | 1.82450286731 |
| percent flood | 7.16437111733 % |
| hydraulic regime | UNDERLOADED / HIGH CAPACITY MARGIN |
| Kister–Gill flood diagnostic | 14.1223228624 mbar/m |
| wet dP / flood-diagnostic dP | 0.00402432966735 |

## Engineering boundary

Phase 6 keeps the existing V3 pressure-drop relation as a **screening model**.
Percent flood is calculated from `Ug / Uflood`; it is not inferred from the
pressure-drop ratio. Kister–Gill pressure drop at flood is diagnostic only.

The current model does not include foaming, entrainment, distributor/support
losses, demisters, fouling or maldistribution.

## Next planned phase

**Phase 7 — Generic Units & Composition Layer**.
