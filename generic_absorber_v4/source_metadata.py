"""Phase 18B — normalized bibliographic metadata for engineering data sources.

The migration layer keeps the original citation string as the immutable identity
anchor and adds structured metadata around it.  Missing bibliographic fields
remain NULL/None; Phase 18B does not invent DOI/year/title values.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

PHASE18B_SOURCE_METADATA_ID = "PHASE18B_SOURCE_METADATA_2026_10_07"
PHASE18B_ACCESSED_ON = "2026-10-07"


@dataclass(frozen=True)
class SourceMetadata:
    source_type: str
    title: Optional[str] = None
    authors: Optional[str] = None
    publication_year: Optional[int] = None
    journal_or_publisher: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    accessed_on: Optional[str] = PHASE18B_ACCESSED_ON
    evidence_role: str = "SUPPORTING"
    quality_note: str = ""
    notes: str = ""


SOURCE_METADATA_BY_CITATION: Dict[str, SourceMetadata] = {
    "Fuller, Schettler & Giddings (1966) atomic diffusion-volume method; C=16.5, H=1.98, Cl=19.5; Air=20.1": SourceMetadata(
        source_type="primary_correlation_literature",
        title="New Method for Prediction of Binary Gas-Phase Diffusion Coefficients",
        authors="Edward N. Fuller; Paul D. Schettler; J. Calvin Giddings",
        publication_year=1966,
        journal_or_publisher="Industrial & Engineering Chemistry",
        url="https://pubs.acs.org/doi/10.1021/ie50677a007",
        doi="10.1021/ie50677a007",
        evidence_role="CORRELATION_METHOD",
        quality_note="Primary publication for the Fuller gas-phase diffusivity correlation used as a Confidence C fallback estimator.",
    ),
    "Wilke–Chang dilute-liquid diffusivity correlation; water phi=2.6; Le Bas group-contribution boiling molar volume": SourceMetadata(
        source_type="primary_correlation_literature",
        title="Correlation of Diffusion Coefficients in Dilute Solutions",
        authors="C. R. Wilke; Pin Chang",
        publication_year=1955,
        journal_or_publisher="AIChE Journal",
        url="https://doi.org/10.1002/aic.690010222",
        doi="10.1002/aic.690010222",
        evidence_role="CORRELATION_METHOD",
        quality_note="Primary publication for the Wilke–Chang dilute-liquid diffusivity correlation used as a Confidence C fallback estimator.",
        notes="Phase 12/13 also use solvent association factors and Le Bas-style boiling-volume inputs; those inputs remain separately auditable assumptions/data.",
    ),
    "scrubber_model.py / ScrubberSimulationV34 locked 2026-10-06": SourceMetadata(
        source_type="internal_reference_code",
        title="ScrubberSimulationV34 locked reference engine",
        authors="Project legacy model",
        publication_year=2026,
        journal_or_publisher="Generic Packed Absorber Simulator project",
        evidence_role="LOCKED_REFERENCE",
        quality_note="Regression reference source; not a substitute for primary scientific literature.",
        notes="Frozen source used to preserve V3 numerical parity during the V4 refactor.",
    ),
    "scrubber_model.py / ScrubberSimulationV34 legacy packing catalog": SourceMetadata(
        source_type="internal_legacy_catalog",
        title="ScrubberSimulationV34 legacy packing catalog",
        authors="Project legacy model",
        publication_year=2026,
        journal_or_publisher="Generic Packed Absorber Simulator project",
        evidence_role="SCREENING_CATALOG",
        quality_note="Legacy engineering catalog; independent vendor verification remains desirable.",
        notes="Used for Phase 17 comparison packings while preserving the locked 25 mm reference packing.",
    ),
    "NIST Chemistry WebBook, 1,1-dichloroethylene Henry's Law data; Gossett, J.M., Environ. Sci. Technol. 21 (1987) 202-208": SourceMetadata(
        source_type="primary_literature_via_curated_database",
        title="Measurement of Henry's law constants for C1 and C2 chlorinated hydrocarbons",
        authors="James M. Gossett",
        publication_year=1987,
        journal_or_publisher="Environmental Science & Technology / NIST Chemistry WebBook",
        url="https://webbook.nist.gov/cgi/inchi?ID=C75354&Mask=39",
        doi="10.1021/es00156a012",
        evidence_role="PRIMARY_EXPERIMENTAL",
        quality_note="Measured Henry-law entry exposed through the NIST Chemistry WebBook; literature scatter is retained as a model uncertainty note.",
    ),
    "U.S. EPA acrylonitrile physical-property compilation and CRC/PubChem near-ambient data: rho~806 kg/m3 at 20 C, rho~800.7 kg/m3 at 25 C, mu~0.34 mPa.s near 24-25 C, surface tension~27.3 mN/m near 24 C": SourceMetadata(
        source_type="government_property_compilation",
        title="Acrylonitrile near-ambient physical-property compilation",
        authors="U.S. Environmental Protection Agency and cited handbook/database sources",
        journal_or_publisher="U.S. EPA NEPIS / CRC / PubChem compilation",
        url="https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=91018F9R.TXT",
        evidence_role="CURATED_SECONDARY",
        quality_note="Near-ambient screening property set assembled from cited compilation sources; not a wide-range correlation.",
    ),
    "Phase 13 screening surrogate: NIST VDC pure-component vapor pressure + ideal-dilute Raoult law with gamma_inf=1. No direct public VDC/AN binary VLE dataset was identified in the Phase 13 search.": SourceMetadata(
        source_type="engineering_screening_surrogate",
        title="VDC/AN ideal-dilute Raoult-law screening surrogate",
        authors="Generic Packed Absorber Simulator V4",
        publication_year=2026,
        journal_or_publisher="Project engineering model using NIST VDC vapor-pressure data",
        url="https://webbook.nist.gov/cgi/cbook.cgi?ID=C75354&Plot=on&Type=ANTOINE&Units=CAL",
        evidence_role="SCREENING_SURROGATE",
        quality_note="Not measured VDC/AN binary equilibrium. Design-grade VLE or activity-coefficient data are still required.",
        notes="gamma_inf=1 assumption is intentionally visible and confidence D.",
    ),
}


def metadata_for_citation(citation: str) -> SourceMetadata:
    """Return structured metadata; unknown sources remain explicit/unresolved."""
    return SOURCE_METADATA_BY_CITATION.get(
        citation,
        SourceMetadata(
            source_type="unclassified",
            accessed_on=PHASE18B_ACCESSED_ON,
            evidence_role="UNCLASSIFIED",
            quality_note="Bibliographic metadata not yet curated in Phase 18B.",
        ),
    )
