# Phase 18D update — SQLite primary read source

Phase 18D performs the controlled product-facing cut-over to `database/absorber_database_v18b.db`. The Streamlit Simulator now uses the validated SQLite database by default, while the verified Python Registry remains available as a reference and explicit controlled fallback. SQLite activation requires integrity, foreign-key, schema-version and full registry-reconstruction checks.

Current gates: **169/169 automated tests PASS**, **82/82 V3 parity PASS**, and **5/5 dual-backend scenarios / 119/119 metrics exact match**.

See `PHASE18D_STATUS.md` for the complete cut-over and fallback policy.

---

# Generic Packed Absorber Simulator V4 — Phase 18C

Phase 18C introduces a backend-neutral engineering-data repository contract. The integrated simulator can now run from either the verified Python registry or the Phase 18B SQLite database without changing physics code.

**Current gates:** Phase 1–18C PASS · **163/163 tests PASS** · **82/82 locked V3 parity metrics PASS** · **119/119 dual-backend scenario metrics PASS**.

New modules:

- `generic_absorber_v4/repository.py`
- `generic_absorber_v4/repository_validation.py`

New product tab: **Repository Backends**. The Simulator also exposes an engineering-data backend selector and records the backend identity in each result.

See `PHASE18C_STATUS.md` for repository contracts, scenario parity, regression and governance details.

---

# Generic Packed Absorber Simulator V4 — Phase 18B

Phase 18B professionalizes the SQLite source/provenance layer while preserving every Phase 18A engineering result. Bibliographic metadata, DOI/URL fields, evidence roles and property-scope usage links are now queryable.

**Current gates:** Phase 1–18B PASS · **158/158 tests PASS** · **82/82 locked V3 parity metrics PASS**.

New database assets:

- `database/absorber_database_v18b.db`
- `database/schema_v18b.sql`
- `generic_absorber_v4/source_metadata.py`
- `generic_absorber_v4/database_v18b.py`

New product tab: **Data Provenance**. The production solver still defaults to the verified Python registry; Phase 18B is a data-governance upgrade, not a physics cut-over.

See `PHASE18B_STATUS.md` for source coverage, structured provenance, parity and governance details.

---

# Generic Packed Absorber Simulator V4 — Phase 18A

Phase 18A introduces the persistent SQLite engineering database schema and migration architecture while keeping the verified Phase 17 Python registry as the production solver data source.

**Current gates:** Phase 1–18A PASS · **151/151 tests PASS** · **82/82 locked V3 parity metrics PASS**.

New database assets:

- `database/absorber_database.db`
- `database/schema.sql`
- `generic_absorber_v4/database.py`
- `generic_absorber_v4/database_migration.py`

The migration gate proves exact Registry -> SQLite -> Registry round-trip parity and reproduces the reference absorber result using the SQLite-reconstructed registry. No production cut-over occurs in this phase.

See `PHASE18A_STATUS.md` for schema, inventory, parity and data-governance details.

---

# Generic Packed Absorber Simulator V4 — Phase 17

Phase 17 adds full-physics engineering comparison tools to the integrated simulator. Packing and solvent alternatives are evaluated by rerunning the complete verified calculation chain; there is no hidden composite "best" score.

**Current gates:** Phase 1–17 PASS · **144/144 tests PASS** · **82/82 locked V3 parity metrics PASS**.

New product tab: **Comparison**. The Phase 17 registry also exposes the remaining legacy V3 random-packing records for screening comparison while preserving the locked 25 mm reference fixture unchanged.

See `PHASE17_STATUS.md` for the comparison rules, packing catalog provenance, example results and engineering interpretation.

---

# Generic Packed Absorber Simulator V4 — Phase 16

Phase 16 adds full-physics 1D/2D parameter sweeps to the integrated simulator. Every sweep point reruns property resolution, Onda/two-film transfer, counter-current ODEs, units/report reconstruction, hydraulics, and applicability; there is no separate shortcut sweep model.

