"""Phase 18F — controlled chemical-database expansion framework.

This module provides a versioned import contract, dry-run validation and an
atomic SQLite writer for adding chemical/pair data to the Phase 18B engineering
database.  It deliberately does *not* invent missing scientific data and it
never performs absorber physics.

Safety / governance principles
-------------------------------
* append-only by default; replacement must be explicit,
* every imported engineering record requires provenance,
* A/B literature/database claims require a bibliographic locator (DOI or URL),
* pair references must point to existing or same-package entities,
* model-specific fields are validated before SQLite is touched,
* commit is one transaction; failure rolls the whole package back,
* dry-run is the default API behavior,
* the Streamlit product uses this module in dry-run mode only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .database_v18b import PHASE18B_SCHEMA_VERSION, SQLiteAbsorberRepositoryV18B
from .database_explorer import CoverageStatus, DatabaseExplorer

PHASE18F_EXPANSION_FRAMEWORK_ID = "PHASE18F_CHEMICAL_EXPANSION_FRAMEWORK_2026_10_07"
PHASE18F_IMPORT_CONTRACT_VERSION = "18F.1"
PHASE18F_TEMPLATE_FILENAME = "chemical_import_template.json"


class ImportSeverity(str, Enum):
    BLOCK = "BLOCK"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class ImportIssue:
    severity: ImportSeverity
    code: str
    message: str
    location: str = "package"


@dataclass(frozen=True)
class ImportInventoryDelta:
    solutes: int = 0
    carriers: int = 0
    solvents: int = 0
    gas_transport_pairs: int = 0
    liquid_transport_pairs: int = 0
    equilibrium_pairs: int = 0
    sources: int = 0
    provenance_records: int = 0


@dataclass(frozen=True)
class ImportValidationReport:
    package_id: str
    contract_version: str
    issues: Tuple[ImportIssue, ...]
    planned_delta: ImportInventoryDelta
    readiness: Tuple[dict, ...] = ()

    @property
    def blocking_issues(self) -> Tuple[ImportIssue, ...]:
        return tuple(x for x in self.issues if x.severity == ImportSeverity.BLOCK)

    @property
    def warnings(self) -> Tuple[ImportIssue, ...]:
        return tuple(x for x in self.issues if x.severity == ImportSeverity.WARNING)

    @property
    def pass_validation(self) -> bool:
        return not self.blocking_issues


@dataclass(frozen=True)
class ImportExecutionReport:
    validation: ImportValidationReport
    committed: bool
    dry_run: bool
    database_path: str
    backup_path: Optional[str]
    before_inventory: dict
    after_inventory: dict
    database_integrity: str
    foreign_key_violations: Tuple[Tuple, ...]

    @property
    def pass_import(self) -> bool:
        if not self.validation.pass_validation:
            return False
        if self.dry_run:
            return not self.committed
        return (
            self.committed
            and self.database_integrity.lower() == "ok"
            and not self.foreign_key_violations
        )


@dataclass(frozen=True)
class Phase18FGateReport:
    dry_run_valid: bool
    dry_run_unchanged: bool
    committed_to_temporary_copy: bool
    temporary_inventory_delta_ok: bool
    imported_coverage_resolvable: bool
    invalid_package_blocked: bool
    collision_blocked: bool
    rollback_unchanged: bool
    primary_database_unchanged: bool
    integrity: str
    foreign_key_violations: int

    @property
    def pass_gate(self) -> bool:
        return all((
            self.dry_run_valid,
            self.dry_run_unchanged,
            self.committed_to_temporary_copy,
            self.temporary_inventory_delta_ok,
            self.imported_coverage_resolvable,
            self.invalid_package_blocked,
            self.collision_blocked,
            self.rollback_unchanged,
            self.primary_database_unchanged,
            self.integrity.lower() == "ok",
            self.foreign_key_violations == 0,
        ))


class ChemicalImportError(RuntimeError):
    pass


class ChemicalImportValidationError(ChemicalImportError):
    def __init__(self, report: ImportValidationReport):
        self.report = report
        msg = "; ".join(f"{i.code}: {i.message}" for i in report.blocking_issues)
        super().__init__(msg or "Chemical import package failed validation.")


def _hash_file(path: str | Path) -> str:
    h = sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join("" if x is None else str(x) for x in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _as_dict(package: Mapping[str, Any] | str | Path) -> Dict[str, Any]:
    if isinstance(package, Mapping):
        return json.loads(json.dumps(package))  # deep-ish copy, JSON contract only
    path = Path(package)
    return json.loads(path.read_text(encoding="utf-8"))


def chemical_import_template() -> Dict[str, Any]:
    """Return a documentation-oriented template, not design data.

    Numeric values are intentionally null so the template cannot be mistaken for
    a real chemical-property record.
    """
    return {
        "contract_version": PHASE18F_IMPORT_CONTRACT_VERSION,
        "package_id": "REPLACE_WITH_UNIQUE_PACKAGE_ID",
        "description": "One auditable chemical-data expansion package.",
        "sources": [
            {
                "source_key": "SRC_IDENTITY",
                "citation": "Full literature/database citation",
                "source_type": "primary_literature_or_curated_database",
                "title": "Source title",
                "authors": "Authors",
                "publication_year": None,
                "journal_or_publisher": None,
                "url": "https://...",
                "doi": None,
                "accessed_on": "YYYY-MM-DD",
                "evidence_role": "PRIMARY_OR_CURATED",
                "quality_note": "Why this source is appropriate.",
                "notes": "",
            }
        ],
        "provenance": [
            {
                "provenance_key": "PROV_IDENTITY",
                "source_key": "SRC_IDENTITY",
                "method": "reported / compiled / correlation / screening surrogate",
                "confidence": "B",
                "resolution_tier": "DATABASE",
                "reference_temperature_K": None,
                "reference_pressure_Pa": None,
                "validity_temperature_min_K": None,
                "validity_temperature_max_K": None,
                "validity_pressure_min_Pa": None,
                "validity_pressure_max_Pa": None,
                "composition_validity_note": "",
                "validity_note": "",
            }
        ],
        "solutes": [
            {
                "solute_id": "new_solute",
                "name": "Chemical name",
                "MW_kg_mol": None,
                "carbon_atoms": None,
                "formula": None,
                "cas_number": None,
                "fuller_diffusion_volume": None,
                "boiling_molar_volume_cm3_mol": None,
                "provenance_key": "PROV_IDENTITY",
            }
        ],
        "carriers": [],
        "solvents": [],
        "gas_transport_pairs": [],
        "liquid_transport_pairs": [],
        "equilibrium_pairs": [],
    }


def write_chemical_import_template(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chemical_import_template(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _issue(issues: list[ImportIssue], severity: ImportSeverity, code: str, message: str, location: str) -> None:
    issues.append(ImportIssue(severity, code, message, location))


def _nonempty(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _positive(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def _optional_positive(v: Any) -> bool:
    return v is None or _positive(v)


def _table_keys(con: sqlite3.Connection, table: str, cols: Sequence[str]) -> set[tuple]:
    sql = f"SELECT {', '.join(cols)} FROM {table}"
    return {tuple(r) for r in con.execute(sql)}


def _existing_state(repo: SQLiteAbsorberRepositoryV18B) -> dict:
    with repo.connect() as con:
        return {
            "solutes": {r[0] for r in con.execute("SELECT solute_id FROM solutes")},
            "carriers": {r[0] for r in con.execute("SELECT carrier_id FROM carrier_gases")},
            "solvents": {r[0] for r in con.execute("SELECT solvent_id FROM solvents")},
            "gas_pairs": _table_keys(con, "gas_transport_pairs", ("solute_id", "carrier_id")),
            "liquid_pairs": _table_keys(con, "liquid_transport_pairs", ("solute_id", "solvent_id")),
            "equilibrium_pairs": _table_keys(con, "equilibrium_pairs", ("solute_id", "solvent_id")),
            "sources": {r[0]: tuple(r[1:]) for r in con.execute(
                "SELECT citation,source_type,title,authors,publication_year,journal_or_publisher,url,doi,evidence_role FROM sources"
            )},
        }


def validate_chemical_import_package(
    package: Mapping[str, Any] | str | Path,
    repository: SQLiteAbsorberRepositoryV18B,
    *,
    allow_replace: bool = False,
) -> ImportValidationReport:
    p = _as_dict(package)
    issues: list[ImportIssue] = []

    package_id = str(p.get("package_id") or "").strip()
    contract_version = str(p.get("contract_version") or "").strip()
    if not package_id:
        _issue(issues, ImportSeverity.BLOCK, "PACKAGE_ID_REQUIRED", "package_id must be a non-empty string.", "package_id")
    if contract_version != PHASE18F_IMPORT_CONTRACT_VERSION:
        _issue(
            issues, ImportSeverity.BLOCK, "CONTRACT_VERSION_MISMATCH",
            f"Expected contract_version {PHASE18F_IMPORT_CONTRACT_VERSION!r}; found {contract_version!r}.",
            "contract_version",
        )

    meta = repository.metadata()
    if meta.get("schema_version") != PHASE18B_SCHEMA_VERSION:
        _issue(
            issues, ImportSeverity.BLOCK, "DATABASE_SCHEMA_MISMATCH",
            f"Phase 18F currently targets SQLite schema {PHASE18B_SCHEMA_VERSION}; database reports {meta.get('schema_version')!r}.",
            "database",
        )

    expected_lists = (
        "sources", "provenance", "solutes", "carriers", "solvents",
        "gas_transport_pairs", "liquid_transport_pairs", "equilibrium_pairs",
    )
    for key in expected_lists:
        if key not in p:
            p[key] = []
            _issue(issues, ImportSeverity.INFO, "OPTIONAL_SECTION_OMITTED", f"Section {key!r} omitted; interpreted as empty.", key)
        elif not isinstance(p[key], list):
            _issue(issues, ImportSeverity.BLOCK, "SECTION_NOT_LIST", f"Section {key!r} must be a JSON list.", key)
            p[key] = []

    existing = _existing_state(repository)

    # Sources
    source_by_key: dict[str, dict] = {}
    for i, src in enumerate(p["sources"]):
        loc = f"sources[{i}]"
        if not isinstance(src, dict):
            _issue(issues, ImportSeverity.BLOCK, "SOURCE_NOT_OBJECT", "Source must be an object.", loc)
            continue
        skey = str(src.get("source_key") or "").strip()
        citation = str(src.get("citation") or "").strip()
        source_type = str(src.get("source_type") or "").strip()
        role = str(src.get("evidence_role") or "").strip()
        if not skey:
            _issue(issues, ImportSeverity.BLOCK, "SOURCE_KEY_REQUIRED", "source_key is required.", loc)
            continue
        if skey in source_by_key:
            _issue(issues, ImportSeverity.BLOCK, "DUPLICATE_SOURCE_KEY", f"Duplicate source_key {skey!r}.", loc)
        source_by_key[skey] = src
        if not citation:
            _issue(issues, ImportSeverity.BLOCK, "SOURCE_CITATION_REQUIRED", "citation is required.", loc)
        if not source_type:
            _issue(issues, ImportSeverity.BLOCK, "SOURCE_TYPE_REQUIRED", "source_type is required.", loc)
        if not role:
            _issue(issues, ImportSeverity.BLOCK, "EVIDENCE_ROLE_REQUIRED", "evidence_role is required.", loc)
        if citation and citation in existing["sources"]:
            old = existing["sources"][citation]
            new = (
                src.get("source_type"), src.get("title"), src.get("authors"), src.get("publication_year"),
                src.get("journal_or_publisher"), src.get("url"), src.get("doi"), src.get("evidence_role"),
            )
            # Null/empty fields in an import are allowed to defer to existing metadata. Nonempty conflicts block.
            labels = ("source_type","title","authors","publication_year","journal_or_publisher","url","doi","evidence_role")
            for label, old_v, new_v in zip(labels, old, new):
                if new_v not in (None, "") and old_v not in (None, "") and str(new_v) != str(old_v):
                    _issue(issues, ImportSeverity.BLOCK, "SOURCE_METADATA_CONFLICT", f"Existing citation has different {label}: {old_v!r} vs {new_v!r}.", loc)

    # Provenance
    prov_by_key: dict[str, dict] = {}
    for i, prov in enumerate(p["provenance"]):
        loc = f"provenance[{i}]"
        if not isinstance(prov, dict):
            _issue(issues, ImportSeverity.BLOCK, "PROVENANCE_NOT_OBJECT", "Provenance must be an object.", loc)
            continue
        pkey = str(prov.get("provenance_key") or "").strip()
        skey = str(prov.get("source_key") or "").strip()
        conf = str(prov.get("confidence") or "").upper().strip()
        method = str(prov.get("method") or "").strip()
        if not pkey:
            _issue(issues, ImportSeverity.BLOCK, "PROVENANCE_KEY_REQUIRED", "provenance_key is required.", loc)
            continue
        if pkey in prov_by_key:
            _issue(issues, ImportSeverity.BLOCK, "DUPLICATE_PROVENANCE_KEY", f"Duplicate provenance_key {pkey!r}.", loc)
        prov_by_key[pkey] = prov
        if skey not in source_by_key:
            _issue(issues, ImportSeverity.BLOCK, "UNKNOWN_SOURCE_KEY", f"Unknown source_key {skey!r}.", loc)
        if conf not in {"A", "B", "C", "D"}:
            _issue(issues, ImportSeverity.BLOCK, "INVALID_CONFIDENCE", "confidence must be A, B, C or D.", loc)
        if not method:
            _issue(issues, ImportSeverity.BLOCK, "METHOD_REQUIRED", "method is required.", loc)
        if conf in {"A", "B"} and skey in source_by_key:
            src = source_by_key[skey]
            if not _nonempty(src.get("title")):
                _issue(issues, ImportSeverity.BLOCK, "AB_SOURCE_TITLE_REQUIRED", "Confidence A/B provenance requires a source title.", loc)
            if not (_nonempty(src.get("doi")) or _nonempty(src.get("url"))):
                _issue(issues, ImportSeverity.BLOCK, "AB_SOURCE_LOCATOR_REQUIRED", "Confidence A/B provenance requires a DOI or URL.", loc)
        for key in ("reference_temperature_K", "reference_pressure_Pa", "validity_temperature_min_K", "validity_temperature_max_K", "validity_pressure_min_Pa", "validity_pressure_max_Pa"):
            if not _optional_positive(prov.get(key)):
                _issue(issues, ImportSeverity.BLOCK, "INVALID_POSITIVE_FIELD", f"{key} must be positive when supplied.", f"{loc}.{key}")
        tmin, tmax = prov.get("validity_temperature_min_K"), prov.get("validity_temperature_max_K")
        if tmin is not None and tmax is not None and _positive(tmin) and _positive(tmax) and tmin >= tmax:
            _issue(issues, ImportSeverity.BLOCK, "INVALID_T_RANGE", "validity_temperature_min_K must be below max.", loc)

    def require_prov(rec: dict, loc: str) -> Optional[str]:
        pk = str(rec.get("provenance_key") or "").strip()
        if not pk:
            _issue(issues, ImportSeverity.BLOCK, "PROVENANCE_REQUIRED", "Every imported engineering record requires provenance_key.", loc)
            return None
        if pk not in prov_by_key:
            _issue(issues, ImportSeverity.BLOCK, "UNKNOWN_PROVENANCE_KEY", f"Unknown provenance_key {pk!r}.", loc)
        return pk

    # Pure components
    package_solutes: set[str] = set()
    readiness: list[dict] = []
    for i, rec in enumerate(p["solutes"]):
        loc = f"solutes[{i}]"
        if not isinstance(rec, dict):
            _issue(issues, ImportSeverity.BLOCK, "SOLUTE_NOT_OBJECT", "Solute must be an object.", loc); continue
        sid = str(rec.get("solute_id") or "").strip()
        require_prov(rec, loc)
        if not sid or not _nonempty(rec.get("name")):
            _issue(issues, ImportSeverity.BLOCK, "SOLUTE_IDENTITY_REQUIRED", "solute_id and name are required.", loc)
        if sid in package_solutes:
            _issue(issues, ImportSeverity.BLOCK, "DUPLICATE_SOLUTE_ID", f"Duplicate solute_id {sid!r}.", loc)
        package_solutes.add(sid)
        if not _positive(rec.get("MW_kg_mol")):
            _issue(issues, ImportSeverity.BLOCK, "SOLUTE_MW_REQUIRED", "MW_kg_mol must be positive.", loc)
        ca = rec.get("carbon_atoms")
        if not isinstance(ca, int) or isinstance(ca, bool) or ca < 0:
            _issue(issues, ImportSeverity.BLOCK, "CARBON_ATOMS_REQUIRED", "carbon_atoms must be a non-negative integer.", loc)
        if sid in existing["solutes"] and not allow_replace:
            _issue(issues, ImportSeverity.BLOCK, "SOLUTE_COLLISION", f"solute_id {sid!r} already exists; explicit replacement required.", loc)
        if not _optional_positive(rec.get("fuller_diffusion_volume")):
            _issue(issues, ImportSeverity.BLOCK, "INVALID_FULLER_VOLUME", "fuller_diffusion_volume must be positive when supplied.", loc)
        if not _optional_positive(rec.get("boiling_molar_volume_cm3_mol")):
            _issue(issues, ImportSeverity.BLOCK, "INVALID_BOILING_VOLUME", "boiling_molar_volume_cm3_mol must be positive when supplied.", loc)
        if not _nonempty(rec.get("cas_number")):
            _issue(issues, ImportSeverity.WARNING, "CAS_MISSING", "CAS number is missing; identity traceability is weaker.", loc)
        if not _nonempty(rec.get("formula")):
            _issue(issues, ImportSeverity.WARNING, "FORMULA_MISSING", "Molecular formula is missing.", loc)
        fuller_ready = _positive(rec.get("fuller_diffusion_volume"))
        wilke_ready = _positive(rec.get("boiling_molar_volume_cm3_mol"))
        if not fuller_ready:
            _issue(issues, ImportSeverity.WARNING, "FULLER_NOT_READY", "No Fuller diffusion volume; gas diffusivity fallback may be unavailable.", loc)
        if not wilke_ready:
            _issue(issues, ImportSeverity.WARNING, "WILKE_CHANG_NOT_READY", "No boiling molar volume; Wilke–Chang fallback may be unavailable.", loc)
        readiness.append({"entity_type":"solute","entity_id":sid,"identity_ready":bool(sid and _positive(rec.get('MW_kg_mol'))),"fuller_ready":fuller_ready,"wilke_chang_ready":wilke_ready})

    package_carriers: set[str] = set()
    for i, rec in enumerate(p["carriers"]):
        loc = f"carriers[{i}]"
        if not isinstance(rec, dict):
            _issue(issues, ImportSeverity.BLOCK, "CARRIER_NOT_OBJECT", "Carrier must be an object.", loc); continue
        cid = str(rec.get("carrier_id") or "").strip(); require_prov(rec, loc)
        package_carriers.add(cid)
        if not cid or not _nonempty(rec.get("name")) or not _positive(rec.get("MW_kg_mol")):
            _issue(issues, ImportSeverity.BLOCK, "CARRIER_IDENTITY_REQUIRED", "carrier_id, name and positive MW_kg_mol are required.", loc)
        if cid in existing["carriers"] and not allow_replace:
            _issue(issues, ImportSeverity.BLOCK, "CARRIER_COLLISION", f"carrier_id {cid!r} already exists.", loc)
        vm = rec.get("viscosity_model")
        if vm not in {"sutherland", "constant"}:
            _issue(issues, ImportSeverity.BLOCK, "INVALID_VISCOSITY_MODEL", "viscosity_model must be sutherland or constant.", loc)
        if vm == "constant" and not _positive(rec.get("mu_Pa_s")):
            _issue(issues, ImportSeverity.BLOCK, "CARRIER_MU_REQUIRED", "constant viscosity_model requires positive mu_Pa_s.", loc)
        if vm == "sutherland" and not all(_positive(rec.get(k)) for k in ("mu_ref_Pa_s","T_ref_K","sutherland_S_K")):
            _issue(issues, ImportSeverity.BLOCK, "SUTHERLAND_FIELDS_REQUIRED", "sutherland model requires positive mu_ref_Pa_s, T_ref_K and sutherland_S_K.", loc)
        fuller_ready = _positive(rec.get("fuller_diffusion_volume"))
        if not fuller_ready:
            _issue(issues, ImportSeverity.WARNING, "CARRIER_FULLER_NOT_READY", "Carrier has no Fuller diffusion volume.", loc)
        readiness.append({"entity_type":"carrier","entity_id":cid,"identity_ready":bool(cid and _positive(rec.get('MW_kg_mol'))),"fuller_ready":fuller_ready,"wilke_chang_ready":False})

    package_solvents: set[str] = set()
    for i, rec in enumerate(p["solvents"]):
        loc = f"solvents[{i}]"
        if not isinstance(rec, dict):
            _issue(issues, ImportSeverity.BLOCK, "SOLVENT_NOT_OBJECT", "Solvent must be an object.", loc); continue
        sid = str(rec.get("solvent_id") or "").strip(); require_prov(rec, loc)
        package_solvents.add(sid)
        if not sid or not _nonempty(rec.get("name")) or not _positive(rec.get("MW_kg_mol")):
            _issue(issues, ImportSeverity.BLOCK, "SOLVENT_IDENTITY_REQUIRED", "solvent_id, name and positive MW_kg_mol are required.", loc)
        if sid in existing["solvents"] and not allow_replace:
            _issue(issues, ImportSeverity.BLOCK, "SOLVENT_COLLISION", f"solvent_id {sid!r} already exists.", loc)
        pm = rec.get("property_model")
        if pm not in {"correlation", "constant", "pseudo_solvent"}:
            _issue(issues, ImportSeverity.BLOCK, "INVALID_SOLVENT_PROPERTY_MODEL", "property_model must be correlation, constant or pseudo_solvent.", loc)
        if pm == "correlation" and not _nonempty(rec.get("property_model_id")):
            _issue(issues, ImportSeverity.BLOCK, "SOLVENT_CORRELATION_ID_REQUIRED", "correlation solvent requires property_model_id.", loc)
        if pm in {"constant", "pseudo_solvent"} and not all(_positive(rec.get(k)) for k in ("rho_kg_m3","mu_Pa_s","sigma_N_m")):
            _issue(issues, ImportSeverity.BLOCK, "SOLVENT_BULK_PROPERTIES_REQUIRED", "constant/pseudo solvent requires positive rho, mu and sigma.", loc)
        wc_ready = _positive(rec.get("wilke_chang_association_factor"))
        if not wc_ready:
            _issue(issues, ImportSeverity.WARNING, "SOLVENT_WILKE_CHANG_NOT_READY", "No Wilke–Chang association factor; liquid diffusivity fallback may be unavailable.", loc)
        readiness.append({"entity_type":"solvent","entity_id":sid,"identity_ready":bool(sid and _positive(rec.get('MW_kg_mol'))),"fuller_ready":False,"wilke_chang_ready":wc_ready})

    valid_solutes = existing["solutes"] | package_solutes
    valid_carriers = existing["carriers"] | package_carriers
    valid_solvents = existing["solvents"] | package_solvents

    def check_pair_ids(rec: dict, loc: str, second: str) -> tuple[str, str]:
        sol = str(rec.get("solute_id") or "").strip()
        sec = str(rec.get(second) or "").strip()
        if sol not in valid_solutes:
            _issue(issues, ImportSeverity.BLOCK, "UNKNOWN_PAIR_SOLUTE", f"Unknown solute_id {sol!r}.", loc)
        valid_second = valid_carriers if second == "carrier_id" else valid_solvents
        if sec not in valid_second:
            _issue(issues, ImportSeverity.BLOCK, "UNKNOWN_PAIR_PARTNER", f"Unknown {second} {sec!r}.", loc)
        return sol, sec

    package_gas_pairs: set[tuple[str,str]] = set()
    for i, rec in enumerate(p["gas_transport_pairs"]):
        loc = f"gas_transport_pairs[{i}]"
        if not isinstance(rec, dict): _issue(issues, ImportSeverity.BLOCK, "GAS_PAIR_NOT_OBJECT", "Pair must be an object.", loc); continue
        require_prov(rec, loc); key = check_pair_ids(rec, loc, "carrier_id"); package_gas_pairs.add(key)
        if key in existing["gas_pairs"] and not allow_replace: _issue(issues, ImportSeverity.BLOCK, "GAS_PAIR_COLLISION", f"Gas pair {key} already exists.", loc)
        if not _positive(rec.get("D_ref_m2_s")): _issue(issues, ImportSeverity.BLOCK, "DG_REQUIRED", "D_ref_m2_s must be positive.", loc)
        if rec.get("model") not in {"fixed_reference", "fuller"}: _issue(issues, ImportSeverity.BLOCK, "INVALID_DG_MODEL", "model must be fixed_reference or fuller.", loc)
        if not _optional_positive(rec.get("T_ref_K")) or not _optional_positive(rec.get("P_ref_Pa")): _issue(issues, ImportSeverity.BLOCK, "INVALID_DG_REFERENCE", "T_ref_K/P_ref_Pa must be positive when supplied.", loc)

    package_liquid_pairs: set[tuple[str,str]] = set()
    for i, rec in enumerate(p["liquid_transport_pairs"]):
        loc = f"liquid_transport_pairs[{i}]"
        if not isinstance(rec, dict): _issue(issues, ImportSeverity.BLOCK, "LIQUID_PAIR_NOT_OBJECT", "Pair must be an object.", loc); continue
        require_prov(rec, loc); key = check_pair_ids(rec, loc, "solvent_id"); package_liquid_pairs.add(key)
        if key in existing["liquid_pairs"] and not allow_replace: _issue(issues, ImportSeverity.BLOCK, "LIQUID_PAIR_COLLISION", f"Liquid pair {key} already exists.", loc)
        if not _positive(rec.get("D_ref_m2_s")): _issue(issues, ImportSeverity.BLOCK, "DL_REQUIRED", "D_ref_m2_s must be positive.", loc)
        if rec.get("model") not in {"fixed_reference", "wilke_chang"}: _issue(issues, ImportSeverity.BLOCK, "INVALID_DL_MODEL", "model must be fixed_reference or wilke_chang.", loc)
        if not _optional_positive(rec.get("T_ref_K")): _issue(issues, ImportSeverity.BLOCK, "INVALID_DL_REFERENCE", "T_ref_K must be positive when supplied.", loc)

    package_eq_pairs: set[tuple[str,str]] = set()
    allowed_eq = {"henry_pc", "linear_m", "tabulated", "reactive", "nonideal_unsupported", "no_data"}
    for i, rec in enumerate(p["equilibrium_pairs"]):
        loc = f"equilibrium_pairs[{i}]"
        if not isinstance(rec, dict): _issue(issues, ImportSeverity.BLOCK, "EQ_PAIR_NOT_OBJECT", "Pair must be an object.", loc); continue
        require_prov(rec, loc); key = check_pair_ids(rec, loc, "solvent_id"); package_eq_pairs.add(key)
        if key in existing["equilibrium_pairs"] and not allow_replace: _issue(issues, ImportSeverity.BLOCK, "EQ_PAIR_COLLISION", f"Equilibrium pair {key} already exists.", loc)
        model = rec.get("model")
        if model not in allowed_eq: _issue(issues, ImportSeverity.BLOCK, "INVALID_EQ_MODEL", f"Unsupported equilibrium model {model!r}.", loc)
        if model == "henry_pc":
            if not _positive(rec.get("H_ref_Pa_m3_mol")) or not _positive(rec.get("T_ref_K")) or not isinstance(rec.get("temperature_coefficient_K"), (int,float)):
                _issue(issues, ImportSeverity.BLOCK, "HENRY_FIELDS_REQUIRED", "henry_pc requires positive H_ref, positive T_ref and numeric temperature_coefficient_K.", loc)
        elif model == "linear_m" and not _positive(rec.get("m_y_over_x")):
            _issue(issues, ImportSeverity.BLOCK, "LINEAR_M_REQUIRED", "linear_m requires positive m_y_over_x.", loc)
        elif model in {"tabulated", "reactive", "nonideal_unsupported", "no_data"}:
            _issue(issues, ImportSeverity.WARNING, "MODEL_NOT_SOLVER_READY", f"Model {model!r} can be stored but is not a standard V4.0 physical-absorption solver model.", loc)
        tmin, tmax = rec.get("validity_temperature_min_K"), rec.get("validity_temperature_max_K")
        if not _optional_positive(tmin) or not _optional_positive(tmax):
            _issue(issues, ImportSeverity.BLOCK, "INVALID_EQ_T_RANGE", "Equilibrium validity temperatures must be positive when supplied.", loc)
        if _positive(tmin) and _positive(tmax) and tmin >= tmax:
            _issue(issues, ImportSeverity.BLOCK, "INVALID_EQ_T_RANGE_ORDER", "Equilibrium Tmin must be below Tmax.", loc)

    # Intra-package duplicate pair IDs are always a block.
    for name, records, keys, fields in (
        ("gas_transport_pairs", p["gas_transport_pairs"], package_gas_pairs, ("solute_id","carrier_id")),
        ("liquid_transport_pairs", p["liquid_transport_pairs"], package_liquid_pairs, ("solute_id","solvent_id")),
        ("equilibrium_pairs", p["equilibrium_pairs"], package_eq_pairs, ("solute_id","solvent_id")),
    ):
        raw_keys = [(str(r.get(fields[0]) or "").strip(), str(r.get(fields[1]) or "").strip()) for r in records if isinstance(r,dict)]
        if len(raw_keys) != len(set(raw_keys)):
            _issue(issues, ImportSeverity.BLOCK, "DUPLICATE_PAIR_IN_PACKAGE", f"Duplicate key in {name}.", name)

    # Inform the user when an imported solute has no equilibrium coverage in the same package.
    for sid in package_solutes:
        eq_n = sum(1 for s, _ in package_eq_pairs if s == sid)
        if eq_n == 0:
            _issue(issues, ImportSeverity.WARNING, "NO_EQUILIBRIUM_PAIR_IN_PACKAGE", f"Solute {sid!r} is importable as identity data but has no equilibrium pair in this package.", f"solute:{sid}")

    delta = ImportInventoryDelta(
        solutes=len(package_solutes), carriers=len(package_carriers), solvents=len(package_solvents),
        gas_transport_pairs=len(package_gas_pairs), liquid_transport_pairs=len(package_liquid_pairs),
        equilibrium_pairs=len(package_eq_pairs), sources=len(source_by_key), provenance_records=len(prov_by_key),
    )
    return ImportValidationReport(package_id, contract_version, tuple(issues), delta, tuple(readiness))


def _source_id(src: dict) -> str:
    return _stable_id("src", src.get("citation"))


def _prov_id(prov: dict, source_id: str) -> str:
    return _stable_id(
        "prov", source_id, prov.get("method"), str(prov.get("confidence") or "").upper(),
        prov.get("resolution_tier"), prov.get("reference_temperature_K"), prov.get("reference_pressure_Pa"),
        prov.get("validity_temperature_min_K"), prov.get("validity_temperature_max_K"),
        prov.get("validity_pressure_min_Pa"), prov.get("validity_pressure_max_Pa"),
        prov.get("composition_validity_note"), prov.get("validity_note"),
    )


def _usage_id(pid: str, etype: str, ekey: str, scope: str, pname: Optional[str]) -> str:
    return _stable_id("use", pid, etype, ekey, scope, pname)


def _insert_or_validate_source(con: sqlite3.Connection, src: dict) -> str:
    citation = str(src["citation"]).strip()
    row = con.execute("SELECT source_id FROM sources WHERE citation=?", (citation,)).fetchone()
    if row is not None:
        return str(row[0])
    sid = _source_id(src)
    con.execute(
        """INSERT INTO sources(source_id,citation,source_type,title,authors,publication_year,journal_or_publisher,url,doi,accessed_on,evidence_role,quality_note,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sid,citation,src.get("source_type"),src.get("title"),src.get("authors"),src.get("publication_year"),
         src.get("journal_or_publisher"),src.get("url"),src.get("doi"),src.get("accessed_on"),
         src.get("evidence_role"),src.get("quality_note") or "",src.get("notes") or ""),
    )
    return sid


