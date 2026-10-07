from __future__ import annotations

import pytest

from generic_absorber_v4 import (
    CorrelationInputError,
    MissingPropertyError,
    PropertyResolver,
    ResolutionTier,
    SoluteSpec,
    build_reference_registry,
    build_phase11_estimation_registry,
    fuller_gas_diffusivity_m2_s,
    run_phase11_estimation_gate,
    wilke_chang_liquid_diffusivity_m2_s,
)


def test_fuller_formula_known_fixture():
    result = fuller_gas_diffusivity_m2_s(
        T_K=298.15,
        P_Pa=101325.0,
        solute_MW_kg_mol=0.078,
        carrier_MW_kg_mol=0.029,
        solute_diffusion_volume=65.0,
        carrier_diffusion_volume=20.1,
    )
    assert result.value_m2_s == pytest.approx(1.0243079686862877e-05, rel=1e-12)


def test_wilke_chang_formula_known_fixture():
    result = wilke_chang_liquid_diffusivity_m2_s(
        T_K=298.15,
        solvent_mu_Pa_s=0.0008904389816146542,
        solvent_MW_kg_mol=18.015e-3,
        solvent_association_factor=2.6,
        solute_boiling_molar_volume_cm3_mol=100.0,
    )
    assert result.value_m2_s == pytest.approx(1.0699566353116642e-09, rel=1e-12)


def test_default_resolver_uses_builtin_estimators_only_when_pair_missing():
    registry = build_phase11_estimation_registry()
    resolver = PropertyResolver(registry)
    dg = resolver.resolve_gas_diffusivity("EST_X", "est_carrier", 298.15, 101325.0)
    dl = resolver.resolve_liquid_diffusivity("EST_X", "est_solvent", 298.15)
    assert dg.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert dl.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert dg.confidence.value == "C"
    assert dl.confidence.value == "C"
    assert dg.estimated is True and dl.estimated is True
    assert "Fuller" in dg.method
    assert "Wilke" in dl.method


def test_database_still_beats_builtin_estimators():
    resolver = PropertyResolver(build_reference_registry())
    dg = resolver.resolve_gas_diffusivity("ACN", "air", 298.15, 101325.0)
    dl = resolver.resolve_liquid_diffusivity("ACN", "water", 298.15)
    assert dg.tier == ResolutionTier.DATABASE
    assert dl.tier == ResolutionTier.DATABASE
    assert dg.value == 1.0e-5
    assert dl.value == 1.0e-9


def test_builtin_estimators_can_be_disabled():
    registry = build_phase11_estimation_registry()
    resolver = PropertyResolver(registry, enable_builtin_estimators=False)
    with pytest.raises(MissingPropertyError):
        resolver.resolve_gas_diffusivity("EST_X", "est_carrier", 298.15, 101325.0)
    with pytest.raises(MissingPropertyError):
        resolver.resolve_liquid_diffusivity("EST_X", "est_solvent", 298.15)


def test_missing_required_estimator_inputs_block_instead_of_guessing():
    registry = build_reference_registry()
    registry.register_solute(SoluteSpec(id="NO_DATA", name="No Data", MW_kg_mol=0.050))
    resolver = PropertyResolver(registry)
    with pytest.raises(MissingPropertyError):
        resolver.resolve_gas_diffusivity("NO_DATA", "air", 298.15, 101325.0)
    with pytest.raises(MissingPropertyError):
        resolver.resolve_liquid_diffusivity("NO_DATA", "water", 298.15)


def test_correlation_functions_reject_nonphysical_inputs():
    with pytest.raises(CorrelationInputError):
        fuller_gas_diffusivity_m2_s(
            T_K=298.15, P_Pa=0.0, solute_MW_kg_mol=0.078,
            carrier_MW_kg_mol=0.029, solute_diffusion_volume=65.0,
            carrier_diffusion_volume=20.1,
        )
    with pytest.raises(CorrelationInputError):
        wilke_chang_liquid_diffusivity_m2_s(
            T_K=298.15, solvent_mu_Pa_s=0.0, solvent_MW_kg_mol=18.015e-3,
            solvent_association_factor=2.6, solute_boiling_molar_volume_cm3_mol=100.0,
        )


def test_phase11_gate_passes():
    report = run_phase11_estimation_gate()
    assert report.pass_gate
    assert report.estimated_DG_m2_s > 0
    assert report.estimated_DL_m2_s > 0
