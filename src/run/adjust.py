"""Day-of adjustments (I-morn variants) and comparison groups, recomputed analytically from the stored event-day
morning hours (hours s-6..s-1) and the stored unadjusted profiles. Only hours <= s-2 enter any adjustment (s9.3)."""
import numpy as np
import pandas as pd

from . import config as C
from . import leakage as LK


def _prof(df, name):
    col = name + "_m"
    if col not in df:
        return None
    return np.vstack([v if isinstance(v, list) else [np.nan] * 6 for v in df[col].values])


def shaped_morning(df, s, p=0.0, shape="4h", obs=False):
    """Target morning hours with the pre-event increase p (multiplicative, uniform over the shaping hours)."""
    a, b = C.SHAPES[shape]
    m = np.vstack(df["morning_obs" if obs else "morning"].values).astype(float)
    p = np.asarray(p, float)
    mult = np.ones((len(m), 6)) if p.ndim else np.ones(6)
    for h in range(s + a, s + b):
        if p.ndim:
            mult[:, h - (s - 6)] += p     # per building-event increase (heterogeneous variant)
        else:
            mult[h - (s - 6)] += p
    return m * mult


def adjusted(df, s, e, p=0.0, shape="4h", obs=False):
    """Window-kWh baseline for every method under pre-event increase p on `shape` hours of the target only."""
    nw = e - s
    m = shaped_morning(df, s, p, shape, obs)
    off = s - 6

    def mh(arr, hs):
        return arr[:, [h - off for h in hs]].mean(1)

    out = {}
    for name in ["pjm0", "caiso0", "ny0", "isone0", "dm0", "wm0", "m3", "mid8", "prev"]:
        out[name] = df[name].values if name in df else np.full(len(df), np.nan)
    H = {k: [s + a for a in C.ADJ[k]] for k in C.ADJ}
    for k in C.ADJ:
        LK.a3_hours(H[k], s, "I-morn")
    pj = _prof(df, "pjm0")
    out["pjmA"] = df.pjm0.values + nw * (mh(m, H["pjm"]) - mh(pj, H["pjm"]))
    ca = _prof(df, "caiso0")
    lo, hi = C.CLIP["caiso"]
    out["caisoA"] = df.caiso0.values * np.clip(mh(m, H["caiso"]) / mh(ca, H["caiso"]), lo, hi)
    ny = _prof(df, "ny0")
    lo, hi = C.CLIP["ny"]
    out["nyA"] = df.ny0.values * np.clip(mh(m, H["ny"]) / mh(ny, H["ny"]), lo, hi)
    ie = _prof(df, "isone0")
    out["isoneA"] = np.maximum(df.isone0.values + nw * (mh(m, H["isone"]) - mh(ie, H["isone"])), 0)
    for nm, key in [("dm", "dm"), ("wm", "wm"), ("m3", "m3")]:
        pr = _prof(df, nm + ("0" if nm != "m3" else ""))
        lo, hi = C.CLIP[key]
        base = out[nm + "0"] if nm != "m3" else out["m3"]
        out[nm + "A"] = base * np.clip(mh(m, H[key]) / mh(pr, H[key]), lo, hi)
    if "don_L" in df:
        out["cgA"] = out["pjmA"] * df.don_L.values / df.don_pjmA.values
        out["cg0"] = df.pjm0.values * df.don_L.values / df.don_pjm0.values
    for c in df.columns:
        if c.startswith("scmr_") or c.startswith("scmc_"):
            out[c] = df[c].values
    sr = "scmr_W%d_l%g" % (C.SCM_W, C.SCM_LAM)
    if sr in df:
        out["scmR"] = df[sr].values
    sc = "scmc_W%d" % C.SCM_C_W
    if sc in df:
        out["scmC"] = df[sc].values
    return out
