"""Analyse results/prereg2016/events_erosion.pkl (2016 development only, _v0) -> erosion_summary.json.
rho = estimated curtailment / true curtailment, estimated = B - L_obs, true = C * L_true, L_true = L_obs / (1 - C).
Erosion per dispatch eta_m = [median_b rho_b(K=10) - median_b rho_b(K=40)] / 30.
Dispatches to tolerance D_m = smallest K (linear interpolation on K = 10..40) with
median_b rho_b(K) <= median_b rho_b(10) - TAU, TAU = 0.10; censored at > 40.
"""
import json, os, site, sys
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd
from scipy.stats import rankdata

OUT = __import__("os").path.join(__import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "..")), "results", "prereg2016")
C, TAU = 0.10, 0.10
df = pd.read_pickle(os.path.join(OUT, "events_erosion.pkl"))  # self-written by prereg_2016_erosion.py (trusted)
mult = np.ones(6)
m = np.vstack(df.morning.values)
def mean_h(arr, hs):
    return arr[:, [h - 8 for h in hs]].mean(1)
prof = lambda c: np.vstack([v if isinstance(v, list) else [np.nan] * 6 for v in df[c].values])
pj = prof("pjm0_m")
B = {"pjm0": df.pjm0.values,
     "pjmA": df.pjm0.values + 4 * (mean_h(m, [10, 11, 12]) - mean_h(pj, [10, 11, 12])),
     "caisoA": df.caiso0.values * np.clip(mean_h(m, [10, 11, 12]) / mean_h(prof("caiso0_m"), [10, 11, 12]), .8, 1.2)}
B["cgA"] = B["pjmA"] * df.don_L.values / df.don_pjmA.values
for c in df.columns:
    if c.startswith("scmr_") or c.startswith("scmc_"):
        B[c] = df[c].values
Lobs = df.L.values; Ltrue = Lobs / (1 - C)
res = {"n_rows": len(df), "K": sorted(df.K.unique().tolist())}
tab = {}
for k, v in B.items():
    rho = (v - Lobs) / (C * Ltrue)
    t = pd.DataFrame({"site": df.site, "b": df.b, "K": df.K, "rho": rho})
    bm = t.groupby(["K", "site", "b"]).rho.mean()
    med = bm.groupby(level=0).median()
    site_med = bm.groupby(level=[0, 1]).median().unstack(0)
    eta = (med.loc[10] - med.loc[40]) / 30
    ks = med.index.values; ref = med.loc[10] - TAU
    below = np.where(med.values <= ref)[0]
    if len(below) == 0:
        D = ">40"
    else:
        i = below[0]
        D = float(ks[i - 1] + (med.values[i - 1] - ref) * (ks[i] - ks[i - 1]) / (med.values[i - 1] - med.values[i]))
    eta_site = (site_med[10] - site_med[40]) / 30
    tab[k] = {"median_rho_by_K": med.round(4).to_dict(), "eta_per_dispatch": round(float(eta), 5), "D_tau": D,
              "eta_site": eta_site.round(5).to_dict()}
res["methods"] = tab
def wilcoxon_p(x, side="greater"):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    signs = np.array(np.meshgrid(*[[1, -1]] * n)).reshape(n, -1).T
    rk = rankdata(np.abs(x)); obs = (np.sign(x) * rk).sum(); st = (signs * rk).sum(1)
    return float((st >= obs).mean()) if side == "greater" else float((st <= obs).mean())
scm = [k for k in B if k.startswith("scmr_")][0]
for a in ["pjmA", "caisoA", "cgA", "pjm0"]:
    d = pd.Series(tab[a]["eta_site"]) - pd.Series(tab[scm]["eta_site"])
    res["H5_dev_%s_minus_%s" % (a, scm)] = {"site_diff": d.round(5).to_dict(), "median": round(float(d.median()), 5),
                                            "wilcoxon_p_greater": wilcoxon_p(d.values, "greater"),
                                            "mde_site": round(float(2.8 * d.std(ddof=1) / np.sqrt(d.notna().sum())), 5)}
json.dump(res, open(os.path.join(OUT, "erosion_summary.json"), "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
