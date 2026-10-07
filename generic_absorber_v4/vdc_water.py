"""Phase 12 — real VDC / water chemistry extension.

This module is the first non-reference real chemistry added to the V4 database.
It deliberately leaves the locked V3 reference snapshot untouched and builds an
expanded registry around it.

Primary equilibrium dataset
---------------------------
VDC (1,1-dichloroethylene; CAS 75-35-4) Henry data are taken from the NIST
Chemistry WebBook compilation, selecting the measured Gossett (1987) entry:

    kH,solubility(298.15 K) = 0.039 mol/(kg water·bar)
    d ln(kH)/d(1/T)         = 3700 K

The solver uses pressure/concentration Henry form p = Hpc*C.  The 298.15 K
value is therefore converted with the V4 water density correlation:

    Hpc = 1e5 / (kH * rho_water)

The published VDC/water Henry literature is scattered; the selected value is a
traceable default, not a claim that the equilibrium uncertainty is negligible.

Transport estimates
-------------------
No experimental VDC/air or VDC/water diffusivity pair is registered here.
Phase 11 fallback estimators are intentionally exercised:

* Fuller gas diffusivity, using atomic increments C=16.5, H=1.98, Cl=19.5 and
  air diffusion volume 20.1.  VDC volume = 75.96.
* Wilke–Chang liquid diffusivity, using water association factor phi=2.6 and
  VDC Le Bas normal-boiling molar-volume estimate 86.2 cm3/mol from
  C=14.8, H=3.7 and Cl=24.6 increments.

Both resolved transport properties therefore remain Confidence C estimates.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Mapping

from .applicability import ApplicabilityCase, ApplicabilityReport, assess_post_applicability, assess_pre_applicability
from .countercurrent import ComponentBoundaryConditions, ComponentCounterCurrentResult, solve_component_countercurrent
from .hydraulics import HydraulicResult, evaluate_hydraulics_from_resolver
from .mass_transfer import AbsorberOperatingPoint, CommonOndaState, ComponentMassTransferResult, evaluate_component_from_resolver
from .models import ConfidenceClass, DataProvenance, EquilibriumPair, SoluteSpec
from .registry import AbsorberDataRegistry, build_reference_registry
from .resolver import PropertyResolver, ResolvedComponentProperties, ResolutionTier
from .units import GasStreamReport, report_gas_stream

PHASE12_VDC_WATER_CASE_ID = "VDC_WATER_REAL_CHEMISTRY_2026_10_07"
VDC_ID = "VDC"
VDC_NAME = "1,1-Dichloroethylene (Vinylidene chloride)"
VDC_CAS = "75-35-4"
VDC_MW_KG_MOL = 96.943e-3
VDC_FORMULA = "C2H2Cl2"
VDC_CARBON_ATOMS = 2

# Fuller (1966) atomic increments: 2*C + 2*H + 2*Cl.
VDC_FULLER_DIFFUSION_VOLUME = 2.0 * 16.5 + 2.0 * 1.98 + 2.0 * 19.5  # 75.96
AIR_FULLER_DIFFUSION_VOLUME = 20.1

# Le Bas normal-boiling molar-volume increments: 2*C + 2*H + 2*Cl.
VDC_LEBAS_BOILING_MOLAR_VOLUME_CM3_MOL = 2.0 * 14.8 + 2.0 * 3.7 + 2.0 * 24.6  # 86.2
WATER_WILKE_CHANG_ASSOCIATION_FACTOR = 2.6

# NIST WebBook / Gossett 1987 measured solubility-form Henry data.
VDC_KH_SOLUBILITY_MOL_KG_BAR_298 = 0.039
VDC_HENRY_TEMPERATURE_COEFFICIENT_K = 3700.0
VDC_HENRY_T_REF_K = 298.15
VDC_HENRY_VALID_MIN_K = 275.65
VDC_HENRY_VALID_MAX_K = 363.65

NIST_GOSSETT_SOURCE = (
    "NIST Chemistry WebBook, 1,1-dichloroethylene Henry's Law data; "
    "Gossett, J.M., Environ. Sci. Technol. 21 (1987) 202-208"
)
FULLER_SOURCE = (
    "Fuller, Schettler & Giddings (1966) atomic diffusion-volume method; "
    "C=16.5, H=1.98, Cl=19.5; Air=20.1"
)
WILKE_CHANG_SOURCE = (
    "Wilke–Chang dilute-liquid diffusivity correlation; water phi=2.6; "
    "Le Bas group-contribution boiling molar volume"
)


def _legacy_water_density_kg_m3(T_K: float) -> float:
    T_C = T_K - 273.15
    return 1000.0 * (
        1.0
        - ((T_C + 288.9414) / (508929.2 * (T_C + 68.12963)))
        * (T_C - 3.9863) ** 2
    )


VDC_WATER_H_REF_PA_M3_MOL = 1.0e5 / (
    VDC_KH_SOLUBILITY_MOL_KG_BAR_298 * _legacy_water_density_kg_m3(VDC_HENRY_T_REF_K)
)

VDC_EQUILIBRIUM_PROVENANCE = DataProvenance(
    source=NIST_GOSSETT_SOURCE,
    method=(
        "Measured solubility-form Henry kH converted to pressure/concentration Hpc "
        "with V4 water density at 298.15 K"
    ),
    confidence=ConfidenceClass.B,
    reference_temperature_K=VDC_HENRY_T_REF_K,
    validity_note=(
        "Primary Phase 12 default uses the measured Gossett (1987) NIST entry. "
        "Published VDC/water Henry values show substantial inter-source scatter; "
        "treat equilibrium sensitivity as an important design uncertainty."
    ),
)


@dataclass(frozen=True)
class VDCWaterReport:
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

    @property
    def pass_gate(self) -> bool:
        return (
            not self.pre_applicability.blocks
            and not self.post_applicability.blocks
            and self.resolved.gas_diffusivity.tier == ResolutionTier.CORRELATION_ESTIMATE
            and self.resolved.liquid_diffusivity.tier == ResolutionTier.CORRELATION_ESTIMATE
            and self.resolved.equilibrium.active_property.tier == ResolutionTier.DATABASE
            and self.resolved.gas_diffusivity.confidence == ConfidenceClass.C
            and self.resolved.liquid_diffusivity.confidence == ConfidenceClass.C
            and self.resolved.equilibrium.active_property.confidence == ConfidenceClass.B
            and self.solver.diagnostics.relative_mass_balance_error <= 1e-7
            and abs(self.solver.diagnostics.boundary_error_x) <= 1e-8
            and self.hydraulics.flooding.gpdc_valid
            and 0.0 <= self.solver.gas_outlet_y < 1.0
        )


def build_vdc_water_registry() -> AbsorberDataRegistry:
    """Extend the locked reference registry without modifying its snapshot."""
    registry = build_reference_registry()
    registry.reference_id = PHASE12_VDC_WATER_CASE_ID

    # Add only estimator metadata to copied Air/Water objects.  All original
    # reference properties remain identical, so ACN/VAc parity is unaffected.
    air = registry.get_carrier("air")
    registry.register_carrier(
        replace(air, fuller_diffusion_volume=AIR_FULLER_DIFFUSION_VOLUME),
        replace=True,
    )
    water = registry.get_solvent("water")
    registry.register_solvent(
        replace(water, wilke_chang_association_factor=WATER_WILKE_CHANG_ASSOCIATION_FACTOR),
        replace=True,
    )

    registry.register_solute(
        SoluteSpec(
            id=VDC_ID,
            name=VDC_NAME,
            MW_kg_mol=VDC_MW_KG_MOL,
            carbon_atoms=VDC_CARBON_ATOMS,
            formula=VDC_FORMULA,
            cas_number=VDC_CAS,
            fuller_diffusion_volume=VDC_FULLER_DIFFUSION_VOLUME,
            boiling_molar_volume_cm3_mol=VDC_LEBAS_BOILING_MOLAR_VOLUME_CM3_MOL,
        )
    )
    registry.register_equilibrium_pair(
        EquilibriumPair(
            solute_id=VDC_ID,
            solvent_id="water",
            model="henry_pc",
            H_ref_Pa_m3_mol=VDC_WATER_H_REF_PA_M3_MOL,
            T_ref_K=VDC_HENRY_T_REF_K,
            temperature_coefficient_K=VDC_HENRY_TEMPERATURE_COEFFICIENT_K,
            validity_temperature_min_K=VDC_HENRY_VALID_MIN_K,
            validity_temperature_max_K=VDC_HENRY_VALID_MAX_K,
            validity_note=VDC_EQUILIBRIUM_PROVENANCE.validity_note,
            provenance=VDC_EQUILIBRIUM_PROVENANCE,
        )
    )
    # Deliberately no VDC/air DG pair and no VDC/water DL pair: Phase 11
    # estimators must resolve both and retain Confidence C provenance.
    return registry


def vdc_water_operating_point() -> AbsorberOperatingPoint:
    """A deterministic engineering fixture using the locked reference column."""
    return AbsorberOperatingPoint(
        diameter_m=0.5,
        packed_height_m=1.4,
        gas_actual_m3_h=117.53,
        liquid_mass_kg_h=2500.0,
        temperature_K=295.15,  # 22 °C
        pressure_Pa=101325.0,
    )


def vdc_water_boundary() -> ComponentBoundaryConditions:
    # 1000 ppmv inlet VDC; fresh water.  This is a software/engineering fixture,
    # not a claim that the plant feed is exactly 1000 ppmv.
    return ComponentBoundaryConditions(gas_inlet_y=1000.0e-6, liquid_inlet_x=0.0)


def run_vdc_water_case() -> VDCWaterReport:
    registry = build_vdc_water_registry()
    resolver = PropertyResolver(registry)
    operating = vdc_water_operating_point()
    boundary = vdc_water_boundary()

    app_case = ApplicabilityCase(
        operating=operating,
        solute_ids=(VDC_ID,),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={VDC_ID: boundary.gas_inlet_y},
        liquid_inlet_x={VDC_ID: boundary.liquid_inlet_x},
    )
    pre = assess_pre_applicability(registry, app_case)

    resolved = resolver.resolve_component_properties(
        VDC_ID, "air", "water", operating.temperature_K, operating.pressure_Pa
    )
    common, transfer = evaluate_component_from_resolver(
        resolver=resolver,
        registry=registry,
        solute_id=VDC_ID,
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=operating,
    )
    solved = solve_component_countercurrent(common, transfer, boundary)
    _, hydraulics = evaluate_hydraulics_from_resolver(
        resolver=resolver,
        registry=registry,
        carrier_id="air",
        solvent_id="water",
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

    inlet_report = report_gas_stream(
        {VDC_ID: boundary.gas_inlet_y},
        {VDC_ID: registry.get_solute(VDC_ID)},
    )
    outlet_report = report_gas_stream(
        {VDC_ID: solved.gas_outlet_y},
        {VDC_ID: registry.get_solute(VDC_ID)},
    )

    return VDCWaterReport(
        case_id=PHASE12_VDC_WATER_CASE_ID,
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
    )
