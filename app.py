from __future__ import annotations

import pandas as pd
import streamlit as st

from generic_absorber_v4 import (
    MissingPairDataError,
    SoluteSpec,
    build_reference_registry,
    locked_reference_data,
)


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


def solute_df(db):
    return pd.DataFrame(
        [
            {
                "ID": s.id,
                "Name": s.name,
                "Formula": s.formula or "—",
                "MW (g/mol)": s.MW_kg_mol * 1000,
                "Carbon atoms": s.carbon_atoms,
                "CAS": s.cas_number or "—",
            }
            for s in db.solutes.values()
        ]
    )


def carrier_df(db):
    return pd.DataFrame(
        [
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
            for c in db.carriers.values()
        ]
    )


def solvent_df(db):
    return pd.DataFrame(
        [
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
            for s in db.solvents.values()
        ]
    )


def gas_pair_df(db):
    return pd.DataFrame(
        [
            {
                "Solute": solute,
                "Carrier": carrier,
                "DG (m²/s)": p.D_ref_m2_s,
                "Model": p.model,
                "T_ref (K)": p.T_ref_K,
                "P_ref (Pa)": p.P_ref_Pa,
                "Data": provenance_text(p),
            }
            for (solute, carrier), p in db.gas_transport_pairs.items()
        ]
    )


def liquid_pair_df(db):
    return pd.DataFrame(
        [
            {
                "Solute": solute,
                "Solvent": solvent,
                "DL (m²/s)": p.D_ref_m2_s,
                "Model": p.model,
                "T_ref (K)": p.T_ref_K,
                "Data": provenance_text(p),
            }
            for (solute, solvent), p in db.liquid_transport_pairs.items()
        ]
    )


def equilibrium_df(db):
    return pd.DataFrame(
        [
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
            for (solute, solvent), p in db.equilibrium_pairs.items()
        ]
    )


def packing_df(db):
    return pd.DataFrame(
        [
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
            for p in db.packings.values()
        ]
    )


def availability_df(registry):
    rows = []
    for solute_id in registry.solutes:
        for carrier_id in registry.carriers:
            for solvent_id in registry.solvents:
                r = registry.availability(solute_id, carrier_id, solvent_id)
                rows.append(
                    {
                        "Solute": solute_id,
                        "Carrier": carrier_id,
                        "Solvent": solvent_id,
                        "DG pair": "✓" if r.gas_transport_available else "✗",
                        "DL pair": "✓" if r.liquid_transport_available else "✗",
                        "Equilibrium": "✓" if r.equilibrium_available else "✗",
                        "Registry status": r.status.value,
                    }
                )
    return pd.DataFrame(rows)


DB = locked_reference_data()
REGISTRY = build_reference_registry()
COUNTS = REGISTRY.inventory_counts()

st.title("🧪 Generic Packed Absorber Simulator V4")
st.caption("Phase 2 — Pair Database & Registry Layer")

st.warning(
    "Phase 2 is still a DATA/LOOKUP layer. Onda mass transfer, counter-current ODE, "
    "pressure drop, GPDC flooding, required height and generic outlet calculations are "
    "not connected yet. Phase 2 adds exact pair lookup, registration rules and explicit "
    "missing-data behavior on top of the locked Phase 1 dataset."
)

with st.sidebar:
    st.header("Development Status")
    st.success("PHASE1_DATA_GATE = PASS")
    st.success("PHASE2_REGISTRY_GATE = PASS")
    st.metric("Reference ID", REGISTRY.reference_id)
    st.metric("Gas transport pairs", COUNTS["gas_transport_pairs"])
    st.metric("Liquid transport pairs", COUNTS["liquid_transport_pairs"])
    st.metric("Equilibrium pairs", COUNTS["equilibrium_pairs"])
    st.divider()
    st.caption("Registry policy")
    st.write("**Exact pair lookup**")
    st.write("**No silent fallback**")
    st.write("**Duplicate registration blocked by default**")
    st.write("**Pair foreign keys validated**")

(
    overview_tab,
    lookup_tab,
    solute_tab,
    fluid_tab,
    pair_tab,
    packing_tab,
    quality_tab,
) = st.tabs(
    [
        "Overview",
        "Registry Lookup",
        "Solutes",
        "Carrier & Solvent",
        "Binary Pairs",
        "Packing",
        "Data Quality",
    ]
)

with overview_tab:
    st.subheader("Phase 2 registry inventory")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Solutes", COUNTS["solutes"])
    c2.metric("Transport pairs", COUNTS["gas_transport_pairs"] + COUNTS["liquid_transport_pairs"])
    c3.metric("Equilibrium pairs", COUNTS["equilibrium_pairs"])
    c4.metric("Packings", COUNTS["packings"])

    st.markdown("### Phase 2 architecture")
    st.code(
        """Phase 1 immutable data objects
        ↓
AbsorberDataRegistry
        ↓
exact pair lookup / registration / availability
        ↓
MissingPairDataError when critical pair data are absent

No property estimation and no physics solver yet.""",
        language="text",
    )

    st.markdown("### Current combination readiness")
    st.dataframe(availability_df(REGISTRY), use_container_width=True, hide_index=True)

