"""Phase 18A migration utilities: V4 registry <-> SQLite with parity gates."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import sqlite3
from typing import Dict, Optional, Tuple

from .database import (
    PHASE18A_DATABASE_ID,
    PHASE18A_SCHEMA_VERSION,
    SCHEMA_SQL,
    DatabaseInventory,
    SQLiteAbsorberRepository,
)
from .models import DataProvenance
from .registry import AbsorberDataRegistry
from .simulation import build_phase14_registry

PHASE18A_MIGRATION_ID = "PHASE18A_SQLITE_SCHEMA_MIGRATION_2026_10_07"


def _stable_id(prefix: str, payload: str) -> str:
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _source_id(source: str) -> str:
    return _stable_id("src", source)


def _provenance_id(p: DataProvenance) -> str:
    payload = "|".join([
        p.source,
        p.method,
        p.confidence.value,
        "" if p.reference_temperature_K is None else repr(float(p.reference_temperature_K)),
        "" if p.reference_pressure_Pa is None else repr(float(p.reference_pressure_Pa)),
        p.validity_note,
    ])
    return _stable_id("prov", payload)


def _insert_provenance(con: sqlite3.Connection, p: Optional[DataProvenance]) -> Optional[str]:
    if p is None:
        return None
    sid = _source_id(p.source)
    pid = _provenance_id(p)
    con.execute(
        "INSERT OR IGNORE INTO sources(source_id, citation) VALUES (?, ?)",
        (sid, p.source),
    )
    con.execute(
        """
        INSERT OR IGNORE INTO provenance(
            provenance_id, source_id, method, confidence,
            reference_temperature_K, reference_pressure_Pa, validity_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pid, sid, p.method, p.confidence.value,
            p.reference_temperature_K, p.reference_pressure_Pa, p.validity_note,
        ),
    )
    return pid


def create_empty_database(path: str | Path, *, overwrite: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"Database already exists: {path}")
        path.unlink()
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(SCHEMA_SQL)
        con.executemany(
            "INSERT INTO schema_metadata(key, value) VALUES (?, ?)",
            [
                ("database_id", PHASE18A_DATABASE_ID),
                ("schema_version", PHASE18A_SCHEMA_VERSION),
                ("migration_id", PHASE18A_MIGRATION_ID),
            ],
        )
        con.commit()
    return path


def migrate_registry_to_sqlite(
    registry: AbsorberDataRegistry,
    path: str | Path,
    *,
    overwrite: bool = True,
    snapshot_id: str = "PHASE17_CURRENT_CATALOG",
) -> SQLiteAbsorberRepository:
    """Transactionally write one registry snapshot to SQLite."""
    path = create_empty_database(path, overwrite=overwrite)
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("INSERT INTO schema_metadata(key, value) VALUES (?, ?)", ("registry_reference_id", registry.reference_id or ""))
        con.execute("INSERT INTO schema_metadata(key, value) VALUES (?, ?)", ("data_snapshot_id", snapshot_id))

        for item in registry.solutes.values():
            con.execute(
                """
                INSERT INTO solutes(
                    solute_id,name,MW_kg_mol,carbon_atoms,formula,cas_number,
                    fuller_diffusion_volume,boiling_molar_volume_cm3_mol,provenance_id
                ) VALUES (?,?,?,?,?,?,?,?,NULL)
                """,
                (item.id,item.name,item.MW_kg_mol,item.carbon_atoms,item.formula,item.cas_number,
                 item.fuller_diffusion_volume,item.boiling_molar_volume_cm3_mol),
            )

        for item in registry.carriers.values():
            pid = _insert_provenance(con, item.provenance)
            con.execute(
                """INSERT INTO carrier_gases VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (item.id,item.name,item.MW_kg_mol,item.viscosity_model,item.mu_Pa_s,
                 item.mu_ref_Pa_s,item.T_ref_K,item.sutherland_S_K,item.fuller_diffusion_volume,pid),
            )

        for item in registry.solvents.values():
            pid = _insert_provenance(con, item.provenance)
            con.execute(
                """INSERT INTO solvents VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (item.id,item.name,item.MW_kg_mol,item.property_model,item.property_model_id,
                 item.rho_kg_m3,item.mu_Pa_s,item.sigma_N_m,item.wilke_chang_association_factor,pid),
            )

        for item in registry.packings.values():
            pid = _insert_provenance(con, item.provenance)
            con.execute(
                """INSERT INTO packings VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (item.id,item.name,item.packing_class,item.area_m2_m3,item.nominal_size_m,
                 item.void_fraction,item.critical_surface_tension_N_m,item.pressure_drop_psi,
                 item.packing_factor_ft_inv,item.packing_factor_basis,pid),
            )

        for item in registry.gas_transport_pairs.values():
            pid = _insert_provenance(con, item.provenance)
            con.execute(
                """INSERT INTO gas_transport_pairs VALUES (?,?,?,?,?,?,?)""",
                (item.solute_id,item.carrier_id,item.D_ref_m2_s,item.T_ref_K,item.P_ref_Pa,item.model,pid),
            )

        for item in registry.liquid_transport_pairs.values():
            pid = _insert_provenance(con, item.provenance)
            con.execute(
                """INSERT INTO liquid_transport_pairs VALUES (?,?,?,?,?,?)""",
                (item.solute_id,item.solvent_id,item.D_ref_m2_s,item.T_ref_K,item.model,pid),
            )

        for item in registry.equilibrium_pairs.values():
            pid = _insert_provenance(con, item.provenance)
            con.execute(
                """INSERT INTO equilibrium_pairs VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (item.solute_id,item.solvent_id,item.model,item.H_ref_Pa_m3_mol,item.T_ref_K,
                 item.temperature_coefficient_K,item.m_y_over_x,item.validity_temperature_min_K,
                 item.validity_temperature_max_K,item.validity_note,pid),
            )
        con.commit()
    return SQLiteAbsorberRepository(path)


