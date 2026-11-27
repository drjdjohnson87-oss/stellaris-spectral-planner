from __future__ import annotations

import pandas as pd
import streamlit as st

from core import harmonic_wavelengths, overlap_table, classify_overlap
from fpbase_adapter import fetch_fluorophore, list_fluorophore_names
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

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.0rem;
        padding-bottom: 1.0rem;
        max-width: 1550px;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0.55rem;
    }
    h1 { margin-bottom: 0.1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

init_store()

st.title("STELLARIS DIVE Spectral Planner")
st.caption(
    "Full 1P/2P spectra with SHG, THG and 4Tune-style detection bands. "
    "FPbase spectra are cached locally after import."
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
shg_round = int(shg_nm + 0.5)
thg_round = int(thg_nm + 0.5)

c1, c2 = st.sidebar.columns(2)
c1.metric("SHG", f"{shg_round} nm")
c2.metric("THG", f"{thg_round} nm")
st.sidebar.caption(
    f"10 nm guide bands: SHG {shg_round - 5}–{shg_round + 5} nm · "
    f"THG {thg_round - 5}–{thg_round + 5} nm"
)

below_detector = []
if shg_nm < 375:
    below_detector.append(f"SHG {shg_round} nm")
if thg_nm < 375:
    below_detector.append(f"THG {thg_round} nm")
if below_detector:
    st.sidebar.caption(
        "Below plotted detector range (375 nm): " + ", ".join(below_detector)
    )

st.sidebar.subheader("Optional 1P markers")
one_p_lines = st.sidebar.multiselect(
    "Laser lines",
    options=[375, 405, 473, 488, 552, 561, 594, 633, 640],
    default=[405, 488, 561],
)

show_1p = st.sidebar.checkbox("Show 1P excitation", value=True)
show_2p = st.sidebar.checkbox("Show measured 2P excitation", value=True)
show_harmonic_bands = st.sidebar.checkbox(
    "Show 10 nm SHG/THG bands", value=True
)

# ---------------- 4Tune ----------------
st.sidebar.subheader("4Tune windows")
show_4tune = st.sidebar.checkbox("Show 4Tune bands", value=True)

tune_defaults = [
    (420, 480),
    (490, 550),
    (560, 620),
    (630, 700),
]
tune_windows = []
narrow_channels = []

for i, default in enumerate(tune_defaults, start=1):
    low, high = st.sidebar.slider(
        f"Ch {i} (nm)",
        min_value=380,
        max_value=800,
        value=default,
        step=1,
        key=f"tune_ch_{i}",
    )
    if high - low < 10:
        narrow_channels.append(i)
        mid = (low + high) / 2
        low = int(mid - 5 + 0.5)
        high = low + 10
        if low < 380:
            low, high = 380, 390
        if high > 800:
            low, high = 790, 800
    tune_windows.append((f"Ch {i}", low, high))

if narrow_channels:
    st.sidebar.warning(
        "4Tune minimum band width is 10 nm. "
        "Plotting was expanded to 10 nm for Ch "
        + ", ".join(map(str, narrow_channels))
        + "."
    )

# ---------------- Local library ----------------
fluor = read_fluorophores()
spectra = read_spectra()
names = sorted(fluor["name"].dropna().astype(str).unique().tolist(), key=str.lower)

st.markdown("#### Fluorophores")
selector_cols = st.columns(4)
slot_values = []

for i, col in enumerate(selector_cols, start=1):
    options = ["— None —"] + names
    key = f"fluor_slot_{i}"

    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = names[i - 1] if i <= len(names) else "— None —"

    with col:
        value = st.selectbox(
            f"Fluorophore {i}",
            options=options,
            key=key,
        )
        slot_values.append(value)

        if value != "— None —":
            types = spectra.loc[spectra["name"] == value, "spectrum_type"].astype(str)
            labels = []
            if types.isin(["EX_1P", "AB_1P"]).any():
                labels.append("1P")
            if (types == "EX_2P").any():
                labels.append("2P")
            if (types == "EM").any():
                labels.append("EM")
            st.caption(" · ".join(labels) if labels else "No spectra")

selected = []
for value in slot_values:
    if value != "— None —" and value not in selected:
        selected.append(value)

if not names:
    st.info("Local library is empty. Import a fluorophore from FPbase below.")

# ---------------- Main plots ----------------
if selected:
    ex_fig = make_excitation_figure(
        spectra,
        selected,
        mp_excitation,
        one_p_lines,
        show_1p,
        show_2p,
    )
    em_fig = make_emission_harmonic_figure(
        spectra,
        selected,
        mp_excitation,
        tune_windows=tune_windows if show_4tune else None,
        show_harmonic_bands=show_harmonic_bands,
    )

    graph_left, graph_right = st.columns(2, gap="small")
    with graph_left:
        st.markdown("##### Excitation")
        st.plotly_chart(ex_fig, use_container_width=True)
    with graph_right:
        st.markdown("##### Emission + SHG / THG")
        st.plotly_chart(em_fig, use_container_width=True)

    with st.expander("Spectral overlap results", expanded=True):
        ov = overlap_table(spectra, selected, mp_excitation)
        if not ov.empty:
            ov["SHG overlap"] = ov["Emission @ SHG"].apply(classify_overlap)
            ov["THG overlap"] = ov["Emission @ THG"].apply(classify_overlap)
            display = ov.copy()

            display["SHG nm"] = shg_round
            display["THG nm"] = thg_round
            display.insert(
                display.columns.get_loc("SHG nm") + 1,
                "SHG 10 nm band",
                f"{shg_round - 5}–{shg_round + 5}",
            )
            display.insert(
                display.columns.get_loc("THG nm") + 1,
                "THG 10 nm band",
                f"{thg_round - 5}–{thg_round + 5}",
            )

            for col in ["Emission @ SHG", "Emission @ THG"]:
                display[col] = display[col].apply(
                    lambda x: "" if pd.isna(x) else f"{float(x):.2f}"
                )

            st.dataframe(display, use_container_width=True, hide_index=True)

        st.caption(
            "Emission-overlap values are normalized emission at the harmonic wavelength. "
            "They indicate spectral collision, not absolute fluorescence versus harmonic brightness."
        )

    missing_2p = []
    for name in selected:
        has_2p = not spectra[
            (spectra["name"] == name) & (spectra["spectrum_type"] == "EX_2P")
        ].empty
        if not has_2p:
            missing_2p.append(name)
    if missing_2p:
        st.info(
            "No measured 2P spectrum stored for: "
            + ", ".join(missing_2p)
            + ". No 2P curve is estimated from the 1P spectrum."
        )

# ---------------- Import / data management ----------------
st.divider()
tab1, tab2, tab3 = st.tabs(
    ["Import from FPbase", "Add custom spectrum", "Local library"]
)

with tab1:
    st.caption(
        "FPbase provides the upstream full spectral arrays. Imported spectra are copied "
        "into the local library, including A_2P curves when available."
    )

    if "fp_names" not in st.session_state:
        st.session_state["fp_names"] = []
    if "fp_browse" not in st.session_state:
        st.session_state["fp_browse"] = ""
    if "fp_name" not in st.session_state:
        st.session_state["fp_name"] = ""

    def copy_fpbase_choice():
        choice = st.session_state.get("fp_browse", "")
        if choice:
            st.session_state["fp_name"] = choice

    browse_col, refresh_col = st.columns([4, 1])
    with browse_col:
        st.selectbox(
            "FPbase fluorophore list",
            options=[""] + st.session_state["fp_names"],
            key="fp_browse",
            on_change=copy_fpbase_choice,
            help="Load the FPbase catalogue once, then choosing a name copies it into the type box below.",
        )
    with refresh_col:
        if st.button("Load / refresh list", use_container_width=True):
            try:
                st.session_state["fp_names"] = list_fluorophore_names()
                st.success(f"Loaded {len(st.session_state['fp_names']):,} FPbase names.")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    import_col, button_col = st.columns([4, 1])
    with import_col:
        st.text_input(
            "Type or choose FPbase name",
            placeholder="e.g. mCherry, EGFP, TagRFP",
            key="fp_name",
        )
    with button_col:
        import_clicked = st.button("Import + add", use_container_width=True)

    if import_clicked:
        fp_name = st.session_state["fp_name"].strip()
        if not fp_name:
            st.error("Enter or choose a fluorophore.")
        else:
            try:
                meta, fp_spectra = fetch_fluorophore(fp_name)
                if fp_spectra.empty:
                    st.error("FPbase returned the fluorophore but no usable spectral curves.")
                else:
                    upsert_fluorophore(meta, fp_spectra)

                    for i in range(1, 5):
                        key = f"fluor_slot_{i}"
                        if st.session_state.get(key, "— None —") == "— None —":
                            st.session_state[key] = meta["name"]
                            break

                    st.success(
                        f"Imported {meta['name']} ({len(fp_spectra):,} spectral points)."
                    )
                    st.rerun()
            except Exception as e:
                st.error(f"FPbase import failed: {e}")

with tab2:
    st.caption(
        "Add fluorophores/dyes missing from FPbase or replace/add a measured 2P curve."
    )
    st.markdown(
        "**Required columns:** `name, spectrum_type, wavelength_nm, intensity`  \n"
        "`spectrum_type`: `EX_1P`, `AB_1P`, `EM`, or `EX_2P`."
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
        if st.button("Add custom spectrum(s)"):
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
        delete_name = st.selectbox(
            "Remove local entry",
            [""] + fluor["name"].astype(str).tolist(),
        )
        if delete_name:
            local_id = fluor.loc[
                fluor["name"].astype(str) == delete_name, "local_id"
            ].iloc[0]
            if st.button(f"Delete {delete_name}"):
                delete_fluorophore(str(local_id))
                st.success(f"Removed {delete_name}.")
                st.rerun()

        export_a, export_b = st.columns(2)
        export_a.download_button(
            "Export fluorophore metadata",
            fluor.to_csv(index=False).encode(),
            "fluorophores.csv",
            "text/csv",
            use_container_width=True,
        )
        export_b.download_button(
            "Export full spectra",
            spectra.to_csv(index=False).encode(),
            "spectra.csv",
            "text/csv",
            use_container_width=True,
        )

st.caption(
    "v0.2 · four independent fluorophore slots · compact paired plots · "
    "10 nm SHG/THG guides · 4Tune windows · FPbase browse-to-import"
)
