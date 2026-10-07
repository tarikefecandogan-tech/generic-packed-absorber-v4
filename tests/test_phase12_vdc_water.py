import math

from generic_absorber_v4 import (
    ConfidenceClass,
    PHASE12_VDC_WATER_CASE_ID,
    PropertyResolver,
    ReadinessStatus,
    ResolutionTier,
    VDC_FULLER_DIFFUSION_VOLUME,
    VDC_LEBAS_BOILING_MOLAR_VOLUME_CM3_MOL,
    VDC_WATER_H_REF_PA_M3_MOL,
    build_vdc_water_registry,
    run_full_v3_parity,
    run_vdc_water_case,
)


def test_vdc_identity_group_contribution_inputs_are_locked():
    assert math.isclose(VDC_FULLER_DIFFUSION_VOLUME, 75.96, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(VDC_LEBAS_BOILING_MOLAR_VOLUME_CM3_MOL, 86.2, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(VDC_WATER_H_REF_PA_M3_MOL, 2571.624262476425, rel_tol=1e-12)


def test_vdc_water_registry_extends_reference_without_transport_pair_fabrication():
    reg = build_vdc_water_registry()
    assert reg.reference_id == PHASE12_VDC_WATER_CASE_ID
    assert reg.get_solute("VDC").cas_number == "75-35-4"
    assert reg.find_gas_transport_pair("VDC", "air") is None
    assert reg.find_liquid_transport_pair("VDC", "water") is None
    assert reg.find_equilibrium_pair("VDC", "water") is not None


def test_vdc_transport_resolves_through_visible_confidence_c_estimators():
    reg = build_vdc_water_registry()
    resolver = PropertyResolver(reg)
    rp = resolver.resolve_component_properties("VDC", "air", "water", 295.15, 101325.0)
    assert rp.gas_diffusivity.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert rp.liquid_diffusivity.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert rp.gas_diffusivity.confidence == ConfidenceClass.C
    assert rp.liquid_diffusivity.confidence == ConfidenceClass.C
    assert rp.equilibrium.active_property.tier == ResolutionTier.DATABASE
    assert rp.equilibrium.active_property.confidence == ConfidenceClass.B
    assert math.isclose(rp.gas_diffusivity.value, 9.198849015533944e-06, rel_tol=1e-12)
    assert math.isclose(rp.liquid_diffusivity.value, 1.0798729298105578e-09, rel_tol=1e-12)
    assert math.isclose(rp.equilibrium.active_property.value, 2266.8696513723917, rel_tol=1e-12)


def test_applicability_recognizes_estimatable_pairs_instead_of_blocking():
    report = run_vdc_water_case()
    assert report.pre_applicability.status == ReadinessStatus.READY_WITH_WARNINGS
    assert not report.pre_applicability.blocks
    warning_codes = {i.code for i in report.pre_applicability.warnings}
    assert "DG_CORRELATION_FALLBACK_VDC" in warning_codes
    assert "DL_CORRELATION_FALLBACK_VDC" in warning_codes


def test_vdc_water_full_chain_is_numerically_healthy_and_screening_confidence():
    report = run_vdc_water_case()
    assert report.pass_gate
    assert report.post_applicability.status == ReadinessStatus.READY_WITH_WARNINGS
    assert report.post_applicability.confidence.overall.value == "SCREENING"
    assert report.solver.diagnostics.relative_mass_balance_error < 1e-12
    assert abs(report.solver.diagnostics.boundary_error_x) < 1e-12
    assert math.isclose(report.solver.gas_outlet_y, 0.0009779697253859427, rel_tol=1e-10)
    assert math.isclose(report.solver.removal_fraction, 0.02203027461405733, rel_tol=1e-10)
    assert report.transfer.absorption_factor < 1.0


def test_phase12_does_not_move_v3_parity_baseline():
    parity = run_full_v3_parity()
    assert parity.passed
    assert parity.passed_count == parity.total_count == 82
