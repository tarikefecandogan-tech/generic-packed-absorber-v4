from dataclasses import replace

import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    ApplicabilityCase,
    ComponentBoundaryConditions,
    ConfidenceLevel,
    EquilibriumPair,
    IssueSeverity,
    ReadinessStatus,
    SoluteSpec,
    assess_post_applicability,
    assess_pre_applicability,
    build_reference_registry,
    build_reference_resolver,
    evaluate_component_from_resolver,
    evaluate_hydraulics_from_resolver,
    solve_independent_solutes,
)


REF_Y = {
    "ACN": 1.964284929935824e-3,
    "VAc": 9.112428087594802e-5,
}


def reference_operating():
    return AbsorberOperatingPoint(
        diameter_m=0.5,
        packed_height_m=1.4,
        gas_actual_m3_h=117.53,
        liquid_mass_kg_h=2500.0,
        temperature_K=295.15,
        pressure_Pa=101325.0,
    )


def reference_case(**kwargs):
    base = dict(
        operating=reference_operating(),
        solute_ids=("ACN", "VAc"),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y=REF_Y,
        liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
    )
    base.update(kwargs)
    return ApplicabilityCase(**base)


def solved_reference():
    registry = build_reference_registry()
    resolver = build_reference_resolver()
    op = reference_operating()

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
        if common is None:
            common = common_i
        transfers[sid] = mt

    boundaries = {
        sid: ComponentBoundaryConditions(gas_inlet_y=REF_Y[sid], liquid_inlet_x=0.0)
        for sid in transfers
    }
    solved = solve_independent_solutes(common, transfers, boundaries)
    _, hydraulics = evaluate_hydraulics_from_resolver(
        resolver=resolver,
        registry=registry,
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=op,
    )
    return registry, resolved, common, transfers, solved, hydraulics


def test_reference_precheck_is_ready_and_dilute_green():
    registry = build_reference_registry()
    report = assess_pre_applicability(registry, reference_case())
    assert report.status == ReadinessStatus.READY
    assert not report.blocks
    assert any(i.code == "DILUTE_GAS_GREEN_ZONE" for i in report.infos)


def test_reference_postcheck_exposes_legacy_data_quality_without_breaking_solver():
    registry, resolved, common, transfers, solved, hydraulics = solved_reference()
    pre = assess_pre_applicability(registry, reference_case())
    report = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=hydraulics,
        packing=registry.get_packing("25mm_metal_pall_ring"),
    )
    assert report.status == ReadinessStatus.READY_WITH_WARNINGS
    assert report.can_run
    assert report.confidence.thermodynamics == ConfidenceLevel.MODERATE
    assert report.confidence.mass_transfer == ConfidenceLevel.MODERATE
    assert report.confidence.hydraulics == ConfidenceLevel.MODERATE
    assert report.confidence.overall == ConfidenceLevel.MODERATE
    assert any(i.code.startswith("UNSPECIFIED_REFERENCE_STATE") for i in report.warnings)
    assert any(i.code == "HYDRAULIC_UNDERLOADED" for i in report.infos)


def test_missing_pair_data_is_blocked_as_insufficient_data():
    registry = build_reference_registry()
    registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.05))
    case = ApplicabilityCase(
        operating=reference_operating(),
        solute_ids=("X",),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"X": 1e-4},
    )
    report = assess_pre_applicability(registry, case)
    assert report.status == ReadinessStatus.INSUFFICIENT_DATA
    assert not report.can_run
    assert {i.severity for i in report.blocks} == {IssueSeverity.BLOCK}
    assert any(i.code == "MISSING_DG_PAIR_X" for i in report.blocks)
    assert any(i.code == "MISSING_DL_PAIR_X" for i in report.blocks)
    assert any(i.code == "MISSING_EQUILIBRIUM_PAIR_X" for i in report.blocks)


def test_reactive_case_is_explicitly_unsupported():
    registry = build_reference_registry()
    report = assess_pre_applicability(registry, reference_case(reactive_system=True))
    assert report.status == ReadinessStatus.UNSUPPORTED_PHYSICS
    assert any(i.code == "REACTIVE_OR_NONPHYSICAL_ABSORPTION_UNSUPPORTED" for i in report.blocks)


def test_nonisothermal_case_is_explicitly_unsupported():
    registry = build_reference_registry()
    report = assess_pre_applicability(registry, reference_case(isothermal=False))
    assert report.status == ReadinessStatus.UNSUPPORTED_PHYSICS
    assert any(i.code == "NONISOTHERMAL_UNSUPPORTED" for i in report.blocks)


def test_yellow_dilute_screening_zone_is_visible_extrapolation():
    registry = build_reference_registry()
    report = assess_pre_applicability(
        registry,
        reference_case(gas_inlet_y={"ACN": 0.012, "VAc": 0.001}),
    )
    assert report.status == ReadinessStatus.OUTSIDE_RECOMMENDED_RANGE
    assert any(i.code == "DILUTE_GAS_YELLOW_ZONE" for i in report.warnings)


