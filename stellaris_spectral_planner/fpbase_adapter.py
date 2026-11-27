from __future__ import annotations

import pandas as pd

from core import clean_spectrum_df


FPBASE_TO_LOCAL = {
    "EX": "EX_1P",
    "AB": "AB_1P",
    "EM": "EM",
    "A_2P": "EX_2P",
}


class FPbaseUnavailable(RuntimeError):
    pass


def _load_fpbase():
    try:
        import fpbase
    except ImportError as e:
        raise FPbaseUnavailable(
            "The 'fpbase' package is not installed. Run: pip install fpbase"
        ) from e
    return fpbase


def list_fluorophore_names():
    """Return FPbase fluorophore names if the API is reachable."""
    fpbase = _load_fpbase()
    names = fpbase.list_fluorophores()
    # fpbase has returned mappings in some versions and lists in others.
    if isinstance(names, dict):
        return sorted(names.keys(), key=str.lower)
    out = []
    for item in names:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out.append(item.get("name") or item.get("key") or str(item))
        else:
            out.append(getattr(item, "name", str(item)))
    return sorted(set(out), key=str.lower)


def fetch_fluorophore(name: str) -> tuple[dict, pd.DataFrame]:
    """
    Fetch one fluorophore from FPbase and return:
      metadata dict, long spectra dataframe.

    Uses the FPbase Python GraphQL wrapper, which includes the full spectrum
    arrays and A_2P curves when present.
    """
    fpbase = _load_fpbase()
    obj = fpbase.get_fluorophore(name)

    state = getattr(obj, "default_state", None)
    if state is None:
        states = getattr(obj, "states", []) or []
        if not states:
            raise ValueError(f"No spectral state found for {name!r}.")
        state = states[0]

    rows = []
    seen_local_types = set()

    for spec in getattr(state, "spectra", []) or []:
        subtype = str(getattr(spec, "subtype", ""))
        local_type = FPBASE_TO_LOCAL.get(subtype)
        if not local_type:
            continue

        # Prefer EX over AB if both exist, but retain AB when EX is absent.
        if local_type == "AB_1P" and "EX_1P" in seen_local_types:
            continue

        data = getattr(spec, "data", None) or []
        if not data:
            continue

        tmp = pd.DataFrame(data, columns=["wavelength_nm", "value_raw"])
        tmp = clean_spectrum_df(tmp)
        tmp["spectrum_type"] = local_type
        tmp["fpbase_subtype"] = subtype
        tmp["spectrum_id"] = getattr(spec, "id", "")
        rows.append(tmp)
        seen_local_types.add(local_type)

    # If both absorption and excitation made it through, keep both; the UI
    # will preferentially plot EX_1P and use AB_1P only as a fallback.
    spectra = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=[
            "wavelength_nm", "value_raw", "value_norm",
            "spectrum_type", "fpbase_subtype", "spectrum_id"
        ]
    )

    meta = {
        "name": getattr(obj, "name", name),
        "fpbase_id": getattr(obj, "id", ""),
        "state": getattr(state, "name", ""),
        "ex_peak_nm": getattr(state, "exMax", None),
        "em_peak_nm": getattr(state, "emMax", None),
        "lifetime_ns": getattr(state, "lifetime", None),
        "quantum_yield": getattr(state, "qy", None),
        "ext_coeff": getattr(state, "ext_coeff", None),
        "source": "FPbase",
    }
    return meta, spectra
