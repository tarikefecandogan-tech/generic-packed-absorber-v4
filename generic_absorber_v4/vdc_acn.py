"""Phase 13 — VDC absorption into liquid acrylonitrile (AN), screening thermodynamics.

This phase adds a real solvent (acrylonitrile) but deliberately does **not**
claim that a validated VDC/AN binary equilibrium dataset is available.

Data governance
---------------
* Acrylonitrile bulk liquid properties are near-ambient literature/database
  values (Confidence B).
* VDC gas diffusivity remains a Fuller estimate (Confidence C).
* VDC liquid diffusivity in acrylonitrile is a Wilke–Chang estimate
  (Confidence C).  The solvent association factor phi=1.0 is a screening
  assumption for a non-hydrogen-bond-donor / nominally unassociated solvent.
* VDC/AN equilibrium is a **screening surrogate** only: dilute ideal-solution
  Raoult form y*=m x with gamma_inf=1 and m=P_sat,VDC/P at 22 °C, 1 atm.
  It is registered as Confidence D and should be replaced by measured VLE,
  infinite-dilution activity coefficient, or calibrated plant/pilot data when
  available.
* Acrylonitrile is materially volatile near ambient conditions.  V4.0 does not
  model solvent evaporation, so the case is explicitly outside the recommended
  model domain even though the mathematical absorber calculation can run.

Project pilot observation (not used for fitting)
------------------------------------------------
The project slide deck reports a realised trial with 300 L/h nitrogen and
18 L/h liquid AN, with final liquid analysis 93.84% AN / 6.16% VDC and gas
outlet 1100 ppm VOC.  The inlet VDC concentration, run duration/material
inventory basis, and solvent evaporation loss are not sufficiently defined to
fit a binary equilibrium coefficient, so Phase 13 preserves this as external
qualitative evidence only.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .applicability import ApplicabilityCase, ApplicabilityReport, assess_post_applicability, assess_pre_applicability
from .countercurrent import ComponentBoundaryConditions, ComponentCounterCurrentResult, solve_component_countercurrent
from .hydraulics import HydraulicResult, evaluate_hydraulics_from_resolver
from .mass_transfer import AbsorberOperatingPoint, CommonOndaState, ComponentMassTransferResult, evaluate_component_from_resolver
from .models import ConfidenceClass, DataProvenance, EquilibriumPair, SolventSpec
from .registry import AbsorberDataRegistry
from .resolver import PropertyResolver, ResolvedComponentProperties, ResolutionTier
from .units import GasStreamReport, report_gas_stream
from .vdc_water import (
    VDC_ID,
    VDC_MW_KG_MOL,
    build_vdc_water_registry,
    run_vdc_water_case,
)

PHASE13_VDC_ACN_CASE_ID = "VDC_ACRYLONITRILE_SCREENING_2026_10_07"
ACN_SOLVENT_ID = "acrylonitrile"
ACN_SOLVENT_NAME = "Acrylonitrile"
ACN_CAS = "107-13-1"
ACN_FORMULA = "C3H3N"
ACN_MW_KG_MOL = 53.06e-3

# Near-ambient bulk liquid properties used as a constant screening property set.
# Density is linearly interpolated between published 20 °C (~806 kg/m3) and
# 25 °C (~800.7 kg/m3) values to 22 °C.
ACN_DENSITY_22C_KG_M3 = 803.88
ACN_VISCOSITY_NEAR_AMBIENT_PA_S = 0.34e-3
ACN_SURFACE_TENSION_NEAR_AMBIENT_N_M = 27.3e-3
ACN_WILKE_CHANG_ASSOCIATION_FACTOR = 1.0

# NIST Antoine parameters, P in bar, T in K.
VDC_ANTOINE_A = 4.1078
VDC_ANTOINE_B = 1104.726
VDC_ANTOINE_C = -35.403
VDC_ANTOINE_TMIN_K = 244.79
VDC_ANTOINE_TMAX_K = 305.7

ACN_ANTOINE_A = 2.69607
ACN_ANTOINE_B = 621.275
ACN_ANTOINE_C = -121.929
ACN_ANTOINE_TMIN_K = 293.0
ACN_ANTOINE_TMAX_K = 343.0

PHASE13_T_K = 295.15
PHASE13_P_PA = 101325.0
VDC_ACN_GAMMA_INFINITY_SCREENING = 1.0

ACN_BULK_SOURCE = (
    "U.S. EPA acrylonitrile physical-property compilation and CRC/PubChem near-ambient data: "
    "rho~806 kg/m3 at 20 C, rho~800.7 kg/m3 at 25 C, mu~0.34 mPa.s near 24-25 C, "
    "surface tension~27.3 mN/m near 24 C"
)
VDC_VP_SOURCE = (
    "NIST Chemistry WebBook, 1,1-dichloroethylene Antoine equation; "
    "Hildenbrand, McDonald, Kramer & Stull (1959)"
)
ACN_VP_SOURCE = (
    "NIST Chemistry WebBook, acrylonitrile Antoine equation; Gubkov, Fermor & Smirnov (1964)"
)
VDC_ACN_EQUILIBRIUM_SOURCE = (
    "Phase 13 screening surrogate: NIST VDC pure-component vapor pressure + ideal-dilute Raoult law "
    "with gamma_inf=1. No direct public VDC/AN binary VLE dataset was identified in the Phase 13 search."
)
WILKE_CHANG_ACN_NOTE = (
    "Wilke–Chang with phi=1.0 screening assumption. Literature recommends phi=1 for unassociated solvents, "
    "but an acrylonitrile-specific association factor was not identified; treat DL as screening-level."
)
PROJECT_PILOT_NOTE = (
    "Project pilot observation: 300 L/h N2, 18 L/h AN; final liquid 93.84% AN / 6.16% VDC; "
    "gas outlet 1100 ppm VOC. Not used for fitting because inlet VDC and complete material-balance basis are missing."
)


def _antoine_pressure_Pa(T_K: float, A: float, B: float, C: float, Tmin: float, Tmax: float) -> float:
    if not math.isfinite(T_K) or not (Tmin <= T_K <= Tmax):
        raise ValueError(f"Antoine temperature {T_K:g} K outside registered range {Tmin:g}-{Tmax:g} K")
    return (10.0 ** (A - B / (T_K + C))) * 1.0e5


def vdc_vapor_pressure_Pa(T_K: float = PHASE13_T_K) -> float:
    return _antoine_pressure_Pa(
        T_K, VDC_ANTOINE_A, VDC_ANTOINE_B, VDC_ANTOINE_C,
        VDC_ANTOINE_TMIN_K, VDC_ANTOINE_TMAX_K,
    )


def acrylonitrile_vapor_pressure_Pa(T_K: float = PHASE13_T_K) -> float:
    return _antoine_pressure_Pa(
        T_K, ACN_ANTOINE_A, ACN_ANTOINE_B, ACN_ANTOINE_C,
        ACN_ANTOINE_TMIN_K, ACN_ANTOINE_TMAX_K,
    )


VDC_ACN_LINEAR_M_22C = (
    VDC_ACN_GAMMA_INFINITY_SCREENING * vdc_vapor_pressure_Pa(PHASE13_T_K) / PHASE13_P_PA
)
ACN_VAPOR_FRACTION_IF_SATURATED_22C = acrylonitrile_vapor_pressure_Pa(PHASE13_T_K) / PHASE13_P_PA

ACN_SOLVENT_PROVENANCE = DataProvenance(
    source=ACN_BULK_SOURCE,
    method="near-ambient constant liquid-property set; 22 C density interpolation",
    confidence=ConfidenceClass.B,
    reference_temperature_K=PHASE13_T_K,
    reference_pressure_Pa=PHASE13_P_PA,
    validity_note=(
        "Use as a narrow near-ambient property set (~20-25 C), not a general temperature correlation. "
        "Wilke-Chang phi=1.0 is separate screening metadata, not an experimentally verified AN association factor."
    ),
)

VDC_ACN_EQUILIBRIUM_PROVENANCE = DataProvenance(
    source=VDC_ACN_EQUILIBRIUM_SOURCE,
    method="ideal-dilute Raoult screening: m = gamma_inf * Psat_VDC / P, gamma_inf=1",
    confidence=ConfidenceClass.D,
    reference_temperature_K=PHASE13_T_K,
    reference_pressure_Pa=PHASE13_P_PA,
    validity_note=(
        "SCREENING ONLY. Direct VDC/AN binary VLE or infinite-dilution activity-coefficient data are required "
        "for design-grade thermodynamics. Registered m is fixed at 22 C and 1 atm."
    ),
)


@dataclass(frozen=True)
class VDCACNReport:
    case_id: str
    registry: AbsorberDataRegistry
    resolver: PropertyResolver
    operating: AbsorberOperatingPoint
    resolved: ResolvedComponentProperties
    common: CommonOndaState
    transfer: ComponentMassTransferResult
    solver: ComponentCounterCurrentResult
    hydraulics: HydraulicResult
    gas_inlet_report: GasStreamReport
    gas_outlet_report: GasStreamReport
    pre_applicability: ApplicabilityReport
    post_applicability: ApplicabilityReport
    water_removal_fraction: float
    water_absorption_factor: float
    acn_vapor_pressure_Pa: float
    vdc_vapor_pressure_Pa: float

    @property
    def removal_improvement_factor_vs_water(self) -> float:
        return self.solver.removal_fraction / max(self.water_removal_fraction, 1e-30)

    @property
    def pass_gate(self) -> bool:
        return (
            not self.pre_applicability.blocks
            and not self.post_applicability.blocks
            and self.resolved.gas_diffusivity.tier == ResolutionTier.CORRELATION_ESTIMATE
            and self.resolved.liquid_diffusivity.tier == ResolutionTier.CORRELATION_ESTIMATE
            and self.resolved.gas_diffusivity.confidence == ConfidenceClass.C
            and self.resolved.liquid_diffusivity.confidence == ConfidenceClass.C
            and self.resolved.equilibrium.active_property.confidence == ConfidenceClass.D
            and self.solver.diagnostics.relative_mass_balance_error <= 1e-7
            and abs(self.solver.diagnostics.boundary_error_x) <= 1e-8
            and self.hydraulics.flooding.gpdc_valid
            and 0.0 <= self.solver.gas_outlet_y < 1.0
            and self.transfer.absorption_factor > self.water_absorption_factor
        )


def build_vdc_acn_registry() -> AbsorberDataRegistry:
    """Extend Phase 12 registry with liquid acrylonitrile and a screening VDC/AN equilibrium pair."""
    registry = build_vdc_water_registry()
    registry.reference_id = PHASE13_VDC_ACN_CASE_ID

    registry.register_solvent(
        SolventSpec(
            id=ACN_SOLVENT_ID,
            name=ACN_SOLVENT_NAME,
            MW_kg_mol=ACN_MW_KG_MOL,
            property_model="constant",
            rho_kg_m3=ACN_DENSITY_22C_KG_M3,
            mu_Pa_s=ACN_VISCOSITY_NEAR_AMBIENT_PA_S,
            sigma_N_m=ACN_SURFACE_TENSION_NEAR_AMBIENT_N_M,
            wilke_chang_association_factor=ACN_WILKE_CHANG_ASSOCIATION_FACTOR,
            provenance=ACN_SOLVENT_PROVENANCE,
        )
    )
    registry.register_equilibrium_pair(
        EquilibriumPair(
            solute_id=VDC_ID,
            solvent_id=ACN_SOLVENT_ID,
            model="linear_m",
            m_y_over_x=VDC_ACN_LINEAR_M_22C,
            validity_temperature_min_K=294.65,
            validity_temperature_max_K=295.65,
            validity_note=VDC_ACN_EQUILIBRIUM_PROVENANCE.validity_note,
            provenance=VDC_ACN_EQUILIBRIUM_PROVENANCE,
        )
    )
    # No VDC/AN liquid transport pair is fabricated: Wilke-Chang must resolve it visibly.
    return registry


def vdc_acn_operating_point() -> AbsorberOperatingPoint:
    return AbsorberOperatingPoint(
        diameter_m=0.5,
        packed_height_m=1.4,
        gas_actual_m3_h=117.53,
        liquid_mass_kg_h=2500.0,
        temperature_K=PHASE13_T_K,
        pressure_Pa=PHASE13_P_PA,
    )


def vdc_acn_boundary() -> ComponentBoundaryConditions:
    return ComponentBoundaryConditions(gas_inlet_y=1000.0e-6, liquid_inlet_x=0.0)


def run_vdc_acn_case() -> VDCACNReport:
    registry = build_vdc_acn_registry()
    resolver = PropertyResolver(registry)
    operating = vdc_acn_operating_point()
    boundary = vdc_acn_boundary()

    app_case = ApplicabilityCase(
        operating=operating,
        solute_ids=(VDC_ID,),
        carrier_id="air",
        solvent_id=ACN_SOLVENT_ID,
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={VDC_ID: boundary.gas_inlet_y},
        liquid_inlet_x={VDC_ID: boundary.liquid_inlet_x},
        solvent_evaporation_expected=True,
    )
    pre = assess_pre_applicability(registry, app_case)

    resolved = resolver.resolve_component_properties(
        VDC_ID, "air", ACN_SOLVENT_ID, operating.temperature_K, operating.pressure_Pa
    )
    common, transfer = evaluate_component_from_resolver(
        resolver=resolver,
        registry=registry,
        solute_id=VDC_ID,
        carrier_id="air",
        solvent_id=ACN_SOLVENT_ID,
        packing_id="25mm_metal_pall_ring",
        operating=operating,
    )
    solved = solve_component_countercurrent(common, transfer, boundary)
    _, hydraulics = evaluate_hydraulics_from_resolver(
        resolver=resolver,
        registry=registry,
        carrier_id="air",
        solvent_id=ACN_SOLVENT_ID,
        packing_id="25mm_metal_pall_ring",
        operating=operating,
    )
    post = assess_post_applicability(
        pre,
        resolved_components={VDC_ID: resolved},
        common=common,
        transfer_results={VDC_ID: transfer},
        solver_results={VDC_ID: solved},
        hydraulics=hydraulics,
        packing=registry.get_packing("25mm_metal_pall_ring"),
    )

    solute_specs = {VDC_ID: registry.get_solute(VDC_ID)}
    inlet_report = report_gas_stream({VDC_ID: boundary.gas_inlet_y}, solute_specs)
    outlet_report = report_gas_stream({VDC_ID: solved.gas_outlet_y}, solute_specs)

    water = run_vdc_water_case()

    return VDCACNReport(
        case_id=PHASE13_VDC_ACN_CASE_ID,
        registry=registry,
        resolver=resolver,
        operating=operating,
        resolved=resolved,
        common=common,
        transfer=transfer,
        solver=solved,
        hydraulics=hydraulics,
        gas_inlet_report=inlet_report,
        gas_outlet_report=outlet_report,
        pre_applicability=pre,
        post_applicability=post,
        water_removal_fraction=water.solver.removal_fraction,
        water_absorption_factor=water.transfer.absorption_factor,
        acn_vapor_pressure_Pa=acrylonitrile_vapor_pressure_Pa(operating.temperature_K),
        vdc_vapor_pressure_Pa=vdc_vapor_pressure_Pa(operating.temperature_K),
    )
