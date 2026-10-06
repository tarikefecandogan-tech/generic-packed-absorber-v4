"""Phase 7 generic units and composition regression tests."""
from __future__ import annotations

import pytest

from generic_absorber_v4 import (
    CompositionFractionBasis,
    ConcentrationTarget,
    GasConcentrationBasis,
    SoluteSpec,
    UnitConversionError,
    actual_m3_h_to_normal_m3_h,
    build_reference_registry,
    canonical_y_from_component_concentrations,
    canonical_y_from_total_and_fractions,
    component_concentration_to_y,
    component_y_to_concentration,
    gas_stream_balance,
    liquid_mg_L_to_x_dilute,
    liquid_x_to_mg_L_dilute,
    normal_m3_h_to_actual_m3_h,
    report_gas_stream,
    DEFAULT_NORMAL_CONDITIONS,
)

REG = build_reference_registry()
SOLUTES = REG.solutes
ACN = SOLUTES["ACN"]
VAC = SOLUTES["VAc"]

Y_ACN_IN = 0.001964284929935824
Y_VAC_IN = 9.112428087594802e-05
Y_ACN_OUT = 3.991282910574221e-06
Y_VAC_OUT = 2.5299699106660017e-05


def test_locked_normal_molar_concentration():
    assert DEFAULT_NORMAL_CONDITIONS.molar_concentration_mol_m3 == pytest.approx(
        44.61503340629259, rel=1e-14
    )


def test_reference_component_mgvoc_to_y_matches_v3_feed():
    assert component_concentration_to_y(4650.0, ACN, "mgVOC/Nm³") == pytest.approx(Y_ACN_IN, rel=1e-14)
    assert component_concentration_to_y(350.0, VAC, "mgVOC/Nm³") == pytest.approx(Y_VAC_IN, rel=1e-14)


def test_reference_component_roundtrip_for_all_reporting_bases():
    for solute, y in [(ACN, Y_ACN_IN), (VAC, Y_VAC_IN)]:
        for basis in GasConcentrationBasis:
            value = component_y_to_concentration(y, solute, basis)
            back = component_concentration_to_y(value, solute, basis)
            assert back == pytest.approx(y, rel=1e-14, abs=1e-16)


def test_reference_total_mixture_from_mass_fractions_matches_locked_v3_input():
    mix = canonical_y_from_total_and_fractions(
        5000.0,
        GasConcentrationBasis.MG_VOC_NM3,
        {"ACN": 0.93, "VAc": 0.07},
        CompositionFractionBasis.VOC_MASS,
        SOLUTES,
    )
    assert mix.canonical_y["ACN"] == pytest.approx(Y_ACN_IN, rel=1e-14)
    assert mix.canonical_y["VAc"] == pytest.approx(Y_VAC_IN, rel=1e-14)
    assert mix.report.total_mgVOC_Nm3 == pytest.approx(5000.0, rel=1e-14)
    assert mix.report.total_mgC_Nm3 == pytest.approx(3353.1344673788503, rel=1e-13)
    assert mix.report.total_ppmv == pytest.approx(2055.409210811772, rel=1e-13)


def test_component_by_component_input_reconstructs_same_reference_feed():
    y = canonical_y_from_component_concentrations(
        {"ACN": 4650.0, "VAc": 350.0},
        GasConcentrationBasis.MG_VOC_NM3,
        SOLUTES,
    )
    assert y["ACN"] == pytest.approx(Y_ACN_IN, rel=1e-14)
    assert y["VAc"] == pytest.approx(Y_VAC_IN, rel=1e-14)


def test_reference_outlet_reporting_matches_locked_v3_values():
    out = report_gas_stream({"ACN": Y_ACN_OUT, "VAc": Y_VAC_OUT}, SOLUTES)
    assert out.total_mgVOC_Nm3 == pytest.approx(106.62228136662561, rel=1e-12)
    assert out.total_mgC_Nm3 == pytest.approx(60.645957347814814, rel=1e-12)
    assert out.total_ppmv == pytest.approx(29.29098201723424, rel=1e-12)
    assert out.components["ACN"].mgVOC_Nm3 == pytest.approx(9.448458953852734, rel=1e-12)
    assert out.components["VAc"].mgVOC_Nm3 == pytest.approx(97.17382241277288, rel=1e-12)


def test_overall_removal_depends_on_reporting_basis():
    bal = gas_stream_balance(
        {"ACN": Y_ACN_IN, "VAc": Y_VAC_IN},
        {"ACN": Y_ACN_OUT, "VAc": Y_VAC_OUT},
        SOLUTES,
    )
    assert bal.overall_removal_molar == pytest.approx(0.9857493184991294, rel=1e-12)
    assert bal.overall_removal_voc_mass == pytest.approx(0.9786755437266749, rel=1e-12)
    assert bal.overall_removal_carbon_mass == pytest.approx(0.9819136518568485, rel=1e-12)
    assert bal.overall_removal_molar != pytest.approx(bal.overall_removal_voc_mass)


