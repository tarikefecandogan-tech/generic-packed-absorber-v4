import math

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    PHASE18B_DATABASE_ID,
    PHASE18B_SCHEMA_VERSION,
    build_phase14_registry,
    build_phase18a_source_registry,
    build_phase18b_database,
    canonical_y_from_total_and_fractions,
    compare_registry_to_phase18b_sqlite,
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


def test_phase18b_schema_metadata_integrity_and_classification(tmp_path):
    repo = build_phase18b_database(tmp_path / "absorber_v18b.db")
    meta = repo.metadata()
    assert meta["database_id"] == PHASE18B_DATABASE_ID
    assert meta["schema_version"] == PHASE18B_SCHEMA_VERSION
    assert meta["migration_parent"] == "PHASE18A_SCHEMA_AND_PARITY"
    assert repo.integrity_check() == "ok"
    assert repo.foreign_key_violations() == ()
    coverage = repo.provenance_coverage()
    assert coverage.sources == 7
    assert coverage.unresolved_source_metadata == 0
    assert coverage.provenance_usage_records >= 20


def test_phase18b_gossett_source_has_professional_bibliography(tmp_path):
    repo = build_phase18b_database(tmp_path / "absorber_v18b.db")
    rows = repo.list_sources_detailed()
    gossett = [r for r in rows if r["doi"] == "10.1021/es00156a012"]
    assert len(gossett) == 1
    row = gossett[0]
    assert row["publication_year"] == 1987
    assert "Henry" in row["title"]
    assert "NIST" in row["journal_or_publisher"]
    assert row["evidence_role"] == "PRIMARY_EXPERIMENTAL"
    assert row["url"].startswith("https://webbook.nist.gov/")


def test_phase18b_fuller_and_wilke_chang_are_registered_methodology_sources(tmp_path):
    repo = build_phase18b_database(tmp_path / "absorber_v18b.db")
    rows = repo.list_sources_detailed()
    dois = {r["doi"] for r in rows if r["doi"]}
    assert "10.1021/ie50677a007" in dois
    assert "10.1002/aic.690010222" in dois
    usage = repo.list_provenance_usage()
    keys = {(r["entity_type"], r["entity_key"], r["property_scope"]) for r in usage}
    assert ("correlation_method", "fuller_gas_diffusivity", "gas_transport_estimation") in keys
    assert ("correlation_method", "wilke_chang_liquid_diffusivity", "liquid_transport_estimation") in keys


def test_phase18b_property_scope_usage_is_queryable(tmp_path):
    repo = build_phase18b_database(tmp_path / "absorber_v18b.db")
    usage = repo.list_provenance_usage()
    scopes = {r["property_scope"] for r in usage}
    assert "equilibrium_property" in scopes
    assert "transport_property" in scopes
    assert "packing_geometry_hydraulics" in scopes
    vdc_water = [
        r for r in usage
        if r["entity_type"] == "equilibrium_pair" and r["entity_key"] == "VDC|water"
    ]
    assert len(vdc_water) == 1
    assert vdc_water[0]["confidence"] == "B"
    assert vdc_water[0]["property_name"] == "H_pc"
    assert vdc_water[0]["validity_temperature_min_K"] is not None
    assert vdc_water[0]["validity_temperature_max_K"] is not None


def test_phase18b_registry_roundtrip_parity(tmp_path):
    expected = build_phase18a_source_registry()
    repo = build_phase18b_database(tmp_path / "absorber_v18b.db")
    report = compare_registry_to_phase18b_sqlite(expected, repo)
    assert report.pass_gate
    assert all(report.core_registry_parity.values())


def test_phase18b_database_loaded_registry_reproduces_reference_simulation(tmp_path):
    python_registry = build_phase14_registry()
    repo = build_phase18b_database(tmp_path / "absorber_v18b.db")
    db_registry = repo.load_registry()
    case = _reference_case(python_registry)
    py_result = run_generic_absorber_case(case, registry=python_registry)
    db_result = run_generic_absorber_case(case, registry=db_registry)
    assert math.isclose(db_result.outlet_report.total_mgVOC_Nm3, py_result.outlet_report.total_mgVOC_Nm3, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(db_result.stream_balance.overall_removal_voc_mass, py_result.stream_balance.overall_removal_voc_mass, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(db_result.hydraulics.flooding.flooding_percent, py_result.hydraulics.flooding.flooding_percent, rel_tol=1e-12, abs_tol=1e-12)


def test_phase18b_source_coverage_summary_is_explicit(tmp_path):
    repo = build_phase18b_database(tmp_path / "absorber_v18b.db")
    c = repo.provenance_coverage()
    assert c.sources_with_type == c.sources
    assert c.sources_with_title == c.sources
    assert c.sources_with_url_or_doi == 5
    assert c.confidence_B == 7
    assert c.confidence_C == 2
    assert c.confidence_D == 1
    assert 0.0 < c.bibliographic_link_fraction < 1.0
