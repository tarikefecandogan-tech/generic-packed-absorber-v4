"""V4 Phase 5 generic counter-current packed-absorber solver.

This module adds the first bed-profile / outlet calculation to V4.  It consumes
Phase 4 common Onda state + per-component mass-transfer coefficients and solves
one independent dilute solute at a time as a two-point boundary-value problem.

Coordinate convention (locked V4 specification)
-----------------------------------------------
    z = 0       gas inlet / liquid outlet (column bottom)
    z = Z       gas outlet / liquid inlet  (column top)

Boundary conditions
-------------------
    y(0) = y_gas_in
    x(Z) = x_liquid_in

The unknown liquid composition at the bottom, x(0), is found by shooting.
The local driving force is never clamped:

    Delta y = y - m x

so a negative driving force naturally represents desorption.

Phase 5 deliberately does NOT add:
- concentration-basis conversion (Phase 7)
- required-height root solve
- pressure drop / GPDC flooding
- reactive or non-ideal coupled multicomponent mass transfer
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Optional

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from .mass_transfer import CommonOndaState, ComponentMassTransferResult


class CounterCurrentSolverError(RuntimeError):
    """Base exception for Phase 5 counter-current calculations."""


class InvalidBoundaryCondition(CounterCurrentSolverError):
    """Raised when inlet compositions are not finite physical mole fractions."""


class BoundaryConditionSolveError(CounterCurrentSolverError):
    """Raised when the shooting variable cannot satisfy x(Z)=x_liquid_in."""


class ODEIntegrationError(CounterCurrentSolverError):
    """Raised when scipy's IVP solver fails for a trial or final integration."""


@dataclass(frozen=True)
class ComponentBoundaryConditions:
    """Canonical mole-fraction boundary conditions for one independent solute."""

    gas_inlet_y: float
    liquid_inlet_x: float = 0.0

    def __post_init__(self) -> None:
        for label, value in (
            ("gas_inlet_y", self.gas_inlet_y),
            ("liquid_inlet_x", self.liquid_inlet_x),
        ):
            if not math.isfinite(value):
                raise InvalidBoundaryCondition(f"{label} must be finite.")
            if value < 0.0 or value >= 1.0:
                raise InvalidBoundaryCondition(
                    f"{label} must satisfy 0 <= value < 1 on the V4 dilute mole-fraction basis."
                )


@dataclass(frozen=True)
class CounterCurrentSolverOptions:
    """Numerical controls separated from absorber physics."""

    ode_rtol: float = 1e-8
    ode_atol: float = 1e-12
    root_xtol: float = 2e-12
    root_rtol: float = 8.881784197001252e-16
    max_step_fraction: float = 0.01
    max_bracket_expansions: int = 40
    maximum_physical_x: float = 0.999999

    def __post_init__(self) -> None:
        if self.ode_rtol <= 0 or self.ode_atol <= 0:
            raise ValueError("ODE tolerances must be positive.")
        if self.root_xtol <= 0 or self.root_rtol <= 0:
            raise ValueError("Root tolerances must be positive.")
        if not (0 < self.max_step_fraction <= 1):
            raise ValueError("max_step_fraction must be in (0, 1].")
        if self.max_bracket_expansions < 1:
            raise ValueError("max_bracket_expansions must be at least 1.")
        if not (0 < self.maximum_physical_x < 1):
            raise ValueError("maximum_physical_x must be in (0, 1).")


@dataclass(frozen=True)
class SolverDiagnostics:
    boundary_error_x: float
    gas_solute_change_mol_s: float
    liquid_solute_change_mol_s: float
    mass_balance_error_mol_s: float
    relative_mass_balance_error: float
    min_driving_force_y: float
    max_driving_force_y: float
    root_iterations: int
    root_function_calls: int
    ode_function_evaluations: int
    mode: str


@dataclass(frozen=True)
class ComponentCounterCurrentResult:
    solute_id: str
    gas_inlet_y: float
    gas_outlet_y: float
    liquid_inlet_x: float
    liquid_bottom_x: float
    removal_fraction: Optional[float]
    packed_height_m: float
    z_m: np.ndarray
    gas_y_profile: np.ndarray
    liquid_x_profile: np.ndarray
    driving_force_profile_y: np.ndarray
    diagnostics: SolverDiagnostics

    @property
    def net_absorption(self) -> bool:
        return self.gas_outlet_y < self.gas_inlet_y

    @property
    def net_desorption(self) -> bool:
        return self.gas_outlet_y > self.gas_inlet_y


@dataclass(frozen=True)
class IndependentSolutesResult:
    """Results for 1–4 independently solved dilute solutes."""

    components: Mapping[str, ComponentCounterCurrentResult]

    def __post_init__(self) -> None:
        if not 1 <= len(self.components) <= 4:
            raise ValueError("V4.0 supports 1 to 4 independent dilute solutes per case.")


