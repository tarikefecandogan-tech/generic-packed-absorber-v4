from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    build_live_methods_report,
    build_phase14_registry,
    canonical_y_from_total_and_fractions,
    run_generic_absorber_case,
)

registry = build_phase14_registry()
solutes = {sid: registry.get_solute(sid) for sid in ("ACN", "VAc")}
feed = canonical_y_from_total_and_fractions(
    5000.0,
    GasConcentrationBasis.MG_VOC_NM3,
    {"ACN": 0.93, "VAc": 0.07},
    CompositionFractionBasis.VOC_MASS,
    solutes,
)
case = GenericAbsorberCase(
    operating=AbsorberOperatingPoint(0.5, 1.4, 117.53, 2500.0, 295.15, 101325.0),
    solute_ids=("ACN", "VAc"),
    carrier_id="air",
    solvent_id="water",
    packing_id="25mm_metal_pall_ring",
    gas_inlet_y=feed.canonical_y,
    liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
)
result = run_generic_absorber_case(case, registry=registry)
report = build_live_methods_report(result)
assert len(report.equations) >= 20
assert len(report.properties) >= 10
assert len(report.assumptions) >= 10
assert len(report.diagnostics) >= 10
assert any(x.scope == "ACN" for x in report.properties)
assert any(x.scope == "VAc" for x in report.properties)
print("PHASE15_LIVE_METHODS_GATE = PASS")
print(f"Equations = {len(report.equations)}")
print(f"Property audit rows = {len(report.properties)}")
print(f"Assumptions = {len(report.assumptions)}")
print(f"Diagnostics = {len(report.diagnostics)}")
