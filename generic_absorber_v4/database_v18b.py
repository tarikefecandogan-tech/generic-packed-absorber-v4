"""Phase 18B — structured source/provenance engineering database layer.

Phase 18A proved that the current engineering registry can be represented in
SQLite without changing solver results. Phase 18B enriches that database with
structured bibliographic metadata, property-scope usage links and source-quality
coverage diagnostics. The production solver still uses the verified Python
registry by default; this phase is data-governance infrastructure.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import sqlite3
from typing import Dict, Iterable, Optional, Tuple

from .database import DatabaseInventory, SQLiteAbsorberRepository
from .models import DataProvenance
from .registry import AbsorberDataRegistry
from .database_migration import build_phase18a_source_registry
from .source_metadata import metadata_for_citation
from .vdc_water import FULLER_SOURCE, WILKE_CHANG_SOURCE

PHASE18B_SCHEMA_VERSION = "18B.1"
PHASE18B_DATABASE_ID = "GENERIC_ABSORBER_ENGINEERING_DB_PHASE18B_2026_10_07"
PHASE18B_PROVENANCE_ID = "PHASE18B_STRUCTURED_PROVENANCE_2026_10_07"

SCHEMA_SQL_18B = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    citation TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    title TEXT,
    authors TEXT,
    publication_year INTEGER,
    journal_or_publisher TEXT,
    url TEXT,
    doi TEXT,
    accessed_on TEXT,
    evidence_role TEXT NOT NULL,
    quality_note TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS provenance (
    provenance_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    method TEXT NOT NULL,
    confidence TEXT NOT NULL CHECK (confidence IN ('A','B','C','D')),
    resolution_tier TEXT,
    reference_temperature_K REAL,
    reference_pressure_Pa REAL,
    validity_temperature_min_K REAL,
    validity_temperature_max_K REAL,
    validity_pressure_min_Pa REAL,
    validity_pressure_max_Pa REAL,
    composition_validity_note TEXT NOT NULL DEFAULT '',
    validity_note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS provenance_usage (
    usage_id TEXT PRIMARY KEY,
    provenance_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    property_scope TEXT NOT NULL,
    property_name TEXT,
    unit TEXT,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id),
    UNIQUE (provenance_id, entity_type, entity_key, property_scope, property_name)
);

CREATE TABLE IF NOT EXISTS solutes (
    solute_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    MW_kg_mol REAL NOT NULL CHECK (MW_kg_mol > 0),
    carbon_atoms INTEGER NOT NULL DEFAULT 0 CHECK (carbon_atoms >= 0),
    formula TEXT,
    cas_number TEXT,
    fuller_diffusion_volume REAL,
    boiling_molar_volume_cm3_mol REAL,
    provenance_id TEXT,
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS carrier_gases (
    carrier_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    MW_kg_mol REAL NOT NULL CHECK (MW_kg_mol > 0),
    viscosity_model TEXT NOT NULL CHECK (viscosity_model IN ('sutherland','constant')),
    mu_Pa_s REAL,
    mu_ref_Pa_s REAL,
    T_ref_K REAL,
    sutherland_S_K REAL,
    fuller_diffusion_volume REAL,
    provenance_id TEXT,
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS solvents (
    solvent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    MW_kg_mol REAL NOT NULL CHECK (MW_kg_mol > 0),
    property_model TEXT NOT NULL CHECK (property_model IN ('correlation','constant','pseudo_solvent')),
    property_model_id TEXT,
    rho_kg_m3 REAL,
    mu_Pa_s REAL,
    sigma_N_m REAL,
    wilke_chang_association_factor REAL,
    provenance_id TEXT,
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS packings (
    packing_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    packing_class TEXT NOT NULL CHECK (packing_class = 'random'),
    area_m2_m3 REAL NOT NULL CHECK (area_m2_m3 > 0),
    nominal_size_m REAL NOT NULL CHECK (nominal_size_m > 0),
    void_fraction REAL NOT NULL CHECK (void_fraction > 0 AND void_fraction < 1),
    critical_surface_tension_N_m REAL NOT NULL CHECK (critical_surface_tension_N_m > 0),
    pressure_drop_psi REAL NOT NULL CHECK (pressure_drop_psi > 0),
    packing_factor_ft_inv REAL,
    packing_factor_basis TEXT NOT NULL CHECK (packing_factor_basis IN ('empirical','literature','geometric_fallback')),
    provenance_id TEXT,
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS gas_transport_pairs (
    solute_id TEXT NOT NULL,
    carrier_id TEXT NOT NULL,
    D_ref_m2_s REAL NOT NULL CHECK (D_ref_m2_s > 0),
    T_ref_K REAL,
    P_ref_Pa REAL,
    model TEXT NOT NULL CHECK (model IN ('fixed_reference','fuller')),
    provenance_id TEXT,
    PRIMARY KEY (solute_id, carrier_id),
    FOREIGN KEY (solute_id) REFERENCES solutes(solute_id),
    FOREIGN KEY (carrier_id) REFERENCES carrier_gases(carrier_id),
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS liquid_transport_pairs (
    solute_id TEXT NOT NULL,
    solvent_id TEXT NOT NULL,
    D_ref_m2_s REAL NOT NULL CHECK (D_ref_m2_s > 0),
    T_ref_K REAL,
    model TEXT NOT NULL CHECK (model IN ('fixed_reference','wilke_chang')),
    provenance_id TEXT,
    PRIMARY KEY (solute_id, solvent_id),
    FOREIGN KEY (solute_id) REFERENCES solutes(solute_id),
    FOREIGN KEY (solvent_id) REFERENCES solvents(solvent_id),
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS equilibrium_pairs (
    solute_id TEXT NOT NULL,
    solvent_id TEXT NOT NULL,
    model TEXT NOT NULL CHECK (model IN ('henry_pc','linear_m','tabulated','reactive','nonideal_unsupported','no_data')),
    H_ref_Pa_m3_mol REAL,
    T_ref_K REAL,
    temperature_coefficient_K REAL,
    m_y_over_x REAL,
    validity_temperature_min_K REAL,
    validity_temperature_max_K REAL,
    validity_note TEXT NOT NULL DEFAULT '',
    provenance_id TEXT,
    PRIMARY KEY (solute_id, solvent_id),
    FOREIGN KEY (solute_id) REFERENCES solutes(solute_id),
    FOREIGN KEY (solvent_id) REFERENCES solvents(solvent_id),
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE INDEX IF NOT EXISTS idx_equilibrium_solvent ON equilibrium_pairs(solvent_id);
CREATE INDEX IF NOT EXISTS idx_liquid_transport_solvent ON liquid_transport_pairs(solvent_id);
CREATE INDEX IF NOT EXISTS idx_gas_transport_carrier ON gas_transport_pairs(carrier_id);
CREATE INDEX IF NOT EXISTS idx_usage_entity ON provenance_usage(entity_type, entity_key);
CREATE INDEX IF NOT EXISTS idx_usage_property_scope ON provenance_usage(property_scope);
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_role ON sources(evidence_role);
"""


