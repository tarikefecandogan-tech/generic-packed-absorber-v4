"""Phase 18C — deterministic parity validation across data repositories."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Tuple

from .mass_transfer import AbsorberOperatingPoint
from .repository import AbsorberDataRepository
from .simulation import GenericAbsorberCase, run_generic_absorber_case
from .units import (
    CompositionFractionBasis,
    GasConcentrationBasis,
    canonical_y_from_total_and_fractions,
)

PHASE18C_PARITY_ID = "PHASE18C_BACKEND_PARITY_2026_10_07"


@dataclass(frozen=True)
class RepositoryScenarioParity:
    scenario_id: str
    python_backend_id: str
    sqlite_backend_id: str
    metrics_checked: int
    max_absolute_error: float
    max_relative_error: float
    readiness_match: bool
    pass_gate: bool


@dataclass(frozen=True)
class RepositoryParityReport:
    registry_dictionary_parity: Mapping[str, bool]
    inventory_match: bool
    reference_id_match: bool
    scenarios: Tuple[RepositoryScenarioParity, ...]

    @property
    def pass_gate(self) -> bool:
        return (
            self.inventory_match
            and self.reference_id_match
            and all(self.registry_dictionary_parity.values())
            and all(row.pass_gate for row in self.scenarios)
        )

    @property
    def metrics_checked(self) -> int:
        return sum(row.metrics_checked for row in self.scenarios)


def _operating() -> AbsorberOperatingPoint:
    return AbsorberOperatingPoint(
        diameter_m=0.5,
        packed_height_m=1.4,
        gas_actual_m3_h=117.53,
        liquid_mass_kg_h=2500.0,
        temperature_K=295.15,
        pressure_Pa=101325.0,
    )


def _scenario_cases(registry) -> Tuple[Tuple[str, GenericAbsorberCase], ...]:
    solutes = {sid: registry.get_solute(sid) for sid in ("ACN", "VAc")}
    ref_feed = canonical_y_from_total_and_fractions(
        5000.0,
        GasConcentrationBasis.MG_VOC_NM3,
        {"ACN": 0.93, "VAc": 0.07},
        CompositionFractionBasis.VOC_MASS,
        solutes,
    ).canonical_y

    return (
        (
            "reference_acn_vac_water",
            GenericAbsorberCase(
                operating=_operating(),
                solute_ids=("ACN", "VAc"),
                carrier_id="air",
                solvent_id="water",
                packing_id="25mm_metal_pall_ring",
                gas_inlet_y=ref_feed,
                liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
            ),
        ),
        (
            "vdc_water",
            GenericAbsorberCase(
                operating=_operating(),
                solute_ids=("VDC",),
                carrier_id="air",
                solvent_id="water",
                packing_id="25mm_metal_pall_ring",
                gas_inlet_y={"VDC": 1000e-6},
                liquid_inlet_x={"VDC": 0.0},
            ),
        ),
        (
            "vdc_acrylonitrile",
            GenericAbsorberCase(
                operating=_operating(),
                solute_ids=("VDC",),
                carrier_id="air",
                solvent_id="acrylonitrile",
                packing_id="25mm_metal_pall_ring",
                gas_inlet_y={"VDC": 1000e-6},
                liquid_inlet_x={"VDC": 0.0},
                solvent_evaporation_expected=True,
            ),
        ),
        (
            "three_solute_water",
            GenericAbsorberCase(
                operating=_operating(),
                solute_ids=("ACN", "VAc", "VDC"),
                carrier_id="air",
                solvent_id="water",
                packing_id="25mm_metal_pall_ring",
                gas_inlet_y={"ACN": 500e-6, "VAc": 100e-6, "VDC": 100e-6},
                liquid_inlet_x={"ACN": 0.0, "VAc": 0.0, "VDC": 0.0},
            ),
        ),
        (
            "vdc_water_preloaded",
            GenericAbsorberCase(
                operating=_operating(),
                solute_ids=("VDC",),
                carrier_id="air",
                solvent_id="water",
                packing_id="25mm_metal_pall_ring",
                gas_inlet_y={"VDC": 1000e-6},
                liquid_inlet_x={"VDC": 2.0e-7},
            ),
        ),
    )


def _compare_numbers(a: float, b: float, *, rtol: float, atol: float) -> tuple[bool, float, float]:
    aa = float(a)
    bb = float(b)
    abs_err = abs(aa - bb)
    scale = max(abs(aa), abs(bb), atol)
    rel_err = abs_err / scale
    return math.isclose(aa, bb, rel_tol=rtol, abs_tol=atol), abs_err, rel_err


def _compare_scenario(
    scenario_id: str,
    case: GenericAbsorberCase,
    python_repository: AbsorberDataRepository,
    sqlite_repository: AbsorberDataRepository,
    *,
    rtol: float,
    atol: float,
) -> RepositoryScenarioParity:
    py = run_generic_absorber_case(case, repository=python_repository)
    db = run_generic_absorber_case(case, repository=sqlite_repository)

    checks = []
    errors = []
    pairs = [
        (py.inlet_report.total_y, db.inlet_report.total_y),
        (py.outlet_report.total_y, db.outlet_report.total_y),
        (py.outlet_report.total_mgVOC_Nm3, db.outlet_report.total_mgVOC_Nm3),
        (py.outlet_report.total_mgC_Nm3, db.outlet_report.total_mgC_Nm3),
        (py.stream_balance.overall_removal_voc_mass, db.stream_balance.overall_removal_voc_mass),
        (py.stream_balance.overall_removal_molar, db.stream_balance.overall_removal_molar),
        (py.stream_balance.total_captured_kg_h, db.stream_balance.total_captured_kg_h),
        (py.hydraulics.pressure_drop.wet_pressure_drop_Pa_m, db.hydraulics.pressure_drop.wet_pressure_drop_Pa_m),
        (py.hydraulics.pressure_drop.total_pressure_drop_Pa, db.hydraulics.pressure_drop.total_pressure_drop_Pa),
        (py.hydraulics.flooding.flooding_percent, db.hydraulics.flooding.flooding_percent),
        (py.common.effective_area_m2_m3, db.common.effective_area_m2_m3),
    ]

    for sid in case.solute_ids:
        pyt = py.transfer_results[sid]
        dbt = db.transfer_results[sid]
        pys = py.solver_results.components[sid]
        dbs = db.solver_results.components[sid]
        pairs.extend([
            (pyt.absorption_factor, dbt.absorption_factor),
            (pyt.HTU_OG_m, dbt.HTU_OG_m),
            (pyt.NTU_OG, dbt.NTU_OG),
            (pyt.equilibrium_slope_m, dbt.equilibrium_slope_m),
            (pys.gas_outlet_y, dbs.gas_outlet_y),
            (pys.liquid_bottom_x, dbs.liquid_bottom_x),
            (pys.removal_fraction, dbs.removal_fraction),
            (pys.diagnostics.relative_mass_balance_error, dbs.diagnostics.relative_mass_balance_error),
        ])

    for a, b in pairs:
        ok, abs_err, rel_err = _compare_numbers(a, b, rtol=rtol, atol=atol)
        checks.append(ok)
        errors.append((abs_err, rel_err))

    readiness_match = (
        py.pre_applicability.status == db.pre_applicability.status
        and py.post_applicability.status == db.post_applicability.status
        and py.post_applicability.confidence == db.post_applicability.confidence
    )

    return RepositoryScenarioParity(
        scenario_id=scenario_id,
        python_backend_id=py.data_source.backend_id,
        sqlite_backend_id=db.data_source.backend_id,
        metrics_checked=len(checks),
        max_absolute_error=max((e[0] for e in errors), default=0.0),
        max_relative_error=max((e[1] for e in errors), default=0.0),
        readiness_match=readiness_match,
        pass_gate=all(checks) and readiness_match,
    )


def run_phase18c_repository_parity(
    python_repository: AbsorberDataRepository,
    sqlite_repository: AbsorberDataRepository,
    *,
    rtol: float = 1e-12,
    atol: float = 1e-12,
) -> RepositoryParityReport:
    """Compare repository content and all deterministic Phase-18C scenarios."""
    py_registry = python_repository.load_registry()
    db_registry = sqlite_repository.load_registry()
    parity = {
        "solutes": py_registry.solutes == db_registry.solutes,
        "carriers": py_registry.carriers == db_registry.carriers,
        "solvents": py_registry.solvents == db_registry.solvents,
        "packings": py_registry.packings == db_registry.packings,
        "gas_transport_pairs": py_registry.gas_transport_pairs == db_registry.gas_transport_pairs,
        "liquid_transport_pairs": py_registry.liquid_transport_pairs == db_registry.liquid_transport_pairs,
        "equilibrium_pairs": py_registry.equilibrium_pairs == db_registry.equilibrium_pairs,
    }
    scenarios = tuple(
        _compare_scenario(sid, case, python_repository, sqlite_repository, rtol=rtol, atol=atol)
        for sid, case in _scenario_cases(py_registry)
    )
    return RepositoryParityReport(
        registry_dictionary_parity=parity,
        inventory_match=py_registry.inventory_counts() == db_registry.inventory_counts(),
        reference_id_match=py_registry.reference_id == db_registry.reference_id,
        scenarios=scenarios,
    )