def test_captured_mass_uses_solved_component_outlets():
    bal = gas_stream_balance(
        {"ACN": Y_ACN_IN, "VAc": Y_VAC_IN},
        {"ACN": Y_ACN_OUT, "VAc": Y_VAC_OUT},
        SOLUTES,
        gas_molar_flow_mol_s=1.34798753171,
    )
    assert bal.captured_kg_h_by_component["ACN"] == pytest.approx(0.5047504956062636, rel=1e-11)
    assert bal.captured_kg_h_by_component["VAc"] == pytest.approx(0.02749977827217954, rel=1e-11)
    assert bal.total_captured_kg_h == pytest.approx(0.5322502738784431, rel=1e-11)


def test_mass_mole_and_carbon_fraction_bases_are_not_interchangeable():
    mass_mix = canonical_y_from_total_and_fractions(
        5000.0, "mgVOC/Nm³", {"ACN": 0.93, "VAc": 0.07}, "voc_mass", SOLUTES
    )
    mole_mix = canonical_y_from_total_and_fractions(
        5000.0, "mgVOC/Nm³", {"ACN": 0.93, "VAc": 0.07}, "mole", SOLUTES
    )
    carbon_mix = canonical_y_from_total_and_fractions(
        5000.0, "mgVOC/Nm³", {"ACN": 0.93, "VAc": 0.07}, "carbon_mass", SOLUTES
    )
    assert mass_mix.canonical_y["ACN"] != pytest.approx(mole_mix.canonical_y["ACN"])
    assert carbon_mix.canonical_y["VAc"] != pytest.approx(mole_mix.canonical_y["VAc"])
    assert mass_mix.report.total_mgVOC_Nm3 == pytest.approx(5000.0)
    assert mole_mix.report.total_mgVOC_Nm3 == pytest.approx(5000.0)
    assert carbon_mix.report.total_mgVOC_Nm3 == pytest.approx(5000.0)


def test_fractions_are_not_silently_normalized():
    with pytest.raises(UnitConversionError):
        canonical_y_from_total_and_fractions(
            5000.0, "mgVOC/Nm³", {"ACN": 93.0, "VAc": 7.0}, "voc_mass", SOLUTES
        )
    mix = canonical_y_from_total_and_fractions(
        5000.0,
        "mgVOC/Nm³",
        {"ACN": 93.0, "VAc": 7.0},
        "voc_mass",
        SOLUTES,
        normalize_fractions=True,
    )
    assert mix.normalized_fractions["ACN"] == pytest.approx(0.93)


def test_liquid_mg_L_and_x_dilute_roundtrip():
    rho_water = 997.8003203174456
    x = liquid_mg_L_to_x_dilute(
        100.0,
        solute_MW_kg_mol=ACN.MW_kg_mol,
        solvent_MW_kg_mol=18.015e-3,
        solvent_density_kg_m3=rho_water,
    )
    back = liquid_x_to_mg_L_dilute(
        x,
        solute_MW_kg_mol=ACN.MW_kg_mol,
        solvent_MW_kg_mol=18.015e-3,
        solvent_density_kg_m3=rho_water,
    )
    assert back == pytest.approx(100.0, rel=1e-14)


def test_actual_normal_flow_conversion_roundtrip():
    qn = actual_m3_h_to_normal_m3_h(
        117.53, temperature_K=295.15, pressure_Pa=101325.0
    )
    assert qn == pytest.approx(108.76950533626969, rel=1e-13)
    qa = normal_m3_h_to_actual_m3_h(
        qn, temperature_K=295.15, pressure_Pa=101325.0
    )
    assert qa == pytest.approx(117.53, rel=1e-14)


def test_zero_carbon_solute_reports_zero_mgc_and_rejects_positive_mgc_input():
    x = SoluteSpec(id="X", name="Zero-carbon solute", MW_kg_mol=0.05, carbon_atoms=0)
    assert component_y_to_concentration(1e-4, x, "mgC/Nm³") == 0.0
    with pytest.raises(UnitConversionError):
        component_concentration_to_y(10.0, x, "mgC/Nm³")


def test_target_keeps_basis_and_scope_explicit():
    target = ConcentrationTarget(20.0, GasConcentrationBasis.MG_VOC_NM3, scope="total")
    assert target.value == 20.0
    assert target.scope == "total"
    with pytest.raises(UnitConversionError):
        ConcentrationTarget(20.0, GasConcentrationBasis.PPMV, scope="component")
