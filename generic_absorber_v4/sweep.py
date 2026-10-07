"""Phase 16 parameter-sweep and sensitivity-analysis engine.

The sweep layer intentionally contains no absorber correlations of its own.
Each point is created by modifying a canonical :class:`GenericAbsorberCase`
and then calling the verified Phase 14 integrated simulator.  Therefore
property resolution, Onda/two-film mass transfer, counter-current ODEs,
hydraulics, unit reconstruction and applicability checks are rerun at every
point.

Phase 16 supports one- and two-dimensional numerical sweeps.  Categorical
chemistry/packing comparisons are reserved for Phase 17.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import math
from typing import Mapping, Optional, Sequence, Tuple

import numpy as np

from .countercurrent import CounterCurrentSolverOptions
from .registry import AbsorberDataRegistry
from .simulation import (
    GenericAbsorberCase,
    GenericAbsorberSimulationResult,
    SimulationBlockedError,
    build_phase14_registry,
    run_generic_absorber_case,
)

PHASE16_PARAMETER_SWEEP_ID = "PHASE16_PARAMETER_SWEEP_2026_10_07"
MAX_SWEEP_POINTS = 225


class SweepError(RuntimeError):
    """Base exception for the Phase 16 sweep layer."""


class InvalidSweepDefinition(SweepError):
    """Raised when sweep axes or point counts are invalid."""


class SweepVariable(str, Enum):
    TEMPERATURE_C = "temperature_C"
    PRESSURE_BAR_ABS = "pressure_bar_abs"
    GAS_ACTUAL_M3_H = "gas_actual_m3_h"
    LIQUID_MASS_KG_H = "liquid_mass_kg_h"
    DIAMETER_M = "diameter_m"
    PACKED_HEIGHT_M = "packed_height_m"
    FEED_SCALE = "feed_scale"

    @property
    def label(self) -> str:
        return {
            self.TEMPERATURE_C: "Temperature",
            self.PRESSURE_BAR_ABS: "Pressure",
            self.GAS_ACTUAL_M3_H: "Actual gas flow",
            self.LIQUID_MASS_KG_H: "Liquid flow",
            self.DIAMETER_M: "Column diameter",
            self.PACKED_HEIGHT_M: "Packed height",
            self.FEED_SCALE: "Feed concentration scale",
        }[self]

    @property
    def unit(self) -> str:
        return {
            self.TEMPERATURE_C: "°C",
            self.PRESSURE_BAR_ABS: "bar abs",
            self.GAS_ACTUAL_M3_H: "m³/h actual",
            self.LIQUID_MASS_KG_H: "kg/h",
            self.DIAMETER_M: "m",
            self.PACKED_HEIGHT_M: "m",
            self.FEED_SCALE: "× base feed",
        }[self]


@dataclass(frozen=True)
class SweepAxis:
    variable: SweepVariable
    start: float
    stop: float
    points: int

    def __post_init__(self) -> None:
        if not isinstance(self.variable, SweepVariable):
            object.__setattr__(self, "variable", SweepVariable(self.variable))
        for name, value in (("start", self.start), ("stop", self.stop)):
            if not math.isfinite(float(value)):
                raise InvalidSweepDefinition(f"{name} must be finite.")
        if int(self.points) != self.points or not 2 <= int(self.points) <= MAX_SWEEP_POINTS:
            raise InvalidSweepDefinition(
                f"points must be an integer between 2 and {MAX_SWEEP_POINTS}."
            )
        if math.isclose(float(self.start), float(self.stop), rel_tol=0.0, abs_tol=0.0):
            raise InvalidSweepDefinition("Sweep start and stop must be different.")
        _validate_axis_value(self.variable, float(self.start))
        _validate_axis_value(self.variable, float(self.stop))

    @property
    def values(self) -> Tuple[float, ...]:
        return tuple(float(x) for x in np.linspace(self.start, self.stop, self.points))


@dataclass(frozen=True)
class ComponentSweepMetrics:
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
class SweepPointResult:
    coordinates: Mapping[str, float]
    success: bool
    status: str
    confidence: str
    outlet_mgVOC_Nm3: Optional[float] = None
    outlet_ppmv: Optional[float] = None
    voc_mass_removal_percent: Optional[float] = None
    captured_kg_h: Optional[float] = None
    flooding_percent: Optional[float] = None
    wet_pressure_drop_mbar_m: Optional[float] = None
    total_pressure_drop_mbar: Optional[float] = None
    solvent_viscosity_Pa_s: Optional[float] = None
    carrier_density_kg_m3: Optional[float] = None
    component_metrics: Mapping[str, ComponentSweepMetrics] = field(default_factory=dict)
    error: Optional[str] = None
    simulation: Optional[GenericAbsorberSimulationResult] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class ParameterSweepResult:
    sweep_id: str
    base_case: GenericAbsorberCase
    axes: Tuple[SweepAxis, ...]
    points: Tuple[SweepPointResult, ...]

    @property
    def total_points(self) -> int:
        return len(self.points)

    @property
    def successful_points(self) -> int:
        return sum(1 for p in self.points if p.success)

    @property
    def failed_points(self) -> int:
        return self.total_points - self.successful_points

    @property
    def is_two_dimensional(self) -> bool:
        return len(self.axes) == 2

    def records(self) -> Tuple[dict, ...]:
        """Flatten sweep results for tables/CSV without recalculating physics."""
        rows = []
        for point in self.points:
            row = {
                **point.coordinates,
                "success": point.success,
                "status": point.status,
                "confidence": point.confidence,
                "outlet_mgVOC_Nm3": point.outlet_mgVOC_Nm3,
                "outlet_ppmv": point.outlet_ppmv,
                "voc_mass_removal_percent": point.voc_mass_removal_percent,
                "captured_kg_h": point.captured_kg_h,
                "flooding_percent": point.flooding_percent,
                "wet_pressure_drop_mbar_m": point.wet_pressure_drop_mbar_m,
                "total_pressure_drop_mbar": point.total_pressure_drop_mbar,
                "solvent_viscosity_Pa_s": point.solvent_viscosity_Pa_s,
                "carrier_density_kg_m3": point.carrier_density_kg_m3,
                "error": point.error,
            }
            for sid, cm in point.component_metrics.items():
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


def _validate_axis_value(variable: SweepVariable, value: float) -> None:
    if variable is SweepVariable.TEMPERATURE_C:
        if value <= -273.15:
            raise InvalidSweepDefinition("Temperature must remain above absolute zero.")
        return
    if variable is SweepVariable.FEED_SCALE:
        if value < 0.0:
            raise InvalidSweepDefinition("Feed scale cannot be negative.")
        return
    if value <= 0.0:
        raise InvalidSweepDefinition(f"{variable.label} must remain positive.")


def base_value_for_variable(case: GenericAbsorberCase, variable: SweepVariable) -> float:
    op = case.operating
    return {
        SweepVariable.TEMPERATURE_C: op.temperature_K - 273.15,
        SweepVariable.PRESSURE_BAR_ABS: op.pressure_Pa / 1.0e5,
        SweepVariable.GAS_ACTUAL_M3_H: op.gas_actual_m3_h,
        SweepVariable.LIQUID_MASS_KG_H: op.liquid_mass_kg_h,
        SweepVariable.DIAMETER_M: op.diameter_m,
        SweepVariable.PACKED_HEIGHT_M: op.packed_height_m,
        SweepVariable.FEED_SCALE: 1.0,
    }[variable]


def suggested_sweep_bounds(case: GenericAbsorberCase, variable: SweepVariable) -> Tuple[float, float]:
    """Return UI-friendly defaults only; these are not correlation validity limits."""
    base = base_value_for_variable(case, variable)
    if variable is SweepVariable.TEMPERATURE_C:
        return base - 5.0, base + 5.0
    if variable is SweepVariable.PRESSURE_BAR_ABS:
        return max(0.05, 0.75 * base), 1.25 * base
    if variable in {SweepVariable.GAS_ACTUAL_M3_H, SweepVariable.LIQUID_MASS_KG_H}:
        return 0.5 * base, 1.5 * base
    if variable is SweepVariable.DIAMETER_M:
        return max(0.01, 0.75 * base), 1.25 * base
    if variable is SweepVariable.PACKED_HEIGHT_M:
        return max(0.01, 0.5 * base), 2.0 * base
    return 0.5, 1.5


def apply_sweep_values(
    base_case: GenericAbsorberCase,
    values: Mapping[SweepVariable, float],
) -> GenericAbsorberCase:
    """Create one canonical case from the base case and numeric sweep coordinates."""
    op = base_case.operating
    changes = {}
    feed_scale = 1.0

    for variable, raw in values.items():
        variable = SweepVariable(variable)
        value = float(raw)
        _validate_axis_value(variable, value)
        if variable is SweepVariable.TEMPERATURE_C:
            changes["temperature_K"] = value + 273.15
        elif variable is SweepVariable.PRESSURE_BAR_ABS:
            changes["pressure_Pa"] = value * 1.0e5
        elif variable is SweepVariable.GAS_ACTUAL_M3_H:
            changes["gas_actual_m3_h"] = value
        elif variable is SweepVariable.LIQUID_MASS_KG_H:
            changes["liquid_mass_kg_h"] = value
        elif variable is SweepVariable.DIAMETER_M:
            changes["diameter_m"] = value
        elif variable is SweepVariable.PACKED_HEIGHT_M:
            changes["packed_height_m"] = value
        elif variable is SweepVariable.FEED_SCALE:
            feed_scale = value

    new_op = replace(op, **changes)
    new_y = {sid: float(y) * feed_scale for sid, y in base_case.gas_inlet_y.items()}
    if sum(new_y.values()) >= 1.0:
        raise InvalidSweepDefinition(
            "Feed-scale point makes total gas solute mole fraction >= 1; dilute gas case is invalid."
        )

    return replace(base_case, operating=new_op, gas_inlet_y=new_y)


def _point_from_simulation(
    coordinates: Mapping[str, float],
    result: GenericAbsorberSimulationResult,
) -> SweepPointResult:
    cm = {}
    for sid in result.case.solute_ids:
        solved = result.solver_results.components[sid]
        mt = result.transfer_results[sid]
        cm[sid] = ComponentSweepMetrics(
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

    first = result.resolved_components[result.case.solute_ids[0]]
    removal = result.stream_balance.overall_removal_voc_mass
    return SweepPointResult(
        coordinates=dict(coordinates),
        success=True,
        status=result.post_applicability.status.value,
        confidence=result.post_applicability.confidence.overall.value,
        outlet_mgVOC_Nm3=result.outlet_report.total_mgVOC_Nm3,
        outlet_ppmv=result.outlet_report.total_ppmv,
        voc_mass_removal_percent=None if removal is None else 100.0 * removal,
        captured_kg_h=result.stream_balance.total_captured_kg_h,
        flooding_percent=result.hydraulics.flooding.flooding_percent,
        wet_pressure_drop_mbar_m=result.hydraulics.pressure_drop.wet_pressure_drop_mbar_m,
        total_pressure_drop_mbar=result.hydraulics.pressure_drop.total_pressure_drop_mbar,
        solvent_viscosity_Pa_s=first.solvent.viscosity.value,
        carrier_density_kg_m3=first.carrier.density.value,
        component_metrics=cm,
        simulation=result,
    )


def run_parameter_sweep(
    base_case: GenericAbsorberCase,
    axes: Sequence[SweepAxis],
    *,
    registry: Optional[AbsorberDataRegistry] = None,
    solver_options: Optional[CounterCurrentSolverOptions] = None,
) -> ParameterSweepResult:
    """Run a 1D or 2D full-physics parameter sweep.

    Each point independently reruns the integrated simulation.  A blocked or
    numerically failed point is retained in the result table instead of aborting
    the remaining sweep.
    """
    axes = tuple(axes)
    if len(axes) not in (1, 2):
        raise InvalidSweepDefinition("Phase 16 supports exactly one or two sweep axes.")
    if len({axis.variable for axis in axes}) != len(axes):
        raise InvalidSweepDefinition("Sweep axes must use different variables.")

    total = math.prod(axis.points for axis in axes)
    if total > MAX_SWEEP_POINTS:
        raise InvalidSweepDefinition(
            f"Sweep requests {total} points; Phase 16 limit is {MAX_SWEEP_POINTS}."
        )

    registry = registry or build_phase14_registry()
    points = []
    if len(axes) == 1:
        coordinate_sets = [((axes[0].variable, x),) for x in axes[0].values]
    else:
        coordinate_sets = [
            ((axes[0].variable, x), (axes[1].variable, y))
            for y in axes[1].values
            for x in axes[0].values
        ]

    for coordinate_set in coordinate_sets:
        values = {var: value for var, value in coordinate_set}
        coordinates = {var.value: float(value) for var, value in coordinate_set}
        try:
            case = apply_sweep_values(base_case, values)
            result = run_generic_absorber_case(
                case, registry=registry, solver_options=solver_options
            )
        except SimulationBlockedError as exc:
            points.append(SweepPointResult(
                coordinates=coordinates,
                success=False,
                status=exc.report.status.value,
                confidence=exc.report.confidence.overall.value,
                error="; ".join(f"{i.code}: {i.message}" for i in exc.report.blocks),
            ))
        except Exception as exc:
            points.append(SweepPointResult(
                coordinates=coordinates,
                success=False,
                status="NUMERICAL_OR_INPUT_FAILURE",
                confidence="NOT RATED",
                error=f"{type(exc).__name__}: {exc}",
            ))
        else:
            points.append(_point_from_simulation(coordinates, result))

    return ParameterSweepResult(
        sweep_id=PHASE16_PARAMETER_SWEEP_ID,
        base_case=base_case,
        axes=axes,
        points=tuple(points),
    )
