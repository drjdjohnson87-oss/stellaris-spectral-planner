from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative

from core import harmonic_wavelengths


PALETTE = qualitative.Plotly + qualitative.Safe + qualitative.Dark24
TUNE_COLORS = [
    "rgba(70, 130, 180, 0.10)",
    "rgba(60, 179, 113, 0.10)",
    "rgba(218, 165, 32, 0.10)",
    "rgba(186, 85, 211, 0.10)",
]


def _color_map(names: list[str]) -> dict[str, str]:
    return {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(names)}


def _spectral_bounds(
    spectra: pd.DataFrame,
    names: list[str],
    spectrum_types: list[str],
    extras: list[float] | None = None,
    fallback: tuple[float, float] = (300, 1400),
    pad_nm: float = 25,
) -> tuple[float, float]:
    d = spectra[
        spectra["name"].isin(names) & spectra["spectrum_type"].isin(spectrum_types)
    ]
    values = d["wavelength_nm"].dropna().astype(float).tolist()
    values.extend([float(v) for v in (extras or [])])
    if not values:
        return fallback
    lo = max(180, min(values) - pad_nm)
    hi = min(1500, max(values) + pad_nm)
    if hi - lo < 100:
        mid = (lo + hi) / 2
        lo, hi = mid - 50, mid + 50
    return lo, hi


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
    plotted_types: list[str] = []

    for name in names:
        d = spectra[spectra["name"] == name]
        c = colors[name]

        if show_1p:
            ex = d[d["spectrum_type"] == "EX_1P"]
            label = "1P excitation"
            used_type = "EX_1P"
            if ex.empty:
                ex = d[d["spectrum_type"] == "AB_1P"]
                label = "1P absorption"
                used_type = "AB_1P"
            if not ex.empty:
                plotted_types.append(used_type)
                fig.add_trace(go.Scatter(
                    x=ex["wavelength_nm"],
                    y=ex["value_norm"],
                    mode="lines",
                    name=f"{name} · {label}",
                    line={"color": c, "width": 2},
                    hovertemplate="%{x:.0f} nm<br>rel. %{y:.3f}<extra></extra>",
                ))

        if show_2p:
            ex2 = d[d["spectrum_type"] == "EX_2P"]
            if not ex2.empty:
                plotted_types.append("EX_2P")
                fig.add_trace(go.Scatter(
                    x=ex2["wavelength_nm"],
                    y=ex2["value_norm"],
                    mode="lines",
                    name=f"{name} · 2P",
                    line={"color": c, "width": 2, "dash": "dash"},
                    hovertemplate="%{x:.0f} nm<br>rel. %{y:.3f}<extra></extra>",
                ))

    fig.add_vline(
        x=mp_excitation_nm,
        line_dash="dot",
        line_width=2.5,
        line_color="black",
        annotation_text=f"MP {mp_excitation_nm:.0f}",
        annotation_position="top",
    )

    for line in one_p_lines or []:
        fig.add_vline(
            x=float(line),
            line_dash="dot",
            line_width=1,
            line_color="rgba(70,70,70,0.55)",
            annotation_text=f"{line:g}",
            annotation_position="bottom",
        )

    x0, x1 = _spectral_bounds(
        spectra,
        names,
        list(set(plotted_types)) or ["EX_1P", "AB_1P", "EX_2P"],
        extras=[mp_excitation_nm] + list(one_p_lines or []),
        fallback=(300, 1400),
        pad_nm=30,
    )
    fig.update_layout(
        height=390,
        xaxis_title="Wavelength (nm)",
        yaxis_title="Relative intensity",
        yaxis_range=[0, 1.05],
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.17,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 10},
        },
        margin={"l": 48, "r": 15, "t": 18, "b": 78},
    )
    fig.update_xaxes(range=[x0, x1])
    return fig


def make_emission_harmonic_figure(
    spectra: pd.DataFrame,
    names: list[str],
    mp_excitation_nm: float,
    tune_windows: list[tuple[str, float, float]] | None = None,
    show_harmonic_bands: bool = True,
):
    colors = _color_map(names)
    shg_nm, thg_nm = harmonic_wavelengths(mp_excitation_nm)
    shg_round = int(shg_nm + 0.5)
    thg_round = int(thg_nm + 0.5)
    fig = go.Figure()

    for i, (label, low, high) in enumerate(tune_windows or []):
        fig.add_vrect(
            x0=low,
            x1=high,
            fillcolor=TUNE_COLORS[i % len(TUNE_COLORS)],
            line_width=1,
            line_color="rgba(80,80,80,0.28)",
            layer="below",
        )
        fig.add_annotation(
            x=(low + high) / 2,
            y=1.02,
            xref="x",
            yref="paper",
            text=label,
            showarrow=False,
            font={"size": 9, "color": "rgba(70,70,70,0.85)"},
        )

    if show_harmonic_bands:
        fig.add_vrect(
            x0=thg_round - 5,
            x1=thg_round + 5,
            fillcolor="rgba(128, 0, 128, 0.18)",
            line_width=0,
            layer="below",
        )
        fig.add_vrect(
            x0=shg_round - 5,
            x1=shg_round + 5,
            fillcolor="rgba(255, 140, 0, 0.18)",
            line_width=0,
            layer="below",
        )

    for name in names:
        em = spectra[(spectra["name"] == name) & (spectra["spectrum_type"] == "EM")]
        if not em.empty:
            fig.add_trace(go.Scatter(
                x=em["wavelength_nm"],
                y=em["value_norm"],
                mode="lines",
                name=f"{name} · EM",
                line={"color": colors[name], "width": 3},
                hovertemplate="%{x:.0f} nm<br>rel. %{y:.3f}<extra></extra>",
            ))

    fig.add_vline(
        x=thg_nm,
        line_dash="dashdot",
        line_width=3.5,
        line_color="purple",
        annotation_text=f"THG {thg_round} nm",
        annotation_position="top left",
    )
    fig.add_vline(
        x=shg_nm,
        line_dash="dash",
        line_width=3.5,
        line_color="darkorange",
        annotation_text=f"SHG {shg_round} nm",
        annotation_position="top right",
    )

    em = spectra[
        spectra["name"].isin(names) & (spectra["spectrum_type"] == "EM")
    ]["wavelength_nm"].dropna()
    bounds = [thg_round - 8, thg_round + 8, shg_round - 8, shg_round + 8]
    if not em.empty:
        bounds.extend([float(em.min()), float(em.max())])
    for _, low, high in tune_windows or []:
        bounds.extend([low, high])

    x0 = 380
    x1 = 800
    fig.update_layout(
        height=390,
        xaxis_title="Detected wavelength (nm)",
        yaxis_title="Relative emission",
        yaxis_range=[0, 1.05],
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.17,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 10},
        },
        margin={"l": 48, "r": 15, "t": 18, "b": 78},
    )
    fig.update_xaxes(range=[x0, x1])
    return fig
