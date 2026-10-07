import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from generic_absorber_v4 import (
    CoverageStatus,
    DatabaseExplorer,
    SQLiteAbsorberRepositoryV18B,
)
from generic_absorber_v4.chemical_import import (
    ChemicalImportValidationError,
    PHASE18F_IMPORT_CONTRACT_VERSION,
    chemical_import_template,
    import_chemical_package,
    phase18f_synthetic_package,
    run_phase18f_expansion_gate,
    validate_chemical_import_package,
)

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "absorber_database_v18b.db"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_db(tmp_path: Path) -> Path:
    out = tmp_path / "test.db"
    shutil.copy2(DB, out)
    return out


def test_template_is_documentation_not_accidentally_valid():
    repo = SQLiteAbsorberRepositoryV18B(DB)
    report = validate_chemical_import_package(chemical_import_template(), repo)
    assert not report.pass_validation
    codes = {x.code for x in report.blocking_issues}
    assert "SOLUTE_MW_REQUIRED" in codes
    assert "CARBON_ATOMS_REQUIRED" in codes


def test_synthetic_package_dry_run_is_valid_and_read_only():
    repo = SQLiteAbsorberRepositoryV18B(DB)
    before = _hash(DB)
    report = import_chemical_package(DB, phase18f_synthetic_package(), dry_run=True)
    after = _hash(DB)
    assert report.pass_import
    assert report.dry_run and not report.committed
    assert before == after
    assert report.validation.planned_delta.solutes == 1
    assert report.validation.planned_delta.equilibrium_pairs == 1


def test_commit_to_copy_is_atomic_and_loadable(tmp_path):
    db = _copy_db(tmp_path)
    before = SQLiteAbsorberRepositoryV18B(db).inventory().__dict__.copy()
    result = import_chemical_package(db, phase18f_synthetic_package(), dry_run=False, create_backup=False)
    after_repo = SQLiteAbsorberRepositoryV18B(db)
    after = after_repo.inventory().__dict__.copy()
    assert result.pass_import and result.committed
    assert after["solutes"] == before["solutes"] + 1
    assert after["equilibrium_pairs"] == before["equilibrium_pairs"] + 1
    registry = after_repo.load_registry()
    assert registry.get_solute("phase18f_demo_solute").MW_kg_mol == pytest.approx(0.075)
    assert after_repo.metadata()["expansion_framework_version"] == PHASE18F_IMPORT_CONTRACT_VERSION


def test_imported_synthetic_coverage_uses_existing_estimators(tmp_path):
    db = _copy_db(tmp_path)
    import_chemical_package(db, phase18f_synthetic_package(), dry_run=False, create_backup=False)
    explorer = DatabaseExplorer.from_path(db)
    cell = explorer.coverage_cell("phase18f_demo_solute", "water", carrier_id="air")
    assert cell.resolvable
    assert cell.overall_status == CoverageStatus.SCREENING
    assert cell.gas_transport_tier == "ESTIMATE"
    assert cell.liquid_transport_tier == "ESTIMATE"


def test_append_only_collision_is_blocked(tmp_path):
    db = _copy_db(tmp_path)
    pkg = phase18f_synthetic_package()
    import_chemical_package(db, pkg, dry_run=False, create_backup=False)
    with pytest.raises(ChemicalImportValidationError) as exc:
        import_chemical_package(db, pkg, dry_run=False, create_backup=False)
    codes = {x.code for x in exc.value.report.blocking_issues}
    assert "SOLUTE_COLLISION" in codes
    assert "EQ_PAIR_COLLISION" in codes


def test_confidence_ab_requires_bibliographic_locator():
    pkg = phase18f_synthetic_package()
    pkg["provenance"][0]["confidence"] = "B"
    pkg["sources"][0]["url"] = None
    pkg["sources"][0]["doi"] = None
    report = validate_chemical_import_package(pkg, SQLiteAbsorberRepositoryV18B(DB))
    assert "AB_SOURCE_LOCATOR_REQUIRED" in {x.code for x in report.blocking_issues}


def test_henry_model_requires_full_henry_fields():
    pkg = phase18f_synthetic_package()
    eq = pkg["equilibrium_pairs"][0]
    eq.update({"model":"henry_pc", "H_ref_Pa_m3_mol":1000.0, "T_ref_K":298.15, "temperature_coefficient_K":None, "m_y_over_x":None})
    report = validate_chemical_import_package(pkg, SQLiteAbsorberRepositoryV18B(DB))
    assert "HENRY_FIELDS_REQUIRED" in {x.code for x in report.blocking_issues}


def test_invalid_package_never_mutates_database_copy(tmp_path):
    db = _copy_db(tmp_path)
    pkg = phase18f_synthetic_package()
    pkg["solutes"][0]["provenance_key"] = "MISSING"
    before = _hash(db)
    with pytest.raises(ChemicalImportValidationError):
        import_chemical_package(db, pkg, dry_run=False, create_backup=False)
    assert _hash(db) == before


def test_phase18f_gate_passes_and_primary_db_is_unchanged():
    before = _hash(DB)
    gate = run_phase18f_expansion_gate(DB)
    after = _hash(DB)
    assert gate.pass_gate
    assert gate.primary_database_unchanged
    assert before == after
