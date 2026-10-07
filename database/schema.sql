-- Generic Packed Absorber Simulator V4 — Phase 18A SQLite schema
-- Authoritative executable schema is generic_absorber_v4.database.SCHEMA_SQL.
-- This copy is included for human review and database tooling.

PRAGMA foreign_keys = ON;

CREATE TABLE schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    citation TEXT NOT NULL UNIQUE,
    source_type TEXT,
    title TEXT,
    url TEXT,
    doi TEXT,
    notes TEXT
);
CREATE TABLE provenance (
    provenance_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    method TEXT NOT NULL,
    confidence TEXT NOT NULL CHECK (confidence IN ('A','B','C','D')),
    reference_temperature_K REAL,
    reference_pressure_Pa REAL,
    validity_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE solutes (
    solute_id TEXT PRIMARY KEY, name TEXT NOT NULL, MW_kg_mol REAL NOT NULL,
    carbon_atoms INTEGER NOT NULL DEFAULT 0, formula TEXT, cas_number TEXT,
    fuller_diffusion_volume REAL, boiling_molar_volume_cm3_mol REAL,
    provenance_id TEXT REFERENCES provenance(provenance_id)
);
CREATE TABLE carrier_gases (
    carrier_id TEXT PRIMARY KEY, name TEXT NOT NULL, MW_kg_mol REAL NOT NULL,
    viscosity_model TEXT NOT NULL, mu_Pa_s REAL, mu_ref_Pa_s REAL, T_ref_K REAL,
    sutherland_S_K REAL, fuller_diffusion_volume REAL,
    provenance_id TEXT REFERENCES provenance(provenance_id)
);
CREATE TABLE solvents (
    solvent_id TEXT PRIMARY KEY, name TEXT NOT NULL, MW_kg_mol REAL NOT NULL,
    property_model TEXT NOT NULL, property_model_id TEXT, rho_kg_m3 REAL,
    mu_Pa_s REAL, sigma_N_m REAL, wilke_chang_association_factor REAL,
    provenance_id TEXT REFERENCES provenance(provenance_id)
);
CREATE TABLE packings (
    packing_id TEXT PRIMARY KEY, name TEXT NOT NULL, packing_class TEXT NOT NULL,
    area_m2_m3 REAL NOT NULL, nominal_size_m REAL NOT NULL, void_fraction REAL NOT NULL,
    critical_surface_tension_N_m REAL NOT NULL, pressure_drop_psi REAL NOT NULL,
    packing_factor_ft_inv REAL, packing_factor_basis TEXT NOT NULL,
    provenance_id TEXT REFERENCES provenance(provenance_id)
);
CREATE TABLE gas_transport_pairs (
    solute_id TEXT NOT NULL REFERENCES solutes(solute_id),
    carrier_id TEXT NOT NULL REFERENCES carrier_gases(carrier_id),
    D_ref_m2_s REAL NOT NULL, T_ref_K REAL, P_ref_Pa REAL, model TEXT NOT NULL,
    provenance_id TEXT REFERENCES provenance(provenance_id),
    PRIMARY KEY (solute_id, carrier_id)
);
CREATE TABLE liquid_transport_pairs (
    solute_id TEXT NOT NULL REFERENCES solutes(solute_id),
    solvent_id TEXT NOT NULL REFERENCES solvents(solvent_id),
    D_ref_m2_s REAL NOT NULL, T_ref_K REAL, model TEXT NOT NULL,
    provenance_id TEXT REFERENCES provenance(provenance_id),
    PRIMARY KEY (solute_id, solvent_id)
);
CREATE TABLE equilibrium_pairs (
    solute_id TEXT NOT NULL REFERENCES solutes(solute_id),
    solvent_id TEXT NOT NULL REFERENCES solvents(solvent_id),
    model TEXT NOT NULL, H_ref_Pa_m3_mol REAL, T_ref_K REAL,
    temperature_coefficient_K REAL, m_y_over_x REAL,
    validity_temperature_min_K REAL, validity_temperature_max_K REAL,
    validity_note TEXT NOT NULL DEFAULT '',
    provenance_id TEXT REFERENCES provenance(provenance_id),
    PRIMARY KEY (solute_id, solvent_id)
);