**Current gates:** Phase 1–16 PASS · **136/136 tests PASS** · **82/82 locked V3 parity metrics PASS**.

New product tab: **Parameter Sweep**. Supported axes are temperature, pressure, actual gas flow, liquid flow, diameter, packed height, and feed concentration scale. Results include outlet/removal, captured mass, flooding, pressure drop, and per-solute A/HTU/NTU.

Phase 16 is sensitivity analysis rather than optimization; validity/confidence and hydraulic feasibility remain visible for every point. See `PHASE16_STATUS.md`.

---

# Generic Packed Absorber Simulator V4 — Phase 14

Phase 14 is the first integrated product-facing release of the V4 development track. It connects the verified data, resolver, Onda/two-film, counter-current ODE, units, hydraulics and applicability layers through a single generic simulation workflow.

**Current gates:** Phase 1–14 PASS · **122/122 tests PASS** · **82/82 locked V3 parity metrics PASS**.

The main Streamlit tab is now **Simulator**. Development and validation tabs remain available for auditability.

---

# Generic Packed Absorber Simulator V4 — Phase 12

Phase 11 introduces controlled transport-property estimation correlations while preserving every prior V3 parity and generic-architecture gate.

Current resolver precedence:

`USER OVERRIDE > REGISTERED DATABASE > CORRELATION ESTIMATE > MISSING`

Built-in correlation fallbacks:

- **Fuller–Schettler–Giddings** for missing gas-phase binary diffusivity `DG`.
- **Wilke–Chang** for missing dilute liquid-phase diffusivity `DL`.

Estimates are never silent: they are returned with `ResolutionTier.CORRELATION_ESTIMATE`, `estimated=True`, and **Confidence C**. If required pure-component inputs are missing, resolution blocks rather than inventing a value.

Regression state:

- Phase 1–11 gates: PASS
- Automated tests: **104/104 PASS**
- Locked V3 full parity: **82/82 PASS**
- Phase 10 synthetic generic chemistry gate: PASS

Run locally:

```bash
pip install -r requirements.txt
streamlit run app.py
```

See `PHASE11_STATUS.md` for the implemented equations, inputs, and gate details.


## Phase 12 — VDC / Water

Phase 12 adds the first real chemistry outside the locked ACN/VAc reference dataset.

- VDC identity: 1,1-dichloroethylene, CAS 75-35-4, MW 96.943 g/mol.
- VDC/water equilibrium: NIST WebBook / Gossett (1987) measured Henry dataset, Confidence B.
- VDC/air DG: Fuller fallback, Confidence C.
- VDC/water DL: Wilke–Chang fallback, Confidence C.
- Applicability pre-check now recognizes estimatable missing transport pairs instead of blocking them as missing data.
- Deterministic VDC/water gate: PASS.
- Automated tests: 110/110 PASS.
- Locked V3 parity: 82/82 PASS.

The default VDC/water fixture gives A << 1 and only low VDC removal at the reference L/G and packed height. This is a screening result, not plant calibration.


## Phase 13 — VDC / Acrylonitrile

Phase 13 adds liquid acrylonitrile as a real solvent and runs a VDC/AN screening case through the complete generic chain.

Data governance is intentionally conservative:

- Acrylonitrile bulk liquid properties: near-ambient literature/database values, Confidence B.
- VDC/air gas diffusivity: Fuller fallback, Confidence C.
- VDC in acrylonitrile liquid diffusivity: Wilke–Chang fallback, Confidence C; phi=1.0 is a screening assumption.
- VDC/AN equilibrium: **Confidence D** ideal-dilute Raoult surrogate at 22 °C and 1 atm, `m = Psat,VDC/P`, gamma_inf=1.
- Acrylonitrile evaporation is materially important near ambient conditions but is not modelled in V4.0, therefore Phase 13 is explicitly outside the recommended design domain.

