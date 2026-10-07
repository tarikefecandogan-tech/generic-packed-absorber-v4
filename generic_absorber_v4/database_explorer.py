"""Phase 18E — read-only engineering database explorer and coverage matrix.

This module adds no absorber physics.  It inspects the primary Phase 18B
SQLite engineering database, reconstructs the canonical registry through the
existing repository layer, and reports data availability/resolution quality.

Coverage policy
---------------
Coverage is evaluated at an explicit audit state (default 298.15 K, 1 atm)
and selected carrier.  For each solute/solvent cell the explorer checks:

* gas transport: registered DATABASE value or Fuller correlation estimate,
* liquid transport: registered DATABASE value or Wilke–Chang estimate,
* equilibrium: registered supported equilibrium and its confidence class.

Overall cell status:
* VERIFIED  — equilibrium + both transport properties are database-backed and
              equilibrium confidence is A/B.
* ESTIMATED — equilibrium is A/B database-backed but one or both transport
              properties require Confidence-C correlation estimates.
* SCREENING — the equilibrium path is confidence D / screening.
* MISSING   — a critical equilibrium or transport property cannot be resolved.
* UNSUPPORTED — registered physics exists but is unsupported by V4.

The matrix is an engineering data-coverage map, not an absorber performance
calculation and not a guarantee of design-grade validity.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from .database_v18b import SQLiteAbsorberRepositoryV18B
from .models import ConfidenceClass
from .resolver import (
    MissingPropertyError,
    PropertyResolver,
    ResolutionTier,
    UnsupportedPropertyModelError,
)

PHASE18E_DATABASE_EXPLORER_ID = "PHASE18E_DATABASE_EXPLORER_2026_10_07"
DEFAULT_COVERAGE_T_K = 298.15
DEFAULT_COVERAGE_P_PA = 101325.0


class CoverageStatus(str, Enum):
    VERIFIED = "VERIFIED"
    ESTIMATED = "ESTIMATED"
    SCREENING = "SCREENING"
    MISSING = "MISSING"
    UNSUPPORTED = "UNSUPPORTED"


STATUS_SYMBOLS: Dict[CoverageStatus, str] = {
    CoverageStatus.VERIFIED: "🟢 VERIFIED",
    CoverageStatus.ESTIMATED: "🟡 ESTIMATED",
    CoverageStatus.SCREENING: "🟠 SCREENING",
    CoverageStatus.MISSING: "🔴 MISSING",
    CoverageStatus.UNSUPPORTED: "⚫ UNSUPPORTED",
}


@dataclass(frozen=True)
class CoverageCell:
    solute_id: str
    solvent_id: str
    carrier_id: str
    gas_transport_tier: str
    gas_transport_confidence: Optional[str]
    liquid_transport_tier: str
    liquid_transport_confidence: Optional[str]
    equilibrium_tier: str
    equilibrium_confidence: Optional[str]
    equilibrium_model: Optional[str]
    overall_status: CoverageStatus
    resolvable: bool
    note: str = ""

    @property
    def display(self) -> str:
        return STATUS_SYMBOLS[self.overall_status]


@dataclass(frozen=True)
class CoverageSummary:
    total_cells: int
    verified: int
    estimated: int
    screening: int
    missing: int
    unsupported: int

    @property
    def resolvable_cells(self) -> int:
        return self.verified + self.estimated + self.screening

    @property
    def resolvable_fraction(self) -> float:
        return 0.0 if self.total_cells == 0 else self.resolvable_cells / self.total_cells


@dataclass(frozen=True)
class ExplorerGateReport:
    integrity: str
    foreign_key_violations: int
    matrix_cells: int
    summary: CoverageSummary
    expected_reference_statuses: Dict[str, bool]
    search_vdc_hits: int
    database_unchanged: bool

    @property
    def pass_gate(self) -> bool:
        return (
            self.integrity.lower() == "ok"
            and self.foreign_key_violations == 0
            and self.matrix_cells > 0
            and all(self.expected_reference_statuses.values())
            and self.search_vdc_hits > 0
            and self.database_unchanged
        )


class DatabaseExplorer:
    """Read-only explorer over the Phase 18B engineering SQLite database."""

    def __init__(self, repository: SQLiteAbsorberRepositoryV18B):
        self.repository = repository
        self.registry = repository.load_registry()
        self.resolver = PropertyResolver(self.registry)

    @classmethod
    def from_path(cls, database_path: str | Path) -> "DatabaseExplorer":
        return cls(SQLiteAbsorberRepositoryV18B(database_path))

    # ------------------------------------------------------------------
    # Core catalog views
    # ------------------------------------------------------------------
    def list_solutes(self) -> Tuple[dict, ...]:
        rows = []
        for s in sorted(self.registry.solutes.values(), key=lambda x: x.id):
            rows.append({
                "solute_id": s.id,
                "name": s.name,
                "formula": s.formula,
                "cas_number": s.cas_number,
                "MW_g_mol": 1000.0 * s.MW_kg_mol,
                "carbon_atoms": s.carbon_atoms,
                "fuller_diffusion_volume": s.fuller_diffusion_volume,
                "boiling_molar_volume_cm3_mol": s.boiling_molar_volume_cm3_mol,
                "fuller_ready": s.fuller_diffusion_volume is not None,
                "wilke_chang_solute_ready": s.boiling_molar_volume_cm3_mol is not None,
            })
        return tuple(rows)

    def list_carriers(self) -> Tuple[dict, ...]:
        rows = []
        for c in sorted(self.registry.carriers.values(), key=lambda x: x.id):
            p = c.provenance
            rows.append({
                "carrier_id": c.id,
                "name": c.name,
                "MW_g_mol": 1000.0 * c.MW_kg_mol,
                "viscosity_model": c.viscosity_model,
                "fuller_diffusion_volume": c.fuller_diffusion_volume,
                "fuller_ready": c.fuller_diffusion_volume is not None,
                "confidence": None if p is None else p.confidence.value,
                "source": None if p is None else p.source,
            })
        return tuple(rows)

    def list_solvents(self) -> Tuple[dict, ...]:
        rows = []
        for s in sorted(self.registry.solvents.values(), key=lambda x: x.id):
            p = s.provenance
            rows.append({
                "solvent_id": s.id,
                "name": s.name,
                "MW_g_mol": 1000.0 * s.MW_kg_mol,
                "property_model": s.property_model,
                "property_model_id": s.property_model_id,
                "rho_kg_m3": s.rho_kg_m3,
                "mu_Pa_s": s.mu_Pa_s,
                "sigma_N_m": s.sigma_N_m,
                "wilke_chang_phi": s.wilke_chang_association_factor,
                "wilke_chang_solvent_ready": s.wilke_chang_association_factor is not None,
                "confidence": None if p is None else p.confidence.value,
                "source": None if p is None else p.source,
            })
        return tuple(rows)

    def list_packings(self) -> Tuple[dict, ...]:
        rows = []
        for p in sorted(self.registry.packings.values(), key=lambda x: x.id):
            prov = p.provenance
            rows.append({
                "packing_id": p.id,
                "name": p.name,
                "area_m2_m3": p.area_m2_m3,
                "nominal_size_mm": 1000.0 * p.nominal_size_m,
                "void_fraction": p.void_fraction,
                "critical_surface_tension_N_m": p.critical_surface_tension_N_m,
                "pressure_drop_psi": p.pressure_drop_psi,
                "packing_factor_ft_inv": p.packing_factor_ft_inv,
                "packing_factor_basis": p.packing_factor_basis,
                "packing_factor_is_estimated": p.packing_factor_ft_inv is None,
                "confidence": None if prov is None else prov.confidence.value,
                "source": None if prov is None else prov.source,
            })
        return tuple(rows)

    def list_equilibrium_pairs(self) -> Tuple[dict, ...]:
        rows = []
        for (solute_id, solvent_id), p in sorted(self.registry.equilibrium_pairs.items()):
            prov = p.provenance
            rows.append({
                "solute_id": solute_id,
                "solvent_id": solvent_id,
                "model": p.model,
                "H_ref_Pa_m3_mol": p.H_ref_Pa_m3_mol,
                "T_ref_K": p.T_ref_K,
                "temperature_coefficient_K": p.temperature_coefficient_K,
                "m_y_over_x": p.m_y_over_x,
                "validity_temperature_min_K": p.validity_temperature_min_K,
                "validity_temperature_max_K": p.validity_temperature_max_K,
                "confidence": None if prov is None else prov.confidence.value,
                "method": None if prov is None else prov.method,
                "source": None if prov is None else prov.source,
                "validity_note": p.validity_note,
            })
        return tuple(rows)

    def list_gas_transport_pairs(self) -> Tuple[dict, ...]:
        rows = []
        for (solute_id, carrier_id), p in sorted(self.registry.gas_transport_pairs.items()):
            prov = p.provenance
            rows.append({
                "solute_id": solute_id,
                "carrier_id": carrier_id,
                "D_ref_m2_s": p.D_ref_m2_s,
                "T_ref_K": p.T_ref_K,
                "P_ref_Pa": p.P_ref_Pa,
                "model": p.model,
                "confidence": None if prov is None else prov.confidence.value,
                "method": None if prov is None else prov.method,
                "source": None if prov is None else prov.source,
            })
        return tuple(rows)

    def list_liquid_transport_pairs(self) -> Tuple[dict, ...]:
        rows = []
        for (solute_id, solvent_id), p in sorted(self.registry.liquid_transport_pairs.items()):
            prov = p.provenance
            rows.append({
                "solute_id": solute_id,
                "solvent_id": solvent_id,
                "D_ref_m2_s": p.D_ref_m2_s,
                "T_ref_K": p.T_ref_K,
                "model": p.model,
                "confidence": None if prov is None else prov.confidence.value,
                "method": None if prov is None else prov.method,
                "source": None if prov is None else prov.source,
            })
        return tuple(rows)

    def list_sources(self) -> Tuple[dict, ...]:
        return self.repository.list_sources_detailed()

    # ------------------------------------------------------------------
    # Coverage resolution
    # ------------------------------------------------------------------
    @staticmethod
    def _resolved_property_label(prop) -> tuple[str, Optional[str]]:
        if prop.tier == ResolutionTier.DATABASE:
            return "DATABASE", prop.confidence.value
        if prop.tier == ResolutionTier.CORRELATION_ESTIMATE:
            return "ESTIMATE", prop.confidence.value
        return prop.tier.value, prop.confidence.value

    def coverage_cell(
        self,
        solute_id: str,
        solvent_id: str,
        *,
        carrier_id: str = "air",
        T_K: float = DEFAULT_COVERAGE_T_K,
        P_Pa: float = DEFAULT_COVERAGE_P_PA,
    ) -> CoverageCell:
        # Validate entity ids first so typos never look like missing coverage.
        self.registry.get_solute(solute_id)
        self.registry.get_solvent(solvent_id)
        self.registry.get_carrier(carrier_id)

        notes = []

        try:
            dg = self.resolver.resolve_gas_diffusivity(solute_id, carrier_id, T_K, P_Pa)
            dg_tier, dg_conf = self._resolved_property_label(dg)
        except MissingPropertyError as exc:
            dg_tier, dg_conf = "MISSING", None
            notes.append(str(exc))
        except UnsupportedPropertyModelError as exc:
            dg_tier, dg_conf = "UNSUPPORTED", None
            notes.append(str(exc))

        try:
            dl = self.resolver.resolve_liquid_diffusivity(solute_id, solvent_id, T_K)
            dl_tier, dl_conf = self._resolved_property_label(dl)
        except MissingPropertyError as exc:
            dl_tier, dl_conf = "MISSING", None
            notes.append(str(exc))
        except UnsupportedPropertyModelError as exc:
            dl_tier, dl_conf = "UNSUPPORTED", None
            notes.append(str(exc))

        eq_model: Optional[str] = None
        try:
            eq = self.resolver.resolve_equilibrium(solute_id, solvent_id, T_K)
            active = eq.active_property
            eq_model = eq.model
            eq_tier, eq_conf = self._resolved_property_label(active)
        except MissingPropertyError as exc:
            eq_tier, eq_conf = "MISSING", None
            notes.append(str(exc))
        except UnsupportedPropertyModelError as exc:
            eq_tier, eq_conf = "UNSUPPORTED", None
            notes.append(str(exc))

        if "UNSUPPORTED" in (dg_tier, dl_tier, eq_tier):
            status = CoverageStatus.UNSUPPORTED
        elif "MISSING" in (dg_tier, dl_tier, eq_tier):
            status = CoverageStatus.MISSING
        elif eq_conf == ConfidenceClass.D.value:
            status = CoverageStatus.SCREENING
        elif "ESTIMATE" in (dg_tier, dl_tier):
            status = CoverageStatus.ESTIMATED
        else:
            status = CoverageStatus.VERIFIED

        return CoverageCell(
            solute_id=solute_id,
            solvent_id=solvent_id,
            carrier_id=carrier_id,
            gas_transport_tier=dg_tier,
            gas_transport_confidence=dg_conf,
            liquid_transport_tier=dl_tier,
            liquid_transport_confidence=dl_conf,
            equilibrium_tier=eq_tier,
            equilibrium_confidence=eq_conf,
            equilibrium_model=eq_model,
            overall_status=status,
            resolvable=status in (
                CoverageStatus.VERIFIED,
                CoverageStatus.ESTIMATED,
                CoverageStatus.SCREENING,
            ),
            note=" | ".join(notes),
        )

    def coverage_cells(
        self,
        *,
        carrier_id: str = "air",
        T_K: float = DEFAULT_COVERAGE_T_K,
        P_Pa: float = DEFAULT_COVERAGE_P_PA,
    ) -> Tuple[CoverageCell, ...]:
        cells = []
        for solute_id in sorted(self.registry.solutes):
            for solvent_id in sorted(self.registry.solvents):
                cells.append(self.coverage_cell(
                    solute_id, solvent_id, carrier_id=carrier_id, T_K=T_K, P_Pa=P_Pa
                ))
        return tuple(cells)

    def coverage_summary(
        self,
        *,
        carrier_id: str = "air",
        T_K: float = DEFAULT_COVERAGE_T_K,
        P_Pa: float = DEFAULT_COVERAGE_P_PA,
    ) -> CoverageSummary:
        cells = self.coverage_cells(carrier_id=carrier_id, T_K=T_K, P_Pa=P_Pa)
        counts = {s: 0 for s in CoverageStatus}
        for cell in cells:
            counts[cell.overall_status] += 1
        return CoverageSummary(
            total_cells=len(cells),
            verified=counts[CoverageStatus.VERIFIED],
            estimated=counts[CoverageStatus.ESTIMATED],
            screening=counts[CoverageStatus.SCREENING],
            missing=counts[CoverageStatus.MISSING],
            unsupported=counts[CoverageStatus.UNSUPPORTED],
        )

    def coverage_matrix_rows(
        self,
        *,
        carrier_id: str = "air",
        T_K: float = DEFAULT_COVERAGE_T_K,
        P_Pa: float = DEFAULT_COVERAGE_P_PA,
    ) -> Tuple[dict, ...]:
        cells = self.coverage_cells(carrier_id=carrier_id, T_K=T_K, P_Pa=P_Pa)
        by_key = {(c.solute_id, c.solvent_id): c for c in cells}
        rows = []
        for solute_id in sorted(self.registry.solutes):
            row = {"Solute": solute_id}
            for solvent_id in sorted(self.registry.solvents):
                row[solvent_id] = by_key[(solute_id, solvent_id)].display
            rows.append(row)
        return tuple(rows)

    def detailed_coverage_rows(
        self,
        *,
        carrier_id: str = "air",
        T_K: float = DEFAULT_COVERAGE_T_K,
        P_Pa: float = DEFAULT_COVERAGE_P_PA,
    ) -> Tuple[dict, ...]:
        return tuple({
            "solute_id": c.solute_id,
            "solvent_id": c.solvent_id,
            "carrier_id": c.carrier_id,
            "overall_status": c.overall_status.value,
            "gas_transport": c.gas_transport_tier,
            "gas_confidence": c.gas_transport_confidence,
            "liquid_transport": c.liquid_transport_tier,
            "liquid_confidence": c.liquid_transport_confidence,
            "equilibrium": c.equilibrium_tier,
            "equilibrium_confidence": c.equilibrium_confidence,
            "equilibrium_model": c.equilibrium_model,
            "resolvable": c.resolvable,
            "note": c.note,
        } for c in self.coverage_cells(carrier_id=carrier_id, T_K=T_K, P_Pa=P_Pa))

    def missing_data_backlog(
        self,
        *,
        carrier_id: str = "air",
        T_K: float = DEFAULT_COVERAGE_T_K,
        P_Pa: float = DEFAULT_COVERAGE_P_PA,
    ) -> Tuple[dict, ...]:
        priority_order = {
            CoverageStatus.MISSING: 1,
            CoverageStatus.UNSUPPORTED: 2,
            CoverageStatus.SCREENING: 3,
            CoverageStatus.ESTIMATED: 4,
            CoverageStatus.VERIFIED: 5,
        }
        rows = []
        for c in self.coverage_cells(carrier_id=carrier_id, T_K=T_K, P_Pa=P_Pa):
            if c.overall_status == CoverageStatus.VERIFIED:
                continue
            missing_items = []
            if c.equilibrium_tier in ("MISSING", "UNSUPPORTED"):
                missing_items.append("equilibrium")
            elif c.overall_status == CoverageStatus.SCREENING:
                missing_items.append("design-grade equilibrium")
            if c.gas_transport_tier == "MISSING":
                missing_items.append("D_G")
            elif c.gas_transport_tier == "ESTIMATE":
                missing_items.append("measured/database D_G")
            if c.liquid_transport_tier == "MISSING":
                missing_items.append("D_L")
            elif c.liquid_transport_tier == "ESTIMATE":
                missing_items.append("measured/database D_L")
            rows.append({
                "priority": priority_order[c.overall_status],
                "solute_id": c.solute_id,
                "solvent_id": c.solvent_id,
                "carrier_id": c.carrier_id,
                "status": c.overall_status.value,
                "data_gap": ", ".join(missing_items) or "review",
                "note": c.note,
            })
        rows.sort(key=lambda r: (r["priority"], r["solute_id"], r["solvent_id"]))
        return tuple(rows)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(self, query: str) -> Tuple[dict, ...]:
        q = (query or "").strip().lower()
        if not q:
            return tuple()
        rows = []

        def add(entity_type: str, entity_key: str, name: str, summary: str) -> None:
            haystack = " ".join([entity_type, entity_key, name or "", summary or ""]).lower()
            if q in haystack:
                rows.append({
                    "entity_type": entity_type,
                    "entity_key": entity_key,
                    "name": name,
                    "summary": summary,
                })

        for r in self.list_solutes():
            add("solute", r["solute_id"], r["name"], f"{r['formula'] or ''} {r['cas_number'] or ''}")
        for r in self.list_solvents():
            add("solvent", r["solvent_id"], r["name"], f"property model={r['property_model']}")
        for r in self.list_carriers():
            add("carrier", r["carrier_id"], r["name"], f"viscosity={r['viscosity_model']}")
        for r in self.list_packings():
            add("packing", r["packing_id"], r["name"], f"Fp basis={r['packing_factor_basis']}")
        for r in self.list_equilibrium_pairs():
            key = f"{r['solute_id']}|{r['solvent_id']}"
            add("equilibrium_pair", key, key, f"{r['model']} confidence={r['confidence']} {r['source'] or ''}")
        for r in self.list_gas_transport_pairs():
            key = f"{r['solute_id']}|{r['carrier_id']}"
            add("gas_transport_pair", key, key, f"{r['model']} confidence={r['confidence']} {r['source'] or ''}")
        for r in self.list_liquid_transport_pairs():
            key = f"{r['solute_id']}|{r['solvent_id']}"
            add("liquid_transport_pair", key, key, f"{r['model']} confidence={r['confidence']} {r['source'] or ''}")
        for r in self.list_sources():
            add(
                "source",
                r.get("source_id", ""),
                r.get("title") or r.get("citation") or "source",
                " ".join(str(r.get(k) or "") for k in ("authors", "doi", "url", "citation")),
            )
        rows.sort(key=lambda r: (r["entity_type"], r["entity_key"]))
        return tuple(rows)


def run_phase18e_explorer_gate(database_path: str | Path) -> ExplorerGateReport:
    """Deterministic acceptance gate for Phase 18E."""
    database_path = Path(database_path)
    before = database_path.read_bytes()
    explorer = DatabaseExplorer.from_path(database_path)
    summary = explorer.coverage_summary(carrier_id="air")
    cells = {(c.solute_id, c.solvent_id): c for c in explorer.coverage_cells(carrier_id="air")}
    expected = {
        "ACN_water_verified": cells[("ACN", "water")].overall_status == CoverageStatus.VERIFIED,
        "VAc_water_verified": cells[("VAc", "water")].overall_status == CoverageStatus.VERIFIED,
        "VDC_water_estimated": cells[("VDC", "water")].overall_status == CoverageStatus.ESTIMATED,
        "VDC_acn_screening": cells[("VDC", "acrylonitrile")].overall_status == CoverageStatus.SCREENING,
        "ACN_acn_missing": cells[("ACN", "acrylonitrile")].overall_status == CoverageStatus.MISSING,
        "VAc_acn_missing": cells[("VAc", "acrylonitrile")].overall_status == CoverageStatus.MISSING,
        "summary_counts": (
            summary.total_cells == 6
            and summary.verified == 2
            and summary.estimated == 1
            and summary.screening == 1
            and summary.missing == 2
            and summary.unsupported == 0
        ),
    }
    hits = explorer.search("VDC")
    after = database_path.read_bytes()
    return ExplorerGateReport(
        integrity=explorer.repository.integrity_check(),
        foreign_key_violations=len(explorer.repository.foreign_key_violations()),
        matrix_cells=len(cells),
        summary=summary,
        expected_reference_statuses=expected,
        search_vdc_hits=len(hits),
        database_unchanged=(before == after),
    )