with lookup_tab:
    st.subheader("Exact pair lookup")
    st.caption(
        "This panel queries the Phase 2 registry. It does not calculate any new property. "
        "It only returns an explicitly registered pair."
    )

    c1, c2, c3 = st.columns(3)
    solute_id = c1.selectbox("Solute", list(REGISTRY.solutes), key="lookup_solute")
    carrier_id = c2.selectbox("Carrier", list(REGISTRY.carriers), key="lookup_carrier")
    solvent_id = c3.selectbox("Solvent", list(REGISTRY.solvents), key="lookup_solvent")

    report = REGISTRY.availability(solute_id, carrier_id, solvent_id)
    if report.status.value == "READY":
        st.success("PAIR DATA READY")
    else:
        st.error(f"PAIR DATA INCOMPLETE · Missing: {', '.join(report.missing)}")

    gas_pair = REGISTRY.find_gas_transport_pair(solute_id, carrier_id)
    liquid_pair = REGISTRY.find_liquid_transport_pair(solute_id, solvent_id)
    eq_pair = REGISTRY.find_equilibrium_pair(solute_id, solvent_id)

    rows = [
        {
            "Required dataset": "Gas transport",
            "Key": f"{solute_id} / {carrier_id}",
            "Available": gas_pair is not None,
            "Model": getattr(gas_pair, "model", "—"),
            "Value": getattr(gas_pair, "D_ref_m2_s", None),
            "Value field": "DG (m²/s)",
        },
        {
            "Required dataset": "Liquid transport",
            "Key": f"{solute_id} / {solvent_id}",
            "Available": liquid_pair is not None,
            "Model": getattr(liquid_pair, "model", "—"),
            "Value": getattr(liquid_pair, "D_ref_m2_s", None),
            "Value field": "DL (m²/s)",
        },
        {
            "Required dataset": "Equilibrium",
            "Key": f"{solute_id} / {solvent_id}",
            "Available": eq_pair is not None,
            "Model": getattr(eq_pair, "model", "—"),
            "Value": getattr(eq_pair, "H_ref_Pa_m3_mol", None)
            if getattr(eq_pair, "model", None) == "henry_pc"
            else getattr(eq_pair, "m_y_over_x", None),
            "Value field": "H_ref (Pa·m³/mol)" if getattr(eq_pair, "model", None) == "henry_pc" else "m",
        },
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### Missing-pair safety demonstration")
    st.write(
        "The button below creates a temporary synthetic solute identity **only in memory**, "
        "without adding transport/equilibrium data. It demonstrates that the registry refuses "
        "to substitute ACN/VAc data for an unknown pair."
    )
    if st.button("Run missing-pair safety check"):
        demo = build_reference_registry()
        demo.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
        try:
            demo.require_equilibrium_pair("X", "water")
        except MissingPairDataError as exc:
            st.success("PASS — missing pair was blocked; no fallback value was used.")
            st.code(str(exc), language="text")
        else:
            st.error("FAIL — missing pair unexpectedly returned data.")

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
        "Water still points to the locked V3 property model. Property calculation/resolution "
        "is a later phase; Phase 2 only registers the solvent definition."
    )

with pair_tab:
    st.subheader("Solute–carrier gas transport pairs")
    st.dataframe(gas_pair_df(DB), use_container_width=True, hide_index=True)
    st.subheader("Solute–solvent liquid transport pairs")
    st.dataframe(liquid_pair_df(DB), use_container_width=True, hide_index=True)
    st.subheader("Solute–solvent equilibrium pairs")
    st.dataframe(equilibrium_df(DB), use_container_width=True, hide_index=True)
    st.info(
        "Legacy DG and DL values still have no invented reference T/P metadata. "
        "The registry returns the locked values exactly as stored."
    )

with packing_tab:
    st.subheader("Locked reference packing")
    st.dataframe(packing_df(DB), use_container_width=True, hide_index=True)

with quality_tab:
    st.subheader("Registry safety rules")
    st.markdown(
        """
- Pair keys are explicit: `(solute, carrier)` or `(solute, solvent)`.
- A pair cannot be registered before its pure-component IDs exist.
- Duplicate registration is rejected unless replacement is explicit.
- `find_*` returns `None` for an absent pair when optional discovery is wanted.
- `require_*` raises `MissingPairDataError` for critical lookup.
- Phase 2 performs **no correlation fallback** and **no cross-chemical substitution**.
        """
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

    st.markdown("### Phase gates")
    st.success("PHASE1_DATA_GATE = PASS")
    st.success("PHASE2_REGISTRY_GATE = PASS")
    st.caption(
        "These are architecture/integrity gates. Scientific source revalidation and property "
        "estimation are deliberately outside Phase 2."
    )

st.divider()
st.caption(
    "Generic Packed Absorber Simulator V4 · Phase 2 · Pair database / registry layer · "
    "Next: Phase 3 property resolver"
)
