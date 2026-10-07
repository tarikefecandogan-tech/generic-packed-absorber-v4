import math
import sqlite3
from pathlib import Path

import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    PHASE18A_DATABASE_ID,
    PHASE18A_SCHEMA_VERSION,
    SQLiteAbsorberRepository,
    build_phase14_registry,
    build_phase18a_database,
    build_phase18a_source_registry,
    canonical_y_from_total_and_fractions,
    compare_registry_to_sqlite,
    run_generic_absorber_case,
)


def _reference_case(registry):
    solutes = {sid: registry.get_solute(sid) for sid in ("ACN", "VAc")}
    feed = canonical_y_from_total_and_fractions(
        5000.0,
        GasConcentrationBasis.MG_VOC_NM3,
        {"ACN": 0.93, "VAc": 0.07},
        CompositionFractionBasis.VOC_MASS,
        solutes,
    )
    return GenericAbsorberCase(
        operating=AbsorberOperatingPoint(
            diameter_m=0.5, packed_height_m=1.4, gas_actual_m3_h=117.53,
            liquid_mass_kg_h=2500.0, temperature_K=295.15, pressure_Pa=101325.0,
        ),
        solute_ids=("ACN", "VAc"), carrier_id="air", solvent_id="water",
        packing_id="25mm_metal_pall_ring", gas_inlet_y=feed.canonical_y,
        liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
    )


def test_phase18a_sqlite_schema_metadata_and_integrity(tmp_path):
    repo = build_phase18a_database(tmp_path / "absorber.db")
    meta = repo.metadata()
    assert meta["database_id"] == PHASE18A_DATABASE_ID
    assert meta["schema_version"] == PHASE18A_SCHEMA_VERSION
    assert repo.integrity_check() == "ok"
    assert repo.foreign_key_violations() == ()


def test_phase18a_inventory_matches_current_engineering_catalog(tmp_path):
    repo = build_phase18a_database(tmp_path / "absorber.db")
    inv = repo.inventory()
    assert (inv.solutes, inv.carriers, inv.solvents, inv.packings) == (3, 1, 2, 10)
    assert (inv.gas_transport_pairs, inv.liquid_transport_pairs, inv.equilibrium_pairs) == (2, 2, 4)
    assert inv.sources == 5
    assert inv.provenance_records == 8


def test_phase18a_registry_roundtrip_is_exact(tmp_path):
    expected = build_phase18a_source_registry()
    repo = build_phase18a_database(tmp_path / "absorber.db")
    report = compare_registry_to_sqlite(expected, repo)
    assert report.pass_gate
    assert all(report.dictionary_parity.values())
    assert report.registry_reference_id_match


def test_phase18a_sqlite_loaded_registry_reproduces_reference_simulation(tmp_path):
    python_registry = build_phase14_registry()
    repo = build_phase18a_database(tmp_path / "absorber.db")
    sqlite_registry = repo.load_registry()
    case = _reference_case(python_registry)

    py_result = run_generic_absorber_case(case, registry=python_registry)
    db_result = run_generic_absorber_case(case, registry=sqlite_registry)

    assert math.isclose(db_result.outlet_report.total_mgVOC_Nm3, py_result.outlet_report.total_mgVOC_Nm3, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(db_result.stream_balance.overall_removal_voc_mass, py_result.stream_balance.overall_removal_voc_mass, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(db_result.hydraulics.flooding.flooding_percent, py_result.hydraulics.flooding.flooding_percent, rel_tol=1e-12, abs_tol=1e-12)
    assert db_result.post_applicability.status == py_result.post_applicability.status


def test_phase18a_sources_are_normalized_and_deduplicated(tmp_path):
    repo = build_phase18a_database(tmp_path / "absorber.db")
    sources = repo.list_sources()
    citations = [row["citation"] for row in sources]
    assert len(citations) == len(set(citations))
    legacy = [row for row in sources if "ScrubberSimulationV34 locked" in row["citation"]]
    assert len(legacy) == 1
    assert legacy[0]["provenance_uses"] == 4


def test_phase18a_foreign_keys_are_actively_enforced(tmp_path):
    repo = build_phase18a_database(tmp_path / "absorber.db")
    with repo.connect() as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                """INSERT INTO gas_transport_pairs
                (solute_id, carrier_id, D_ref_m2_s, model)
                VALUES ('DOES_NOT_EXIST', 'air', 1e-5, 'fixed_reference')"""
            )


def test_phase18a_prebuilt_repository_api_reads_equilibrium_catalog(tmp_path):
    repo = build_phase18a_database(tmp_path / "absorber.db")
    rows = repo.list_equilibrium_pairs()
    keys = {(r["solute_id"], r["solvent_id"], r["model"]) for r in rows}
    assert ("ACN", "water", "henry_pc") in keys
    assert ("VAc", "water", "henry_pc") in keys
    assert ("VDC", "water", "henry_pc") in keys
    assert ("VDC", "acrylonitrile", "linear_m") in keys
