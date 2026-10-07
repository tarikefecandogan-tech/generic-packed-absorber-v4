from pathlib import Path
import sqlite3

import pytest

from generic_absorber_v4 import (
    CoverageStatus,
    DatabaseExplorer,
    PropertyResolver,
    ResolutionTier,
    SQLiteAbsorberRepositoryV18B,
    build_sqlite_v18h_repository,
    default_sqlite_database_path,
    select_primary_data_repository,
    validate_chemical_import_package,
)
from generic_absorber_v4.verified_batch_v18h import (
    PHASE18H_BATCH_ID,
    PHASE18H_DATA_SNAPSHOT_ID,
    PHASE18H_DATABASE_FILENAME,
    PHASE18H_VOCS,
    phase18h_verified_batch_package,
    run_phase18h_verified_batch_gate,
)

ROOT = Path(__file__).resolve().parents[1]
DB18G = ROOT / "database" / "absorber_database_v18g.db"
DB18H = ROOT / "database" / "absorber_database_v18h.db"


def test_phase18h_batch_contract_is_valid_against_phase18g_database():
    repo = SQLiteAbsorberRepositoryV18B(DB18G)
    report = validate_chemical_import_package(phase18h_verified_batch_package(), repo)
    assert report.pass_validation
    assert report.package_id == PHASE18H_BATCH_ID
    assert report.planned_delta.solutes == 5
    assert report.planned_delta.equilibrium_pairs == 5
    assert report.planned_delta.gas_transport_pairs == 0
    assert report.planned_delta.liquid_transport_pairs == 0


def test_phase18h_database_inventory_and_metadata():
    repo = SQLiteAbsorberRepositoryV18B(DB18H)
    inv = repo.inventory()
    md = repo.metadata()
    assert inv.solutes == 13
    assert inv.equilibrium_pairs == 14
    assert inv.gas_transport_pairs == 2
    assert inv.liquid_transport_pairs == 2
    assert md["data_snapshot_id"] == PHASE18H_DATA_SNAPSHOT_ID
    assert md["verified_expansion_batch"] == PHASE18H_BATCH_ID
    assert md["last_import_package_id"] == PHASE18H_BATCH_ID
    assert md["parent_data_snapshot"].startswith("PHASE18G_")
    assert repo.integrity_check().lower() == "ok"
    assert repo.foreign_key_violations() == ()


@pytest.mark.parametrize("record", PHASE18H_VOCS, ids=lambda r: r.solute_id)
def test_phase18h_identity_and_henry_values_are_exact(record):
    repo = SQLiteAbsorberRepositoryV18B(DB18H)
    reg = repo.load_registry()
    sol = reg.get_solute(record.solute_id)
    eq = reg.find_equilibrium_pair(record.solute_id, "water")
    assert sol.name == record.name
    assert sol.formula == record.formula
    assert sol.cas_number == record.cas_number
    assert sol.MW_kg_mol == pytest.approx(record.MW_kg_mol, rel=0, abs=1e-15)
    assert sol.fuller_diffusion_volume == pytest.approx(record.fuller_diffusion_volume)
    assert sol.boiling_molar_volume_cm3_mol == pytest.approx(record.boiling_molar_volume_cm3_mol)
    assert eq is not None and eq.model == "henry_pc"
    assert eq.H_ref_Pa_m3_mol == pytest.approx(record.H_ref_Pa_m3_mol, rel=1e-14)
    assert eq.T_ref_K == pytest.approx(298.15)
    assert eq.temperature_coefficient_K == pytest.approx(record.henry_temperature_coefficient_K)
    assert eq.provenance is not None
    assert eq.provenance.confidence.value == "B"


@pytest.mark.parametrize("record", PHASE18H_VOCS, ids=lambda r: r.solute_id)
def test_phase18h_transport_remains_visible_correlation_estimate(record):
    repo = SQLiteAbsorberRepositoryV18B(DB18H)
    reg = repo.load_registry()
    resolver = PropertyResolver(reg)
    assert reg.find_gas_transport_pair(record.solute_id, "air") is None
    assert reg.find_liquid_transport_pair(record.solute_id, "water") is None
    dg = resolver.resolve_gas_diffusivity(record.solute_id, "air", 298.15, 101325.0)
    dl = resolver.resolve_liquid_diffusivity(record.solute_id, "water", 298.15)
    assert dg.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert dl.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert dg.confidence.value == "C"
    assert dl.confidence.value == "C"


@pytest.mark.parametrize("record", PHASE18H_VOCS, ids=lambda r: r.solute_id)
def test_phase18h_coverage_is_estimated_for_water_and_missing_for_acn(record):
    explorer = DatabaseExplorer.from_path(DB18H)
    water = explorer.coverage_cell(record.solute_id, "water")
    acn = explorer.coverage_cell(record.solute_id, "acrylonitrile")
    assert water.overall_status == CoverageStatus.ESTIMATED
    assert water.equilibrium_confidence == "B"
    assert acn.overall_status == CoverageStatus.MISSING


def test_phase18h_field_level_provenance_splits_identity_from_transport_inputs():
    ids = tuple(r.solute_id for r in PHASE18H_VOCS)
    with sqlite3.connect(DB18H) as con:
        for sid in ids:
            rows = con.execute(
                "SELECT p.confidence,u.property_scope,u.property_name "
                "FROM provenance_usage u JOIN provenance p ON p.provenance_id=u.provenance_id "
                "WHERE u.entity_type='solute' AND u.entity_key=?",
                (sid,),
            ).fetchall()
            got = {(c, s, n) for c, s, n in rows}
            assert ("B", "identity", "MW_formula_CAS_carbon_count") in got
            assert ("C", "correlation_input", "Fuller diffusion volume") in got
            assert ("C", "correlation_input", "Le Bas boiling molar volume") in got
            assert all(scope != "identity_transport_inputs" for _, scope, _ in got)


def test_phase18h_repository_is_product_default_primary():
    assert default_sqlite_database_path().name == PHASE18H_DATABASE_FILENAME
    repo, decision = select_primary_data_repository(allow_python_fallback=False)
    assert not decision.fallback_used
    assert repo.descriptor.backend_id == "sqlite_v18h"
    assert repo.descriptor.label == "SQLite Engineering Database v18H"
    explicit = build_sqlite_v18h_repository(DB18H)
    assert explicit.descriptor.backend_id == "sqlite_v18h"


def test_phase18h_full_gate():
    report = run_phase18h_verified_batch_gate(DB18H)
    assert report.pass_gate
    assert report.phase18g_preserved
    assert len(report.fixture_results) == 5
    assert all(r.mass_balance_error < 1e-8 for r in report.fixture_results)
