"""Human-readable Phase 4 regression gate."""
from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    build_reference_registry,
    build_reference_resolver,
    evaluate_component_from_resolver,
)

op = AbsorberOperatingPoint(
    diameter_m=0.5,
    packed_height_m=1.4,
    gas_actual_m3_h=117.53,
    liquid_mass_kg_h=2500.0,
    temperature_K=295.15,
    pressure_Pa=101325.0,
)
resolver = build_reference_resolver()
registry = build_reference_registry()
expected = {
    "ACN": {"A": 50.49051331523841, "HTU": 0.2220933460636276, "NTU": 6.303655759227084, "KG": 2.802392662477365e-6},
    "VAc": {"A": 1.1779113136890638, "HTU": 0.6379884514458747, "NTU": 2.194397087952261, "KG": 9.75554905395585e-7},
}

ok = True
for sid in ("ACN", "VAc"):
    common, result = evaluate_component_from_resolver(
        resolver=resolver,
        registry=registry,
        solute_id=sid,
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=op,
    )
    checks = {
        "A": result.absorption_factor,
        "HTU": result.HTU_OG_m,
        "NTU": result.NTU_OG,
        "KG": result.K_G,
    }
    for key, value in checks.items():
        ref = expected[sid][key]
        passed = abs(value-ref) <= 1e-10 * max(abs(ref), 1.0)
        ok &= passed
        print(f"{sid:4s} {key:3s}: {value:.14g} | ref={ref:.14g} | {'PASS' if passed else 'FAIL'}")

print(f"a_e: {common.effective_area_m2_m3:.14g} m2/m3")
print("PHASE4_MASS_TRANSFER_GATE =", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