def _insert_provenance(con: sqlite3.Connection, prov: dict, sid: str) -> str:
    pid = _prov_id(prov, sid)
    con.execute(
        """INSERT OR IGNORE INTO provenance(
        provenance_id,source_id,method,confidence,resolution_tier,reference_temperature_K,reference_pressure_Pa,
        validity_temperature_min_K,validity_temperature_max_K,validity_pressure_min_Pa,validity_pressure_max_Pa,
        composition_validity_note,validity_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid,sid,prov.get("method"),str(prov.get("confidence")).upper(),prov.get("resolution_tier"),
         prov.get("reference_temperature_K"),prov.get("reference_pressure_Pa"),prov.get("validity_temperature_min_K"),
         prov.get("validity_temperature_max_K"),prov.get("validity_pressure_min_Pa"),prov.get("validity_pressure_max_Pa"),
         prov.get("composition_validity_note") or "",prov.get("validity_note") or ""),
    )
    return pid


def _insert_usage(con: sqlite3.Connection, pid: str, etype: str, ekey: str, scope: str, pname: Optional[str], unit: Optional[str], notes: str = "") -> None:
    con.execute(
        """INSERT OR IGNORE INTO provenance_usage(usage_id,provenance_id,entity_type,entity_key,property_scope,property_name,unit,notes)
        VALUES (?,?,?,?,?,?,?,?)""",
        (_usage_id(pid,etype,ekey,scope,pname),pid,etype,ekey,scope,pname,unit,notes),
    )


def _upsert_sql(table: str, columns: Sequence[str], conflict_cols: Sequence[str], allow_replace: bool) -> str:
    placeholders = ",".join("?" for _ in columns)
    base = f"INSERT INTO {table}({','.join(columns)}) VALUES ({placeholders})"
    if not allow_replace:
        return base
    update_cols = [c for c in columns if c not in conflict_cols]
    assignments = ",".join(f"{c}=excluded.{c}" for c in update_cols)
    return base + f" ON CONFLICT({','.join(conflict_cols)}) DO UPDATE SET {assignments}"


def import_chemical_package(
    database_path: str | Path,
    package: Mapping[str, Any] | str | Path,
    *,
    dry_run: bool = True,
    allow_replace: bool = False,
    create_backup: bool = True,
    backup_path: str | Path | None = None,
) -> ImportExecutionReport:
    database_path = Path(database_path)
    repo = SQLiteAbsorberRepositoryV18B(database_path)
    validation = validate_chemical_import_package(package, repo, allow_replace=allow_replace)
    before = repo.inventory().__dict__.copy()
    if not validation.pass_validation:
        raise ChemicalImportValidationError(validation)

    if dry_run:
        return ImportExecutionReport(
            validation=validation, committed=False, dry_run=True, database_path=str(database_path), backup_path=None,
            before_inventory=before, after_inventory=before.copy(), database_integrity=repo.integrity_check(),
            foreign_key_violations=repo.foreign_key_violations(),
        )

    p = _as_dict(package)
    backup_used: Optional[Path] = None
    if create_backup:
        backup_used = Path(backup_path) if backup_path is not None else database_path.with_suffix(database_path.suffix + ".pre18f.bak")
        shutil.copy2(database_path, backup_used)

    try:
        with repo.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            source_ids = {str(s["source_key"]): _insert_or_validate_source(con, s) for s in p.get("sources", [])}
            prov_ids = {}
            for prov in p.get("provenance", []):
                prov_ids[str(prov["provenance_key"])] = _insert_provenance(con, prov, source_ids[str(prov["source_key"])])

            for rec in p.get("solutes", []):
                pid = prov_ids[str(rec["provenance_key"])]
                cols = ("solute_id","name","MW_kg_mol","carbon_atoms","formula","cas_number","fuller_diffusion_volume","boiling_molar_volume_cm3_mol","provenance_id")
                vals = (rec["solute_id"],rec["name"],rec["MW_kg_mol"],rec["carbon_atoms"],rec.get("formula"),rec.get("cas_number"),rec.get("fuller_diffusion_volume"),rec.get("boiling_molar_volume_cm3_mol"),pid)
                con.execute(_upsert_sql("solutes",cols,("solute_id",),allow_replace),vals)
                _insert_usage(con,pid,"solute",rec["solute_id"],"identity_transport_inputs","MW_formula_CAS_Fuller_LeBas",None)

            for rec in p.get("carriers", []):
                pid = prov_ids[str(rec["provenance_key"])]
                cols=("carrier_id","name","MW_kg_mol","viscosity_model","mu_Pa_s","mu_ref_Pa_s","T_ref_K","sutherland_S_K","fuller_diffusion_volume","provenance_id")
                vals=(rec["carrier_id"],rec["name"],rec["MW_kg_mol"],rec["viscosity_model"],rec.get("mu_Pa_s"),rec.get("mu_ref_Pa_s"),rec.get("T_ref_K"),rec.get("sutherland_S_K"),rec.get("fuller_diffusion_volume"),pid)
                con.execute(_upsert_sql("carrier_gases",cols,("carrier_id",),allow_replace),vals)
                _insert_usage(con,pid,"carrier_gas",rec["carrier_id"],"bulk_properties","viscosity_and_identity",None)

            for rec in p.get("solvents", []):
                pid = prov_ids[str(rec["provenance_key"])]
                cols=("solvent_id","name","MW_kg_mol","property_model","property_model_id","rho_kg_m3","mu_Pa_s","sigma_N_m","wilke_chang_association_factor","provenance_id")
                vals=(rec["solvent_id"],rec["name"],rec["MW_kg_mol"],rec["property_model"],rec.get("property_model_id"),rec.get("rho_kg_m3"),rec.get("mu_Pa_s"),rec.get("sigma_N_m"),rec.get("wilke_chang_association_factor"),pid)
                con.execute(_upsert_sql("solvents",cols,("solvent_id",),allow_replace),vals)
                _insert_usage(con,pid,"solvent",rec["solvent_id"],"bulk_properties","rho_mu_sigma_and_model",None)

            for rec in p.get("gas_transport_pairs", []):
                pid=prov_ids[str(rec["provenance_key"])]
                cols=("solute_id","carrier_id","D_ref_m2_s","T_ref_K","P_ref_Pa","model","provenance_id")
                vals=(rec["solute_id"],rec["carrier_id"],rec["D_ref_m2_s"],rec.get("T_ref_K"),rec.get("P_ref_Pa"),rec["model"],pid)
                con.execute(_upsert_sql("gas_transport_pairs",cols,("solute_id","carrier_id"),allow_replace),vals)
                _insert_usage(con,pid,"gas_transport_pair",f"{rec['solute_id']}|{rec['carrier_id']}","transport_property","D_G","m2/s")

            for rec in p.get("liquid_transport_pairs", []):
                pid=prov_ids[str(rec["provenance_key"])]
                cols=("solute_id","solvent_id","D_ref_m2_s","T_ref_K","model","provenance_id")
                vals=(rec["solute_id"],rec["solvent_id"],rec["D_ref_m2_s"],rec.get("T_ref_K"),rec["model"],pid)
                con.execute(_upsert_sql("liquid_transport_pairs",cols,("solute_id","solvent_id"),allow_replace),vals)
                _insert_usage(con,pid,"liquid_transport_pair",f"{rec['solute_id']}|{rec['solvent_id']}","transport_property","D_L","m2/s")

            for rec in p.get("equilibrium_pairs", []):
                pid=prov_ids[str(rec["provenance_key"])]
                cols=("solute_id","solvent_id","model","H_ref_Pa_m3_mol","T_ref_K","temperature_coefficient_K","m_y_over_x","validity_temperature_min_K","validity_temperature_max_K","validity_note","provenance_id")
                vals=(rec["solute_id"],rec["solvent_id"],rec["model"],rec.get("H_ref_Pa_m3_mol"),rec.get("T_ref_K"),rec.get("temperature_coefficient_K"),rec.get("m_y_over_x"),rec.get("validity_temperature_min_K"),rec.get("validity_temperature_max_K"),rec.get("validity_note") or "",pid)
                con.execute(_upsert_sql("equilibrium_pairs",cols,("solute_id","solvent_id"),allow_replace),vals)
                pname="H_pc" if rec["model"]=="henry_pc" else "m_y_over_x"
                punit="Pa m3/mol" if rec["model"]=="henry_pc" else "dimensionless"
                _insert_usage(con,pid,"equilibrium_pair",f"{rec['solute_id']}|{rec['solvent_id']}","equilibrium_property",pname,punit)

            # Trace the latest controlled import without changing the core schema version.
            con.execute("INSERT OR REPLACE INTO schema_metadata(key,value) VALUES (?,?)", ("expansion_framework_version",PHASE18F_IMPORT_CONTRACT_VERSION))
            con.execute("INSERT OR REPLACE INTO schema_metadata(key,value) VALUES (?,?)", ("last_import_package_id",validation.package_id))
            con.commit()
    except Exception:
        # sqlite context manager rolls back on exception; explicit backup remains for operator recovery.
        raise

    repo_after = SQLiteAbsorberRepositoryV18B(database_path)
    return ImportExecutionReport(
        validation=validation, committed=True, dry_run=False, database_path=str(database_path),
        backup_path=None if backup_used is None else str(backup_used), before_inventory=before,
        after_inventory=repo_after.inventory().__dict__.copy(), database_integrity=repo_after.integrity_check(),
        foreign_key_violations=repo_after.foreign_key_violations(),
    )


def phase18f_synthetic_package() -> Dict[str, Any]:
    """Synthetic QA-only package used to verify the importer; not scientific data."""
    return {
        "contract_version": PHASE18F_IMPORT_CONTRACT_VERSION,
        "package_id": "PHASE18F_SYNTHETIC_IMPORT_QA_ONLY",
        "description": "Synthetic nonphysical QA fixture; imported only into temporary test copies.",
        "sources": [{
            "source_key":"SRC_QA", "citation":"Phase 18F synthetic QA fixture — not scientific data",
            "source_type":"synthetic_validation", "title":"Phase 18F synthetic import fixture",
            "authors":"Generic Packed Absorber Simulator V4", "publication_year":2026,
            "journal_or_publisher":"Internal validation", "url":"https://example.invalid/phase18f-qa", "doi":None,
            "accessed_on":"2026-10-07", "evidence_role":"SYNTHETIC_QA", "quality_note":"Not scientific property data.", "notes":"Temporary-copy gate only."
        }],
        "provenance":[{
            "provenance_key":"PROV_QA", "source_key":"SRC_QA", "method":"synthetic QA fixture",
            "confidence":"D", "resolution_tier":"SCREENING", "reference_temperature_K":298.15,
            "reference_pressure_Pa":101325.0, "validity_temperature_min_K":280.0, "validity_temperature_max_K":320.0,
            "validity_pressure_min_Pa":None, "validity_pressure_max_Pa":None,
            "composition_validity_note":"QA only", "validity_note":"Synthetic; never use for design."
        }],
        "solutes":[{
            "solute_id":"phase18f_demo_solute", "name":"Phase18F Demo Solute", "MW_kg_mol":0.075,
            "carbon_atoms":2, "formula":"X2", "cas_number":"QA-ONLY", "fuller_diffusion_volume":70.0,
            "boiling_molar_volume_cm3_mol":90.0, "provenance_key":"PROV_QA"
        }],
        "carriers":[], "solvents":[], "gas_transport_pairs":[], "liquid_transport_pairs":[],
        "equilibrium_pairs":[{
            "solute_id":"phase18f_demo_solute", "solvent_id":"water", "model":"linear_m",
            "H_ref_Pa_m3_mol":None, "T_ref_K":None, "temperature_coefficient_K":None,
            "m_y_over_x":1.5, "validity_temperature_min_K":280.0, "validity_temperature_max_K":320.0,
            "validity_note":"Synthetic QA only", "provenance_key":"PROV_QA"
        }],
    }


def run_phase18f_expansion_gate(database_path: str | Path) -> Phase18FGateReport:
    database_path = Path(database_path)
    primary_hash_before = _hash_file(database_path)
    repo = SQLiteAbsorberRepositoryV18B(database_path)
    package = phase18f_synthetic_package()

    dry_hash_before = _hash_file(database_path)
    dry = import_chemical_package(database_path, package, dry_run=True)
    dry_hash_after = _hash_file(database_path)

    with tempfile.TemporaryDirectory(prefix="phase18f_gate_") as td:
        tmp_db = Path(td) / database_path.name
        shutil.copy2(database_path, tmp_db)
        tmp_repo_before = SQLiteAbsorberRepositoryV18B(tmp_db)
        inv_before = tmp_repo_before.inventory().__dict__.copy()
        executed = import_chemical_package(tmp_db, package, dry_run=False, create_backup=False)
        tmp_repo_after = SQLiteAbsorberRepositoryV18B(tmp_db)
        inv_after = tmp_repo_after.inventory().__dict__.copy()
        explorer = DatabaseExplorer(tmp_repo_after)
        cell = explorer.coverage_cell("phase18f_demo_solute", "water", carrier_id="air", T_K=298.15, P_Pa=101325.0)
        delta_ok = (
            inv_after["solutes"] == inv_before["solutes"] + 1
            and inv_after["equilibrium_pairs"] == inv_before["equilibrium_pairs"] + 1
            and inv_after["gas_transport_pairs"] == inv_before["gas_transport_pairs"]
            and inv_after["liquid_transport_pairs"] == inv_before["liquid_transport_pairs"]
        )

        # Invalid provenance reference must block before mutation.
        invalid = json.loads(json.dumps(package))
        invalid["solutes"][0]["provenance_key"] = "NO_SUCH_PROVENANCE"
        invalid_before = _hash_file(tmp_db)
        invalid_blocked = False
        try:
            import_chemical_package(tmp_db, invalid, dry_run=False, create_backup=False)
        except ChemicalImportValidationError:
            invalid_blocked = True
        invalid_after = _hash_file(tmp_db)

        # Collision on a second append-only import must block.
        collision_blocked = False
        try:
            import_chemical_package(tmp_db, package, dry_run=False, create_backup=False)
        except ChemicalImportValidationError:
            collision_blocked = True

    primary_hash_after = _hash_file(database_path)
    return Phase18FGateReport(
        dry_run_valid=dry.validation.pass_validation and dry.pass_import,
        dry_run_unchanged=(dry_hash_before == dry_hash_after),
        committed_to_temporary_copy=executed.committed and executed.pass_import,
        temporary_inventory_delta_ok=delta_ok,
        imported_coverage_resolvable=(cell.resolvable and cell.overall_status == CoverageStatus.SCREENING),
        invalid_package_blocked=invalid_blocked,
        collision_blocked=collision_blocked,
        rollback_unchanged=(invalid_before == invalid_after),
        primary_database_unchanged=(primary_hash_before == primary_hash_after),
        integrity=repo.integrity_check(),
        foreign_key_violations=len(repo.foreign_key_violations()),
    )