def _validate_solver_inputs(
    common: CommonOndaState,
    transfer: ComponentMassTransferResult,
) -> None:
    checks = (
        ("packed height", common.packed_height_m),
        ("gas molar flux", common.gas_molar_flux_mol_m2_s),
        ("liquid molar flux", common.liquid_molar_flux_mol_m2_s),
        ("gas molar flow", common.gas_molar_flow_mol_s),
        ("liquid molar flow", common.liquid_molar_flow_mol_s),
        ("effective wetted area", common.effective_area_m2_m3),
        ("pressure", common.pressure_Pa),
        ("K_G", transfer.K_G),
        ("equilibrium slope m", transfer.equilibrium_slope_m),
    )
    for label, value in checks:
        if not math.isfinite(value) or value <= 0:
            raise CounterCurrentSolverError(f"{label} must be finite and positive.")


def solve_component_countercurrent(
    common: CommonOndaState,
    transfer: ComponentMassTransferResult,
    boundary: ComponentBoundaryConditions,
    *,
    options: Optional[CounterCurrentSolverOptions] = None,
) -> ComponentCounterCurrentResult:
    """Solve one independent solute by shooting + solve_ivp + Brent root finding.

    The coefficient basis and ODE signs preserve the locked V3 reference case,
    while the boundary condition is generalized to nonzero solvent inlet
    loading.  No chemical name is inspected anywhere in this function.
    """

    _validate_solver_inputs(common, transfer)
    options = options or CounterCurrentSolverOptions()

    Z = common.packed_height_m
    G_flux = common.gas_molar_flux_mol_m2_s
    L_flux = common.liquid_molar_flux_mol_m2_s
    y_in = boundary.gas_inlet_y
    x_top = boundary.liquid_inlet_x
    m = transfer.equilibrium_slope_m
    rate_constant = transfer.K_G * common.effective_area_m2_m3 * common.pressure_Pa

    # The only zero shortcut allowed by the V4 specification: both streams are
    # solute-free.  y_in=0 with x_top>0 must still solve and can desorb.
    if y_in == 0.0 and x_top == 0.0:
        z = np.array([0.0, Z], dtype=float)
        zeros = np.zeros(2, dtype=float)
        diagnostics = SolverDiagnostics(
            boundary_error_x=0.0,
            gas_solute_change_mol_s=0.0,
            liquid_solute_change_mol_s=0.0,
            mass_balance_error_mol_s=0.0,
            relative_mass_balance_error=0.0,
            min_driving_force_y=0.0,
            max_driving_force_y=0.0,
            root_iterations=0,
            root_function_calls=0,
            ode_function_evaluations=0,
            mode="NO_TRANSFER",
        )
        return ComponentCounterCurrentResult(
            solute_id=transfer.solute_id,
            gas_inlet_y=0.0,
            gas_outlet_y=0.0,
            liquid_inlet_x=0.0,
            liquid_bottom_x=0.0,
            removal_fraction=None,
            packed_height_m=Z,
            z_m=z,
            gas_y_profile=zeros.copy(),
            liquid_x_profile=zeros.copy(),
            driving_force_profile_y=zeros.copy(),
            diagnostics=diagnostics,
        )

    max_step = max(Z * options.max_step_fraction, 1e-5)

    def integrate(x_bottom: float):
        def ode(_z: float, state: np.ndarray) -> list[float]:
            y, x = state
            driving = y - m * x
            rate = rate_constant * driving
            return [-rate / G_flux, -rate / L_flux]

        sol = solve_ivp(
            ode,
            (0.0, Z),
            (y_in, x_bottom),
            rtol=options.ode_rtol,
            atol=options.ode_atol,
            max_step=max_step,
        )
        if not sol.success:
            raise ODEIntegrationError(sol.message)
        return sol

    def boundary_error(x_bottom: float) -> float:
        return float(integrate(x_bottom).y[1, -1] - x_top)

    # x_bottom is constrained to a non-negative physical mole fraction.  The
    # initial upper bound preserves the old fresh-solvent V3 bracket exactly
    # when x_top=0, while also supporting a preloaded solvent.
    lower = 0.0
    x_eq_feed = y_in / max(m, 1e-30)
    upper = max(1e-12, 2.0 * x_eq_feed, 2.0 * x_top)
    upper = min(upper, options.maximum_physical_x)

    f_lower = boundary_error(lower)
    if abs(f_lower) <= options.root_xtol:
        x_bottom = lower
        root_iterations = 0
        root_calls = 1
    else:
        f_upper = boundary_error(upper)
        expansions = 0
        while f_lower * f_upper > 0 and upper < options.maximum_physical_x:
            expansions += 1
            if expansions > options.max_bracket_expansions:
                break
            upper = min(
                options.maximum_physical_x,
                max(upper * 2.0, upper + 1e-12),
            )
            f_upper = boundary_error(upper)

        if f_lower * f_upper > 0:
            raise BoundaryConditionSolveError(
                f"{transfer.solute_id}: x_bottom shooting root was not bracketed on "
                f"[0, {upper:.6g}]. Residuals were {f_lower:.6g} and {f_upper:.6g}. "
                "The requested boundary conditions may not admit a physical non-negative "
                "liquid-bottom mole fraction under the current constant-coefficient model."
            )

        root, root_info = brentq(
            boundary_error,
            lower,
            upper,
            xtol=options.root_xtol,
            rtol=options.root_rtol,
            full_output=True,
            disp=False,
        )
        x_bottom = float(root)
        root_iterations = int(root_info.iterations)
        root_calls = int(root_info.function_calls)

    sol = integrate(x_bottom)
    y_profile = np.asarray(sol.y[0], dtype=float)
    x_profile = np.asarray(sol.y[1], dtype=float)
    z = np.asarray(sol.t, dtype=float)

    # Numerical noise can create tiny values below zero.  Do not clamp the ODE
    # or driving force; only normalize an endpoint if it is below the ODE atol.
    y_out_raw = float(y_profile[-1])
    if y_out_raw < 0 and abs(y_out_raw) <= 10.0 * options.ode_atol:
        y_out = 0.0
        y_profile = y_profile.copy()
        y_profile[-1] = 0.0
    else:
        y_out = y_out_raw

    x_top_calc = float(x_profile[-1])
    boundary_residual = x_top_calc - x_top
    driving = y_profile - m * x_profile

    physical_tol = max(1e-10, 100.0 * options.ode_atol)
    if float(np.min(y_profile)) < -physical_tol or float(np.max(y_profile)) >= 1.0 + physical_tol:
        raise CounterCurrentSolverError(
            f"{transfer.solute_id}: gas mole-fraction profile left physical bounds [0, 1)."
        )
    if float(np.min(x_profile)) < -physical_tol or float(np.max(x_profile)) >= 1.0 + physical_tol:
        raise CounterCurrentSolverError(
            f"{transfer.solute_id}: liquid mole-fraction profile left physical bounds [0, 1)."
        )

    gas_change = common.gas_molar_flow_mol_s * (y_in - y_out)
    liquid_change = common.liquid_molar_flow_mol_s * (x_bottom - x_top)
    balance_error = gas_change - liquid_change
    scale = max(abs(gas_change), abs(liquid_change), 1e-30)
    relative_balance_error = abs(balance_error) / scale

    if y_in > 0:
        removal = (y_in - y_out) / y_in
    else:
        removal = None

    delta = y_in - y_out
    if abs(delta) <= max(1e-14, 10.0 * options.ode_atol):
        mode = "NEAR_EQUILIBRIUM"
    elif delta > 0:
        mode = "NET_ABSORPTION"
    else:
        mode = "NET_DESORPTION"

    diagnostics = SolverDiagnostics(
        boundary_error_x=boundary_residual,
        gas_solute_change_mol_s=gas_change,
        liquid_solute_change_mol_s=liquid_change,
        mass_balance_error_mol_s=balance_error,
        relative_mass_balance_error=relative_balance_error,
        min_driving_force_y=float(np.min(driving)),
        max_driving_force_y=float(np.max(driving)),
        root_iterations=root_iterations,
        root_function_calls=root_calls,
        ode_function_evaluations=int(sol.nfev),
        mode=mode,
    )

    return ComponentCounterCurrentResult(
        solute_id=transfer.solute_id,
        gas_inlet_y=y_in,
        gas_outlet_y=y_out,
        liquid_inlet_x=x_top,
        liquid_bottom_x=x_bottom,
        removal_fraction=removal,
        packed_height_m=Z,
        z_m=z,
        gas_y_profile=y_profile,
        liquid_x_profile=x_profile,
        driving_force_profile_y=np.asarray(driving, dtype=float),
        diagnostics=diagnostics,
    )


def solve_independent_solutes(
    common: CommonOndaState,
    transfers: Mapping[str, ComponentMassTransferResult],
    boundaries: Mapping[str, ComponentBoundaryConditions],
    *,
    options: Optional[CounterCurrentSolverOptions] = None,
) -> IndependentSolutesResult:
    """Solve 1–4 independent dilute solutes using the shared bulk-flow state."""

    if not 1 <= len(transfers) <= 4:
        raise CounterCurrentSolverError(
            "V4.0 supports 1 to 4 independent dilute solutes per case."
        )
    if set(transfers) != set(boundaries):
        raise CounterCurrentSolverError(
            "Transfer-result IDs and boundary-condition IDs must match exactly."
        )

    solved: dict[str, ComponentCounterCurrentResult] = {}
    for solute_id, transfer in transfers.items():
        if transfer.solute_id != solute_id:
            raise CounterCurrentSolverError(
                f"Transfer key '{solute_id}' does not match result solute_id '{transfer.solute_id}'."
            )
        solved[solute_id] = solve_component_countercurrent(
            common,
            transfer,
            boundaries[solute_id],
            options=options,
        )
    return IndependentSolutesResult(components=solved)
