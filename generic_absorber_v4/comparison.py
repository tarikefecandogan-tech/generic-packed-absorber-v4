"""Phase 17 engineering comparison tools.

Every comparison alternative is evaluated through the full Phase 14 integrated
simulator.  This module deliberately does not calculate a hidden composite
"best" score: performance, hydraulics, applicability and confidence remain
separate engineering decision dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Mapping, Optional, Sequence, Tuple

from .registry import AbsorberDataRegistry
from .simulation import (
    GenericAbsorberCase,
    GenericAbsorberSimulationResult,
    build_phase14_registry,
    compatible_solutes,
    run_generic_absorber_case,
)

PHASE17_COMPARISON_ID = "PHASE17_ENGINEERING_COMPARISON_TOOLS_2026_10_07"
MAX_COMPARISON_ALTERNATIVES = 20


class ComparisonError(RuntimeError):
    pass


class InvalidComparisonDefinition(ComparisonError):
    pass


class ComparisonMode(str, Enum):
    PACKING = "packing"
    SOLVENT = "solvent"
    SCENARIO = "scenario"


@dataclass(frozen=True)
class NamedCase:
    label: str
    case: GenericAbsorberCase

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise InvalidComparisonDefinition("Scenario label cannot be blank.")


@dataclass(frozen=True)
class ComponentComparisonMetrics:
    solute_id: str
    inlet_ppmv: float
    outlet_ppmv: float
    removal_percent: Optional[float]
    absorption_factor: float
    HTU_OG_m: float
    NTU_OG: float
    equilibrium_slope_m: float
    mode: str


@dataclass(frozen=True)
class ComparisonAlternativeResult:
    label: str
    mode: ComparisonMode
    success: bool
    solvent_id: str
    packing_id: str
    status: str
    confidence: str
    outlet_mgVOC_Nm3: Optional[float] = None
    outlet_ppmv: Optional[float] = None
    voc_mass_removal_percent: Optional[float] = None
    captured_kg_h: Optional[float] = None
    flooding_percent: Optional[float] = None
    wet_pressure_drop_mbar_m: Optional[float] = None
    total_pressure_drop_mbar: Optional[float] = None
    component_metrics: Mapping[str, ComponentComparisonMetrics] = field(default_factory=dict)
    error: Optional[str] = None
    simulation: Optional[GenericAbsorberSimulationResult] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class EngineeringComparisonResult:
    comparison_id: str
    mode: ComparisonMode
    base_case: Optional[GenericAbsorberCase]
    alternatives: Tuple[ComparisonAlternativeResult, ...]

    @property
    def successful_alternatives(self) -> int:
        return sum(1 for a in self.alternatives if a.success)

    @property
    def failed_alternatives(self) -> int:
        return len(self.alternatives) - self.successful_alternatives

    def records(self) -> Tuple[dict, ...]:
        rows = []
        for alt in self.alternatives:
            row = {
                "label": alt.label,
                "mode": alt.mode.value,
                "success": alt.success,
                "solvent_id": alt.solvent_id,
                "packing_id": alt.packing_id,
                "status": alt.status,
                "confidence": alt.confidence,
                "outlet_mgVOC_Nm3": alt.outlet_mgVOC_Nm3,
                "outlet_ppmv": alt.outlet_ppmv,
                "voc_mass_removal_percent": alt.voc_mass_removal_percent,
                "captured_kg_h": alt.captured_kg_h,
                "flooding_percent": alt.flooding_percent,
                "wet_pressure_drop_mbar_m": alt.wet_pressure_drop_mbar_m,
                "total_pressure_drop_mbar": alt.total_pressure_drop_mbar,
                "error": alt.error,
            }
            for sid, cm in alt.component_metrics.items():
                prefix = f"{sid}__"
                row.update({
                    prefix + "inlet_ppmv": cm.inlet_ppmv,
                    prefix + "outlet_ppmv": cm.outlet_ppmv,
                    prefix + "removal_percent": cm.removal_percent,
                    prefix + "absorption_factor": cm.absorption_factor,
                    prefix + "HTU_OG_m": cm.HTU_OG_m,
                    prefix + "NTU_OG": cm.NTU_OG,
                    prefix + "equilibrium_slope_m": cm.equilibrium_slope_m,
                    prefix + "mode": cm.mode,
                })
            rows.append(row)
        return tuple(rows)


def _result_from_simulation(
    label: str,
    mode: ComparisonMode,
    result: GenericAbsorberSimulationResult,
) -> ComparisonAlternativeResult:
    metrics = {}
    for sid in result.case.solute_ids:
        solved = result.solver_results.components[sid]
        mt = result.transfer_results[sid]
        metrics[sid] = ComponentComparisonMetrics(
            solute_id=sid,
            inlet_ppmv=result.inlet_report.components[sid].ppmv,
            outlet_ppmv=result.outlet_report.components[sid].ppmv,
            removal_percent=None if solved.removal_fraction is None else 100.0 * solved.removal_fraction,
            absorption_factor=mt.absorption_factor,
            HTU_OG_m=mt.HTU_OG_m,
            NTU_OG=mt.NTU_OG,
            equilibrium_slope_m=mt.equilibrium_slope_m,
            mode=solved.diagnostics.mode,
        )
    removal = result.stream_balance.overall_removal_voc_mass
    return ComparisonAlternativeResult(
        label=label,
        mode=mode,
        success=True,
        solvent_id=result.case.solvent_id,
        packing_id=result.case.packing_id,
        status=result.post_applicability.status.value,
        confidence=result.post_applicability.confidence.overall.value,
        outlet_mgVOC_Nm3=result.outlet_report.total_mgVOC_Nm3,
        outlet_ppmv=result.outlet_report.total_ppmv,
        voc_mass_removal_percent=None if removal is None else 100.0 * removal,
        captured_kg_h=result.stream_balance.total_captured_kg_h,
        flooding_percent=result.hydraulics.flooding.flooding_percent,
        wet_pressure_drop_mbar_m=result.hydraulics.pressure_drop.wet_pressure_drop_mbar_m,
        total_pressure_drop_mbar=result.hydraulics.pressure_drop.total_pressure_drop_mbar,
        component_metrics=metrics,
        simulation=result,
    )


def _failure(
    label: str,
    mode: ComparisonMode,
    case: GenericAbsorberCase,
    exc: Exception,
) -> ComparisonAlternativeResult:
    return ComparisonAlternativeResult(
        label=label,
        mode=mode,
        success=False,
        solvent_id=case.solvent_id,
        packing_id=case.packing_id,
        status="FAILED_OR_BLOCKED",
        confidence="NOT_RATED",
        error=str(exc),
    )


def _validate_count(items: Sequence[object]) -> None:
    if not 1 <= len(items) <= MAX_COMPARISON_ALTERNATIVES:
        raise InvalidComparisonDefinition(
            f"Comparison requires 1-{MAX_COMPARISON_ALTERNATIVES} alternatives."
        )


def compare_packings(
    base_case: GenericAbsorberCase,
    packing_ids: Sequence[str],
    *,
    registry: Optional[AbsorberDataRegistry] = None,
) -> EngineeringComparisonResult:
    """Compare packing alternatives on an otherwise identical basis."""
    _validate_count(packing_ids)
    if len(set(packing_ids)) != len(packing_ids):
        raise InvalidComparisonDefinition("Packing alternatives must be unique.")
    registry = registry or build_phase14_registry()
    results = []
    for packing_id in packing_ids:
        case = replace(base_case, packing_id=packing_id)
        try:
            label = registry.get_packing(packing_id).name
            sim = run_generic_absorber_case(case, registry=registry)
            results.append(_result_from_simulation(label, ComparisonMode.PACKING, sim))
        except Exception as exc:
            results.append(_failure(str(packing_id), ComparisonMode.PACKING, case, exc))
    return EngineeringComparisonResult(
        comparison_id=PHASE17_COMPARISON_ID,
        mode=ComparisonMode.PACKING,
        base_case=base_case,
        alternatives=tuple(results),
    )


def compare_solvents(
    base_case: GenericAbsorberCase,
    solvent_ids: Sequence[str],
    *,
    registry: Optional[AbsorberDataRegistry] = None,
    solvent_evaporation_expected: Optional[Mapping[str, bool]] = None,
) -> EngineeringComparisonResult:
    """Compare solvents while preserving feed, carrier, packing and geometry.

    Unsupported solute-solvent combinations become failed alternatives rather
    than causing the complete comparison to abort.
    """
    _validate_count(solvent_ids)
    if len(set(solvent_ids)) != len(solvent_ids):
        raise InvalidComparisonDefinition("Solvent alternatives must be unique.")
    registry = registry or build_phase14_registry()
    evaporation = dict(solvent_evaporation_expected or {})
    results = []
    for solvent_id in solvent_ids:
        case = replace(
            base_case,
            solvent_id=solvent_id,
            solvent_evaporation_expected=bool(evaporation.get(solvent_id, False)),
        )
        try:
            label = registry.get_solvent(solvent_id).name
            compatibility = compatible_solutes(
                registry,
                carrier_id=case.carrier_id,
                solvent_id=solvent_id,
                temperature_K=case.operating.temperature_K,
                pressure_Pa=case.operating.pressure_Pa,
            )
            by_id = {row.solute_id: row for row in compatibility}
            missing = [sid for sid in case.solute_ids if sid not in by_id or not by_id[sid].ready]
            if missing:
                reasons = "; ".join(
                    f"{sid}: {by_id[sid].reason if sid in by_id else 'not registered'}" for sid in missing
                )
                raise ComparisonError(f"Selected chemistry is not resolvable in solvent '{solvent_id}': {reasons}")
            sim = run_generic_absorber_case(case, registry=registry)
            results.append(_result_from_simulation(label, ComparisonMode.SOLVENT, sim))
        except Exception as exc:
            results.append(_failure(str(solvent_id), ComparisonMode.SOLVENT, case, exc))
    return EngineeringComparisonResult(
        comparison_id=PHASE17_COMPARISON_ID,
        mode=ComparisonMode.SOLVENT,
        base_case=base_case,
        alternatives=tuple(results),
    )


def compare_named_cases(
    cases: Sequence[NamedCase],
    *,
    registry: Optional[AbsorberDataRegistry] = None,
) -> EngineeringComparisonResult:
    """Compare complete named scenarios without forcing them onto one chemistry."""
    _validate_count(cases)
    labels = [item.label for item in cases]
    if len(set(labels)) != len(labels):
        raise InvalidComparisonDefinition("Scenario labels must be unique.")
    registry = registry or build_phase14_registry()
    results = []
    for item in cases:
        try:
            sim = run_generic_absorber_case(item.case, registry=registry)
            results.append(_result_from_simulation(item.label, ComparisonMode.SCENARIO, sim))
        except Exception as exc:
            results.append(_failure(item.label, ComparisonMode.SCENARIO, item.case, exc))
    return EngineeringComparisonResult(
        comparison_id=PHASE17_COMPARISON_ID,
        mode=ComparisonMode.SCENARIO,
        base_case=None,
        alternatives=tuple(results),
    )
