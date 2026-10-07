"""Phase 18A — SQLite engineering database schema and repository layer.

This module introduces a persistent, relational representation of the V4 data
objects without changing the solver's active data source.  Phase 18A is a
migration architecture phase: the physics engine continues to use
``AbsorberDataRegistry`` by default while SQLite round-trip parity is proven.

Design rules
------------
* Standard-library ``sqlite3`` only; no new runtime dependency.
* Foreign keys are enabled on every connection.
* Sources and provenance are normalized separately.
* Missing values stay NULL; no engineering values are invented by the DB layer.
* Repository reads reconstruct the existing immutable dataclasses exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Dict, Iterable, Optional, Tuple

from .models import (
    CarrierGasSpec,
    ConfidenceClass,
    DataProvenance,
    EquilibriumPair,
    GasTransportPair,
    LiquidTransportPair,
    PackingSpec,
    SoluteSpec,
    SolventSpec,
)
from .registry import AbsorberDataRegistry

PHASE18A_SCHEMA_VERSION = "18A.1"
PHASE18A_DATABASE_ID = "GENERIC_ABSORBER_ENGINEERING_DB_PHASE18A_2026_10_07"

SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    citation TEXT NOT NULL UNIQUE,
    source_type TEXT,
    title TEXT,
    url TEXT,
    doi TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS provenance (
    provenance_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    method TEXT NOT NULL,
    confidence TEXT NOT NULL CHECK (confidence IN ('A','B','C','D')),
    reference_temperature_K REAL,
    reference_pressure_Pa REAL,
    validity_note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
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
"""


@dataclass(frozen=True)
class DatabaseInventory:
    solutes: int
    carriers: int
    solvents: int
    packings: int
    gas_transport_pairs: int
    liquid_transport_pairs: int
    equilibrium_pairs: int
    sources: int
    provenance_records: int

    @property
    def engineering_records(self) -> int:
        return (
            self.solutes
            + self.carriers
            + self.solvents
            + self.packings
            + self.gas_transport_pairs
            + self.liquid_transport_pairs
            + self.equilibrium_pairs
        )


