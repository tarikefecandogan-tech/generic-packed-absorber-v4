from pathlib import Path

from generic_absorber_v4 import (
    CoverageStatus,
    DatabaseExplorer,
    run_phase18e_explorer_gate,
)

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "absorber_database_v18b.db"


def test_explorer_inventory_matches_phase18d_database():
    explorer = DatabaseExplorer.from_path(DB)
    assert len(explorer.list_solutes()) == 3
    assert len(explorer.list_carriers()) == 1
    assert len(explorer.list_solvents()) == 2
    assert len(explorer.list_packings()) == 10
    assert len(explorer.list_gas_transport_pairs()) == 2
    assert len(explorer.list_liquid_transport_pairs()) == 2
    assert len(explorer.list_equilibrium_pairs()) == 4


def test_coverage_matrix_reference_statuses():
    explorer = DatabaseExplorer.from_path(DB)
    cells = {(c.solute_id, c.solvent_id): c for c in explorer.coverage_cells(carrier_id="air")}
    assert cells[("ACN", "water")].overall_status == CoverageStatus.VERIFIED
    assert cells[("VAc", "water")].overall_status == CoverageStatus.VERIFIED
    assert cells[("VDC", "water")].overall_status == CoverageStatus.ESTIMATED
    assert cells[("VDC", "acrylonitrile")].overall_status == CoverageStatus.SCREENING
    assert cells[("ACN", "acrylonitrile")].overall_status == CoverageStatus.MISSING
    assert cells[("VAc", "acrylonitrile")].overall_status == CoverageStatus.MISSING


def test_coverage_summary_and_matrix_shape():
    explorer = DatabaseExplorer.from_path(DB)
    summary = explorer.coverage_summary(carrier_id="air")
    assert summary.total_cells == 6
    assert summary.verified == 2
    assert summary.estimated == 1
    assert summary.screening == 1
    assert summary.missing == 2
    assert summary.unsupported == 0
    rows = explorer.coverage_matrix_rows(carrier_id="air")
    assert len(rows) == 3
    assert set(rows[0]) == {"Solute", "water", "acrylonitrile"}


def test_transport_resolution_details_are_visible():
    explorer = DatabaseExplorer.from_path(DB)
    vdc_water = explorer.coverage_cell("VDC", "water", carrier_id="air")
    assert vdc_water.gas_transport_tier == "ESTIMATE"
    assert vdc_water.gas_transport_confidence == "C"
    assert vdc_water.liquid_transport_tier == "ESTIMATE"
    assert vdc_water.liquid_transport_confidence == "C"
    assert vdc_water.equilibrium_tier == "DATABASE"
    assert vdc_water.equilibrium_confidence == "B"


def test_search_finds_cross_table_vdc_records():
    explorer = DatabaseExplorer.from_path(DB)
    hits = explorer.search("VDC")
    kinds = {h["entity_type"] for h in hits}
    assert "solute" in kinds
    assert "equilibrium_pair" in kinds
    assert len(hits) >= 3


def test_missing_data_backlog_prioritizes_true_missing_pairs():
    explorer = DatabaseExplorer.from_path(DB)
    backlog = explorer.missing_data_backlog(carrier_id="air")
    assert backlog
    missing = [r for r in backlog if r["status"] == "MISSING"]
    keys = {(r["solute_id"], r["solvent_id"]) for r in missing}
    assert ("ACN", "acrylonitrile") in keys
    assert ("VAc", "acrylonitrile") in keys
    assert all(r["priority"] == 1 for r in missing)


def test_explorer_is_read_only_for_database_file():
    before = DB.read_bytes()
    explorer = DatabaseExplorer.from_path(DB)
    explorer.list_sources()
    explorer.coverage_cells(carrier_id="air")
    explorer.search("water")
    after = DB.read_bytes()
    assert before == after


def test_phase18e_gate_passes():
    report = run_phase18e_explorer_gate(DB)
    assert report.pass_gate
    assert report.integrity.lower() == "ok"
    assert report.foreign_key_violations == 0
    assert report.matrix_cells == 6
    assert report.database_unchanged