def build_phase18a_source_registry() -> AbsorberDataRegistry:
    """Return the current Phase 17 engineering catalog used as migration source."""
    return build_phase14_registry()


def build_phase18a_database(path: str | Path, *, overwrite: bool = True) -> SQLiteAbsorberRepository:
    return migrate_registry_to_sqlite(
        build_phase18a_source_registry(), path, overwrite=overwrite,
        snapshot_id="PHASE17_ENGINEERING_CATALOG_2026_10_07",
    )


@dataclass(frozen=True)
class MigrationParityReport:
    expected_inventory: Dict[str, int]
    actual_inventory: DatabaseInventory
    registry_reference_id_match: bool
    dictionary_parity: Dict[str, bool]
    sqlite_integrity: str
    foreign_key_violations: Tuple[Tuple, ...]

    @property
    def pass_gate(self) -> bool:
        inventory_match = (
            self.expected_inventory["solutes"] == self.actual_inventory.solutes
            and self.expected_inventory["carriers"] == self.actual_inventory.carriers
            and self.expected_inventory["solvents"] == self.actual_inventory.solvents
            and self.expected_inventory["packings"] == self.actual_inventory.packings
            and self.expected_inventory["gas_transport_pairs"] == self.actual_inventory.gas_transport_pairs
            and self.expected_inventory["liquid_transport_pairs"] == self.actual_inventory.liquid_transport_pairs
            and self.expected_inventory["equilibrium_pairs"] == self.actual_inventory.equilibrium_pairs
        )
        return (
            inventory_match
            and self.registry_reference_id_match
            and all(self.dictionary_parity.values())
            and self.sqlite_integrity.lower() == "ok"
            and not self.foreign_key_violations
        )


def compare_registry_to_sqlite(
    expected: AbsorberDataRegistry,
    repository: SQLiteAbsorberRepository,
) -> MigrationParityReport:
    actual = repository.load_registry()
    expected_counts = expected.inventory_counts()
    parity = {
        "solutes": expected.solutes == actual.solutes,
        "carriers": expected.carriers == actual.carriers,
        "solvents": expected.solvents == actual.solvents,
        "packings": expected.packings == actual.packings,
        "gas_transport_pairs": expected.gas_transport_pairs == actual.gas_transport_pairs,
        "liquid_transport_pairs": expected.liquid_transport_pairs == actual.liquid_transport_pairs,
        "equilibrium_pairs": expected.equilibrium_pairs == actual.equilibrium_pairs,
    }
    return MigrationParityReport(
        expected_inventory=expected_counts,
        actual_inventory=repository.inventory(),
        registry_reference_id_match=(expected.reference_id == actual.reference_id),
        dictionary_parity=parity,
        sqlite_integrity=repository.integrity_check(),
        foreign_key_violations=repository.foreign_key_violations(),
    )
