from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
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
assert result.pass_gate
assert abs(result.outlet_report.total_mgVOC_Nm3 - 106.6222813666) < 1e-6
print("PHASE14_INTEGRATED_SIMULATOR_GATE = PASS")
print(f"Outlet mgVOC/Nm3 = {result.outlet_report.total_mgVOC_Nm3:.9f}")
print(f"VOC mass removal = {100*result.stream_balance.overall_removal_voc_mass:.6f}%")
