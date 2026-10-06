"""Standalone Phase 8 applicability/validity gate for the locked reference case."""
from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    ApplicabilityCase,
    ComponentBoundaryConditions,
    ReadinessStatus,
    assess_post_applicability,
    assess_pre_applicability,
    build_reference_registry,
    build_reference_resolver,
    evaluate_component_from_resolver,
    evaluate_hydraulics_from_resolver,
    solve_independent_solutes,
)

Y = {
    "ACN": 1.964284929935824e-3,
    "VAc": 9.112428087594802e-5,
}
op = AbsorberOperatingPoint(
    diameter_m=0.5,
    packed_height_m=1.4,
    gas_actual_m3_h=117.53,
    liquid_mass_kg_h=2500.0,
    temperature_K=295.15,
    pressure_Pa=101325.0,
)
registry = build_reference_registry()
resolver = build_reference_resolver()
case = ApplicabilityCase(
    operating=op,
    solute_ids=("ACN", "VAc"),
    carrier_id="air",
    solvent_id="water",
    packing_id="25mm_metal_pall_ring",
    gas_inlet_y=Y,
    liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
)
pre = assess_pre_applicability(registry, case)
assert pre.status == ReadinessStatus.READY

resolved = {}
transfers = {}
common = None
for sid in ("ACN", "VAc"):
    resolved[sid] = resolver.resolve_component_properties(
        sid, "air", "water", op.temperature_K, op.pressure_Pa
    )
    common_i, mt = evaluate_component_from_resolver(
        resolver=resolver,
        registry=registry,
        solute_id=sid,
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=op,
    )
    common = common or common_i
    transfers[sid] = mt

solved = solve_independent_solutes(
    common,
    transfers,
    {sid: ComponentBoundaryConditions(gas_inlet_y=Y[sid], liquid_inlet_x=0.0) for sid in Y},
)
_, hyd = evaluate_hydraulics_from_resolver(
    resolver=resolver,
    registry=registry,
    carrier_id="air",
    solvent_id="water",
    packing_id="25mm_metal_pall_ring",
    operating=op,
)
post = assess_post_applicability(
    pre,
    resolved_components=resolved,
    common=common,
    transfer_results=transfers,
    solver_results=solved,
    hydraulics=hyd,
    packing=registry.get_packing("25mm_metal_pall_ring"),
)
assert post.status == ReadinessStatus.READY_WITH_WARNINGS
assert post.confidence.overall.value == "MODERATE"
assert not post.blocks
assert any(i.code.startswith("UNSPECIFIED_REFERENCE_STATE") for i in post.warnings)

print("PRE_STATUS =", pre.status.value)
print("FINAL_STATUS =", post.status.value)
print("OVERALL_CONFIDENCE =", post.confidence.overall.value)
print("BLOCKS =", len(post.blocks))
print("WARNINGS =", len(post.warnings))
print("INFO =", len(post.infos))
print("PHASE8_APPLICABILITY_GATE = PASS")
