"""Human-readable Phase 6 V3 hydraulics-parity gate."""
from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    build_reference_registry,
    build_reference_resolver,
    evaluate_hydraulics_from_resolver,
)

op = AbsorberOperatingPoint(
    diameter_m=0.5,
    packed_height_m=1.4,
    gas_actual_m3_h=117.53,
    liquid_mass_kg_h=2500.0,
    temperature_K=295.15,
    pressure_Pa=101325.0,
)
_, h = evaluate_hydraulics_from_resolver(
    resolver=build_reference_resolver(),
    registry=build_reference_registry(),
    carrier_id="air",
    solvent_id="water",
    packing_id="25mm_metal_pall_ring",
    operating=op,
)

checks = {
    "hL": (h.pressure_drop.liquid_holdup_fraction, 0.05713056691346087, 1e-10),
    "dPdry_Pa_m": (h.pressure_drop.dry_pressure_drop_Pa_m, 4.729685067279156, 1e-10),
    "dPwet_Pa_m": (h.pressure_drop.wet_pressure_drop_Pa_m, 5.683288286702279, 1e-10),
    "U_flood_m_s": (h.flooding.flood_velocity_m_s, 2.3208029666997687, 1e-9),
    "F_LV_flood": (h.flooding.F_LV_flood, 0.0440888436630539, 1e-9),
    "CP_flood": (h.flooding.CP_flood, 1.8245028673067514, 1e-9),
    "flood_pct": (h.flooding.flooding_percent, 7.164371117329295, 1e-9),
    "dP_flood_mbar_m": (h.flooding.flood_pressure_drop_mbar_m, 14.12232286238167, 1e-9),
    "dP_ratio": (h.pressure_drop_ratio_to_flood, 0.004024329667353191, 1e-9),
}

ok = True
for label, (value, ref, rtol) in checks.items():
    tol = rtol * max(abs(ref), 1e-12)
    passed = abs(value - ref) <= tol
    ok &= passed
    print(f"{label:20s}: {value:.14g} | ref={ref:.14g} | {'PASS' if passed else 'FAIL'}")

print("regime              :", h.flooding.hydraulic_regime)
print("Fp basis            :", h.flooding.packing_factor_basis)
print("PHASE6_HYDRAULICS_GATE =", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