def test_red_dilute_screening_zone_is_visible_extrapolation():
    registry = build_reference_registry()
    report = assess_pre_applicability(
        registry,
        reference_case(gas_inlet_y={"ACN": 0.05, "VAc": 0.001}),
    )
    assert report.status == ReadinessStatus.OUTSIDE_RECOMMENDED_RANGE
    assert any(i.code == "DILUTE_GAS_RED_ZONE" for i in report.warnings)


def test_registered_unsupported_equilibrium_model_blocks_case():
    registry = build_reference_registry()
    registry.register_equilibrium_pair(
        EquilibriumPair(solute_id="ACN", solvent_id="water", model="reactive"),
        replace=True,
    )
    report = assess_pre_applicability(registry, reference_case())
    assert report.status == ReadinessStatus.UNSUPPORTED_PHYSICS
    assert any(i.code == "UNSUPPORTED_EQUILIBRIUM_ACN" for i in report.blocks)


def test_low_onda_reynolds_marks_outside_recommended_range():
    registry, resolved, common, transfers, solved, hydraulics = solved_reference()
    pre = assess_pre_applicability(registry, reference_case())
    low_common = replace(common, Re_L=5.0, Re_G=20.0)
    report = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=low_common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=hydraulics,
        packing=registry.get_packing("25mm_metal_pall_ring"),
    )
    assert report.status == ReadinessStatus.OUTSIDE_RECOMMENDED_RANGE
    assert any(i.code == "ONDA_LOW_RE_L" for i in report.warnings)
    assert any(i.code == "ONDA_LOW_RE_G" for i in report.warnings)


def test_flooding_is_hydraulically_infeasible_and_outside_range():
    registry, resolved, common, transfers, solved, hydraulics = solved_reference()
    pre = assess_pre_applicability(registry, reference_case())
    flooded = replace(
        hydraulics,
        flooding=replace(hydraulics.flooding, flooding_percent=105.0, flooding_fraction=1.05),
    )
    report = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=flooded,
        packing=registry.get_packing("25mm_metal_pall_ring"),
    )
    assert report.status == ReadinessStatus.OUTSIDE_RECOMMENDED_RANGE
    assert any(i.code == "HYDRAULIC_FLOODING" for i in report.blocks)


def test_mass_balance_failure_becomes_numerical_failure():
    registry, resolved, common, transfers, solved, hydraulics = solved_reference()
    pre = assess_pre_applicability(registry, reference_case())
    acn = solved.components["ACN"]
    bad_acn = replace(
        acn,
        diagnostics=replace(acn.diagnostics, relative_mass_balance_error=1e-3),
    )
    bad_solved = {"ACN": bad_acn, "VAc": solved.components["VAc"]}
    report = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=bad_solved,
        hydraulics=hydraulics,
        packing=registry.get_packing("25mm_metal_pall_ring"),
    )
    assert report.status == ReadinessStatus.NUMERICAL_FAILURE
    assert not report.can_run
    assert any(i.code == "NUMERICAL_MASS_BALANCE_FAILURE_ACN" for i in report.blocks)


def test_negative_driving_force_is_warning_not_clamped_or_called_numerical_failure():
    registry, resolved, common, transfers, solved, hydraulics = solved_reference()
    pre = assess_pre_applicability(registry, reference_case())
    acn = solved.components["ACN"]
    desorb_acn = replace(
        acn,
        gas_outlet_y=acn.gas_inlet_y * 1.1,
        diagnostics=replace(acn.diagnostics, min_driving_force_y=-1e-5),
    )
    report = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results={"ACN": desorb_acn, "VAc": solved.components["VAc"]},
        hydraulics=hydraulics,
        packing=registry.get_packing("25mm_metal_pall_ring"),
    )
    assert report.status == ReadinessStatus.READY_WITH_WARNINGS
    assert any(i.code == "NEGATIVE_DRIVING_FORCE_ACN" for i in report.warnings)
    assert any(i.code == "NET_DESORPTION_ACN" for i in report.warnings)


def test_explicit_numerical_failure_flag_has_highest_numerical_status():
    registry, resolved, common, transfers, solved, hydraulics = solved_reference()
    pre = assess_pre_applicability(registry, reference_case())
    report = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=hydraulics,
        packing=registry.get_packing("25mm_metal_pall_ring"),
        numerical_failure="Synthetic ODE failure for test.",
    )
    assert report.status == ReadinessStatus.NUMERICAL_FAILURE
    assert any(i.code == "NUMERICAL_SOLVER_FAILURE" for i in report.blocks)


def test_more_than_four_components_is_unsupported_even_before_pair_checks():
    registry = build_reference_registry()
    case = reference_case(solute_ids=("ACN", "VAc", "A", "B", "C"))
    report = assess_pre_applicability(registry, case)
    assert report.status in {ReadinessStatus.UNSUPPORTED_PHYSICS, ReadinessStatus.INSUFFICIENT_DATA}
    assert any(i.code == "UNSUPPORTED_COMPONENT_COUNT" for i in report.blocks)
