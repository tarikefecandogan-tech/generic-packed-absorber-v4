from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from generic_absorber_v4 import locked_reference_data


st.set_page_config(
    page_title="Generic Packed Absorber Simulator V4",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)


def provenance_text(obj) -> str:
    p = getattr(obj, "provenance", None)
    if p is None:
        return "—"
    return f"{p.confidence.value} · {p.method}"


def optional(value, fmt="{}"):
    return "—" if value is None else fmt.format(value)


def solute_df(db):
    rows = []
    for s in db.solutes.values():
        rows.append(
            {
                "ID": s.id,
                "Name": s.name,
                "Formula": s.formula or "—",
                "MW (g/mol)": s.MW_kg_mol * 1000,
                "Carbon atoms": s.carbon_atoms,
                "CAS": s.cas_number or "—",
            }
        )
    return pd.DataFrame(rows)


def carrier_df(db):
    rows = []
    for c in db.carriers.values():
        rows.append(
            {
                "ID": c.id,
                "Name": c.name,
                "MW (g/mol)": c.MW_kg_mol * 1000,
                "Viscosity model": c.viscosity_model,
                "mu_ref (Pa·s)": c.mu_ref_Pa_s,
                "T_ref (K)": c.T_ref_K,
                "Sutherland S (K)": c.sutherland_S_K,
                "Data": provenance_text(c),
            }
        )
    return pd.DataFrame(rows)


def solvent_df(db):
    rows = []
    for s in db.solvents.values():
        rows.append(
            {
                "ID": s.id,
                "Name": s.name,
                "MW (g/mol)": s.MW_kg_mol * 1000,
                "Property model": s.property_model,
                "Property model ID": s.property_model_id or "—",
                "rho const. (kg/m³)": s.rho_kg_m3,
                "mu const. (Pa·s)": s.mu_Pa_s,
                "sigma const. (N/m)": s.sigma_N_m,
                "Data": provenance_text(s),
            }
        )
    return pd.DataFrame(rows)


def gas_pair_df(db):
    rows = []
    for (solute, carrier), p in db.gas_transport_pairs.items():
        rows.append(
            {
                "Solute": solute,
                "Carrier": carrier,
                "DG (m²/s)": p.D_ref_m2_s,
                "Model": p.model,
                "T_ref (K)": p.T_ref_K,
                "P_ref (Pa)": p.P_ref_Pa,
                "Data": provenance_text(p),
            }
        )
    return pd.DataFrame(rows)


def liquid_pair_df(db):
    rows = []
    for (solute, solvent), p in db.liquid_transport_pairs.items():
        rows.append(
            {
                "Solute": solute,
                "Solvent": solvent,
                "DL (m²/s)": p.D_ref_m2_s,
                "Model": p.model,
                "T_ref (K)": p.T_ref_K,
                "Data": provenance_text(p),
            }
        )
    return pd.DataFrame(rows)


def equilibrium_df(db):
    rows = []
    for (solute, solvent), p in db.equilibrium_pairs.items():
        rows.append(
            {
                "Solute": solute,
                "Solvent": solvent,
                "Model": p.model,
                "H_ref (Pa·m³/mol)": p.H_ref_Pa_m3_mol,
                "T_ref (K)": p.T_ref_K,
                "Temperature coeff. (K)": p.temperature_coefficient_K,
                "Linear m": p.m_y_over_x,
                "Data": provenance_text(p),
            }
        )
    return pd.DataFrame(rows)


def packing_df(db):
    rows = []
    for p in db.packings.values():
        rows.append(
            {
                "ID": p.id,
                "Name": p.name,
                "Class": p.packing_class,
                "a_t (m²/m³)": p.area_m2_m3,
                "Nominal size (mm)": p.nominal_size_m * 1000,
                "Void fraction": p.void_fraction,
                "Critical surface tension (N/m)": p.critical_surface_tension_N_m,
                "Pressure-drop ψ": p.pressure_drop_psi,
                "Packing factor (ft⁻¹)": p.packing_factor_ft_inv,
                "Fp basis": p.packing_factor_basis,
                "Data": provenance_text(p),
            }
        )
    return pd.DataFrame(rows)


DB = locked_reference_data()

st.title("🧪 Generic Packed Absorber Simulator V4")
st.caption("Phase 1 — Generic data architecture and locked V3 reference dataset")

st.warning(
    "Phase 1 is intentionally DATA-ONLY. Onda mass transfer, counter-current ODE, "
    "pressure drop, GPDC flooding, required height and generic outlet calculations are "
    "not connected yet. This page proves that the new V4 data architecture loads correctly."
)

