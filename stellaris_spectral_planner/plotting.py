from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative

from core import harmonic_wavelengths


PALETTE = qualitative.Plotly + qualitative.Safe + qualitative.Dark24


def _color_map(names: list[str]) -> dict[str, str]:
    return {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(names)}


def make_excitation_figure(
    spectra: pd.DataFrame,
    names: list[str],
    mp_excitation_nm: float,
    one_p_lines: list[float] | None = None,
    show_1p: bool = True,
    show_2p: bool = True,
):
    colors = _color_map(names)
    fig = go.Figure()

    for name in names:
        d = spectra[spectra["name"] == name]
        c = colors[name]

        if show_1p:
            ex = d[d["spectrum_type"] == "EX_1P"]
            label = "1P excitation"
            if ex.empty:
                ex = d[d["spectrum_type"] == "AB_1P"]
                label = "1P absorption"
            if not ex.empty:
                fig.add_trace(go.Scatter(
                    x=ex["wavelength_nm"], y=ex["value_norm"],
                    mode="lines", name=f"{name} — {label}",
                    line={"color": c, "width": 2},
                    hovertemplate="%{x:.1f} nm<br>rel. %{y:.3f}<extra></extra>",
                ))

        if show_2p:
            ex2 = d[d["spectrum_type"] == "EX_2P"]
            if not ex2.empty:
                fig.add_trace(go.Scatter(
                    x=ex2["wavelength_nm"], y=ex2["value_norm"],
                    mode="lines", name=f"{name} — 2P excitation",
                    line={"color": c, "width": 2, "dash": "dash"},
                    hovertemplate="%{x:.1f} nm<br>rel. %{y:.3f}<extra></extra>",
                ))

    fig.add_vline(
        x=mp_excitation_nm, line_dash="dot", line_width=2,
        annotation_text=f"MP {mp_excitation_nm:.0f} nm",
        annotation_position="top",
    )

    for line in one_p_lines or []:
        fig.add_vline(
            x=float(line), line_dash="dot", line_width=1,
            annotation_text=f"{line:g}",
            annotation_position="bottom",
        )

    fig.update_layout(
        title="Excitation spectra",
        xaxis_title="Wavelength (nm)",
        yaxis_title="Relative spectral intensity (independently normalized)",
        yaxis_range=[0, 1.05],
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.22},
        margin={"l": 50, "r": 30, "t": 55, "b": 120},
    )
    fig.update_xaxes(range=[300, 1400])
    return fig


def make_emission_harmonic_figure(
    spectra: pd.DataFrame,
    names: list[str],
    mp_excitation_nm: float,
):
    colors = _color_map(names)
    shg_nm, thg_nm = harmonic_wavelengths(mp_excitation_nm)
    fig = go.Figure()

    for name in names:
        em = spectra[(spectra["name"] == name) & (spectra["spectrum_type"] == "EM")]
        if not em.empty:
            fig.add_trace(go.Scatter(
                x=em["wavelength_nm"], y=em["value_norm"],
                mode="lines", name=f"{name} — emission",
                line={"color": colors[name], "width": 3},
                hovertemplate="%{x:.1f} nm<br>rel. %{y:.3f}<extra></extra>",
            ))

    fig.add_vline(
        x=shg_nm, line_dash="dash", line_width=3,
        annotation_text=f"SHG {shg_nm:.1f} nm",
        annotation_position="top left",
    )
    fig.add_vline(
        x=thg_nm, line_dash="dashdot", line_width=3,
        annotation_text=f"THG {thg_nm:.1f} nm",
        annotation_position="top right",
    )

    fig.update_layout(
        title=f"Emission spectra with harmonics from {mp_excitation_nm:.0f} nm excitation",
        xaxis_title="Detected wavelength (nm)",
        yaxis_title="Relative emission (independently normalized)",
        yaxis_range=[0, 1.05],
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.22},
        margin={"l": 50, "r": 30, "t": 55, "b": 120},
    )
    fig.update_xaxes(range=[200, 850])
    return fig
