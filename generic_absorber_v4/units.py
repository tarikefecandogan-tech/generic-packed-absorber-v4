"""Generic units and composition layer for Packed Absorber Simulator V4.

Phase 7 keeps the physics solvers on canonical variables:

* gas composition: component mole fraction ``y_i``
* liquid loading: component mole fraction ``x_i``
* temperature: K
* pressure: Pa
* actual gas flow: m3/h at operating T/P

UI/reporting bases are converted here and nowhere inside the mass-transfer,
ODE or hydraulics layers.  The fixed normal reference used by the locked V3
case is 273.15 K and 101325 Pa.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Mapping, Optional

from .models import SoluteSpec

R = 8.314462618
MW_C_KG_MOL = 12.011e-3


class UnitConversionError(ValueError):
    """Base error for invalid unit/composition conversions."""


class GasConcentrationBasis(str, Enum):
    MG_VOC_NM3 = "mgVOC/Nm³"
    MG_C_NM3 = "mgC/Nm³"
    PPMV = "ppmv"


class CompositionFractionBasis(str, Enum):
    MOLE = "mole"
    VOC_MASS = "voc_mass"
    CARBON_MASS = "carbon_mass"


@dataclass(frozen=True)
class NormalConditions:
    temperature_K: float = 273.15
    pressure_Pa: float = 101325.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.temperature_K) or self.temperature_K <= 0:
            raise UnitConversionError("Normal-condition temperature must be positive.")
        if not math.isfinite(self.pressure_Pa) or self.pressure_Pa <= 0:
            raise UnitConversionError("Normal-condition pressure must be positive.")

    @property
    def molar_concentration_mol_m3(self) -> float:
        return self.pressure_Pa / (R * self.temperature_K)


DEFAULT_NORMAL_CONDITIONS = NormalConditions()


@dataclass(frozen=True)
class ComponentGasReport:
    solute_id: str
    y: float
    ppmv: float
    mgVOC_Nm3: float
    mgC_Nm3: float


@dataclass(frozen=True)
class GasStreamReport:
    components: Mapping[str, ComponentGasReport]
    total_y: float
    total_ppmv: float
    total_mgVOC_Nm3: float
    total_mgC_Nm3: float


@dataclass(frozen=True)
class MixtureInputResult:
    canonical_y: Mapping[str, float]
    normalized_fractions: Mapping[str, float]
    fraction_basis: CompositionFractionBasis
    requested_total_value: float
    requested_total_basis: GasConcentrationBasis
    report: GasStreamReport


@dataclass(frozen=True)
class GasStreamBalance:
    inlet: GasStreamReport
    outlet: GasStreamReport
    component_removal_fraction: Mapping[str, Optional[float]]
    overall_removal_molar: Optional[float]
    overall_removal_voc_mass: Optional[float]
    overall_removal_carbon_mass: Optional[float]
    captured_kg_h_by_component: Mapping[str, float]
    total_captured_kg_h: float


@dataclass(frozen=True)
class ConcentrationTarget:
    """Future design target represented without losing its reporting basis."""

    value: float
    basis: GasConcentrationBasis
    scope: str = "total"  # total | component
    solute_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.value) or self.value < 0:
            raise UnitConversionError("Target concentration must be finite and non-negative.")
        if self.scope not in {"total", "component"}:
            raise UnitConversionError("Target scope must be 'total' or 'component'.")
        if self.scope == "component" and not self.solute_id:
            raise UnitConversionError("Component target requires solute_id.")
        if self.scope == "total" and self.solute_id is not None:
            raise UnitConversionError("Total target must not carry solute_id.")


def _coerce_gas_basis(basis: GasConcentrationBasis | str) -> GasConcentrationBasis:
    if isinstance(basis, GasConcentrationBasis):
        return basis
    aliases = {
        "mgvoc/nm3": GasConcentrationBasis.MG_VOC_NM3,
        "mgvoc/nm³": GasConcentrationBasis.MG_VOC_NM3,
        "mgvoc": GasConcentrationBasis.MG_VOC_NM3,
        "mgc/nm3": GasConcentrationBasis.MG_C_NM3,
        "mgc/nm³": GasConcentrationBasis.MG_C_NM3,
        "mgc": GasConcentrationBasis.MG_C_NM3,
        "ppmv": GasConcentrationBasis.PPMV,
        "ppm": GasConcentrationBasis.PPMV,
    }
    key = str(basis).strip().lower()
    try:
        return aliases[key]
    except KeyError as exc:
        raise UnitConversionError(f"Unsupported gas concentration basis: {basis!r}") from exc


def _coerce_fraction_basis(basis: CompositionFractionBasis | str) -> CompositionFractionBasis:
    if isinstance(basis, CompositionFractionBasis):
        return basis
    aliases = {
        "mole": CompositionFractionBasis.MOLE,
        "molar": CompositionFractionBasis.MOLE,
        "mole_fraction": CompositionFractionBasis.MOLE,
        "voc_mass": CompositionFractionBasis.VOC_MASS,
        "mass": CompositionFractionBasis.VOC_MASS,
        "mass_fraction": CompositionFractionBasis.VOC_MASS,
        "carbon_mass": CompositionFractionBasis.CARBON_MASS,
        "carbon": CompositionFractionBasis.CARBON_MASS,
        "carbon_fraction": CompositionFractionBasis.CARBON_MASS,
    }
    key = str(basis).strip().lower()
    try:
        return aliases[key]
    except KeyError as exc:
        raise UnitConversionError(f"Unsupported composition-fraction basis: {basis!r}") from exc


def _validate_y(y: float) -> float:
    y = float(y)
    if not math.isfinite(y) or y < 0 or y >= 1:
        raise UnitConversionError("Gas mole fraction y must be finite and in [0, 1).")
    return y


def _validate_x(x: float) -> float:
    x = float(x)
    if not math.isfinite(x) or x < 0 or x >= 1:
        raise UnitConversionError("Liquid mole fraction x must be finite and in [0, 1).")
    return x


def _carbon_molar_mass(solute: SoluteSpec) -> float:
    return solute.carbon_atoms * MW_C_KG_MOL


def _basis_factor_per_y(
    solute: SoluteSpec,
    basis: GasConcentrationBasis,
    normal: NormalConditions,
) -> float:
    if basis is GasConcentrationBasis.PPMV:
        return 1.0e6
    cN = normal.molar_concentration_mol_m3
    if basis is GasConcentrationBasis.MG_VOC_NM3:
        return cN * solute.MW_kg_mol * 1.0e6
    return cN * _carbon_molar_mass(solute) * 1.0e6


def component_y_to_concentration(
    y: float,
    solute: SoluteSpec,
    basis: GasConcentrationBasis | str,
    *,
    normal: NormalConditions = DEFAULT_NORMAL_CONDITIONS,
) -> float:
    """Convert canonical gas mole fraction to a component reporting basis."""

    y = _validate_y(y)
    basis = _coerce_gas_basis(basis)
    return y * _basis_factor_per_y(solute, basis, normal)


def component_concentration_to_y(
    value: float,
    solute: SoluteSpec,
    basis: GasConcentrationBasis | str,
    *,
    normal: NormalConditions = DEFAULT_NORMAL_CONDITIONS,
) -> float:
    """Convert a component concentration to canonical gas mole fraction y."""

    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise UnitConversionError("Component concentration must be finite and non-negative.")
    basis = _coerce_gas_basis(basis)
    factor = _basis_factor_per_y(solute, basis, normal)
    if factor == 0.0:
        if value == 0.0:
            return 0.0
        raise UnitConversionError(
            f"{solute.id}: positive mgC concentration is impossible with carbon_atoms=0."
        )
    return _validate_y(value / factor)


def report_gas_stream(
    y_by_solute: Mapping[str, float],
    solutes: Mapping[str, SoluteSpec],
    *,
    normal: NormalConditions = DEFAULT_NORMAL_CONDITIONS,
) -> GasStreamReport:
    """Build component and total reports from canonical y values.

    Outlet composition is always reconstructed from solved component y values;
    inlet mixture fractions are never reused to infer outlet composition.
    """

    if not y_by_solute:
        raise UnitConversionError("At least one gas component is required.")
    if len(y_by_solute) > 4:
        raise UnitConversionError("V4.0 supports at most four independent solutes.")

    components: dict[str, ComponentGasReport] = {}
    total_y = 0.0
    total_voc = 0.0
    total_c = 0.0
    for sid, y_value in y_by_solute.items():
        try:
            solute = solutes[sid]
        except KeyError as exc:
            raise UnitConversionError(f"Unknown solute id in composition: {sid}") from exc
        y = _validate_y(y_value)
        voc = component_y_to_concentration(y, solute, GasConcentrationBasis.MG_VOC_NM3, normal=normal)
        carbon = component_y_to_concentration(y, solute, GasConcentrationBasis.MG_C_NM3, normal=normal)
        comp = ComponentGasReport(
            solute_id=sid,
            y=y,
            ppmv=y * 1.0e6,
            mgVOC_Nm3=voc,
            mgC_Nm3=carbon,
        )
        components[sid] = comp
        total_y += y
        total_voc += voc
        total_c += carbon

    if total_y >= 1.0:
        raise UnitConversionError("Total dilute-solute mole fraction must remain below 1.")
    return GasStreamReport(
        components=components,
        total_y=total_y,
        total_ppmv=total_y * 1.0e6,
        total_mgVOC_Nm3=total_voc,
        total_mgC_Nm3=total_c,
    )


def canonical_y_from_component_concentrations(
    values_by_solute: Mapping[str, float],
    basis: GasConcentrationBasis | str,
    solutes: Mapping[str, SoluteSpec],
    *,
    normal: NormalConditions = DEFAULT_NORMAL_CONDITIONS,
) -> Mapping[str, float]:
    """Convert component-by-component UI concentrations to canonical y_i."""

    if not values_by_solute:
        raise UnitConversionError("At least one component concentration is required.")
    y = {
        sid: component_concentration_to_y(value, solutes[sid], basis, normal=normal)
        for sid, value in values_by_solute.items()
    }
    report_gas_stream(y, solutes, normal=normal)  # validates total y and IDs
    return y


def _validated_fractions(
    fractions: Mapping[str, float],
    solutes: Mapping[str, SoluteSpec],
    *,
    normalize: bool,
    tolerance: float = 1e-9,
) -> dict[str, float]:
    if not fractions:
        raise UnitConversionError("At least one mixture fraction is required.")
    if len(fractions) > 4:
        raise UnitConversionError("V4.0 supports at most four independent solutes.")
    out: dict[str, float] = {}
    for sid, value in fractions.items():
        if sid not in solutes:
            raise UnitConversionError(f"Unknown solute id in fractions: {sid}")
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise UnitConversionError("Composition fractions must be finite and non-negative.")
        out[sid] = value
    total = sum(out.values())
    if total <= 0:
        raise UnitConversionError("Composition fractions must have positive sum.")
    if normalize:
        return {sid: value / total for sid, value in out.items()}
    if abs(total - 1.0) > tolerance:
        raise UnitConversionError(
            f"Composition fractions must sum to 1.0 (received {total:.12g}); "
            "explicitly request normalization if desired."
        )
    return out


def canonical_y_from_total_and_fractions(
    total_value: float,
    total_basis: GasConcentrationBasis | str,
    fractions: Mapping[str, float],
    fraction_basis: CompositionFractionBasis | str,
    solutes: Mapping[str, SoluteSpec],
    *,
    normal: NormalConditions = DEFAULT_NORMAL_CONDITIONS,
    normalize_fractions: bool = False,
) -> MixtureInputResult:
    """Convert total mixture concentration + composition fractions to y_i.

    The total reporting basis and the composition-fraction basis are independent.
    This avoids assuming that mass fractions, mole fractions and carbon fractions
    are interchangeable.
    """

    total_value = float(total_value)
    if not math.isfinite(total_value) or total_value < 0:
        raise UnitConversionError("Total mixture concentration must be finite and non-negative.")
    total_basis = _coerce_gas_basis(total_basis)
    fraction_basis = _coerce_fraction_basis(fraction_basis)
    f = _validated_fractions(fractions, solutes, normalize=normalize_fractions)

    raw_y: dict[str, float] = {}
    for sid, fraction in f.items():
        solute = solutes[sid]
        if fraction_basis is CompositionFractionBasis.MOLE:
            raw_y[sid] = fraction
        elif fraction_basis is CompositionFractionBasis.VOC_MASS:
            raw_y[sid] = fraction / solute.MW_kg_mol
        else:
            carbon_mw = _carbon_molar_mass(solute)
            if carbon_mw <= 0:
                if fraction == 0:
                    raw_y[sid] = 0.0
                else:
                    raise UnitConversionError(
                        f"{sid}: nonzero carbon-mass fraction requires carbon_atoms > 0."
                    )
            else:
                raw_y[sid] = fraction / carbon_mw

    # Concentration in any supported basis is linear in y under fixed normal
    # conditions.  Scale the basis-consistent raw y ratios to the requested total.
    basis_per_scale = sum(
        raw * _basis_factor_per_y(solutes[sid], total_basis, normal)
        for sid, raw in raw_y.items()
    )

    if total_value == 0:
        scale = 0.0
    elif basis_per_scale <= 0:
        raise UnitConversionError("Mixture basis produced a non-positive conversion scale.")
    else:
        scale = total_value / basis_per_scale

    canonical = {sid: scale * raw for sid, raw in raw_y.items()}
    report = report_gas_stream(canonical, solutes, normal=normal)
    return MixtureInputResult(
        canonical_y=canonical,
        normalized_fractions=f,
        fraction_basis=fraction_basis,
        requested_total_value=total_value,
        requested_total_basis=total_basis,
        report=report,
    )


def liquid_mg_L_to_x_dilute(
    concentration_mg_L: float,
    *,
    solute_MW_kg_mol: float,
    solvent_MW_kg_mol: float,
    solvent_density_kg_m3: float,
) -> float:
    """Dilute liquid loading conversion used by V4.0.

    x ~= (C_mg/L * 1e-3 / MW_i) / (rho_L / MW_L)
    """

    c = float(concentration_mg_L)
    if not math.isfinite(c) or c < 0:
        raise UnitConversionError("Liquid concentration must be finite and non-negative.")
    if solute_MW_kg_mol <= 0 or solvent_MW_kg_mol <= 0 or solvent_density_kg_m3 <= 0:
        raise UnitConversionError("Molecular weights and solvent density must be positive.")
    x = c * 1.0e-3 * solvent_MW_kg_mol / (solute_MW_kg_mol * solvent_density_kg_m3)
    return _validate_x(x)


def liquid_x_to_mg_L_dilute(
    x: float,
    *,
    solute_MW_kg_mol: float,
    solvent_MW_kg_mol: float,
    solvent_density_kg_m3: float,
) -> float:
    x = _validate_x(x)
    if solute_MW_kg_mol <= 0 or solvent_MW_kg_mol <= 0 or solvent_density_kg_m3 <= 0:
        raise UnitConversionError("Molecular weights and solvent density must be positive.")
    return x * solute_MW_kg_mol * solvent_density_kg_m3 / (1.0e-3 * solvent_MW_kg_mol)


def actual_m3_h_to_normal_m3_h(
    actual_m3_h: float,
    *,
    temperature_K: float,
    pressure_Pa: float,
    normal: NormalConditions = DEFAULT_NORMAL_CONDITIONS,
) -> float:
    """Ideal-gas volumetric-flow conversion at constant molar flow."""

    q = float(actual_m3_h)
    if not math.isfinite(q) or q < 0:
        raise UnitConversionError("Gas volumetric flow must be finite and non-negative.")
    if temperature_K <= 0 or pressure_Pa <= 0:
        raise UnitConversionError("Operating temperature and pressure must be positive.")
    return q * (pressure_Pa / normal.pressure_Pa) * (normal.temperature_K / temperature_K)


def normal_m3_h_to_actual_m3_h(
    normal_m3_h: float,
    *,
    temperature_K: float,
    pressure_Pa: float,
    normal: NormalConditions = DEFAULT_NORMAL_CONDITIONS,
) -> float:
    qn = float(normal_m3_h)
    if not math.isfinite(qn) or qn < 0:
        raise UnitConversionError("Normal gas volumetric flow must be finite and non-negative.")
    if temperature_K <= 0 or pressure_Pa <= 0:
        raise UnitConversionError("Operating temperature and pressure must be positive.")
    return qn * (normal.pressure_Pa / pressure_Pa) * (temperature_K / normal.temperature_K)


def gas_stream_balance(
    inlet_y: Mapping[str, float],
    outlet_y: Mapping[str, float],
    solutes: Mapping[str, SoluteSpec],
    *,
    gas_molar_flow_mol_s: Optional[float] = None,
    normal: NormalConditions = DEFAULT_NORMAL_CONDITIONS,
) -> GasStreamBalance:
    """Aggregate solved component results without reusing inlet fractions."""

    if set(inlet_y) != set(outlet_y):
        raise UnitConversionError("Inlet and outlet solute keys must match exactly.")
    inlet = report_gas_stream(inlet_y, solutes, normal=normal)
    outlet = report_gas_stream(outlet_y, solutes, normal=normal)

    component_removal: dict[str, Optional[float]] = {}
    captured: dict[str, float] = {}
    for sid in inlet_y:
        yi = float(inlet_y[sid])
        yo = float(outlet_y[sid])
        component_removal[sid] = None if yi == 0 else (yi - yo) / yi
        if gas_molar_flow_mol_s is None:
            captured[sid] = 0.0
        else:
            if not math.isfinite(gas_molar_flow_mol_s) or gas_molar_flow_mol_s < 0:
                raise UnitConversionError("Gas molar flow must be finite and non-negative.")
            captured[sid] = (
                gas_molar_flow_mol_s * (yi - yo) * solutes[sid].MW_kg_mol * 3600.0
            )

    def removal(cin: float, cout: float) -> Optional[float]:
        return None if cin == 0 else (cin - cout) / cin

    return GasStreamBalance(
        inlet=inlet,
        outlet=outlet,
        component_removal_fraction=component_removal,
        overall_removal_molar=removal(inlet.total_y, outlet.total_y),
        overall_removal_voc_mass=removal(inlet.total_mgVOC_Nm3, outlet.total_mgVOC_Nm3),
        overall_removal_carbon_mass=removal(inlet.total_mgC_Nm3, outlet.total_mgC_Nm3),
        captured_kg_h_by_component=captured,
        total_captured_kg_h=sum(captured.values()),
    )