class SQLiteAbsorberRepository:
    """Read-oriented repository over the Phase 18A SQLite schema."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        if not self.database_path.exists():
            raise FileNotFoundError(f"Absorber database does not exist: {self.database_path}")

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.database_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def metadata(self) -> Dict[str, str]:
        with self.connect() as con:
            return {
                row["key"]: row["value"]
                for row in con.execute("SELECT key, value FROM schema_metadata ORDER BY key")
            }

    def integrity_check(self) -> str:
        with self.connect() as con:
            return str(con.execute("PRAGMA integrity_check").fetchone()[0])

    def foreign_key_violations(self) -> Tuple[Tuple, ...]:
        with self.connect() as con:
            rows = con.execute("PRAGMA foreign_key_check").fetchall()
            return tuple(tuple(row) for row in rows)

    def inventory(self) -> DatabaseInventory:
        tables = {
            "solutes": "solutes",
            "carriers": "carrier_gases",
            "solvents": "solvents",
            "packings": "packings",
            "gas_transport_pairs": "gas_transport_pairs",
            "liquid_transport_pairs": "liquid_transport_pairs",
            "equilibrium_pairs": "equilibrium_pairs",
            "sources": "sources",
            "provenance_records": "provenance",
        }
        with self.connect() as con:
            counts = {
                key: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for key, table in tables.items()
            }
        return DatabaseInventory(**counts)

    def _provenance(self, con: sqlite3.Connection, provenance_id: Optional[str]) -> Optional[DataProvenance]:
        if provenance_id is None:
            return None
        row = con.execute(
            """
            SELECT p.*, s.citation
            FROM provenance p
            JOIN sources s ON s.source_id = p.source_id
            WHERE p.provenance_id = ?
            """,
            (provenance_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Broken provenance reference: {provenance_id}")
        return DataProvenance(
            source=row["citation"],
            method=row["method"],
            confidence=ConfidenceClass(row["confidence"]),
            reference_temperature_K=row["reference_temperature_K"],
            reference_pressure_Pa=row["reference_pressure_Pa"],
            validity_note=row["validity_note"] or "",
        )

    def load_registry(self) -> AbsorberDataRegistry:
        """Reconstruct the canonical V4 registry from SQLite records."""
        meta = self.metadata()
        registry = AbsorberDataRegistry(reference_id=meta.get("registry_reference_id"))
        with self.connect() as con:
            for row in con.execute("SELECT * FROM solutes ORDER BY solute_id"):
                registry.register_solute(SoluteSpec(
                    id=row["solute_id"], name=row["name"], MW_kg_mol=row["MW_kg_mol"],
                    carbon_atoms=row["carbon_atoms"], formula=row["formula"],
                    cas_number=row["cas_number"], fuller_diffusion_volume=row["fuller_diffusion_volume"],
                    boiling_molar_volume_cm3_mol=row["boiling_molar_volume_cm3_mol"],
                ))

            for row in con.execute("SELECT * FROM carrier_gases ORDER BY carrier_id"):
                registry.register_carrier(CarrierGasSpec(
                    id=row["carrier_id"], name=row["name"], MW_kg_mol=row["MW_kg_mol"],
                    viscosity_model=row["viscosity_model"], mu_Pa_s=row["mu_Pa_s"],
                    mu_ref_Pa_s=row["mu_ref_Pa_s"], T_ref_K=row["T_ref_K"],
                    sutherland_S_K=row["sutherland_S_K"],
                    fuller_diffusion_volume=row["fuller_diffusion_volume"],
                    provenance=self._provenance(con, row["provenance_id"]),
                ))

            for row in con.execute("SELECT * FROM solvents ORDER BY solvent_id"):
                registry.register_solvent(SolventSpec(
                    id=row["solvent_id"], name=row["name"], MW_kg_mol=row["MW_kg_mol"],
                    property_model=row["property_model"], property_model_id=row["property_model_id"],
                    rho_kg_m3=row["rho_kg_m3"], mu_Pa_s=row["mu_Pa_s"], sigma_N_m=row["sigma_N_m"],
                    wilke_chang_association_factor=row["wilke_chang_association_factor"],
                    provenance=self._provenance(con, row["provenance_id"]),
                ))

            for row in con.execute("SELECT * FROM packings ORDER BY packing_id"):
                registry.register_packing(PackingSpec(
                    id=row["packing_id"], name=row["name"], packing_class=row["packing_class"],
                    area_m2_m3=row["area_m2_m3"], nominal_size_m=row["nominal_size_m"],
                    void_fraction=row["void_fraction"],
                    critical_surface_tension_N_m=row["critical_surface_tension_N_m"],
                    pressure_drop_psi=row["pressure_drop_psi"],
                    packing_factor_ft_inv=row["packing_factor_ft_inv"],
                    packing_factor_basis=row["packing_factor_basis"],
                    provenance=self._provenance(con, row["provenance_id"]),
                ))

            for row in con.execute("SELECT * FROM gas_transport_pairs ORDER BY solute_id, carrier_id"):
                registry.register_gas_transport_pair(GasTransportPair(
                    solute_id=row["solute_id"], carrier_id=row["carrier_id"],
                    D_ref_m2_s=row["D_ref_m2_s"], T_ref_K=row["T_ref_K"], P_ref_Pa=row["P_ref_Pa"],
                    model=row["model"], provenance=self._provenance(con, row["provenance_id"]),
                ))

            for row in con.execute("SELECT * FROM liquid_transport_pairs ORDER BY solute_id, solvent_id"):
                registry.register_liquid_transport_pair(LiquidTransportPair(
                    solute_id=row["solute_id"], solvent_id=row["solvent_id"],
                    D_ref_m2_s=row["D_ref_m2_s"], T_ref_K=row["T_ref_K"], model=row["model"],
                    provenance=self._provenance(con, row["provenance_id"]),
                ))

            for row in con.execute("SELECT * FROM equilibrium_pairs ORDER BY solute_id, solvent_id"):
                registry.register_equilibrium_pair(EquilibriumPair(
                    solute_id=row["solute_id"], solvent_id=row["solvent_id"], model=row["model"],
                    H_ref_Pa_m3_mol=row["H_ref_Pa_m3_mol"], T_ref_K=row["T_ref_K"],
                    temperature_coefficient_K=row["temperature_coefficient_K"], m_y_over_x=row["m_y_over_x"],
                    validity_temperature_min_K=row["validity_temperature_min_K"],
                    validity_temperature_max_K=row["validity_temperature_max_K"],
                    validity_note=row["validity_note"] or "",
                    provenance=self._provenance(con, row["provenance_id"]),
                ))
        return registry

    def list_sources(self) -> Tuple[dict, ...]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT s.source_id, s.citation, COUNT(p.provenance_id) AS provenance_uses
                FROM sources s
                LEFT JOIN provenance p ON p.source_id = s.source_id
                GROUP BY s.source_id, s.citation
                ORDER BY s.source_id
                """
            ).fetchall()
            return tuple(dict(row) for row in rows)

    def list_equilibrium_pairs(self) -> Tuple[dict, ...]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT e.solute_id, e.solvent_id, e.model, e.H_ref_Pa_m3_mol,
                       e.T_ref_K, e.temperature_coefficient_K, e.m_y_over_x,
                       p.confidence, s.citation AS source
                FROM equilibrium_pairs e
                LEFT JOIN provenance p ON p.provenance_id = e.provenance_id
                LEFT JOIN sources s ON s.source_id = p.source_id
                ORDER BY e.solute_id, e.solvent_id
                """
            ).fetchall()
            return tuple(dict(row) for row in rows)
