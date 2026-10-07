"""Phase 17 comparison packing catalog.

The locked Phase 1 reference dataset intentionally contains only the selected
25 mm Metal Pall Ring.  Phase 17 adds the remaining legacy V3 random-packing
records as comparison alternatives without changing the locked reference
fixture.  These values are useful for engineering screening; they have not been
re-verified against current vendor datasheets in this phase.
"""
from __future__ import annotations

from typing import Dict

from .models import ConfidenceClass, DataProvenance, PackingSpec
from .registry import AbsorberDataRegistry

PHASE17_PACKING_CATALOG_ID = "PHASE17_LEGACY_V3_PACKING_COMPARISON_CATALOG_2026_10_07"

LEGACY_PACKING_PROVENANCE = DataProvenance(
    source="scrubber_model.py / ScrubberSimulationV34 legacy packing catalog",
    method="legacy_v3_comparison_catalog",
    confidence=ConfidenceClass.B,
    validity_note=(
        "Migrated from the locked V3 packing table for Phase 17 comparison. "
        "Use as an engineering-screening catalog unless independently verified "
        "against a current vendor datasheet."
    ),
)

# The locked 25 mm Metal Pall Ring remains defined in reference_data.py and is
# deliberately not re-registered here.
COMPARISON_PACKINGS: Dict[str, PackingSpec] = {
    "38mm_metal_pall_ring": PackingSpec(
        id="38mm_metal_pall_ring",
        name="38mm Metal Pall Ring",
        packing_class="random",
        area_m2_m3=145.0,
        nominal_size_m=0.038,
        void_fraction=0.967,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=1.00,
        packing_factor_ft_inv=28.0,
        packing_factor_basis="empirical",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
    "imtp_25": PackingSpec(
        id="imtp_25",
        name="IMTP #25",
        packing_class="random",
        area_m2_m3=226.0,
        nominal_size_m=0.025,
        void_fraction=0.970,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=1.10,
        packing_factor_ft_inv=41.0,
        packing_factor_basis="empirical",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
    "imtp_40": PackingSpec(
        id="imtp_40",
        name="IMTP #40",
        packing_class="random",
        area_m2_m3=150.0,
        nominal_size_m=0.040,
        void_fraction=0.975,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=0.90,
        packing_factor_ft_inv=24.0,
        packing_factor_basis="empirical",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
    "cmr_2": PackingSpec(
        id="cmr_2",
        name="CMR #2",
        packing_class="random",
        area_m2_m3=188.0,
        nominal_size_m=0.025,
        void_fraction=0.967,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=1.00,
        packing_factor_ft_inv=None,
        packing_factor_basis="geometric_fallback",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
    "cmr_3": PackingSpec(
        id="cmr_3",
        name="CMR #3",
        packing_class="random",
        area_m2_m3=135.0,
        nominal_size_m=0.040,
        void_fraction=0.972,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=0.80,
        packing_factor_ft_inv=None,
        packing_factor_basis="geometric_fallback",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
    "13mm_super_raschig": PackingSpec(
        id="13mm_super_raschig",
        name="13mm Super Raschig",
        packing_class="random",
        area_m2_m3=250.0,
        nominal_size_m=0.013,
        void_fraction=0.965,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=1.00,
        packing_factor_ft_inv=None,
        packing_factor_basis="geometric_fallback",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
    "16mm_super_raschig": PackingSpec(
        id="16mm_super_raschig",
        name="16mm Super Raschig",
        packing_class="random",
        area_m2_m3=215.0,
        nominal_size_m=0.016,
        void_fraction=0.961,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=0.90,
        packing_factor_ft_inv=None,
        packing_factor_basis="geometric_fallback",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
    "25mm_super_raschig": PackingSpec(
        id="25mm_super_raschig",
        name="25mm Super Raschig",
        packing_class="random",
        area_m2_m3=150.0,
        nominal_size_m=0.025,
        void_fraction=0.972,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=0.80,
        packing_factor_ft_inv=None,
        packing_factor_basis="geometric_fallback",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
    "38mm_super_raschig": PackingSpec(
        id="38mm_super_raschig",
        name="38mm Super Raschig",
        packing_class="random",
        area_m2_m3=120.0,
        nominal_size_m=0.038,
        void_fraction=0.978,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=0.70,
        packing_factor_ft_inv=None,
        packing_factor_basis="geometric_fallback",
        provenance=LEGACY_PACKING_PROVENANCE,
    ),
}


def register_phase17_comparison_packings(registry: AbsorberDataRegistry) -> AbsorberDataRegistry:
    """Add legacy comparison packings without replacing any existing record."""
    for packing in COMPARISON_PACKINGS.values():
        if packing.id not in registry.packings:
            registry.register_packing(packing)
    return registry