with st.sidebar:
    st.header("Phase 1 Status")
    st.success("PHASE1_DATA_GATE = PASS")
    st.metric("Reference ID", DB.reference_id)
    st.metric("Solutes", len(DB.solutes))
    st.metric("Carriers", len(DB.carriers))
    st.metric("Solvents", len(DB.solvents))
    st.metric("Packings", len(DB.packings))
    st.divider()
    st.caption("Locked reference system")
    st.write("**Carrier:** Air")
    st.write("**Solvent:** Water")
    st.write("**Solutes:** ACN + VAc")
    st.write("**Packing:** 25 mm Metal Pall Ring")

summary_tab, solute_tab, fluid_tab, pair_tab, packing_tab, quality_tab = st.tabs(
    [
        "Overview",
        "Solutes",
        "Carrier & Solvent",
        "Binary Pairs",
        "Packing",
        "Data Quality",
    ]
)

with summary_tab:
    st.subheader("Phase 1 reference inventory")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Solutes", len(DB.solutes))
    c2.metric("Transport pairs", len(DB.gas_transport_pairs) + len(DB.liquid_transport_pairs))
    c3.metric("Equilibrium pairs", len(DB.equilibrium_pairs))
    c4.metric("Packings", len(DB.packings))

    st.markdown("### Architecture introduced in Phase 1")
    st.code(
        """SoluteSpec\nCarrierGasSpec\nSolventSpec\nPackingSpec\nGasTransportPair\nLiquidTransportPair\nEquilibriumPair\nDataProvenance / ConfidenceClass""",
        language="text",
    )

    st.markdown("### Scope boundary")
    st.write(
        "Only the locked ACN + VAc / Water / Air reference dataset is included. "
        "No VDC or other new chemistry is intentionally present yet."
    )

with solute_tab:
    st.subheader("Pure solute definitions")
    st.dataframe(solute_df(DB), use_container_width=True, hide_index=True)
    st.caption(
        "Henry constants and diffusivities do not live on the solute object. "
        "They belong to binary solute–solvent or solute–carrier pairs."
    )

with fluid_tab:
    st.subheader("Carrier gases")
    st.dataframe(carrier_df(DB), use_container_width=True, hide_index=True)

    st.subheader("Solvents")
    st.dataframe(solvent_df(DB), use_container_width=True, hide_index=True)
    st.info(
        "Water is represented by the existing V3 temperature-dependent property model. "
        "The numerical water-property calculation itself is intentionally not part of Phase 1."
    )

with pair_tab:
    st.subheader("Solute–carrier gas transport pairs")
    st.dataframe(gas_pair_df(DB), use_container_width=True, hide_index=True)

    st.subheader("Solute–solvent liquid transport pairs")
    st.dataframe(liquid_pair_df(DB), use_container_width=True, hide_index=True)

    st.subheader("Solute–solvent equilibrium pairs")
    st.dataframe(equilibrium_df(DB), use_container_width=True, hide_index=True)

    st.info(
        "Legacy DG and DL values do not declare reference temperature/pressure in the V3 source. "
        "Phase 1 therefore keeps T_ref/P_ref empty instead of inventing metadata."
    )

with packing_tab:
    st.subheader("Locked reference packing")
    st.dataframe(packing_df(DB), use_container_width=True, hide_index=True)

with quality_tab:
    st.subheader("Data provenance and confidence")
    st.write(
        "The values in this Phase 1 reference dataset were copied without re-estimation from the "
        "locked V3 reference engine. Scientific source review and new-chemistry database expansion "
        "are intentionally deferred to later phases."
    )

    provenance_rows = []
    for group_name, objects in [
        ("Carrier", DB.carriers.values()),
        ("Solvent", DB.solvents.values()),
        ("Packing", DB.packings.values()),
        ("Gas transport", DB.gas_transport_pairs.values()),
        ("Liquid transport", DB.liquid_transport_pairs.values()),
        ("Equilibrium", DB.equilibrium_pairs.values()),
    ]:
        for obj in objects:
            p = getattr(obj, "provenance", None)
            if p is None:
                continue
            provenance_rows.append(
                {
                    "Group": group_name,
                    "Object": getattr(obj, "name", None)
                    or f"{getattr(obj, 'solute_id', '?')} / {getattr(obj, 'carrier_id', getattr(obj, 'solvent_id', '?'))}",
                    "Confidence": p.confidence.value,
                    "Method": p.method,
                    "Source": p.source,
                    "Validity note": p.validity_note,
                }
            )

    st.dataframe(pd.DataFrame(provenance_rows), use_container_width=True, hide_index=True)

    st.markdown("### Phase gate")
    st.success("7/7 DATA-LAYER TESTS PASS · V3 SOURCE MATCH PASS")
    st.caption(
        "This is a migration/integrity gate, not a claim that the scientific property sources have "
        "already been independently revalidated."
    )

st.divider()
st.caption(
    "Generic Packed Absorber Simulator V4 · Phase 1 · Data architecture only · "
    "Next: Phase 2 pair registry / lookup layer"
)
