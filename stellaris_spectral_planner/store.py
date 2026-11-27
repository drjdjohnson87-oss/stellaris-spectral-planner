from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime, timezone

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
FLUOR_FILE = DATA_DIR / "fluorophores.csv"
SPECTRA_FILE = DATA_DIR / "spectra.csv"

FLUOR_COLUMNS = [
    "local_id",
    "name",
    "fpbase_id",
    "state",
    "ex_peak_nm",
    "em_peak_nm",
    "lifetime_ns",
    "quantum_yield",
    "ext_coeff",
    "source",
    "imported_at",
]

SPECTRA_COLUMNS = [
    "local_id",
    "name",
    "state",
    "spectrum_type",
    "fpbase_subtype",
    "spectrum_id",
    "wavelength_nm",
    "value_raw",
    "value_norm",
    "source",
]


def init_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not FLUOR_FILE.exists():
        pd.DataFrame(columns=FLUOR_COLUMNS).to_csv(FLUOR_FILE, index=False)
    if not SPECTRA_FILE.exists():
        pd.DataFrame(columns=SPECTRA_COLUMNS).to_csv(SPECTRA_FILE, index=False)


def safe_id(name: str, suffix: str | None = None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "fluorophore"
    return f"{base}-{suffix}" if suffix else base


def read_fluorophores() -> pd.DataFrame:
    init_store()
    return pd.read_csv(FLUOR_FILE)


def read_spectra() -> pd.DataFrame:
    init_store()
    return pd.read_csv(SPECTRA_FILE)


def upsert_fluorophore(meta: dict, spectra: pd.DataFrame) -> str:
    init_store()

    fp_id = str(meta.get("fpbase_id") or "").strip()
    local_id = meta.get("local_id") or safe_id(meta["name"], fp_id if fp_id else None)

    fdf = read_fluorophores()
    sdf = read_spectra()

    fdf = fdf[fdf["local_id"].astype(str) != str(local_id)]
    sdf = sdf[sdf["local_id"].astype(str) != str(local_id)]

    row = {
        "local_id": local_id,
        "name": meta["name"],
        "fpbase_id": fp_id,
        "state": meta.get("state", ""),
        "ex_peak_nm": meta.get("ex_peak_nm"),
        "em_peak_nm": meta.get("em_peak_nm"),
        "lifetime_ns": meta.get("lifetime_ns"),
        "quantum_yield": meta.get("quantum_yield"),
        "ext_coeff": meta.get("ext_coeff"),
        "source": meta.get("source", "custom"),
        "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    fdf = pd.concat([fdf, pd.DataFrame([row])], ignore_index=True)

    spec = spectra.copy()
    spec["local_id"] = local_id
    spec["name"] = meta["name"]
    spec["state"] = meta.get("state", "")
    spec["source"] = meta.get("source", "custom")
    for col in SPECTRA_COLUMNS:
        if col not in spec.columns:
            spec[col] = ""
    spec = spec[SPECTRA_COLUMNS]
    sdf = pd.concat([sdf, spec], ignore_index=True)

    fdf.to_csv(FLUOR_FILE, index=False)
    sdf.to_csv(SPECTRA_FILE, index=False)
    return local_id


def delete_fluorophore(local_id: str) -> None:
    fdf = read_fluorophores()
    sdf = read_spectra()
    fdf = fdf[fdf["local_id"].astype(str) != str(local_id)]
    sdf = sdf[sdf["local_id"].astype(str) != str(local_id)]
    fdf.to_csv(FLUOR_FILE, index=False)
    sdf.to_csv(SPECTRA_FILE, index=False)


def import_custom_long_csv(df: pd.DataFrame) -> list[str]:
    """
    Import one or more custom fluorophores from long-format CSV.

    Required columns:
      name, spectrum_type, wavelength_nm, intensity

    spectrum_type should be one of:
      EX_1P, AB_1P, EM, EX_2P

    Optional:
      state, ex_peak_nm, em_peak_nm, lifetime_ns, source
    """
    required = {"name", "spectrum_type", "wavelength_nm", "intensity"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Custom CSV is missing: {sorted(missing)}")

    imported = []
    from core import clean_spectrum_df

    for name, grp in df.groupby("name", sort=False):
        state = str(grp["state"].iloc[0]) if "state" in grp.columns else ""
        out_parts = []
        for stype, sgrp in grp.groupby("spectrum_type", sort=False):
            tmp = sgrp[["wavelength_nm", "intensity"]].rename(columns={"intensity": "value_raw"})
            tmp = clean_spectrum_df(tmp)
            tmp["spectrum_type"] = str(stype)
            tmp["fpbase_subtype"] = ""
            tmp["spectrum_id"] = ""
            out_parts.append(tmp)

        spectra = pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame()
        meta = {
            "name": str(name),
            "state": state,
            "ex_peak_nm": grp["ex_peak_nm"].iloc[0] if "ex_peak_nm" in grp.columns else None,
            "em_peak_nm": grp["em_peak_nm"].iloc[0] if "em_peak_nm" in grp.columns else None,
            "lifetime_ns": grp["lifetime_ns"].iloc[0] if "lifetime_ns" in grp.columns else None,
            "source": str(grp["source"].iloc[0]) if "source" in grp.columns else "custom CSV",
        }
        imported.append(upsert_fluorophore(meta, spectra))
    return imported