def _stable_id(prefix: str, payload: str) -> str:
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _source_id(citation: str) -> str:
    return _stable_id("src", citation)


def _provenance_id(p: DataProvenance) -> str:
    payload = "|".join([
        p.source,
        p.method,
        p.confidence.value,
        "" if p.reference_temperature_K is None else repr(float(p.reference_temperature_K)),
        "" if p.reference_pressure_Pa is None else repr(float(p.reference_pressure_Pa)),
        p.validity_note or "",
    ])
    return _stable_id("prov", payload)


def _usage_id(provenance_id: str, entity_type: str, entity_key: str, property_scope: str, property_name: Optional[str]) -> str:
    return _stable_id("use", "|".join([provenance_id, entity_type, entity_key, property_scope, property_name or ""]))


def create_empty_phase18b_database(path: str | Path, *, overwrite: bool = True) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and overwrite:
        path.unlink()
    if path.exists():
        raise FileExistsError(path)
    with sqlite3.connect(path) as con:
        con.executescript(SCHEMA_SQL_18B)
        con.execute("INSERT INTO schema_metadata(key,value) VALUES (?,?)", ("schema_version", PHASE18B_SCHEMA_VERSION))
        con.execute("INSERT INTO schema_metadata(key,value) VALUES (?,?)", ("database_id", PHASE18B_DATABASE_ID))
        con.execute("INSERT INTO schema_metadata(key,value) VALUES (?,?)", ("provenance_architecture_id", PHASE18B_PROVENANCE_ID))
        con.execute("INSERT INTO schema_metadata(key,value) VALUES (?,?)", ("created_on", "2026-10-07"))
        con.commit()
    return path