The deterministic Phase 13 fixture uses the same column/flow basis as Phase 12 so the solvent effect is easy to compare. The screening calculation predicts much stronger VDC uptake into AN than water, but this is not design validation until direct VDC/AN equilibrium data and solvent evaporation are represented.

The project pilot trial (300 L/h N2, 18 L/h AN, final liquid 93.84% AN / 6.16% VDC, outlet 1100 ppm VOC) is preserved as external qualitative evidence only. It is not used to fit the equilibrium slope because the available slide summary does not document inlet VDC and a complete material-balance basis.

## Phase 15 — Live Methods & Assumptions

Phase 15 adds `generic_absorber_v4/methods.py`, a report-only engineering audit layer for the integrated Simulator. After a case is run, **Methods & Assumptions** displays the equations actually used, live numerical results, resolved property provenance, correlation/estimate tiers, active assumptions, solver closure diagnostics, hydraulic diagnostics, applicability issues, and confidence ratings. The audit consumes the existing simulation result and does not duplicate the physics calculation.

Phase 15 validation: **127/127 automated tests PASS**; locked V3 parity remains **82/82 PASS**.

---

# Generic Packed Absorber Simulator V4 — Phase 18E

Phase 18E adds a read-only **Database Explorer & Coverage Matrix** on top of the SQLite primary engineering database.

**Current gates:** Phase 1–18E PASS · **177/177 tests PASS** · **82/82 locked V3 parity metrics PASS**.

New explorer capabilities:

- browse solutes, solvents, carrier gases and packings;
- inspect registered equilibrium / gas-transport / liquid-transport pairs;
- search IDs, names, CAS/source/DOI text across the catalog;
- display a carrier-aware solute × solvent coverage matrix;
- distinguish VERIFIED, ESTIMATED, SCREENING, MISSING and UNSUPPORTED data paths;
- generate a prioritized missing-data / data-quality backlog.

The explorer is deliberately read-only and does not calculate absorber performance. See `PHASE18E_STATUS.md` for the current coverage snapshot and acceptance gate.

## Phase 18F — controlled chemical database expansion
Phase 18F adds a versioned JSON ingestion contract (`18F.1`) for expanding the engineering database without bypassing provenance or validation. Use `database/templates/chemical_import_template.json` as the starting form.

Validation/dry-run is the default:

```bash
python chemical_import_cli.py my_chemical_package.json
```

An explicit transactional commit is:

```bash
python chemical_import_cli.py my_chemical_package.json --commit
```

A backup is created by default before a commit. Existing IDs/pairs remain append-only unless the operator explicitly adds `--allow-replace`. The Streamlit `Expansion Framework` tab is deliberately dry-run only.

Phase 18F does **not** add a new real chemical to the primary SQLite database; it creates the controlled path by which reviewed data can be added in the next expansion stages.

## Phase 18G — first verified chemical expansion batch

Phase 18G uses the controlled Phase-18F import framework to add the first five real VOCs to a new primary SQLite snapshot: acetone, benzene, toluene, ethylbenzene and dichloromethane. NIST identity and water-Henry data are Confidence B; fixed transport pairs are deliberately not invented, so Fuller/Wilke–Chang remain visible Confidence-C fallbacks.

The product primary database is now `database/absorber_database_v18g.db`. The frozen `absorber_database_v18b.db` remains packaged for historical Python↔SQLite parity gates.

Current regression state: **206/206 tests PASS** and **82/82 locked V3 parity metrics PASS**. See `PHASE18G_STATUS.md` and `database/batches/phase18g_verified_batch.json` for the auditable batch record.

## Phase 18G deployment-hardening note

This release is rebased on the Phase-18F Streamlit import/loading repair. Keep the whole ZIP together when deploying: `app.py`, `generic_absorber_v4/`, and `database/` must come from the same release. Top-level tabs are lazy-loaded and Phase-18F/18G feature imports are startup-safe so an optional feature mismatch does not take down the core simulator.
