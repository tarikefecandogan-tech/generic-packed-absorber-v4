# Phase 18A — Database Schema & Migration Architecture

**Gate:** `PHASE18A_DATABASE_MIGRATION_GATE = PASS`  
**Automated regression:** **151/151 PASS**  
**Locked V3 parity:** **82/82 PASS**  
**Production solver data source:** unchanged — verified Python registry remains active by default.

## Objective

Introduce a persistent SQLite engineering-data layer without changing any existing absorber physics or silently switching the production solver away from the verified registry.

Core migration rule:

`Phase 17 Python registry -> SQLite -> reconstructed registry -> identical objects/results`

Phase 18A intentionally performs **architecture migration before database expansion**.

## New files

- `generic_absorber_v4/database.py`
- `generic_absorber_v4/database_migration.py`
- `database/absorber_database.db`
- `database/schema.sql`
- `tests/test_phase18a_database_migration.py`
- `phase18a_check.py`

## SQLite schema

Tables:

1. `schema_metadata`
2. `sources`
3. `provenance`
4. `solutes`
5. `carrier_gases`
6. `solvents`
7. `packings`
8. `gas_transport_pairs`
9. `liquid_transport_pairs`
10. `equilibrium_pairs`

`source` and `provenance` are deliberately normalized separately. A citation can therefore be reused by multiple engineering records while each record can retain its own method, confidence class, reference conditions and validity note.

## Migrated Phase 17 inventory

- Solutes: **3** — ACN, VAc, VDC
- Carrier gases: **1** — Air
- Solvents: **2** — Water, Acrylonitrile
- Packings: **10**
- Registered gas-transport pairs: **2**
- Registered liquid-transport pairs: **2**
- Equilibrium pairs: **4**
- Normalized sources: **5**
- Provenance records: **8**

Missing VDC transport pairs remain missing in SQLite exactly as they are in the verified registry; Phase 11 correlations continue to resolve them at runtime. No estimated DG/DL value is written into the database as if it were measured pair data.

## Migration parity gate

The Phase 18A gate verifies:

- SQLite `PRAGMA integrity_check = ok`.
- Foreign-key check returns zero violations.
- Registry reference ID survives round trip.
- Exact dataclass dictionary parity for solutes, carriers, solvents, packings, gas pairs, liquid pairs and equilibrium pairs.
- Table inventory equals the source registry inventory.
- Normalized sources are deduplicated.
- SQLite foreign keys actively reject invalid pair inserts.
- A reference ACN+VAc/water absorber case run with the SQLite-reconstructed registry reproduces the existing Python-registry result to machine precision.

Reference integrated result remains:

- Outlet: **106.622281 mgVOC/Nm³**
- VOC-mass removal: **97.867554%**
- Flooding: **7.164371%**

## Streamlit

A new **Database Migration** tab displays:

- schema version,
- engineering-record inventory,
- source/provenance counts,
- SQLite integrity,
- foreign-key violations,
- equilibrium-pair catalog,
- normalized sources,
- on-demand Registry <-> SQLite parity gate.

This is deliberately a migration/audit screen, **not yet the final Database Explorer**.

## Data-governance notes

- Phase 18A does not invent source metadata that the current dataclasses do not contain.
- `SoluteSpec` currently has no provenance field, therefore pure-solute identity rows are migrated with nullable provenance rather than fabricated citations.
- Current source citation strings are preserved exactly from existing `DataProvenance` records.
- New database fields such as URL/DOI/title exist in the schema for future enrichment but remain NULL unless explicitly populated from verified source work.
- The existing V3 reference snapshot and all reference metrics remain immutable.

## Next database phases

Recommended continuation:

- **Phase 18B:** formal current-catalog seed/migration versioning and richer source metadata.
- **Phase 18C:** repository abstraction so the simulator can select Registry or SQLite through one interface.
- **Phase 18D:** production cut-over parity gate (`old registry == SQLite repository`) across reference, VDC/water, VDC/AN, sweeps and comparisons.
- **Phase 18E:** Database Explorer UI.
- **Phase 18F:** coverage matrix.
- **Phase 18G:** systematic verified chemical/solvent/packing expansion.