def _insert_source(con: sqlite3.Connection, citation: str) -> str:
    sid = _source_id(citation)
    md = metadata_for_citation(citation)
    con.execute(
        """
        INSERT OR IGNORE INTO sources(
            source_id,citation,source_type,title,authors,publication_year,
            journal_or_publisher,url,doi,accessed_on,evidence_role,quality_note,notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (sid,citation,md.source_type,md.title,md.authors,md.publication_year,
         md.journal_or_publisher,md.url,md.doi,md.accessed_on,md.evidence_role,
         md.quality_note,md.notes),
    )
    return sid


def _resolution_tier_from_confidence(p: DataProvenance) -> str:
    method = (p.method or "").lower()
    if "fuller" in method or "wilke" in method or "estimate" in method:
        return "CORRELATION_ESTIMATE"
    if p.confidence.value == "D" or "screen" in method or "surrogate" in method:
        return "SCREENING"
    return "DATABASE"


def _insert_provenance(con: sqlite3.Connection, p: Optional[DataProvenance]) -> Optional[str]:
    if p is None:
        return None
    sid = _insert_source(con, p.source)
    pid = _provenance_id(p)
    con.execute(
        """
        INSERT OR IGNORE INTO provenance(
            provenance_id,source_id,method,confidence,resolution_tier,
            reference_temperature_K,reference_pressure_Pa,
            validity_temperature_min_K,validity_temperature_max_K,
            validity_pressure_min_Pa,validity_pressure_max_Pa,
            composition_validity_note,validity_note
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (pid,sid,p.method,p.confidence.value,_resolution_tier_from_confidence(p),
         p.reference_temperature_K,p.reference_pressure_Pa,
         None,None,None,None,"",p.validity_note or ""),
    )
    return pid


def _insert_usage(
    con: sqlite3.Connection,
    provenance_id: Optional[str],
    entity_type: str,
    entity_key: str,
    property_scope: str,
    property_name: Optional[str] = None,
    unit: Optional[str] = None,
    notes: str = "",
) -> None:
    if provenance_id is None:
        return
    uid = _usage_id(provenance_id,entity_type,entity_key,property_scope,property_name)
    con.execute(
        """INSERT OR IGNORE INTO provenance_usage
        (usage_id,provenance_id,entity_type,entity_key,property_scope,property_name,unit,notes)
        VALUES (?,?,?,?,?,?,?,?)""",
        (uid,provenance_id,entity_type,entity_key,property_scope,property_name,unit,notes),
    )


def _insert_methodology_source(
    con: sqlite3.Connection,
    citation: str,
    method: str,
    confidence: str,
    entity_key: str,
    property_scope: str,
) -> None:
    sid = _insert_source(con, citation)
    payload = "|".join([citation,method,confidence,"methodology"])
    pid = _stable_id("prov", payload)
    con.execute(
        """INSERT OR IGNORE INTO provenance(
        provenance_id,source_id,method,confidence,resolution_tier,
        reference_temperature_K,reference_pressure_Pa,
        validity_temperature_min_K,validity_temperature_max_K,
        validity_pressure_min_Pa,validity_pressure_max_Pa,
        composition_validity_note,validity_note)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid,sid,method,confidence,"CORRELATION_ESTIMATE",None,None,None,None,None,None,"",
         "Methodology source registered for fallback estimation; individual resolved values remain case dependent."),
    )
    _insert_usage(con,pid,"correlation_method",entity_key,property_scope,None,None,"Reusable estimator methodology")


def migrate_registry_to_phase18b_sqlite(
    registry: AbsorberDataRegistry,
    path: str | Path,
    *,
    overwrite: bool = True,
    snapshot_id: str = "PHASE17_ENGINEERING_CATALOG_2026_10_07",
) -> "SQLiteAbsorberRepositoryV18B":
    path = create_empty_phase18b_database(path, overwrite=overwrite)
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("INSERT INTO schema_metadata(key,value) VALUES (?,?)", ("registry_reference_id",registry.reference_id or ""))
        con.execute("INSERT INTO schema_metadata(key,value) VALUES (?,?)", ("data_snapshot_id",snapshot_id))
        con.execute("INSERT INTO schema_metadata(key,value) VALUES (?,?)", ("migration_parent", "PHASE18A_SCHEMA_AND_PARITY"))

        for item in registry.solutes.values():
            con.execute(
                """INSERT INTO solutes(
                solute_id,name,MW_kg_mol,carbon_atoms,formula,cas_number,
                fuller_diffusion_volume,boiling_molar_volume_cm3_mol,provenance_id)
                VALUES (?,?,?,?,?,?,?,?,NULL)""",
                (item.id,item.name,item.MW_kg_mol,item.carbon_atoms,item.formula,item.cas_number,
                 item.fuller_diffusion_volume,item.boiling_molar_volume_cm3_mol),
            )

        for item in registry.carriers.values():
            pid = _insert_provenance(con,item.provenance)
            con.execute("""INSERT INTO carrier_gases VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (item.id,item.name,item.MW_kg_mol,item.viscosity_model,item.mu_Pa_s,
                 item.mu_ref_Pa_s,item.T_ref_K,item.sutherland_S_K,item.fuller_diffusion_volume,pid))
            _insert_usage(con,pid,"carrier_gas",item.id,"bulk_properties","viscosity_and_identity",None)

        for item in registry.solvents.values():
            pid = _insert_provenance(con,item.provenance)
            con.execute("""INSERT INTO solvents VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (item.id,item.name,item.MW_kg_mol,item.property_model,item.property_model_id,
                 item.rho_kg_m3,item.mu_Pa_s,item.sigma_N_m,item.wilke_chang_association_factor,pid))
            _insert_usage(con,pid,"solvent",item.id,"bulk_properties","rho_mu_sigma_and_model",None)

        for item in registry.packings.values():
            pid = _insert_provenance(con,item.provenance)
            con.execute("""INSERT INTO packings VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (item.id,item.name,item.packing_class,item.area_m2_m3,item.nominal_size_m,
                 item.void_fraction,item.critical_surface_tension_N_m,item.pressure_drop_psi,
                 item.packing_factor_ft_inv,item.packing_factor_basis,pid))
            _insert_usage(con,pid,"packing",item.id,"packing_geometry_hydraulics","a_dp_eps_sigma_c_psi_Fp",None)

        for item in registry.gas_transport_pairs.values():
            pid = _insert_provenance(con,item.provenance)
            con.execute("""INSERT INTO gas_transport_pairs VALUES (?,?,?,?,?,?,?)""",
                (item.solute_id,item.carrier_id,item.D_ref_m2_s,item.T_ref_K,item.P_ref_Pa,item.model,pid))
            _insert_usage(con,pid,"gas_transport_pair",f"{item.solute_id}|{item.carrier_id}","transport_property","D_G","m2/s")

        for item in registry.liquid_transport_pairs.values():
            pid = _insert_provenance(con,item.provenance)
            con.execute("""INSERT INTO liquid_transport_pairs VALUES (?,?,?,?,?,?)""",
                (item.solute_id,item.solvent_id,item.D_ref_m2_s,item.T_ref_K,item.model,pid))
            _insert_usage(con,pid,"liquid_transport_pair",f"{item.solute_id}|{item.solvent_id}","transport_property","D_L","m2/s")

        for item in registry.equilibrium_pairs.values():
            pid = _insert_provenance(con,item.provenance)
            con.execute("""INSERT INTO equilibrium_pairs VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (item.solute_id,item.solvent_id,item.model,item.H_ref_Pa_m3_mol,item.T_ref_K,
                 item.temperature_coefficient_K,item.m_y_over_x,item.validity_temperature_min_K,
                 item.validity_temperature_max_K,item.validity_note,pid))
            pname = "H_pc" if item.model == "henry_pc" else "m_y_over_x"
            punit = "Pa m3/mol" if item.model == "henry_pc" else "dimensionless"
            _insert_usage(con,pid,"equilibrium_pair",f"{item.solute_id}|{item.solvent_id}","equilibrium_property",pname,punit)
            if pid is not None:
                con.execute(
                    """UPDATE provenance SET validity_temperature_min_K=?, validity_temperature_max_K=?
                    WHERE provenance_id=?""",
                    (item.validity_temperature_min_K,item.validity_temperature_max_K,pid),
                )

        # Methodology sources used by the resolver when measured pair data are absent.
        _insert_methodology_source(con,FULLER_SOURCE,"Fuller gas diffusivity correlation","C","fuller_gas_diffusivity","gas_transport_estimation")
        _insert_methodology_source(con,WILKE_CHANG_SOURCE,"Wilke–Chang liquid diffusivity correlation","C","wilke_chang_liquid_diffusivity","liquid_transport_estimation")
        con.commit()
    return SQLiteAbsorberRepositoryV18B(path)


def build_phase18b_database(path: str | Path, *, overwrite: bool = True) -> "SQLiteAbsorberRepositoryV18B":
    return migrate_registry_to_phase18b_sqlite(build_phase18a_source_registry(),path,overwrite=overwrite)


@dataclass(frozen=True)
class ProvenanceCoverageSummary:
    sources: int
    sources_with_type: int
    sources_with_title: int
    sources_with_url_or_doi: int
    sources_with_year: int
    provenance_records: int
    provenance_usage_records: int
    unresolved_source_metadata: int
    confidence_A: int
    confidence_B: int
    confidence_C: int
    confidence_D: int

    @property
    def bibliographic_link_fraction(self) -> float:
        return 0.0 if self.sources == 0 else self.sources_with_url_or_doi / self.sources


@dataclass(frozen=True)
class Phase18BParityReport:
    core_registry_parity: Dict[str,bool]
    sqlite_integrity: str
    foreign_key_violations: Tuple[Tuple,...]
    coverage: ProvenanceCoverageSummary

    @property
    def pass_gate(self) -> bool:
        return (
            all(self.core_registry_parity.values())
            and self.sqlite_integrity.lower() == "ok"
            and not self.foreign_key_violations
            and self.coverage.sources > 0
            and self.coverage.provenance_usage_records > 0
            and self.coverage.unresolved_source_metadata == 0
        )


class SQLiteAbsorberRepositoryV18B(SQLiteAbsorberRepository):
    """Phase 18B repository. Core registry loading stays Phase-18A compatible."""

    def provenance_coverage(self) -> ProvenanceCoverageSummary:
        with self.connect() as con:
            src = con.execute("""SELECT
                COUNT(*) AS n,
                SUM(CASE WHEN source_type IS NOT NULL AND source_type <> '' THEN 1 ELSE 0 END) AS typed,
                SUM(CASE WHEN title IS NOT NULL AND title <> '' THEN 1 ELSE 0 END) AS titled,
                SUM(CASE WHEN (url IS NOT NULL AND url <> '') OR (doi IS NOT NULL AND doi <> '') THEN 1 ELSE 0 END) AS linked,
                SUM(CASE WHEN publication_year IS NOT NULL THEN 1 ELSE 0 END) AS yeared,
                SUM(CASE WHEN source_type='unclassified' THEN 1 ELSE 0 END) AS unresolved
                FROM sources""").fetchone()
            prov_n = int(con.execute("SELECT COUNT(*) FROM provenance").fetchone()[0])
            use_n = int(con.execute("SELECT COUNT(*) FROM provenance_usage").fetchone()[0])
            conf = {r[0]:int(r[1]) for r in con.execute("SELECT confidence,COUNT(*) FROM provenance GROUP BY confidence")}
        return ProvenanceCoverageSummary(
            sources=int(src["n"] or 0),sources_with_type=int(src["typed"] or 0),
            sources_with_title=int(src["titled"] or 0),sources_with_url_or_doi=int(src["linked"] or 0),
            sources_with_year=int(src["yeared"] or 0),provenance_records=prov_n,
            provenance_usage_records=use_n,unresolved_source_metadata=int(src["unresolved"] or 0),
            confidence_A=conf.get("A",0),confidence_B=conf.get("B",0),confidence_C=conf.get("C",0),confidence_D=conf.get("D",0),
        )

    def list_sources_detailed(self) -> Tuple[dict,...]:
        with self.connect() as con:
            rows = con.execute("""
                SELECT s.*, COUNT(DISTINCT p.provenance_id) AS provenance_records,
                       COUNT(u.usage_id) AS usage_records
                FROM sources s
                LEFT JOIN provenance p ON p.source_id=s.source_id
                LEFT JOIN provenance_usage u ON u.provenance_id=p.provenance_id
                GROUP BY s.source_id
                ORDER BY s.source_type,s.publication_year,s.source_id
            """).fetchall()
        return tuple(dict(r) for r in rows)

    def list_provenance_usage(self) -> Tuple[dict,...]:
        with self.connect() as con:
            rows = con.execute("""
                SELECT u.entity_type,u.entity_key,u.property_scope,u.property_name,u.unit,
                       p.method,p.confidence,p.resolution_tier,p.reference_temperature_K,
                       p.reference_pressure_Pa,p.validity_temperature_min_K,p.validity_temperature_max_K,
                       p.validity_note,s.source_type,s.evidence_role,s.title,s.citation,s.url,s.doi
                FROM provenance_usage u
                JOIN provenance p ON p.provenance_id=u.provenance_id
                JOIN sources s ON s.source_id=p.source_id
                ORDER BY u.entity_type,u.entity_key,u.property_scope,u.property_name
            """).fetchall()
        return tuple(dict(r) for r in rows)

    def list_source_type_summary(self) -> Tuple[dict,...]:
        with self.connect() as con:
            rows = con.execute("""
                SELECT source_type,evidence_role,COUNT(*) AS sources
                FROM sources GROUP BY source_type,evidence_role
                ORDER BY source_type,evidence_role
            """).fetchall()
        return tuple(dict(r) for r in rows)


def compare_registry_to_phase18b_sqlite(expected: AbsorberDataRegistry, repository: SQLiteAbsorberRepositoryV18B) -> Phase18BParityReport:
    actual = repository.load_registry()
    parity = {
        "solutes": expected.solutes == actual.solutes,
        "carriers": expected.carriers == actual.carriers,
        "solvents": expected.solvents == actual.solvents,
        "packings": expected.packings == actual.packings,
        "gas_transport_pairs": expected.gas_transport_pairs == actual.gas_transport_pairs,
        "liquid_transport_pairs": expected.liquid_transport_pairs == actual.liquid_transport_pairs,
        "equilibrium_pairs": expected.equilibrium_pairs == actual.equilibrium_pairs,
        "registry_reference_id": expected.reference_id == actual.reference_id,
    }
    return Phase18BParityReport(
        core_registry_parity=parity,
        sqlite_integrity=repository.integrity_check(),
        foreign_key_violations=repository.foreign_key_violations(),
        coverage=repository.provenance_coverage(),
    )
