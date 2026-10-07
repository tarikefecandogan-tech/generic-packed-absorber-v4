-- Generic Packed Absorber Simulator V4 — Phase 18B structured provenance schema

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    citation TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    title TEXT,
    authors TEXT,
    publication_year INTEGER,
    journal_or_publisher TEXT,
    url TEXT,
    doi TEXT,
    accessed_on TEXT,
    evidence_role TEXT NOT NULL,
    quality_note TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS provenance (
    provenance_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    method TEXT NOT NULL,
    confidence TEXT NOT NULL CHECK (confidence IN ('A','B','C','D')),
    resolution_tier TEXT,
    reference_temperature_K REAL,
    reference_pressure_Pa REAL,
    validity_temperature_min_K REAL,
    validity_temperature_max_K REAL,
    validity_pressure_min_Pa REAL,
    validity_pressure_max_Pa REAL,
    composition_validity_note TEXT NOT NULL DEFAULT '',
    validity_note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS provenance_usage (
    usage_id TEXT PRIMARY KEY,
    provenance_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    property_scope TEXT NOT NULL,
    property_name TEXT,
    unit TEXT,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id),
    UNIQUE (provenance_id, entity_type, entity_key, property_scope, property_name)
);

CREATE TABLE IF NOT EXISTS solutes (
    solute_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    MW_kg_mol REAL NOT NULL CHECK (MW_kg_mol > 0),
    carbon_atoms INTEGER NOT NULL DEFAULT 0 CHECK (carbon_atoms >= 0),
    formula TEXT,
    cas_number TEXT,
    fuller_diffusion_volume REAL,
    boiling_molar_volume_cm3_mol REAL,
    provenance_id TEXT,
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS carrier_gases (
    carrier_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    MW_kg_mol REAL NOT NULL CHECK (MW_kg_mol > 0),
    viscosity_model TEXT NOT NULL CHECK (viscosity_model IN ('sutherland','constant')),
    mu_Pa_s REAL,
    mu_ref_Pa_s REAL,
    T_ref_K REAL,
    sutherland_S_K REAL,
    fuller_diffusion_volume REAL,
    provenance_id TEXT,
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS solvents (
    solvent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    MW_kg_mol REAL NOT NULL CHECK (MW_kg_mol > 0),
    property_model TEXT NOT NULL CHECK (property_model IN ('correlation','constant','pseudo_solvent')),
    property_model_id TEXT,
    rho_kg_m3 REAL,
    mu_Pa_s REAL,
    sigma_N_m REAL,
    wilke_chang_association_factor REAL,
    provenance_id TEXT,
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS packings (
    packing_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    packing_class TEXT NOT NULL CHECK (packing_class = 'random'),
    area_m2_m3 REAL NOT NULL CHECK (area_m2_m3 > 0),
    nominal_size_m REAL NOT NULL CHECK (nominal_size_m > 0),
    void_fraction REAL NOT NULL CHECK (void_fraction > 0 AND void_fraction < 1),
    critical_surface_tension_N_m REAL NOT NULL CHECK (critical_surface_tension_N_m > 0),
    pressure_drop_psi REAL NOT NULL CHECK (pressure_drop_psi > 0),
    packing_factor_ft_inv REAL,
    packing_factor_basis TEXT NOT NULL CHECK (packing_factor_basis IN ('empirical','literature','geometric_fallback')),
    provenance_id TEXT,
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS gas_transport_pairs (
    solute_id TEXT NOT NULL,
    carrier_id TEXT NOT NULL,
    D_ref_m2_s REAL NOT NULL CHECK (D_ref_m2_s > 0),
    T_ref_K REAL,
    P_ref_Pa REAL,
    model TEXT NOT NULL CHECK (model IN ('fixed_reference','fuller')),
    provenance_id TEXT,
    PRIMARY KEY (solute_id, carrier_id),
    FOREIGN KEY (solute_id) REFERENCES solutes(solute_id),
    FOREIGN KEY (carrier_id) REFERENCES carrier_gases(carrier_id),
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS liquid_transport_pairs (
    solute_id TEXT NOT NULL,
    solvent_id TEXT NOT NULL,
    D_ref_m2_s REAL NOT NULL CHECK (D_ref_m2_s > 0),
    T_ref_K REAL,
    model TEXT NOT NULL CHECK (model IN ('fixed_reference','wilke_chang')),
    provenance_id TEXT,
    PRIMARY KEY (solute_id, solvent_id),
    FOREIGN KEY (solute_id) REFERENCES solutes(solute_id),
    FOREIGN KEY (solvent_id) REFERENCES solvents(solvent_id),
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS equilibrium_pairs (
    solute_id TEXT NOT NULL,
    solvent_id TEXT NOT NULL,
    model TEXT NOT NULL CHECK (model IN ('henry_pc','linear_m','tabulated','reactive','nonideal_unsupported','no_data')),
    H_ref_Pa_m3_mol REAL,
    T_ref_K REAL,
    temperature_coefficient_K REAL,
    m_y_over_x REAL,
    validity_temperature_min_K REAL,
    validity_temperature_max_K REAL,
    validity_note TEXT NOT NULL DEFAULT '',
    provenance_id TEXT,
    PRIMARY KEY (solute_id, solvent_id),
    FOREIGN KEY (solute_id) REFERENCES solutes(solute_id),
    FOREIGN KEY (solvent_id) REFERENCES solvents(solvent_id),
    FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
);

CREATE INDEX IF NOT EXISTS idx_equilibrium_solvent ON equilibrium_pairs(solvent_id);
CREATE INDEX IF NOT EXISTS idx_liquid_transport_solvent ON liquid_transport_pairs(solvent_id);
CREATE INDEX IF NOT EXISTS idx_gas_transport_carrier ON gas_transport_pairs(carrier_id);
CREATE INDEX IF NOT EXISTS idx_usage_entity ON provenance_usage(entity_type, entity_key);
CREATE INDEX IF NOT EXISTS idx_usage_property_scope ON provenance_usage(property_scope);
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_role ON sources(evidence_role);
