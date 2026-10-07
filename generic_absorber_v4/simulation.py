"""Phase 14 integrated generic absorber simulation orchestrator.

This module is the first product-facing composition layer of V4.  It does not
introduce new transport, equilibrium, ODE, or hydraulic correlations.  Instead,
it connects the already-verified Phase 1-13 layers into one reusable calculation
workflow that is independent of Streamlit.

Calculation chain
-----------------
input/canonical case -> applicability pre-check -> property resolution -> common
Onda state -> per-solute mass transfer -> independent counter-current solves ->
hydraulics -> unit/report reconstruction -> applicability post-check.

The physics modules remain chemical-name independent.  The default Phase 14
catalog simply combines the registered chemistries available through Phase 13.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .applicability import (
    ApplicabilityCase,
    ApplicabilityReport,
    assess_post_applicability,
    assess_pre_applicability,
)
from .countercurrent import (
    ComponentBoundaryConditions,
    CounterCurrentSolverOptions,
    IndependentSolutesResult,
    solve_independent_solutes,
)
from .hydraulics import HydraulicResult, calculate_hydraulics
from .mass_transfer import (
    AbsorberOperatingPoint,
    CommonOndaState,
    ComponentMassTransferResult,
    calculate_common_onda_state,
    calculate_component_mass_transfer,
)
from .registry import AbsorberDataRegistry
from .resolver import PropertyResolver, ResolvedComponentProperties
from .units import GasStreamBalance, GasStreamReport, gas_stream_balance, report_gas_stream
from .vdc_acn import build_vdc_acn_registry
from .packing_catalog import register_phase17_comparison_packings

PHASE14_INTEGRATED_SIMULATOR_ID = "PHASE14_INTEGRATED_GENERIC_SIMULATOR_2026_10_07"


class IntegratedSimulationError(RuntimeError):
    """Base exception for the Phase 14 orchestration layer."""


class SimulationBlockedError(IntegratedSimulationError):
    """Raised when the pre-applicability gate contains a blocking issue."""

    def __init__(self, report: ApplicabilityReport):
        self.report = report
        codes = ", ".join(issue.code for issue in report.blocks) or "unknown block"
        super().__init__(f"Simulation blocked by pre-applicability gate: {codes}")


@dataclass(frozen=True)
class GenericAbsorberCase:
    operating: AbsorberOperatingPoint
    solute_ids: Tuple[str, ...]
    carrier_id: str
    solvent_id: str
    packing_id: str
    gas_inlet_y: Mapping[str, float]
    liquid_inlet_x: Mapping[str, float] = field(default_factory=dict)
    solvent_evaporation_expected: bool = False
    foaming_expected: bool = False

    def __post_init__(self) -> None:
        if not 1 <= len(self.solute_ids) <= 4:
            raise ValueError("GenericAbsorberCase requires 1-4 solutes.")
        if len(set(self.solute_ids)) != len(self.solute_ids):
            raise ValueError("GenericAbsorberCase solute IDs must be unique.")
        if set(self.gas_inlet_y) != set(self.solute_ids):
            raise ValueError("gas_inlet_y keys must exactly match solute_ids.")
        unknown_liquid = set(self.liquid_inlet_x) - set(self.solute_ids)
        if unknown_liquid:
            raise ValueError(f"liquid_inlet_x contains unknown solutes: {sorted(unknown_liquid)}")
        for sid in self.solute_ids:
            y = float(self.gas_inlet_y[sid])
            x = float(self.liquid_inlet_x.get(sid, 0.0))
            if not 0.0 <= y < 1.0:
                raise ValueError(f"{sid}: gas inlet y must be in [0,1).")
            if not 0.0 <= x < 1.0:
                raise ValueError(f"{sid}: liquid inlet x must be in [0,1).")
        if sum(float(self.gas_inlet_y[sid]) for sid in self.solute_ids) >= 1.0:
            raise ValueError("Total gas solute mole fraction must remain below 1.")


@dataclass(frozen=True)
class SoluteCompatibility:
    solute_id: str
    ready: bool
    reason: str


@dataclass(frozen=True)
class GenericAbsorberSimulationResult:
    case_id: str
    case: GenericAbsorberCase
    registry: AbsorberDataRegistry
    resolver: PropertyResolver
    pre_applicability: ApplicabilityReport
    post_applicability: ApplicabilityReport
    resolved_components: Mapping[str, ResolvedComponentProperties]
    common: CommonOndaState
    transfer_results: Mapping[str, ComponentMassTransferResult]
    solver_results: IndependentSolutesResult
    hydraulics: HydraulicResult
    inlet_report: GasStreamReport
    outlet_report: GasStreamReport
    stream_balance: GasStreamBalance

    @property
    def pass_gate(self) -> bool:
        return not self.pre_applicability.blocks and not self.post_applicability.blocks


def build_phase14_registry() -> AbsorberDataRegistry:
    """Return the combined registered chemistry catalog available at Phase 14."""
    registry = build_vdc_acn_registry()
    register_phase17_comparison_packings(registry)
    registry.reference_id = PHASE14_INTEGRATED_SIMULATOR_ID
    return registry


def compatible_solutes(
    registry: AbsorberDataRegistry,
    *,
    carrier_id: str,
    solvent_id: str,
    temperature_K: float,
    pressure_Pa: float,
) -> Tuple[SoluteCompatibility, ...]:
    """Report which catalog solutes can be fully resolved for a selected fluid pair.

    Missing fixed transport pairs may still be READY when the Phase 11
    correlations can resolve them.  Equilibrium has no silent estimator.
    """
    resolver = PropertyResolver(registry)
    rows = []
    for sid in registry.solutes:
        try:
            resolver.resolve_component_properties(
                sid, carrier_id, solvent_id, temperature_K, pressure_Pa
            )
        except Exception as exc:  # explicit reason is surfaced to the UI
            rows.append(SoluteCompatibility(sid, False, str(exc)))
        else:
            rows.append(SoluteCompatibility(sid, True, "READY"))
    return tuple(rows)


def run_generic_absorber_case(
    case: GenericAbsorberCase,
    *,
    registry: Optional[AbsorberDataRegistry] = None,
    solver_options: Optional[CounterCurrentSolverOptions] = None,
) -> GenericAbsorberSimulationResult:
    """Run the complete verified V4 calculation chain for one generic case."""
    registry = registry or build_phase14_registry()
    resolver = PropertyResolver(registry)

    app_case = ApplicabilityCase(
        operating=case.operating,
        solute_ids=case.solute_ids,
        carrier_id=case.carrier_id,
        solvent_id=case.solvent_id,
        packing_id=case.packing_id,
        gas_inlet_y=case.gas_inlet_y,
        liquid_inlet_x=case.liquid_inlet_x,
        solvent_evaporation_expected=case.solvent_evaporation_expected,
        foaming_expected=case.foaming_expected,
    )
    pre = assess_pre_applicability(registry, app_case)
    if pre.blocks:
        raise SimulationBlockedError(pre)

    resolved: dict[str, ResolvedComponentProperties] = {}
    for sid in case.solute_ids:
        resolved[sid] = resolver.resolve_component_properties(
            sid,
            case.carrier_id,
            case.solvent_id,
            case.operating.temperature_K,
            case.operating.pressure_Pa,
        )

    packing = registry.get_packing(case.packing_id)
    first = resolved[case.solute_ids[0]]
    common = calculate_common_onda_state(
        case.operating, packing, first.carrier, first.solvent
    )

    transfers = {
        sid: calculate_component_mass_transfer(common, resolved[sid])
        for sid in case.solute_ids
    }
    boundaries = {
        sid: ComponentBoundaryConditions(
            gas_inlet_y=float(case.gas_inlet_y[sid]),
            liquid_inlet_x=float(case.liquid_inlet_x.get(sid, 0.0)),
        )
        for sid in case.solute_ids
    }
    solved = solve_independent_solutes(
        common, transfers, boundaries, options=solver_options
    )

    hydraulics = calculate_hydraulics(
        common, packing, first.carrier, first.solvent
    )

    solutes = {sid: registry.get_solute(sid) for sid in case.solute_ids}
    inlet_report = report_gas_stream(case.gas_inlet_y, solutes)
    outlet_y = {
        sid: solved.components[sid].gas_outlet_y for sid in case.solute_ids
    }
    outlet_report = report_gas_stream(outlet_y, solutes)
    balance = gas_stream_balance(
        case.gas_inlet_y,
        outlet_y,
        solutes,
        gas_molar_flow_mol_s=common.gas_molar_flow_mol_s,
    )

    post = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=hydraulics,
        packing=packing,
    )

    return GenericAbsorberSimulationResult(
        case_id=PHASE14_INTEGRATED_SIMULATOR_ID,
        case=case,
        registry=registry,
        resolver=resolver,
        pre_applicability=pre,
        post_applicability=post,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=hydraulics,
        inlet_report=inlet_report,
        outlet_report=outlet_report,
        stream_balance=balance,
    )
