"""Human-readable Phase 5 V3 outlet-parity gate."""
from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    ComponentBoundaryConditions,
    build_reference_registry,
    build_reference_resolver,
    evaluate_component_from_resolver,
    solve_component_countercurrent,
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

reference = {
    "ACN": {
        "y_in": 0.001964284929935824,
        "x_bottom": 6.854941710034729e-05,
        "y_out": 3.991282910574221e-06,
        "removal": 0.9979680733432574,
    },
    "VAc": {
        "y_in": 9.112428087594802e-05,
        "x_bottom": 2.301816729348773e-06,
        "y_out": 2.5299699106660017e-05,
        "removal": 0.7223605073920776,
    },
}

ok = True
for sid, ref in reference.items():
    common, mt = evaluate_component_from_resolver(
        resolver=resolver,
        registry=registry,
        solute_id=sid,
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=op,
    )
    result = solve_component_countercurrent(
        common,
        mt,
        ComponentBoundaryConditions(ref["y_in"], 0.0),
    )
    checks = {
        "x_bottom": result.liquid_bottom_x,
        "y_out": result.gas_outlet_y,
        "removal": result.removal_fraction,
    }
    for key, value in checks.items():
        expected = ref[key]
        tol = 1e-8 * max(abs(expected), 1e-12)
        passed = abs(value - expected) <= tol
        ok &= passed
        print(f"{sid:4s} {key:8s}: {value:.14g} | ref={expected:.14g} | {'PASS' if passed else 'FAIL'}")
    print(
        f"     boundary={result.diagnostics.boundary_error_x:.3e}  "
        f"mass-balance(rel)={result.diagnostics.relative_mass_balance_error:.3e}  "
        f"mode={result.diagnostics.mode}"
    )

print("PHASE5_COUNTERCURRENT_GATE =", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
