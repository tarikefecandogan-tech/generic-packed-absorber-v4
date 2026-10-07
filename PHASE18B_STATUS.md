# Phase 18B — Structured Sources & Property Provenance

**Gate:** `PHASE18B_STRUCTURED_PROVENANCE_GATE = PASS`  
**Automated regression:** **158/158 PASS**  
**Locked V3 parity:** **82/82 PASS**  
**Production solver data source:** unchanged — verified Python registry remains active by default.

## Objective

Professionalize the Phase 18A SQLite database without changing absorber physics. Phase 18B turns free-text source citations into structured bibliographic records and explicitly links provenance to the engineering property/method scope it supports.

Core rule:

`same engineering catalog + richer source governance -> identical reconstructed registry -> identical simulation result`

## New files

- `generic_absorber_v4/source_metadata.py`
- `generic_absorber_v4/database_v18b.py`
- `database/absorber_database_v18b.db`
- `database/schema_v18b.sql`
- `tests/test_phase18b_structured_provenance.py`
- `phase18b_check.py`

## Phase 18B schema additions

The Phase 18A engineering tables are retained. The source/provenance layer is enriched with:

### `sources`

- `source_type`
- `title`
- `authors`
- `publication_year`
- `journal_or_publisher`
- `url`
- `doi`
- `accessed_on`
- `evidence_role`
- `quality_note`
- `notes`

### `provenance`

In addition to method/confidence/reference conditions:

- `resolution_tier`
- temperature validity range
- pressure validity range
- composition-validity note

### `provenance_usage`

A new normalized table linking provenance to engineering use:

- entity type
- entity key
- property scope
- property name
- unit
- usage note

This allows queries such as: “Which source supports VDC/water Henry data?” or “Which methods are used for gas-transport estimates?” without parsing free-text citations.

## Structured catalog inventory

Current Phase 18B database:

- Engineering solutes: **3**
- Carrier gases: **1**
- Solvents: **2**
- Packings: **10**
- Registered gas-transport pairs: **2**
- Registered liquid-transport pairs: **2**
- Equilibrium pairs: **4**
- Structured sources: **7**
- Provenance records: **10**
- Property/method usage links: **23**
- Unclassified source records: **0**

Confidence distribution across provenance records:

- A: **0**
- B: **7**
- C: **2**
- D: **1**

Five of seven sources currently have a DOI and/or web URL. The remaining two are internal locked/legacy project references and are deliberately labelled as such rather than given fabricated external links.

## Bibliographic upgrades

Phase 18B formally registers:

- Gossett (1987), *Measurement of Henry's law constants for C1 and C2 chlorinated hydrocarbons*, DOI `10.1021/es00156a012`.
- Fuller, Schettler & Giddings (1966), gas-phase binary diffusivity correlation, DOI `10.1021/ie50677a007`.
- Wilke & Chang (1955), dilute-liquid diffusivity correlation, DOI `10.1002/aic.690010222`.
- NIST WebBook URLs used for VDC Henry/vapor-pressure traceability.
- U.S. EPA/compiled acrylonitrile near-ambient property source.
- Internal locked V3 sources and Phase 13 screening surrogate remain explicitly labelled as non-primary evidence.

## Provenance usage examples

The database can now directly report:

- `equilibrium_pair | VDC|water | H_pc | Confidence B | primary experimental`
- `gas_transport_pair | ACN|air | D_G | Confidence B | locked reference`
- `liquid_transport_pair | VAc|water | D_L | Confidence B | locked reference`
- `correlation_method | fuller_gas_diffusivity | gas_transport_estimation | Confidence C`
- `correlation_method | wilke_chang_liquid_diffusivity | liquid_transport_estimation | Confidence C`
- packing geometry/hydraulic catalog usage links.

## Regression / parity gate

Phase 18B verifies:

- SQLite integrity = `ok`.
- zero foreign-key violations.
- no unclassified source metadata in the curated Phase 18B source set.
- exact dataclass parity for the core engineering registry.
- Gossett, Fuller and Wilke–Chang DOI metadata are queryable.
- property/method provenance usage is queryable.
- database-loaded registry reproduces the locked reference absorber result to machine precision.
- all Phase 1–18A regression tests remain green.

Reference integrated result remains unchanged:

- Outlet: **106.622281 mgVOC/Nm³**
- VOC-mass removal: **97.867554%**
- Flooding: **7.164371%**

## Streamlit

New **Data Provenance** tab shows:

- source/provenance/usage counts,
- metadata coverage,
- confidence distribution,
- structured source catalog,
- DOI/URL fields,
- property/method usage links,
- source-type/evidence-role summary,
- on-demand Phase 18B parity gate.

The existing **Database Migration** tab remains available for Phase 18A schema/parity audit.

## Important governance boundary

Phase 18B improves traceability; it does **not** claim every current engineering value is design-grade literature data. Internal V3 reference values, legacy packing catalog entries and the VDC/AN screening surrogate stay visibly labelled. This is intentional: database quality should improve by replacing weak evidence with verified sources, not by hiding it.

## Recommended next step

**Phase 18C — Repository Abstraction / Data Provider Interface**: make the Simulator capable of receiving either the verified Python registry or the SQLite repository through one common interface, then run full cross-provider regression before any production cut-over.
