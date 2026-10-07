import math

from generic_absorber_v4 import (
    ACN_SOLVENT_ID,
    ConfidenceClass,
    PHASE13_VDC_ACN_CASE_ID,
    PropertyResolver,
    ResolutionTier,
    VDC_ACN_LINEAR_M_22C,
    build_vdc_acn_registry,
    run_full_v3_parity,
    run_vdc_acn_case,
)


def test_phase13_registers_real_acrylonitrile_solvent_without_fabricating_dl_pair():
    reg = build_vdc_acn_registry()
    assert reg.reference_id == PHASE13_VDC_ACN_CASE_ID
    acn = reg.get_solvent(ACN_SOLVENT_ID)
    assert math.isclose(acn.MW_kg_mol, 53.06e-3, rel_tol=0, abs_tol=1e-15)
    assert math.isclose(acn.rho_kg_m3, 803.88, rel_tol=0, abs_tol=1e-12)
    assert reg.find_liquid_transport_pair("VDC", ACN_SOLVENT_ID) is None
    assert reg.find_equilibrium_pair("VDC", ACN_SOLVENT_ID) is not None


def test_phase13_equilibrium_is_explicit_confidence_d_screening_surrogate():
    reg = build_vdc_acn_registry()
    resolver = PropertyResolver(reg)
    rp = resolver.resolve_component_properties("VDC", "air", ACN_SOLVENT_ID, 295.15, 101325.0)
    assert rp.equilibrium.active_property.tier == ResolutionTier.DATABASE
    assert rp.equilibrium.active_property.confidence == ConfidenceClass.D
    assert math.isclose(rp.equilibrium.active_property.value, VDC_ACN_LINEAR_M_22C, rel_tol=1e-14)
    assert rp.gas_diffusivity.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert rp.liquid_diffusivity.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert rp.gas_diffusivity.confidence == ConfidenceClass.C
    assert rp.liquid_diffusivity.confidence == ConfidenceClass.C


def test_phase13_full_chain_is_numerically_healthy_but_outside_recommended_domain():
    report = run_vdc_acn_case()
    assert report.pass_gate
    assert not report.pre_applicability.blocks
    assert not report.post_applicability.blocks
    assert report.post_applicability.confidence.overall.value == "SCREENING"
    assert report.solver.diagnostics.relative_mass_balance_error < 1e-10
    assert abs(report.solver.diagnostics.boundary_error_x) < 1e-10
    assert report.transfer.absorption_factor > 1.0
    assert report.solver.removal_fraction > report.water_removal_fraction
    codes = {i.code for i in report.pre_applicability.warnings}
    assert "SOLVENT_EVAPORATION_NOT_MODELLED" in codes


def test_phase13_acn_solvent_is_materially_volatile_at_fixture_conditions():
    report = run_vdc_acn_case()
    assert report.acn_vapor_pressure_Pa > 1.0e4
    assert report.acn_vapor_pressure_Pa / report.operating.pressure_Pa > 0.10


def test_phase13_does_not_move_locked_v3_parity():
    parity = run_full_v3_parity()
    assert parity.passed
    assert parity.passed_count == parity.total_count == 82
