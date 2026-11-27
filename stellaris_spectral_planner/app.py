from __future__ import annotations

import io
import pandas as pd
import streamlit as st

from core import harmonic_wavelengths, overlap_table, classify_overlap
from fpbase_adapter import fetch_fluorophore, list_fluorophore_names, FPbaseUnavailable
from plotting import make_excitation_figure, make_emission_harmonic_figure
from store import (
    init_store,
    read_fluorophores,
    read_spectra,
    upsert_fluorophore,
    delete_fluorophore,
    import_custom_long_csv,
)

st.set_page_config(
    page_title="STELLARIS Spectral Planner",
    page_icon="🔬",
    layout="wide",
)

init_store()

st.title("STELLARIS DIVE Spectral Planner")
st.caption(
    "Plan 1P/2P excitation and inspect where SHG/THG land relative to full fluorophore emission spectra. "
    "Imported FPbase spectra are cached locally in CSV files."
)

# ---------------- Sidebar: excitation ----------------
st.sidebar.header("Excitation")
mp_excitation = st.sidebar.slider(
    "Multiphoton excitation (nm)",
    min_value=680,
    max_value=1300,
    value=1040,
    step=1,
)
shg_nm, thg_nm = harmonic_wavelengths(mp_excitation)
c1, c2 = st.sidebar.columns(2)
c1.metric("SHG", f"{shg_nm:.1f} nm")
c2.metric("THG", f"{thg_nm:.1f} nm")

st.sidebar.subheader("Optional 1P laser markers")
one_p_lines = st.sidebar.multiselect(
    "Show laser lines",
    options=[375, 405, 473, 488, 552, 561, 594, 633, 640],
    default=[405, 488, 561],
)

show_1p = st.sidebar.checkbox("Show 1P excitation", value=True)
show_2p = st.sidebar.checkbox("Show measured 2P excitation", value=True)

# ---------------- Local library ----------------
fluor = read_fluorophores()
spectra = read_spectra()

names = sorted(fluor["name"].dropna().astype(str).unique().tolist(), key=str.lower)
default_names = names[:2]

selected = st.multiselect(
    "Fluorophores",
    options=names,
    default=default_names,
    help="Import from FPbase below if the fluorophore is not yet in the local library.",
)

if not names:
    st.info("Your local library is empty. Import a fluorophore from FPbase below to start.")

# ---------------- Main plots ----------------
if selected:
    ex_fig = make_excitation_figure(
        spectra, selected, mp_excitation, one_p_lines, show_1p, show_2p
    )
    st.plotly_chart(ex_fig, use_container_width=True)

    em_fig = make_emission_harmonic_figure(spectra, selected, mp_excitation)
    st.plotly_chart(em_fig, use_container_width=True)

    st.subheader("Harmonic / emission spectral overlap")
    ov = overlap_table(spectra, selected, mp_excitation)
    if not ov.empty:
        ov["SHG overlap"] = ov["Emission @ SHG"].apply(classify_overlap)
        ov["THG overlap"] = ov["Emission @ THG"].apply(classify_overlap)
        display = ov.copy()
        for col in ["Emission @ SHG", "Emission @ THG"]:
            display[col] = display[col].apply(
                lambda x: "" if pd.isna(x) else f"{float(x):.3f}"
            )
        display["SHG nm"] = display["SHG nm"].map(lambda x: f"{x:.1f}")
        display["THG nm"] = display["THG nm"].map(lambda x: f"{x:.1f}")
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.caption(
        "Overlap values are the fluorophore's normalized emission intensity interpolated at the harmonic wavelength. "
        "They indicate spectral collision only — not the expected relative brightness of fluorescence versus SHG/THG."
    )

    missing_2p = []
    for name in selected:
        has_2p = not spectra[
            (spectra["name"] == name) & (spectra["spectrum_type"] == "EX_2P")
        ].empty
        if not has_2p:
            missing_2p.append(name)
    if missing_2p:
        st.warning(
            "No measured 2P spectrum is stored for: "
            + ", ".join(missing_2p)
            + ". The app deliberately does not invent a 2P curve by doubling the 1P wavelength."
        )

# ---------------- Import / data management ----------------
st.divider()
tab1, tab2, tab3 = st.tabs(["Import from FPbase", "Add custom spectrum", "Local library"])

