import math

from generic_absorber_v4 import (
    REFERENCE_ID,
    REFERENCE_SOURCE_SHA256,
    V3_REFERENCE_METRICS,
    reference_chain_health,
    run_full_v3_parity,
)


def test_full_v3_parity_gate_passes_every_locked_metric():
    report = run_full_v3_parity()
    assert report.reference_id == REFERENCE_ID
    assert report.passed
    assert report.failed_count == 0
    assert report.passed_count == report.total_count
    assert report.total_count == len(V3_REFERENCE_METRICS)


def test_all_reference_metric_names_are_unique():
    names = [m.name for m in V3_REFERENCE_METRICS]
    assert len(names) == len(set(names))


def test_every_defined_parity_section_passes():
    report = run_full_v3_parity()
    expected_sections = {
        "Units & Feed",
        "Bulk & Common Onda",
        "ACN Mass Transfer",
        "VAc Mass Transfer",
        "Counter-Current & Outlet",
        "Hydraulics",
    }
    assert set(report.sections) == expected_sections
    assert all(report.section_passed(section) for section in expected_sections)


def test_numeric_parity_errors_are_within_declared_tolerances():
    report = run_full_v3_parity()
    numeric = [m for m in report.metrics if m.rtol is not None]
    assert numeric
    for metric in numeric:
        assert metric.passed
        assert metric.absolute_error is not None
        assert metric.relative_error is not None
        allowed = metric.atol + metric.rtol * abs(float(metric.expected))
        assert metric.absolute_error <= allowed


def test_exact_non_numeric_reference_checks_pass():
    report = run_full_v3_parity()
    exact = [m for m in report.metrics if m.rtol is None]
    assert {m.name for m in exact} == {
        "packing_factor_basis",
        "packing_factor_estimated",
        "hydraulic_regime",
    }
    assert all(m.passed for m in exact)


def test_primary_reference_outputs_are_present_and_passed():
    report = run_full_v3_parity()
    by_name = {m.name: m for m in report.metrics}
    primary = {
        "outlet_total_mgVOC_Nm3": 106.62228136662561,
        "overall_VOC_mass_removal_fraction": 0.9786755437266749,
        "ACN_absorption_factor": 50.49051331523841,
        "VAc_absorption_factor": 1.1779113136890638,
        "ACN_HTU_OG_m": 0.2220933460636276,
        "VAc_HTU_OG_m": 0.6379884514458746,
        "wet_dP_Pa_m": 5.683288286702279,
        "U_flood_m_s": 2.3208029666997687,
        "flooding_percent": 7.164371117329295,
    }
    for name, expected in primary.items():
        assert name in by_name
        assert by_name[name].passed
        assert math.isclose(float(by_name[name].expected), expected, rel_tol=1e-15, abs_tol=1e-15)


def test_integrated_chain_health_remains_phase8_valid_and_numerically_closed():
    health = reference_chain_health()
    assert health["phase8_pre_status"] == "READY"
    assert health["phase8_final_status"] == "READY_WITH_WARNINGS"
    assert health["phase8_overall_confidence"] == "MODERATE"
    assert health["ACN_mass_balance_relative_error"] < 1e-10
    assert health["VAc_mass_balance_relative_error"] < 1e-10


def test_reference_source_hash_is_frozen_sha256():
    assert REFERENCE_SOURCE_SHA256 == "90ddffaa5517d2851d9bec7e3621653fc01959e236a2b4bccb34e276219fd967"
    assert len(REFERENCE_SOURCE_SHA256) == 64


def test_required_height_is_not_silently_claimed_as_phase9_parity_scope():
    names = {m.name.lower() for m in V3_REFERENCE_METRICS}
    assert all("required_height" not in name for name in names)
