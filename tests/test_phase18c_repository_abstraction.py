import math
from pathlib import Path

import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    GenericAbsorberCase,
    RepositoryKind,
    build_phase14_registry,
    build_phase18b_database,
    build_python_registry_repository,
    build_sqlite_v18b_repository,
    run_generic_absorber_case,
    run_phase18c_repository_parity,
)


def _repos(tmp_path):
    py_repo = build_python_registry_repository()
    db_path = tmp_path / "absorber_v18b.db"
    build_phase18b_database(db_path)
    db_repo = build_sqlite_v18b_repository(db_path)
    return py_repo, db_repo


def _vdc_water_case():
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


def test_phase18c_repository_descriptors_are_explicit(tmp_path):
    py_repo, db_repo = _repos(tmp_path)
    assert py_repo.descriptor.kind == RepositoryKind.PYTHON_REGISTRY
    assert db_repo.descriptor.kind == RepositoryKind.SQLITE
    assert py_repo.descriptor.read_only
    assert db_repo.descriptor.read_only
    assert db_repo.descriptor.schema_version is not None


def test_phase18c_simulator_accepts_repository_backend(tmp_path):
    py_repo, db_repo = _repos(tmp_path)
    case = _vdc_water_case()
    py = run_generic_absorber_case(case, repository=py_repo)
    db = run_generic_absorber_case(case, repository=db_repo)
    assert py.data_source.backend_id == "python_registry_phase17"
    assert db.data_source.backend_id == "sqlite_v18b"
    assert math.isclose(py.outlet_report.total_y, db.outlet_report.total_y, rel_tol=1e-12, abs_tol=1e-12)


def test_phase18c_registry_and_repository_are_mutually_exclusive(tmp_path):
    py_repo, _ = _repos(tmp_path)
    with pytest.raises(ValueError, match="either registry= or repository="):
        run_generic_absorber_case(
            _vdc_water_case(), registry=build_phase14_registry(), repository=py_repo
        )


def test_phase18c_full_repository_parity_suite(tmp_path):
    py_repo, db_repo = _repos(tmp_path)
    report = run_phase18c_repository_parity(py_repo, db_repo)
    assert report.pass_gate
    assert report.inventory_match
    assert report.reference_id_match
    assert all(report.registry_dictionary_parity.values())
    assert len(report.scenarios) == 5
    assert report.metrics_checked >= 90
    assert all(row.pass_gate for row in report.scenarios)
    assert max(row.max_absolute_error for row in report.scenarios) <= 1e-12


def test_phase18c_default_path_remains_backward_compatible():
    result = run_generic_absorber_case(_vdc_water_case())
    assert result.data_source.kind == RepositoryKind.DEFAULT_REGISTRY
    assert result.solver_results.components["VDC"].removal_fraction > 0.0
