"""Phase 18G — first verified chemical expansion batch.

This module is data-governance/orchestration only.  It adds five common VOCs
through the controlled Phase-18F import path and verifies that the resulting
SQLite database can resolve and simulate them without inventing fixed
transport-pair data.

Scientific policy
-----------------
* Identity and water Henry data are taken from the NIST Chemistry WebBook.
* For each NIST/Sander Henry table the selected default is the first method
  ``L`` row that reports both kH° and d ln(kH)/d(1/T).  This deterministic rule
  avoids cherry-picking among literature entries.
* NIST reports Henry solubility form kH [mol/(kg water bar)].  It is converted
  to the simulator canonical pressure/concentration form p = Hpc*C via
  Hpc = 1e5/(kH*rho_water_298).
* Fuller and Le Bas group-contribution volumes are engineering estimator inputs
  (Confidence C), not measured diffusion coefficients.  No fixed D_G or D_L
  pair is registered for the new VOCs; Phase 11 correlations remain visible.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Dict, Mapping, Tuple

from .chemical_import import (
    PHASE18F_IMPORT_CONTRACT_VERSION,
    import_chemical_package,
)
from .database_explorer import CoverageStatus, DatabaseExplorer
from .database_v18b import SQLiteAbsorberRepositoryV18B
from .mass_transfer import AbsorberOperatingPoint
from .repository import RegistryLoaderRepository, RepositoryDescriptor, RepositoryKind
from .resolver import PropertyResolver, ResolutionTier
from .simulation import GenericAbsorberCase, run_generic_absorber_case

PHASE18G_BATCH_ID = "PHASE18G_FIRST_VERIFIED_CHEMICAL_BATCH_2026_10_07"
PHASE18G_DATA_SNAPSHOT_ID = "PHASE18G_VERIFIED_CHEMICAL_BATCH_2026_10_07"
PHASE18G_DATABASE_FILENAME = "absorber_database_v18g.db"
PHASE18G_BATCH_FILENAME = "phase18g_verified_batch.json"
PHASE18G_ACCESSED_ON = "2026-10-07"
WATER_RHO_298_KG_M3 = 997.0751177

# Methodology metadata already present for Fuller in Phase 18B.
FULLER_CITATION = (
    "Fuller, Schettler & Giddings (1966) atomic diffusion-volume method; "
    "C=16.5, H=1.98, Cl=19.5; Air=20.1"
)
LEBAS_CITATION = (
    "Poling, Prausnitz & O'Connell (2001), The Properties of Gases and Liquids, "
    "5th ed.; Le Bas group-contribution boiling molar volume increments"
)


@dataclass(frozen=True)
class VerifiedVOCRecord:
    solute_id: str
    name: str
    formula: str
    cas_number: str
    MW_kg_mol: float
    carbon_atoms: int
    fuller_diffusion_volume: float
    boiling_molar_volume_cm3_mol: float
    nist_url: str
    kh_solubility_mol_kg_bar_298: float
    henry_temperature_coefficient_K: float

    @property
    def H_ref_Pa_m3_mol(self) -> float:
        return 1.0e5 / (self.kh_solubility_mol_kg_bar_298 * WATER_RHO_298_KG_M3)


PHASE18G_VOCS: Tuple[VerifiedVOCRecord, ...] = (
    VerifiedVOCRecord(
        "acetone", "Acetone", "C3H6O", "67-64-1", 58.0791e-3, 3,
        66.86, 74.0,
        "https://webbook.nist.gov/cgi/cbook.cgi?ID=C67641&Mask=1F",
        30.0, 4600.0,
    ),
    VerifiedVOCRecord(
        "benzene", "Benzene", "C6H6", "71-43-2", 78.1118e-3, 6,
        90.68, 96.0,
        "https://webbook.nist.gov/cgi/cbook.cgi?ID=C71432&Mask=1F",
        0.16, 4100.0,
    ),
    VerifiedVOCRecord(
        "toluene", "Toluene", "C7H8", "108-88-3", 92.1384e-3, 7,
        111.14, 118.2,
        "https://webbook.nist.gov/cgi/cbook.cgi?ID=C108883&Mask=1F",
        0.15, 4000.0,
    ),
    VerifiedVOCRecord(
        "ethylbenzene", "Ethylbenzene", "C8H10", "100-41-4", 106.1650e-3, 8,
        131.60, 140.4,
        "https://webbook.nist.gov/cgi/cbook.cgi?ID=C100414&Mask=1F",
        0.12, 5100.0,
    ),
    VerifiedVOCRecord(
        "dichloromethane", "Dichloromethane (Methylene chloride)", "CH2Cl2", "75-09-2", 84.933e-3, 1,
        59.46, 71.4,
        "https://webbook.nist.gov/cgi/cbook.cgi?ID=C75092&Mask=1F",
        0.36, 4100.0,
    ),
)

PHASE18G_HENRY_SELECTION_RULE = (
    "NIST/Sander table: first method='L' row containing both kH° and "
    "d ln(kH)/d(1/T); no cross-source averaging."
)


def _nist_source_key(rec: VerifiedVOCRecord) -> str:
    return f"SRC_NIST_{rec.solute_id.upper()}"


def _id_prov_key(rec: VerifiedVOCRecord) -> str:
    return f"PROV_NIST_ID_{rec.solute_id.upper()}"


def _henry_prov_key(rec: VerifiedVOCRecord) -> str:
    return f"PROV_NIST_HENRY_{rec.solute_id.upper()}"


def phase18g_verified_batch_package() -> dict:
    sources = []
    provenance = []
    solutes = []
    equilibrium_pairs = []

    for rec in PHASE18G_VOCS:
        skey = _nist_source_key(rec)
        sources.append({
            "source_key": skey,
            "citation": (
                f"NIST Chemistry WebBook SRD 69 — {rec.name}: identity and Henry's Law data "
                f"(CAS {rec.cas_number})"
            ),
            "source_type": "curated_thermophysical_database",
            "title": f"NIST Chemistry WebBook — {rec.name}",
            "authors": "National Institute of Standards and Technology (NIST); Henry compilation includes Sander literature entries",
            "publication_year": None,
            "journal_or_publisher": "NIST Chemistry WebBook, SRD 69",
            "url": rec.nist_url,
            "doi": None,
            "accessed_on": PHASE18G_ACCESSED_ON,
            "evidence_role": "CURATED_DATABASE_COMPILATION",
            "quality_note": (
                "Identity data and literature-compiled water Henry data from NIST. "
                "Individual literature entries may scatter; Phase 18G uses a deterministic selection rule and retains this uncertainty note."
            ),
            "notes": PHASE18G_HENRY_SELECTION_RULE,
        })
        provenance.append({
            "provenance_key": _id_prov_key(rec),
            "source_key": skey,
            "method": "NIST Chemistry WebBook curated pure-component identity record",
            "confidence": "B",
            "resolution_tier": "DATABASE",
            "reference_temperature_K": None,
            "reference_pressure_Pa": None,
            "validity_temperature_min_K": None,
            "validity_temperature_max_K": None,
            "validity_pressure_min_Pa": None,
            "validity_pressure_max_Pa": None,
            "composition_validity_note": "Pure-component identity only.",
            "validity_note": "MW/formula/CAS compiled by NIST; transport group-contribution inputs have separate Confidence C methodology provenance.",
        })
        provenance.append({
            "provenance_key": _henry_prov_key(rec),
            "source_key": skey,
            "method": (
                "NIST/Sander water Henry solubility-form kH converted to Hpc; "
                + PHASE18G_HENRY_SELECTION_RULE
            ),
            "confidence": "B",
            "resolution_tier": "DATABASE",
            "reference_temperature_K": 298.15,
            "reference_pressure_Pa": None,
            "validity_temperature_min_K": None,
            "validity_temperature_max_K": None,
            "validity_pressure_min_Pa": None,
            "validity_pressure_max_Pa": None,
            "composition_validity_note": "Dilute solute in water; literature Henry compilation.",
            "validity_note": (
                f"Selected kH°={rec.kh_solubility_mol_kg_bar_298:g} mol/(kg water·bar), "
                f"temperature coefficient={rec.henry_temperature_coefficient_K:g} K. "
                "NIST table contains multiple literature values; sensitivity to equilibrium uncertainty remains advisable."
            ),
        })
        solutes.append({
            "solute_id": rec.solute_id,
            "name": rec.name,
            "MW_kg_mol": rec.MW_kg_mol,
            "carbon_atoms": rec.carbon_atoms,
            "formula": rec.formula,
            "cas_number": rec.cas_number,
            "fuller_diffusion_volume": rec.fuller_diffusion_volume,
            "boiling_molar_volume_cm3_mol": rec.boiling_molar_volume_cm3_mol,
            "provenance_key": _id_prov_key(rec),
        })
        equilibrium_pairs.append({
            "solute_id": rec.solute_id,
            "solvent_id": "water",
            "model": "henry_pc",
            "H_ref_Pa_m3_mol": rec.H_ref_Pa_m3_mol,
            "T_ref_K": 298.15,
            "temperature_coefficient_K": rec.henry_temperature_coefficient_K,
            "m_y_over_x": None,
            "validity_temperature_min_K": None,
            "validity_temperature_max_K": None,
            "validity_note": (
                PHASE18G_HENRY_SELECTION_RULE
                + " NIST literature scatter is not averaged; this is the traceable Phase 18G default."
            ),
            "provenance_key": _henry_prov_key(rec),
        })

    # Le Bas methodology is a separate Confidence-C source because the values
    # stored on the solute row are correlation inputs rather than NIST identity data.
    sources.append({
        "source_key": "SRC_LEBAS_POLING",
        "citation": LEBAS_CITATION,
        "source_type": "engineering_property_handbook",
        "title": "The Properties of Gases and Liquids, Fifth Edition",
        "authors": "Bruce E. Poling; John M. Prausnitz; John P. O'Connell",
        "publication_year": 2001,
        "journal_or_publisher": "McGraw-Hill",
        "url": "https://books.google.com/books?id=s_NUAAAAMAAJ",
        "doi": None,
        "accessed_on": PHASE18G_ACCESSED_ON,
        "evidence_role": "GROUP_CONTRIBUTION_METHOD",
        "quality_note": "Engineering handbook source for Le Bas group-contribution boiling molar-volume increments used as Wilke–Chang input.",
        "notes": "C=14.8, H=3.7, O=7.4, Cl=24.6 cm3/mol contributions; six-membered ring correction -15.0 cm3/mol.",
    })
    provenance.append({
        "provenance_key": "PROV_LEBAS_GROUP_VOLUME",
        "source_key": "SRC_LEBAS_POLING",
        "method": "Le Bas group-contribution boiling molar volume",
        "confidence": "C",
        "resolution_tier": "CORRELATION_ESTIMATE",
        "reference_temperature_K": None,
        "reference_pressure_Pa": None,
        "validity_temperature_min_K": None,
        "validity_temperature_max_K": None,
        "validity_pressure_min_Pa": None,
        "validity_pressure_max_Pa": None,
        "composition_validity_note": "Pure-solute group-contribution input for Wilke–Chang.",
        "validity_note": "Estimator input only; not a measured liquid diffusivity.",
    })

    return {
        "contract_version": PHASE18F_IMPORT_CONTRACT_VERSION,
        "package_id": PHASE18G_BATCH_ID,
        "description": "First verified expansion batch: five common VOC identities + water Henry equilibrium; transport remains correlation-estimated.",
        "sources": sources,
        "provenance": provenance,
        "solutes": solutes,
        "carriers": [],
        "solvents": [],
        "gas_transport_pairs": [],
        "liquid_transport_pairs": [],
        "equilibrium_pairs": equilibrium_pairs,
    }


def write_phase18g_batch_json(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(phase18g_verified_batch_package(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _stable_usage_id(provenance_id: str, entity_type: str, entity_key: str, scope: str, pname: str) -> str:
    from hashlib import sha256
    payload = "|".join([provenance_id, entity_type, entity_key, scope, pname])
    return f"use_{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _add_field_level_transport_provenance(database_path: str | Path) -> None:
    """Replace the importer's combined identity/transport usage with field-level provenance."""
    path = Path(database_path)
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA foreign_keys=ON")
        fuller = con.execute(
            "SELECT p.provenance_id FROM provenance p JOIN sources s ON s.source_id=p.source_id "
            "WHERE s.citation=? AND p.method='Fuller gas diffusivity correlation' LIMIT 1",
            (FULLER_CITATION,),
        ).fetchone()
        lebas = con.execute(
            "SELECT provenance_id FROM provenance WHERE method='Le Bas group-contribution boiling molar volume' LIMIT 1"
        ).fetchone()
        if fuller is None or lebas is None:
            raise RuntimeError("Required Fuller/Le Bas methodology provenance not available for Phase 18G.")
        fuller_pid, lebas_pid = str(fuller[0]), str(lebas[0])

        for rec in PHASE18G_VOCS:
            identity_pid_row = con.execute(
                "SELECT provenance_id FROM solutes WHERE solute_id=?", (rec.solute_id,)
            ).fetchone()
            if identity_pid_row is None:
                raise RuntimeError(f"Imported solute missing: {rec.solute_id}")
            identity_pid = str(identity_pid_row[0])
            # Remove Phase18F's coarse combined usage for these records only.
            con.execute(
                "DELETE FROM provenance_usage WHERE entity_type='solute' AND entity_key=? "
                "AND property_scope='identity_transport_inputs'",
                (rec.solute_id,),
            )
            usages = (
                (identity_pid, "identity", "MW_formula_CAS_carbon_count", None,
                 "NIST identity fields; excludes transport group-contribution inputs."),
                (fuller_pid, "correlation_input", "Fuller diffusion volume", "dimensionless group volume",
                 f"Group-contribution result {rec.fuller_diffusion_volume:g}; used only when Fuller D_G fallback is invoked."),
                (lebas_pid, "correlation_input", "Le Bas boiling molar volume", "cm3/mol",
                 f"Group-contribution result {rec.boiling_molar_volume_cm3_mol:g}; used only when Wilke–Chang D_L fallback is invoked."),
            )
            for pid, scope, pname, unit, notes in usages:
                uid = _stable_usage_id(pid, "solute", rec.solute_id, scope, pname)
                con.execute(
                    "INSERT OR IGNORE INTO provenance_usage(usage_id,provenance_id,entity_type,entity_key,property_scope,property_name,unit,notes) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (uid, pid, "solute", rec.solute_id, scope, pname, unit, notes),
                )

        metadata = {
            "data_snapshot_id": PHASE18G_DATA_SNAPSHOT_ID,
            "verified_expansion_batch": PHASE18G_BATCH_ID,
            "primary_database_filename": PHASE18G_DATABASE_FILENAME,
        }
        for key, value in metadata.items():
            con.execute("INSERT OR REPLACE INTO schema_metadata(key,value) VALUES (?,?)", (key, value))
        con.commit()


