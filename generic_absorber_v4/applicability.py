"""V4 Phase 8 applicability, validity, and confidence engine.

This module does not calculate absorption performance.  It inspects the inputs,
registered data, resolved properties, correlation diagnostics, numerical solver
results, and hydraulics results produced by Phases 1–7 and turns them into an
explicit engineering readiness report.

Design rules
------------
* Critical missing data are BLOCK issues; no silent property fallback is allowed.
* Unsupported physics are distinguished from ordinary extrapolation warnings.
* Correlation-range extrapolation is visible, never silent.
* Numerical failure is distinguished from physical desorption or difficult absorption.
* Confidence is categorical (HIGH / MODERATE / SCREENING / NOT_RATED), never a fake percentage.
* The weakest critical category controls the overall confidence rating.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Mapping, Optional, Sequence, Tuple

from .countercurrent import ComponentCounterCurrentResult, IndependentSolutesResult
from .hydraulics import HydraulicResult
from .mass_transfer import AbsorberOperatingPoint, CommonOndaState, ComponentMassTransferResult
from .models import ConfidenceClass, PackingSpec
from .registry import AbsorberDataRegistry, UnknownEntityError
from .resolver import ResolvedComponentProperties, ResolvedProperty


class IssueSeverity(str, Enum):
    BLOCK = "BLOCK"
    WARNING = "WARNING"
    INFO = "INFO"


class ReadinessStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    OUTSIDE_RECOMMENDED_RANGE = "OUTSIDE_RECOMMENDED_RANGE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNSUPPORTED_PHYSICS = "UNSUPPORTED_PHYSICS"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    SCREENING = "SCREENING"
    NOT_RATED = "NOT_RATED"


@dataclass(frozen=True)
class ApplicabilityIssue:
    code: str
    severity: IssueSeverity
    scope: str
    message: str
    outside_recommended_range: bool = False
    category: str = "general"


@dataclass(frozen=True)
class ConfidenceSummary:
    thermodynamics: ConfidenceLevel = ConfidenceLevel.NOT_RATED
    mass_transfer: ConfidenceLevel = ConfidenceLevel.NOT_RATED
    hydraulics: ConfidenceLevel = ConfidenceLevel.NOT_RATED
    overall: ConfidenceLevel = ConfidenceLevel.NOT_RATED
    rationale: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicabilityReport:
    status: ReadinessStatus
    issues: Tuple[ApplicabilityIssue, ...]
    confidence: ConfidenceSummary = field(default_factory=ConfidenceSummary)

    @property
    def blocks(self) -> Tuple[ApplicabilityIssue, ...]:
        return tuple(i for i in self.issues if i.severity == IssueSeverity.BLOCK)

    @property
    def warnings(self) -> Tuple[ApplicabilityIssue, ...]:
        return tuple(i for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def infos(self) -> Tuple[ApplicabilityIssue, ...]:
        return tuple(i for i in self.issues if i.severity == IssueSeverity.INFO)

    @property
    def can_run(self) -> bool:
        return self.status not in {
            ReadinessStatus.INSUFFICIENT_DATA,
            ReadinessStatus.UNSUPPORTED_PHYSICS,
            ReadinessStatus.NUMERICAL_FAILURE,
        }


@dataclass(frozen=True)
class ApplicabilityCase:
    operating: AbsorberOperatingPoint
    solute_ids: Tuple[str, ...]
    carrier_id: str
    solvent_id: str
    packing_id: str
    gas_inlet_y: Mapping[str, float]
    liquid_inlet_x: Mapping[str, float] = field(default_factory=dict)
    physical_absorption: bool = True
    isothermal: bool = True
    independent_solutes: bool = True
    reactive_system: bool = False
    nonideal_multicomponent_vle_required: bool = False
    solvent_evaporation_expected: bool = False
    foaming_expected: bool = False


_CONFIDENCE_RANK = {
    ConfidenceLevel.NOT_RATED: 0,
    ConfidenceLevel.SCREENING: 1,
    ConfidenceLevel.MODERATE: 2,
    ConfidenceLevel.HIGH: 3,
}


def _issue(
    code: str,
    severity: IssueSeverity,
    scope: str,
    message: str,
    *,
    outside: bool = False,
    category: str = "general",
) -> ApplicabilityIssue:
    return ApplicabilityIssue(
        code=code,
        severity=severity,
        scope=scope,
        message=message,
        outside_recommended_range=outside,
        category=category,
    )


def _status_from_issues(issues: Sequence[ApplicabilityIssue]) -> ReadinessStatus:
    codes = {i.code for i in issues if i.severity == IssueSeverity.BLOCK}
    categories = {i.category for i in issues if i.severity == IssueSeverity.BLOCK}

    if "numerical" in categories or any(c.startswith("NUMERICAL_") for c in codes):
        return ReadinessStatus.NUMERICAL_FAILURE
    if "unsupported_physics" in categories:
        return ReadinessStatus.UNSUPPORTED_PHYSICS
    if "data" in categories:
        return ReadinessStatus.INSUFFICIENT_DATA
    if any(i.outside_recommended_range for i in issues):
        return ReadinessStatus.OUTSIDE_RECOMMENDED_RANGE
    if any(i.severity == IssueSeverity.BLOCK for i in issues):
        return ReadinessStatus.OUTSIDE_RECOMMENDED_RANGE
    if any(i.severity == IssueSeverity.WARNING for i in issues):
        return ReadinessStatus.READY_WITH_WARNINGS
    return ReadinessStatus.READY


def _confidence_from_classes(classes: Sequence[ConfidenceClass]) -> ConfidenceLevel:
    if not classes:
        return ConfidenceLevel.NOT_RATED
    if any(c in (ConfidenceClass.C, ConfidenceClass.D) for c in classes):
        return ConfidenceLevel.SCREENING
    if any(c == ConfidenceClass.B for c in classes):
        return ConfidenceLevel.MODERATE
    return ConfidenceLevel.HIGH


def _weakest(levels: Sequence[ConfidenceLevel]) -> ConfidenceLevel:
    rated = [x for x in levels if x != ConfidenceLevel.NOT_RATED]
    if not rated:
        return ConfidenceLevel.NOT_RATED
    return min(rated, key=lambda x: _CONFIDENCE_RANK[x])


def _packing_confidence(packing: Optional[PackingSpec]) -> Optional[ConfidenceClass]:
    if packing is None or packing.provenance is None:
        return None
    return packing.provenance.confidence


def _collect_property_classes(props: Sequence[ResolvedProperty]) -> list[ConfidenceClass]:
    return [p.confidence for p in props]


def assess_pre_applicability(
    registry: AbsorberDataRegistry,
    case: ApplicabilityCase,
) -> ApplicabilityReport:
    """Validate model-domain and data readiness before running the physics core."""
    issues: list[ApplicabilityIssue] = []

    if not 1 <= len(case.solute_ids) <= 4:
        issues.append(_issue(
            "UNSUPPORTED_COMPONENT_COUNT", IssueSeverity.BLOCK, "model",
            f"V4.0 supports 1–4 independent dilute solutes; received {len(case.solute_ids)}.",
            category="unsupported_physics",
        ))

    if len(set(case.solute_ids)) != len(case.solute_ids):
        issues.append(_issue(
            "DUPLICATE_SOLUTE_ID", IssueSeverity.BLOCK, "input",
            "Each solute ID must appear only once in a case.", category="data",
        ))

    if not case.physical_absorption or case.reactive_system:
        issues.append(_issue(
            "REACTIVE_OR_NONPHYSICAL_ABSORPTION_UNSUPPORTED", IssueSeverity.BLOCK, "model",
            "V4.0 supports non-reactive physical absorption only.",
            category="unsupported_physics",
        ))
    if not case.isothermal:
        issues.append(_issue(
            "NONISOTHERMAL_UNSUPPORTED", IssueSeverity.BLOCK, "model",
            "V4.0 mass transfer is isothermal; an energy balance is not implemented.",
            category="unsupported_physics",
        ))
    if not case.independent_solutes or case.nonideal_multicomponent_vle_required:
        issues.append(_issue(
            "COUPLED_NONIDEAL_VLE_UNSUPPORTED", IssueSeverity.BLOCK, "model",
            "V4.0 solves dilute solutes independently and does not implement coupled nonideal multicomponent VLE.",
            category="unsupported_physics",
        ))

    if case.solvent_evaporation_expected:
        issues.append(_issue(
            "SOLVENT_EVAPORATION_NOT_MODELLED", IssueSeverity.WARNING, "model",
            "Materially volatile solvent is expected, but solvent evaporation is not included in V4.0.",
            outside=True, category="model_domain",
        ))
    if case.foaming_expected:
        issues.append(_issue(
            "FOAMING_CORRECTION_NOT_MODELLED", IssueSeverity.WARNING, "hydraulics",
            "Foaming is expected, but no foaming correction is applied to hydraulic capacity.",
            category="hydraulics",
        ))

    # Pure-component / packing identity checks.
    try:
        registry.get_carrier(case.carrier_id)
    except UnknownEntityError as exc:
        issues.append(_issue("MISSING_CARRIER", IssueSeverity.BLOCK, "data", str(exc), category="data"))
    try:
        registry.get_solvent(case.solvent_id)
    except UnknownEntityError as exc:
        issues.append(_issue("MISSING_SOLVENT", IssueSeverity.BLOCK, "data", str(exc), category="data"))
    try:
        packing = registry.get_packing(case.packing_id)
        if packing.packing_class != "random":
            issues.append(_issue(
                "STRUCTURED_PACKING_UNSUPPORTED", IssueSeverity.BLOCK, "packing",
                "V4.0 Onda/GPDC implementation is defined for random packing only.",
                category="unsupported_physics",
            ))
    except UnknownEntityError as exc:
        packing = None
        issues.append(_issue("MISSING_PACKING", IssueSeverity.BLOCK, "data", str(exc), category="data"))

    total_y = 0.0
    for sid in case.solute_ids:
        try:
            registry.get_solute(sid)
        except UnknownEntityError as exc:
            issues.append(_issue(f"MISSING_SOLUTE_{sid}", IssueSeverity.BLOCK, sid, str(exc), category="data"))
            continue

        y = case.gas_inlet_y.get(sid)
        if y is None:
            issues.append(_issue(
                f"MISSING_GAS_BOUNDARY_{sid}", IssueSeverity.BLOCK, sid,
                "Gas inlet mole fraction y_in is required for every solute.", category="data",
            ))
        elif not math.isfinite(y) or y < 0 or y >= 1:
            issues.append(_issue(
                f"INVALID_GAS_BOUNDARY_{sid}", IssueSeverity.BLOCK, sid,
                f"Gas inlet y must satisfy 0 <= y < 1; received {y!r}.", category="data",
            ))
        else:
            total_y += y

        x = case.liquid_inlet_x.get(sid, 0.0)
        if not math.isfinite(x) or x < 0 or x >= 1:
            issues.append(_issue(
                f"INVALID_LIQUID_BOUNDARY_{sid}", IssueSeverity.BLOCK, sid,
                f"Liquid inlet x must satisfy 0 <= x < 1; received {x!r}.", category="data",
            ))

        # Pair completeness.
        try:
            availability = registry.availability(sid, case.carrier_id, case.solvent_id)
            if not availability.gas_transport_available:
                solute_obj = registry.get_solute(sid)
                carrier_obj = registry.get_carrier(case.carrier_id)
                if (
                    solute_obj.fuller_diffusion_volume is not None
                    and carrier_obj.fuller_diffusion_volume is not None
                ):
                    issues.append(_issue(
                        f"DG_CORRELATION_FALLBACK_{sid}", IssueSeverity.WARNING, sid,
                        f"Gas-transport pair {sid}/{case.carrier_id} is not registered; "
                        "Fuller correlation inputs are available, so DG will be estimated as Confidence C.",
                        category="data",
                    ))
                else:
                    issues.append(_issue(
                        f"MISSING_DG_PAIR_{sid}", IssueSeverity.BLOCK, sid,
                        f"Gas-transport pair {sid}/{case.carrier_id} is not registered and Fuller inputs are incomplete.",
                        category="data",
                    ))
            if not availability.liquid_transport_available:
                solute_obj = registry.get_solute(sid)
                solvent_obj = registry.get_solvent(case.solvent_id)
                if (
                    solute_obj.boiling_molar_volume_cm3_mol is not None
                    and solvent_obj.wilke_chang_association_factor is not None
                ):
                    issues.append(_issue(
                        f"DL_CORRELATION_FALLBACK_{sid}", IssueSeverity.WARNING, sid,
                        f"Liquid-transport pair {sid}/{case.solvent_id} is not registered; "
                        "Wilke–Chang inputs are available, so DL will be estimated as Confidence C.",
                        category="data",
                    ))
                else:
                    issues.append(_issue(
                        f"MISSING_DL_PAIR_{sid}", IssueSeverity.BLOCK, sid,
                        f"Liquid-transport pair {sid}/{case.solvent_id} is not registered and Wilke–Chang inputs are incomplete.",
                        category="data",
                    ))
            if not availability.equilibrium_available:
                issues.append(_issue(
                    f"MISSING_EQUILIBRIUM_PAIR_{sid}", IssueSeverity.BLOCK, sid,
                    f"Equilibrium pair {sid}/{case.solvent_id} is not registered.", category="data",
                ))
            else:
                eq = registry.require_equilibrium_pair(sid, case.solvent_id)
                if eq.model not in ("henry_pc", "linear_m"):
                    issues.append(_issue(
                        f"UNSUPPORTED_EQUILIBRIUM_{sid}", IssueSeverity.BLOCK, sid,
                        f"Equilibrium model '{eq.model}' is not solved in V4.0.",
                        category="unsupported_physics",
                    ))
                T = case.operating.temperature_K
                if eq.validity_temperature_min_K is not None and T < eq.validity_temperature_min_K:
                    issues.append(_issue(
                        f"EQUILIBRIUM_T_LOW_{sid}", IssueSeverity.WARNING, sid,
                        f"Operating temperature {T:.2f} K is below the registered equilibrium validity range.",
                        outside=True, category="model_domain",
                    ))
                if eq.validity_temperature_max_K is not None and T > eq.validity_temperature_max_K:
                    issues.append(_issue(
                        f"EQUILIBRIUM_T_HIGH_{sid}", IssueSeverity.WARNING, sid,
                        f"Operating temperature {T:.2f} K is above the registered equilibrium validity range.",
                        outside=True, category="model_domain",
                    ))
        except UnknownEntityError:
            # Missing pure entities are already reported above.
            pass

    # Deliberately labelled engineering screening thresholds, not universal laws.
    if total_y >= 0.05:
        issues.append(_issue(
            "DILUTE_GAS_RED_ZONE", IssueSeverity.WARNING, "feed",
            f"Total solute gas mole fraction is {total_y:.4f} (>=0.05). The independent dilute-solute assumption is outside the recommended V4.0 range.",
            outside=True, category="model_domain",
        ))
    elif total_y >= 0.01:
        issues.append(_issue(
            "DILUTE_GAS_YELLOW_ZONE", IssueSeverity.WARNING, "feed",
            f"Total solute gas mole fraction is {total_y:.4f} (0.01–0.05). Treat results as extrapolative screening.",
            outside=True, category="model_domain",
        ))
    else:
        issues.append(_issue(
            "DILUTE_GAS_GREEN_ZONE", IssueSeverity.INFO, "feed",
            f"Total solute gas mole fraction is {total_y:.4f} (<0.01), within the V4.0 dilute-gas screening zone.",
            category="model_domain",
        ))

    return ApplicabilityReport(status=_status_from_issues(issues), issues=tuple(issues))


def _solver_components(
    solver_results: Optional[IndependentSolutesResult | Mapping[str, ComponentCounterCurrentResult]],
) -> Mapping[str, ComponentCounterCurrentResult]:
    if solver_results is None:
        return {}
    if isinstance(solver_results, IndependentSolutesResult):
        return solver_results.components
    return solver_results


def _build_confidence(
    resolved_components: Mapping[str, ResolvedComponentProperties],
    packing: Optional[PackingSpec],
    hydraulics: Optional[HydraulicResult],
) -> ConfidenceSummary:
    thermo_classes: list[ConfidenceClass] = []
    mt_classes: list[ConfidenceClass] = []
    hyd_classes: list[ConfidenceClass] = []
    rationale: list[str] = []

    seen_bulk = False
    for rp in resolved_components.values():
        thermo_classes.extend(_collect_property_classes([rp.equilibrium.active_property]))
        mt_classes.extend(_collect_property_classes([rp.gas_diffusivity, rp.liquid_diffusivity]))
        if not seen_bulk:
            mt_classes.extend(_collect_property_classes([
                rp.carrier.density, rp.carrier.viscosity,
                rp.solvent.density, rp.solvent.viscosity, rp.solvent.surface_tension,
            ]))
            hyd_classes.extend(_collect_property_classes([
                rp.carrier.density,
                rp.solvent.density, rp.solvent.viscosity,
            ]))
            seen_bulk = True

    pc = _packing_confidence(packing)
    if pc is not None:
        mt_classes.append(pc)
        hyd_classes.append(pc)

    thermodynamics = _confidence_from_classes(thermo_classes)
    mass_transfer = _confidence_from_classes(mt_classes)
    hydraulics_level = _confidence_from_classes(hyd_classes)

    if hydraulics is not None and hydraulics.flooding.packing_factor_estimated:
        hydraulics_level = ConfidenceLevel.SCREENING
        rationale.append("Hydraulics downgraded to SCREENING because the GPDC packing factor is estimated.")

    for rp in resolved_components.values():
        for prop in (rp.gas_diffusivity, rp.liquid_diffusivity, rp.equilibrium.active_property):
            if prop.estimated:
                rationale.append(f"{rp.solute_id} {prop.name} is correlation-estimated ({prop.method}).")

    overall = _weakest([thermodynamics, mass_transfer, hydraulics_level])
    return ConfidenceSummary(
        thermodynamics=thermodynamics,
        mass_transfer=mass_transfer,
        hydraulics=hydraulics_level,
        overall=overall,
        rationale=tuple(dict.fromkeys(rationale)),
    )


def assess_post_applicability(
    pre_report: ApplicabilityReport,
    *,
    resolved_components: Mapping[str, ResolvedComponentProperties],
    common: Optional[CommonOndaState] = None,
    transfer_results: Optional[Mapping[str, ComponentMassTransferResult]] = None,
    solver_results: Optional[IndependentSolutesResult | Mapping[str, ComponentCounterCurrentResult]] = None,
    hydraulics: Optional[HydraulicResult] = None,
    packing: Optional[PackingSpec] = None,
    numerical_failure: Optional[str] = None,
) -> ApplicabilityReport:
    """Add correlation, solver, hydraulic, and confidence checks after calculation."""
    issues = list(pre_report.issues)

    if numerical_failure:
        issues.append(_issue(
            "NUMERICAL_SOLVER_FAILURE", IssueSeverity.BLOCK, "solver",
            numerical_failure, category="numerical",
        ))

    # Property-quality flags.  The reference case intentionally exposes its
    # legacy diffusivity reference-state limitation rather than hiding it.
    for sid, rp in resolved_components.items():
        for prop in (rp.gas_diffusivity, rp.liquid_diffusivity):
            note = (prop.note or "").lower()
            if "not defined" in note or "were not defined" in note:
                issues.append(_issue(
                    f"UNSPECIFIED_REFERENCE_STATE_{sid}_{prop.name.replace(' ', '_').upper()}",
                    IssueSeverity.WARNING,
                    sid,
                    f"{prop.name} uses a locked legacy fixed value whose original reference state was not specified.",
                    category="data_quality",
                ))
            if prop.estimated:
                issues.append(_issue(
                    f"ESTIMATED_PROPERTY_{sid}_{prop.name.replace(' ', '_').upper()}",
                    IssueSeverity.WARNING,
                    sid,
                    f"{prop.name} is correlation-estimated; result confidence is screening-level unless externally validated.",
                    category="data_quality",
                ))

    if common is not None:
        if common.Re_L < 10.0:
            issues.append(_issue(
                "ONDA_LOW_RE_L", IssueSeverity.WARNING, "mass_transfer",
                f"Re_L={common.Re_L:.3g} < 10; low liquid loading/incomplete wetting may reduce Onda reliability.",
                outside=True, category="correlation_range",
            ))
        if common.Re_G < 50.0:
            issues.append(_issue(
                "ONDA_LOW_RE_G", IssueSeverity.WARNING, "mass_transfer",
                f"Re_G={common.Re_G:.3g} < 50; gas-side Onda correlation is in a low-Re screening region.",
                outside=True, category="correlation_range",
            ))
        if common.wetting_fraction < 0.30:
            issues.append(_issue(
                "LOW_EFFECTIVE_WETTING", IssueSeverity.WARNING, "mass_transfer",
                f"Effective wetting is {100*common.wetting_fraction:.1f}% (<30%); poor liquid distribution is a material risk.",
                outside=True, category="correlation_range",
            ))

    for sid, mt in (transfer_results or {}).items():
        if mt.absorption_factor <= 1.0:
            issues.append(_issue(
                f"ABSORPTION_FACTOR_LOW_{sid}", IssueSeverity.WARNING, sid,
                f"Absorption factor A={mt.absorption_factor:.4g} <= 1; absorption is thermodynamically/operationally difficult.",
                category="performance",
            ))

    for sid, result in _solver_components(solver_results).items():
        d = result.diagnostics
        if not all(math.isfinite(v) for v in (
            result.gas_outlet_y, result.liquid_bottom_x,
            d.boundary_error_x, d.relative_mass_balance_error,
            d.min_driving_force_y, d.max_driving_force_y,
        )):
            issues.append(_issue(
                f"NUMERICAL_NONFINITE_{sid}", IssueSeverity.BLOCK, sid,
                "Solver returned a non-finite state or diagnostic.", category="numerical",
            ))
            continue

        if result.gas_outlet_y < -1e-12 or result.gas_outlet_y >= 1.0 or result.liquid_bottom_x < -1e-12 or result.liquid_bottom_x >= 1.0:
            issues.append(_issue(
                f"NUMERICAL_PHYSICAL_BOUNDS_{sid}", IssueSeverity.BLOCK, sid,
                "Solved gas/liquid composition lies outside physical mole-fraction bounds.", category="numerical",
            ))

        mbe = abs(d.relative_mass_balance_error)
        bce = abs(d.boundary_error_x)
        if mbe > 1e-4:
            issues.append(_issue(
                f"NUMERICAL_MASS_BALANCE_FAILURE_{sid}", IssueSeverity.BLOCK, sid,
                f"Relative solute mass-balance error is {mbe:.3e} (>1e-4).", category="numerical",
            ))
        elif mbe > 1e-7:
            issues.append(_issue(
                f"MASS_BALANCE_WARNING_{sid}", IssueSeverity.WARNING, sid,
                f"Relative solute mass-balance error is {mbe:.3e} (>1e-7).", category="numerical_quality",
            ))
        if bce > 1e-5:
            issues.append(_issue(
                f"NUMERICAL_BOUNDARY_FAILURE_{sid}", IssueSeverity.BLOCK, sid,
                f"Liquid-inlet boundary closure error is {bce:.3e} (>1e-5).", category="numerical",
            ))
        elif bce > 1e-8:
            issues.append(_issue(
                f"BOUNDARY_CLOSURE_WARNING_{sid}", IssueSeverity.WARNING, sid,
                f"Liquid-inlet boundary closure error is {bce:.3e} (>1e-8).", category="numerical_quality",
            ))

        if d.min_driving_force_y < -1e-12:
            issues.append(_issue(
                f"NEGATIVE_DRIVING_FORCE_{sid}", IssueSeverity.WARNING, sid,
                f"Local y-mx reaches {d.min_driving_force_y:.3e}; a desorption zone exists and is retained physically.",
                category="performance",
            ))
        if result.net_desorption:
            issues.append(_issue(
                f"NET_DESORPTION_{sid}", IssueSeverity.WARNING, sid,
                "Gas outlet exceeds gas inlet for this component: the column has net desorption, not net absorption.",
                category="performance",
            ))

    if hydraulics is not None:
        f = hydraulics.flooding
        if f.packing_factor_estimated:
            issues.append(_issue(
                "ESTIMATED_GPDC_PACKING_FACTOR", IssueSeverity.WARNING, "hydraulics",
                "No empirical/literature GPDC packing factor is registered; geometric a/eps^3 fallback is being used.",
                category="hydraulics",
            ))
        if not f.gpdc_valid:
            issues.append(_issue(
                "GPDC_OUTSIDE_F_LV_RANGE", IssueSeverity.WARNING, "hydraulics",
                f"F_LV={f.F_LV_flood:.4g} is outside the implemented GPDC correlation range.",
                outside=True, category="correlation_range",
            ))
        if f.flooding_percent >= 100.0:
            issues.append(_issue(
                "HYDRAULIC_FLOODING", IssueSeverity.BLOCK, "hydraulics",
                f"GPDC predicts {f.flooding_percent:.1f}% of flood (>=100%); the operating point is hydraulically infeasible.",
                outside=True, category="hydraulics",
            ))
        elif f.flooding_percent >= 90.0:
            issues.append(_issue(
                "NEAR_FLOODING", IssueSeverity.WARNING, "hydraulics",
                f"Column operates at {f.flooding_percent:.1f}% of predicted flood velocity (>90%).",
                outside=True, category="hydraulics",
            ))
        elif f.flooding_percent >= 80.0:
            issues.append(_issue(
                "HIGH_HYDRAULIC_LOADING", IssueSeverity.WARNING, "hydraulics",
                f"Column operates at {f.flooding_percent:.1f}% of predicted flood velocity (>80%).",
                category="hydraulics",
            ))
        elif f.flooding_percent < 40.0:
            issues.append(_issue(
                "HYDRAULIC_UNDERLOADED", IssueSeverity.INFO, "hydraulics",
                f"Column operates at {f.flooding_percent:.1f}% of predicted flood velocity (<40%): high capacity margin / underloaded regime.",
                category="hydraulics",
            ))

    confidence = _build_confidence(resolved_components, packing, hydraulics)
    return ApplicabilityReport(
        status=_status_from_issues(issues),
        issues=tuple(issues),
        confidence=confidence,
    )
