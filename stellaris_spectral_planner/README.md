# STELLARIS DIVE Spectral Planner — v0.1

A small local Streamlit app for planning STELLARIS DIVE fluorescence / harmonic imaging.

## v0.1 features

- Imports full fluorescence spectrum arrays from FPbase.
- Caches imported spectra locally as CSV.
- Plots 1P excitation / absorption spectra.
- Plots measured 2P excitation (`A_2P`) when FPbase provides it.
- Plots the full emission spectrum.
- Adjustable multiphoton excitation wavelength (680–1300 nm).
- Automatically calculates and overlays:
  - SHG = excitation / 2
  - THG = excitation / 3
- Interpolates fluorophore emission at the SHG and THG wavelength to flag spectral collision.
- Optional 1P laser markers (375, 405, 473, 488, 552, 561 etc.).
- Custom long-format CSV import for missing or improved spectra.
- Local library export.

## Why FPbase through its API rather than scraping the graph?

The Python `fpbase` package is a wrapper around FPbase's GraphQL API and returns the actual spectrum arrays.
This includes the spectrum subtype `A_2P` when a measured two-photon curve is available.

The app copies those arrays into:
- `data/fluorophores.csv`
- `data/spectra.csv`

After import, plotting from the local cache does not require FPbase.

## Recommended development setup

Python 3.11 or 3.12 is recommended.

### Windows

Open PowerShell in this folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Streamlit normally opens:

`http://localhost:8501`

Leave the terminal running. During development, Streamlit detects file changes and offers to rerun / automatically reruns, so this is a good way to test changes interactively.

## Best way to test during development

Use three levels:

### 1. Fast unit tests

```bash
pytest -q
```

These test the maths and data handling without needing the GUI or internet.

### 2. Local UI testing

```bash
streamlit run app.py
```

Keep this open while editing. Test:
- MP wavelength slider
- SHG/THG values
- fluorophore selections
- plot zoom / hover
- missing 2P warnings
- custom CSV import

### 3. FPbase integration test

A useful first FPbase test is `mCherry`, because FPbase's Python package documentation shows EX, EM and A_2P spectra for it.

Also test a fluorophore without a 2P spectrum to make sure the app gives a warning rather than inventing a curve.

## Sanity checks for harmonics

- 1040 nm -> SHG 520 nm; THG 346.67 nm
- 1275 nm -> SHG 637.5 nm; THG 425 nm
- 920 nm -> SHG 460 nm; THG 306.67 nm

## Local spectral CSV schema

`data/spectra.csv` is long-format. Important columns:

- `name`
- `state`
- `spectrum_type`
  - `EX_1P`
  - `AB_1P`
  - `EM`
  - `EX_2P`
- `wavelength_nm`
- `value_raw`
- `value_norm`
- `source`

Raw spectrum shape is preserved. `value_norm` is independently normalized to 0–1 only for plotting.

## Custom spectrum format

Required columns:

```text
name,spectrum_type,wavelength_nm,intensity
```

Example:

```text
MyDye,EM,500,0.12
MyDye,EM,501,0.15
MyDye,EX_2P,900,0.08
MyDye,EX_2P,910,0.11
```

This lets you add literature spectra even when FPbase lacks them.

## Important scientific caveats

- A measured 2P spectrum is **not** inferred by simply doubling a 1P excitation spectrum.
- 1P and 2P curves are independently normalized for display. Their plotted heights are not directly comparable in absolute excitation probability.
- SHG and THG are shown at the theoretical harmonic wavelength. Their actual detected strength depends on sample structure, phase matching, excitation power, objective, collection efficiency and detector sensitivity.
- The "overlap" table only reports where the harmonic lies on a normalized fluorophore emission curve. It is a spectral-conflict indicator, not an absolute signal prediction.

## Likely v0.2 additions

- 4Tune adjustable detector windows with overlap / capture calculations.
- STELLARIS WLL and Firefly presets.
- Objective transmission curves (25x VISIR, 40x IRAPO) if we can obtain reliable data.
- Dichroic/filter curves from the actual Rapp/Leica setup.
- Save/load experiment configurations.
- Better FPbase search/autocomplete.
- Fluorophore state selection for photoswitchable / photoconvertible proteins.
- Detector-response weighting and predicted channel capture.