def apply_phase18g_verified_batch(database_path: str | Path, *, allow_replace: bool = False) -> None:
    """Commit the verified batch to a Phase-18B-schema database and add field-level provenance."""
    report = import_chemical_package(
        database_path,
        phase18g_verified_batch_package(),
        dry_run=False,
        allow_replace=allow_replace,
        create_backup=False,
    )
    if not report.pass_import:
        raise RuntimeError("Phase 18G controlled import did not pass.")
    _add_field_level_transport_provenance(database_path)


@dataclass(frozen=True)
class Phase18GFixtureResult:
    solute_id: str
    outlet_ppmv: float
    removal_fraction: float
    absorption_factor: float
    HTU_OG_m: float
    NTU_OG: float
    mass_balance_error: float
    readiness: str


@dataclass(frozen=True)
class Phase18GGateReport:
    integrity: str
    foreign_key_violations: int
    inventory_solutes: int
    inventory_equilibrium_pairs: int
    identity_ok: bool
    henry_ok: bool
    transport_estimated_c: bool
    water_coverage_estimated: bool
    acrylonitrile_coverage_missing: bool
    no_new_fixed_transport_pairs: bool
    provenance_field_split_ok: bool
    fixture_results: Tuple[Phase18GFixtureResult, ...]

    @property
    def pass_gate(self) -> bool:
        return all((
            self.integrity.lower() == "ok",
            self.foreign_key_violations == 0,
            self.inventory_solutes == 8,
            self.inventory_equilibrium_pairs == 9,
            self.identity_ok,
            self.henry_ok,
            self.transport_estimated_c,
            self.water_coverage_estimated,
            self.acrylonitrile_coverage_missing,
            self.no_new_fixed_transport_pairs,
            self.provenance_field_split_ok,
            len(self.fixture_results) == len(PHASE18G_VOCS),
            all(r.mass_balance_error < 1e-8 for r in self.fixture_results),
        ))