with tab1:
    st.markdown(
        "FPbase is used as the upstream source. The full spectral arrays are copied into the local CSV library, "
        "including **A_2P** curves when FPbase provides them."
    )

    col_a, col_b = st.columns([3, 1])
    fp_name = col_a.text_input(
        "FPbase fluorophore name",
        placeholder="e.g. mCherry, EGFP, DAPI",
        key="fp_name",
    )
    if col_b.button("Import / update", use_container_width=True):
        if not fp_name.strip():
            st.error("Enter a fluorophore name.")
        else:
            try:
                meta, fp_spectra = fetch_fluorophore(fp_name.strip())
                if fp_spectra.empty:
                    st.error("FPbase returned the fluorophore but no usable spectral curves.")
                else:
                    upsert_fluorophore(meta, fp_spectra)
                    st.success(
                        f"Imported {meta['name']} ({len(fp_spectra):,} spectral points). "
                        "Reloading the local library…"
                    )
                    st.rerun()
            except Exception as e:
                st.error(f"FPbase import failed: {e}")

    with st.expander("Optional: load FPbase name catalogue"):
        st.caption(
            "This makes browsing easier but performs a larger API request. It is not required for exact-name imports."
        )
        if st.button("Fetch FPbase fluorophore names"):
            try:
                fp_names = list_fluorophore_names()
                st.session_state["fp_names"] = fp_names
                st.success(f"Loaded {len(fp_names):,} names.")
            except Exception as e:
                st.error(str(e))
        if "fp_names" in st.session_state:
            chosen = st.selectbox("Browse names", st.session_state["fp_names"])
            st.code(chosen)

with tab2:
    st.markdown(
        "Use this for fluorophores or dyes that are missing from FPbase, or to add a better measured 2P spectrum."
    )
    st.markdown(
        "**Required columns:** `name, spectrum_type, wavelength_nm, intensity`  \n"
        "`spectrum_type` must be one of `EX_1P`, `AB_1P`, `EM`, `EX_2P`."
    )
    template = pd.DataFrame(
        [
            {"name": "Example", "spectrum_type": "EX_1P", "wavelength_nm": 400, "intensity": 0.05},
            {"name": "Example", "spectrum_type": "EX_1P", "wavelength_nm": 401, "intensity": 0.06},
            {"name": "Example", "spectrum_type": "EM", "wavelength_nm": 500, "intensity": 0.10},
            {"name": "Example", "spectrum_type": "EM", "wavelength_nm": 501, "intensity": 0.12},
        ]
    )
    st.download_button(
        "Download custom CSV template",
        data=template.to_csv(index=False).encode(),
        file_name="custom_spectrum_template.csv",
        mime="text/csv",
    )
    upload = st.file_uploader("Upload custom long-format CSV", type=["csv"])
    if upload is not None:
        custom = pd.read_csv(upload)
        st.dataframe(custom.head(20), use_container_width=True)
        if st.button("Add custom spectrum(s) to local library"):
            try:
                imported = import_custom_long_csv(custom)
                st.success(f"Imported {len(imported)} fluorophore(s).")
                st.rerun()
            except Exception as e:
                st.error(str(e))

with tab3:
    fluor = read_fluorophores()
    spectra = read_spectra()
    st.dataframe(fluor, use_container_width=True, hide_index=True)

    if not fluor.empty:
        delete_name = st.selectbox("Remove local entry", [""] + fluor["name"].astype(str).tolist())
        if delete_name:
            local_id = fluor.loc[fluor["name"].astype(str) == delete_name, "local_id"].iloc[0]
            if st.button(f"Delete {delete_name}"):
                delete_fluorophore(str(local_id))
                st.success(f"Removed {delete_name}.")
                st.rerun()

        st.download_button(
            "Export local fluorophore metadata",
            fluor.to_csv(index=False).encode(),
            "fluorophores.csv",
            "text/csv",
        )
        st.download_button(
            "Export full local spectra",
            spectra.to_csv(index=False).encode(),
            "spectra.csv",
            "text/csv",
        )

st.divider()
st.caption(
    "Version 0.1 base: full spectral curves, FPbase import/cache, 1P/2P excitation display, "
    "adjustable MP wavelength, automatic SHG/THG, emission-overlap readout, and custom CSV import."
)
