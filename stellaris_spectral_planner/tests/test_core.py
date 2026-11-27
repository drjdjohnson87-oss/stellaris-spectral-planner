import pandas as pd
import pytest

from core import (
    harmonic_wavelengths,
    normalize_values,
    interpolate_relative_intensity,
    overlap_table,
)


def test_harmonics_1040():
    shg, thg = harmonic_wavelengths(1040)
    assert shg == pytest.approx(520.0)
    assert thg == pytest.approx(346.6666667)


def test_harmonics_1275():
    shg, thg = harmonic_wavelengths(1275)
    assert shg == pytest.approx(637.5)
    assert thg == pytest.approx(425.0)


def test_normalize():
    arr = normalize_values([0, 2, 4])
    assert list(arr) == pytest.approx([0, 0.5, 1.0])


def test_interpolate():
    d = pd.DataFrame(
        {"wavelength_nm": [500, 510, 520], "value_norm": [0.0, 0.5, 1.0]}
    )
    assert interpolate_relative_intensity(515, d) == pytest.approx(0.75)
    assert interpolate_relative_intensity(490, d) is None


def test_overlap_table():
    spectra = pd.DataFrame(
        {
            "name": ["Demo", "Demo", "Demo"],
            "spectrum_type": ["EM", "EM", "EM"],
            "wavelength_nm": [500, 520, 540],
            "value_norm": [0.0, 1.0, 0.0],
        }
    )
    out = overlap_table(spectra, ["Demo"], 1040)
    assert out.loc[0, "SHG nm"] == pytest.approx(520)
    assert out.loc[0, "Emission @ SHG"] == pytest.approx(1.0)
    assert out.loc[0, "Emission @ THG"] is None