def _database_repository(database_path: str | Path) -> RegistryLoaderRepository:
    raw = SQLiteAbsorberRepositoryV18B(database_path)
    return RegistryLoaderRepository(
        loader=raw.load_registry,
        _descriptor=RepositoryDescriptor(
            backend_id="sqlite_v18g",
            kind=RepositoryKind.SQLITE,
            label="SQLite Engineering Database v18G",
            source=str(Path(database_path)),
            schema_version=raw.metadata().get("schema_version"),
            read_only=True,
        ),
    )


def run_phase18g_verified_batch_gate(database_path: str | Path) -> Phase18GGateReport:
    repo_raw = SQLiteAbsorberRepositoryV18B(database_path)
    registry = repo_raw.load_registry()
    resolver = PropertyResolver(registry)
    explorer = DatabaseExplorer(repo_raw)

    # Identity and equilibrium exactness.
    identity_ok = True
    henry_ok = True
    transport_ok = True
    cov_water_ok = True
    cov_acn_missing = True
    fixtures = []

    for rec in PHASE18G_VOCS:
        s = registry.get_solute(rec.solute_id)
        identity_ok = identity_ok and (
            s.name == rec.name
            and s.formula == rec.formula
            and s.cas_number == rec.cas_number
            and abs(s.MW_kg_mol - rec.MW_kg_mol) < 1e-15
            and s.carbon_atoms == rec.carbon_atoms
            and abs(float(s.fuller_diffusion_volume) - rec.fuller_diffusion_volume) < 1e-12
            and abs(float(s.boiling_molar_volume_cm3_mol) - rec.boiling_molar_volume_cm3_mol) < 1e-12
        )
        eq_pair = registry.find_equilibrium_pair(rec.solute_id, "water")
        henry_ok = henry_ok and (
            eq_pair is not None
            and eq_pair.model == "henry_pc"
            and abs(float(eq_pair.H_ref_Pa_m3_mol) - rec.H_ref_Pa_m3_mol) < 1e-12
            and abs(float(eq_pair.T_ref_K) - 298.15) < 1e-12
            and abs(float(eq_pair.temperature_coefficient_K) - rec.henry_temperature_coefficient_K) < 1e-12
            and eq_pair.provenance is not None
            and eq_pair.provenance.confidence.value == "B"
        )

        dg = resolver.resolve_gas_diffusivity(rec.solute_id, "air", 298.15, 101325.0)
        dl = resolver.resolve_liquid_diffusivity(rec.solute_id, "water", 298.15)
        transport_ok = transport_ok and (
            dg.tier == ResolutionTier.CORRELATION_ESTIMATE
            and dl.tier == ResolutionTier.CORRELATION_ESTIMATE
            and dg.confidence.value == "C"
            and dl.confidence.value == "C"
        )

        wc = explorer.coverage_cell(rec.solute_id, "water", carrier_id="air", T_K=298.15, P_Pa=101325.0)
        ac = explorer.coverage_cell(rec.solute_id, "acrylonitrile", carrier_id="air", T_K=298.15, P_Pa=101325.0)
        cov_water_ok = cov_water_ok and wc.overall_status == CoverageStatus.ESTIMATED
        cov_acn_missing = cov_acn_missing and ac.overall_status == CoverageStatus.MISSING

        case = GenericAbsorberCase(
            operating=AbsorberOperatingPoint(
                diameter_m=0.5,
                packed_height_m=1.4,
                gas_actual_m3_h=117.53,
                liquid_mass_kg_h=2500.0,
                temperature_K=295.15,
                pressure_Pa=101325.0,
            ),
            solute_ids=(rec.solute_id,),
            carrier_id="air",
            solvent_id="water",
            packing_id="25mm_metal_pall_ring",
            gas_inlet_y={rec.solute_id: 1000.0e-6},
            liquid_inlet_x={rec.solute_id: 0.0},
        )
        result = run_generic_absorber_case(case, repository=_database_repository(database_path))
        comp = result.solver_results.components[rec.solute_id]
        transfer = result.transfer_results[rec.solute_id]
        fixtures.append(Phase18GFixtureResult(
            solute_id=rec.solute_id,
            outlet_ppmv=comp.gas_outlet_y * 1.0e6,
            removal_fraction=comp.removal_fraction,
            absorption_factor=transfer.absorption_factor,
            HTU_OG_m=transfer.HTU_OG_m,
            NTU_OG=transfer.NTU_OG,
            mass_balance_error=abs(comp.diagnostics.relative_mass_balance_error),
            readiness=result.post_applicability.status.value,
        ))

    new_ids = tuple(r.solute_id for r in PHASE18G_VOCS)
    with repo_raw.connect() as con:
        gas_n = con.execute(
            f"SELECT COUNT(*) FROM gas_transport_pairs WHERE solute_id IN ({','.join('?' for _ in new_ids)})",
            new_ids,
        ).fetchone()[0]
        liquid_n = con.execute(
            f"SELECT COUNT(*) FROM liquid_transport_pairs WHERE solute_id IN ({','.join('?' for _ in new_ids)})",
            new_ids,
        ).fetchone()[0]
        split_ok = True
        for sid in new_ids:
            rows = con.execute(
                "SELECT property_scope,property_name FROM provenance_usage WHERE entity_type='solute' AND entity_key=?",
                (sid,),
            ).fetchall()
            scopes = {(str(a), str(b)) for a, b in rows}
            split_ok = split_ok and (
                ("identity", "MW_formula_CAS_carbon_count") in scopes
                and ("correlation_input", "Fuller diffusion volume") in scopes
                and ("correlation_input", "Le Bas boiling molar volume") in scopes
                and not any(a == "identity_transport_inputs" for a, _ in scopes)
            )

    inv = repo_raw.inventory()
    return Phase18GGateReport(
        integrity=repo_raw.integrity_check(),
        foreign_key_violations=len(repo_raw.foreign_key_violations()),
        inventory_solutes=inv.solutes,
        inventory_equilibrium_pairs=inv.equilibrium_pairs,
        identity_ok=identity_ok,
        henry_ok=henry_ok,
        transport_estimated_c=transport_ok,
        water_coverage_estimated=cov_water_ok,
        acrylonitrile_coverage_missing=cov_acn_missing,
        no_new_fixed_transport_pairs=(gas_n == 0 and liquid_n == 0),
        provenance_field_split_ok=split_ok,
        fixture_results=tuple(fixtures),
    )


def phase18g_batch_rows() -> Tuple[dict, ...]:
    return tuple({
        "solute_id": r.solute_id,
        "name": r.name,
        "formula": r.formula,
        "CAS": r.cas_number,
        "MW_g_mol": r.MW_kg_mol * 1000.0,
        "kH_298_mol_kg_bar": r.kh_solubility_mol_kg_bar_298,
        "dlnkH_d1T_K": r.henry_temperature_coefficient_K,
        "Hpc_298_Pa_m3_mol": r.H_ref_Pa_m3_mol,
        "Fuller_volume_C": r.fuller_diffusion_volume,
        "LeBas_Vb_cm3_mol_C": r.boiling_molar_volume_cm3_mol,
        "equilibrium_confidence": "B",
        "transport_path": "Fuller + Wilke–Chang estimates (C)",
        "NIST_url": r.nist_url,
    } for r in PHASE18G_VOCS)
