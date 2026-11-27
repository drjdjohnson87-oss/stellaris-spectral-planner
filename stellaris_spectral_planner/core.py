from __future__ import annotations

import math
import numpy as np
import pandas as pd


def harmonic_wavelengths(excitation_nm: float) -> tuple[float, float]:
    """Return SHG and THG wavelengths for an excitation wavelength in nm."""
    x = float(excitation_nm)
    if x <= 0:
        raise ValueError("Excitation wavelength must be > 0 nm.")
    return x / 2.0, x / 3.0


def normalize_values(values) -> np.ndarray:
    """Normalize a spectrum to 0..1 without changing its shape."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    finite = np.isfinite(arr)
    if not finite.any():
        return np.full_like(arr, np.nan, dtype=float)
    vmax = np.nanmax(arr)
    vmin = np.nanmin(arr)
    if math.isclose(vmax, vmin):
        return np.zeros_like(arr, dtype=float)
    # Spectra should generally be non-negative. Shift only if needed.
    if vmin < 0:
        arr = arr - vmin
        vmax = np.nanmax(arr)
    if vmax == 0:
        return np.zeros_like(arr, dtype=float)
    return arr / vmax


def clean_spectrum_df(df: pd.DataFrame) -> pd.DataFrame:
    """Validate/sort a spectrum dataframe and add value_norm."""
    required = {"wavelength_nm", "value_raw"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    out = df.copy()
    out["wavelength_nm"] = pd.to_numeric(out["wavelength_nm"], errors="coerce")
    out["value_raw"] = pd.to_numeric(out["value_raw"], errors="coerce")
    out = out.dropna(subset=["wavelength_nm", "value_raw"])
    out = out.sort_values("wavelength_nm").drop_duplicates("wavelength_nm", keep="last")
    out["value_norm"] = normalize_values(out["value_raw"].to_numpy())
    return out.reset_index(drop=True)


def interpolate_relative_intensity(
    wavelength_nm: float,
    spectrum_df: pd.DataFrame,
    value_col: str = "value_norm",
) -> float | None:
    """
    Return interpolated relative intensity at wavelength_nm.

    Returns None if the wavelength lies outside the measured spectral range.
    """
    if spectrum_df.empty:
        return None
    d = spectrum_df.sort_values("wavelength_nm")
    x = d["wavelength_nm"].to_numpy(dtype=float)
    y = d[value_col].to_numpy(dtype=float)
    target = float(wavelength_nm)
    if target < np.nanmin(x) or target > np.nanmax(x):
        return None
    return float(np.interp(target, x, y))


def overlap_table(
    spectra: pd.DataFrame,
    selected_names: list[str],
    excitation_nm: float,
) -> pd.DataFrame:
    """
    Build a simple spectral-overlap table for emission vs SHG/THG.

    This is deliberately *not* an absolute brightness prediction.
    """
    shg_nm, thg_nm = harmonic_wavelengths(excitation_nm)
    rows = []
    for name in selected_names:
        em = spectra[(spectra["name"] == name) & (spectra["spectrum_type"] == "EM")]
        if em.empty:
            rows.append(
                {
                    "Fluorophore": name,
                    "SHG nm": shg_nm,
                    "Emission @ SHG": None,
                    "THG nm": thg_nm,
                    "Emission @ THG": None,
                }
            )
            continue
        rows.append(
            {
                "Fluorophore": name,
                "SHG nm": shg_nm,
                "Emission @ SHG": interpolate_relative_intensity(shg_nm, em),
                "THG nm": thg_nm,
                "Emission @ THG": interpolate_relative_intensity(thg_nm, em),
            }
        )
    return pd.DataFrame(rows)


def classify_overlap(value: float | None) -> str:
    """Human-readable qualitative overlap flag from a normalized emission value."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "Outside measured emission range"
    if value >= 0.5:
        return "High spectral overlap"
    if value >= 0.15:
        return "Moderate spectral overlap"
    if value > 0:
        return "Low spectral overlap"
    return "Minimal / none"
