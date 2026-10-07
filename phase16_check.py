from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    SweepAxis,
    SweepVariable,
    build_phase14_registry,
    canonical_y_from_total_and_fractions,
    run_parameter_sweep,
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
sweep = run_parameter_sweep(
    case,
    [SweepAxis(SweepVariable.LIQUID_MASS_KG_H, 1500.0, 3500.0, 5)],
    registry=registry,
)
assert sweep.total_points == 5
assert sweep.successful_points == 5
assert all("ACN" in p.component_metrics for p in sweep.points)
print("PHASE16_PARAMETER_SWEEP_GATE = PASS")
print(f"Sweep points = {sweep.total_points}")
print(f"Successful = {sweep.successful_points}")
print(f"Failed = {sweep.failed_points}")
