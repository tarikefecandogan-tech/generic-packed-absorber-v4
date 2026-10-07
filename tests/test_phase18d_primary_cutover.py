from pathlib import Path

import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    GenericAbsorberCase,
    PrimaryRepositoryUnavailableError,
    RepositoryKind,
    build_phase18b_database,
    build_python_registry_repository,
    run_generic_absorber_case,
    run_phase18d_cutover_gate,
    select_primary_data_repository,
)


def _case():
    return GenericAbsorberCase(
        operating=AbsorberOperatingPoint(
            diameter_m=0.5,
            packed_height_m=1.4,
            gas_actual_m3_h=117.53,
            liquid_mass_kg_h=2500.0,
            temperature_K=295.15,
            pressure_Pa=101325.0,
        ),
        solute_ids=("VDC",),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"VDC": 1000e-6},
        liquid_inlet_x={"VDC": 0.0},
    )


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "absorber_database_v18b.db"
    build_phase18b_database(path)
    return path


def test_phase18d_valid_database_selects_sqlite_primary(tmp_path):
    repo, decision = select_primary_data_repository(_db(tmp_path))
    assert decision.pass_gate
    assert not decision.fallback_used
    assert decision.active_kind == RepositoryKind.SQLITE
    assert repo.descriptor.kind == RepositoryKind.SQLITE
    assert decision.sqlite_integrity.lower() == "ok"
    assert decision.foreign_key_violations == 0


def test_phase18d_primary_result_matches_python_reference(tmp_path):
    repo, decision = select_primary_data_repository(_db(tmp_path))
    assert not decision.fallback_used
    py_repo = build_python_registry_repository()
    case = _case()
    primary = run_generic_absorber_case(case, repository=repo)
    python = run_generic_absorber_case(case, repository=py_repo)
    assert primary.data_source.kind == RepositoryKind.SQLITE
    assert primary.outlet_report.total_y == pytest.approx(python.outlet_report.total_y, rel=1e-12, abs=1e-12)
    assert primary.hydraulics.flooding.flooding_percent == pytest.approx(
        python.hydraulics.flooding.flooding_percent, rel=1e-12, abs=1e-12
    )


def test_phase18d_missing_database_uses_explicit_controlled_fallback(tmp_path):
    missing = tmp_path / "missing.db"
    repo, decision = select_primary_data_repository(missing, allow_python_fallback=True)
    assert decision.fallback_used
    assert decision.active_kind == RepositoryKind.CONTROLLED_FALLBACK
    assert repo.descriptor.kind == RepositoryKind.CONTROLLED_FALLBACK
    assert "FileNotFoundError" in decision.fallback_reason
    result = run_generic_absorber_case(_case(), repository=repo)
    assert result.data_source.kind == RepositoryKind.CONTROLLED_FALLBACK


def test_phase18d_missing_database_strict_mode_fails(tmp_path):
    with pytest.raises(PrimaryRepositoryUnavailableError):
        select_primary_data_repository(
            tmp_path / "missing.db", allow_python_fallback=False
        )


def test_phase18d_corrupt_database_never_masquerades_as_sqlite(tmp_path):
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"this is not a sqlite database")
    repo, decision = select_primary_data_repository(corrupt, allow_python_fallback=True)
    assert decision.fallback_used
    assert repo.descriptor.kind == RepositoryKind.CONTROLLED_FALLBACK
    assert decision.active_kind != RepositoryKind.SQLITE
    assert decision.fallback_reason


def test_phase18d_full_cutover_gate(tmp_path):
    db_path = _db(tmp_path)
    report = run_phase18d_cutover_gate(
        db_path,
        missing_database_probe=tmp_path / "definitely_missing.db",
    )
    assert report.pass_gate
    assert report.default_is_sqlite
    assert report.parity.pass_gate
    assert report.parity.metrics_checked >= 90
    assert report.fallback_test_passed
    assert report.strict_failure_test_passed
