"""Analyse results/prereg2016/events_R*.pkl (2016 development data only, _v0). Writes results/prereg2016/summary.json.
Computes: SCM grid choice, method table R1/R3, H1-H4 development estimates and MDEs, TOST margin anchors,
pre-cooling p* curves (analytic recompute of every adjusted rule from the stored event-day morning hours).
"""
import json, os, site, sys
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd

OUT = __import__("os").path.join(__import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "..")), "results", "prereg2016")
rng = np.random.default_rng(5)
# pickles are self-written by prereg_2016.py in this project (trusted)
R1 = pd.read_pickle(os.path.join(OUT, "events_R1.pkl"))
R3 = pd.read_pickle(os.path.join(OUT, "events_R3.pkl"))
res = {"n_events_R1": len(R1), "n_events_R3": len(R3), "n_b_R1": int(R1.b.nunique()), "sites_R1": sorted(R1.site.unique())}
H = lambda hs: [h - 8 for h in hs]  # index into stored morning hours 8..13
P4 = [10, 11, 12, 13]; P2 = [12, 13]

def adjusted(df, p=0.0, hours=P4):
    """Baselines (window kWh) for every method under pre-cooling p on `hours` (target only)."""
    mult = np.ones(6); mult[H(hours)] += p
    m = np.vstack(df.morning.values) * mult
    out = {}
    def mean_h(arr, hs):
        return arr[:, H(hs)].mean(1)
    def prof(name):
        return np.vstack([v if isinstance(v, list) else [np.nan] * 6 for v in df[name + "_m"].values]) if name + "_m" in df else None
    for name in ["pjm0", "caiso0", "ny0", "isone0", "dm0", "wm0", "m3", "mid8", "prev"]:
        out[name] = df[name].values if name in df else np.full(len(df), np.nan)
    pj = prof("pjm0"); out["pjmA"] = df.pjm0.values + 4 * (mean_h(m, [10, 11, 12]) - mean_h(pj, [10, 11, 12]))
    ca = prof("caiso0"); out["caisoA"] = df.caiso0.values * np.clip(mean_h(m, [10, 11, 12]) / mean_h(ca, [10, 11, 12]), .8, 1.2)
    ny = prof("ny0"); out["nyA"] = df.ny0.values * np.clip(mean_h(m, [10, 11]) / mean_h(ny, [10, 11]), .8, 1.2)
    ie = prof("isone0"); out["isoneA"] = np.maximum(df.isone0.values + 4 * (mean_h(m, [11, 12]) - mean_h(ie, [11, 12])), 0)
    dm = prof("dm0"); out["dmA"] = df.dm0.values * np.clip(mean_h(m, [10, 11]) / mean_h(dm, [10, 11]), .8, 1.2)
    wm = prof("wm0"); out["wmA"] = df.wm0.values * np.clip(mean_h(m, [10, 11]) / mean_h(wm, [10, 11]), .6, 1.4)
    m3 = prof("m3"); out["m3A"] = df.m3.values * np.clip(mean_h(m, [10, 11]) / mean_h(m3, [10, 11]), .8, 1.2)
    out["cgA"] = out["pjmA"] * df.don_L.values / df.don_pjmA.values
    out["cg0"] = df.pjm0.values * df.don_L.values / df.don_pjm0.values
    for c in df.columns:
        if c.startswith("scmr_") or c.startswith("scmc_"):
            out[c] = df[c].values
    return out

def per_building(df, base):
    L = df.L.values
    t = pd.DataFrame({k: (v - L) / L for k, v in base.items()})
    t["b"] = df.b.values; t["site"] = df.site.values; t["use"] = df.use.values
    absmean = t.groupby(["site", "b"]).agg(lambda x: np.nanmean(np.abs(x)) if np.issubdtype(np.asarray(x).dtype, np.number) else x.iloc[0])
    return t, absmean

# ---- SCM grid (R1, no pre-cooling) ----
b0 = adjusted(R1)
t0, a0 = per_building(R1, b0)
scm_cols = [c for c in b0 if c.startswith("scm")]
grid = {c: round(float(a0[c].median()), 4) for c in scm_cols}
res["scm_grid_median_relMAE"] = grid
best_r = min([c for c in scm_cols if c.startswith("scmr_")], key=lambda c: grid[c])
best_c = min([c for c in scm_cols if c.startswith("scmc_")], key=lambda c: grid[c])
res["scm_best_ridge"] = best_r; res["scm_best_classic"] = best_c

meths = ["prev", "pjm0", "pjmA", "caiso0", "caisoA", "ny0", "nyA", "isone0", "isoneA", "dm0", "dmA", "wm0", "wmA", "m3", "m3A", "mid8", "cg0", "cgA", best_r, best_c]
common = R1.dropna(subset=["pjm0", "caiso0", "don_L"]).index
res["common_support_share_R1"] = round(len(common) / len(R1), 3)
tab = {}
for name, df in [("R1", R1), ("R3", R3)]:
    if "don_L" not in df:
        continue
    bb = adjusted(df)
    t, a = per_building(df, {k: bb[k] for k in meths if k in bb})
    bias = t.groupby(["site", "b"])[[k for k in meths if k in bb]].mean()
    tab[name] = {k: {"median_relMAE": round(float(a[k].median()), 4), "median_bias": round(float(bias[k].median()), 4),
                     "n_b": int(a[k].notna().sum())} for k in meths if k in bb}
res["methods_2016"] = tab

# ---- helpers for site-level inference ----
def site_median(series):
    return series.groupby(level=0).median()

def signflip_p(x, one_sided="less", stat="wilcoxon"):
    """Exact site-level sign-flip test; statistic = median (default) or mean of the site values."""
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    signs = np.array(np.meshgrid(*[[1, -1]] * n)).reshape(n, -1).T
    if stat == "wilcoxon":   # exact signed-rank: statistic = sum of signed ranks of |x|
        from scipy.stats import rankdata
        rk = rankdata(np.abs(x)); obs = (np.sign(x) * rk).sum(); st = (signs * rk).sum(1)
    else:
        f = np.median if stat == "median" else np.mean
        obs = f(x); st = f(signs * x, axis=1)
    return float((st <= obs).mean()) if one_sided == "less" else float((st >= obs).mean())

def two_stage_ci(a, col_fn, B=2000, alpha=0.10):
    """a: per-building frame indexed (site,b); col_fn(frame)->per-building values; statistic = median over sites of
    site medians."""
    v = col_fn(a)
    sites = v.index.get_level_values(0).unique().tolist()
    groups = {s: v.loc[s].dropna().values for s in sites}
    stats = []
    for _ in range(B):
        ss = rng.choice(sites, len(sites), replace=True)
        meds = [np.median(rng.choice(groups[s], len(groups[s]), replace=True)) for s in ss if len(groups[s])]
        stats.append(np.median(meds))
    est = float(np.median([np.median(groups[s]) for s in sites if len(groups[s])]))
    return est, [float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2))]

def mde(site_vals):
    sv = np.asarray(site_vals); sv = sv[~np.isnan(sv)]
    return float(2.8 * sv.std(ddof=1) / np.sqrt(len(sv)))

# ---- H1: PJM unadjusted, bias R1 - R3 (paired by building) ----
bR1 = adjusted(R1); bR3 = adjusted(R3)
tR1 = pd.DataFrame({"b": R1.b, "site": R1.site, "e": (bR1["pjm0"] - R1.L) / R1.L}).groupby(["site", "b"]).e.mean()
tR3 = pd.DataFrame({"b": R3.b, "site": R3.site, "e": (bR3["pjm0"] - R3.L) / R3.L}).groupby(["site", "b"]).e.mean()
d1 = (tR1 - tR3).dropna()
s1 = site_median(d1)
res["H1_dev"] = {"site_median_of_bias_diff": s1.round(4).to_dict(), "median_over_sites": round(float(s1.median()), 4),
                 "mean_over_sites": round(float(s1.mean()), 4), "signflip_p_less": signflip_p(s1.values, "less"),
                 "signflip_p_less_meanstat": signflip_p(s1.values, "less", "mean"),
                 "signflip_p_less_medianstat": signflip_p(s1.values, "less", "median"),
                 "mde_site_mean": round(mde(s1.values), 4)}
# ---- H2: log(relMAE pjmA / pjm0) on R1 ----
lr2 = np.log(a0["pjmA"] / a0["pjm0"]).replace([np.inf, -np.inf], np.nan).dropna()
s2 = site_median(lr2)
res["H2_dev"] = {"site_median_log_ratio": s2.round(4).to_dict(), "median_over_sites": round(float(s2.median()), 4),
                 "signflip_p_less": signflip_p(s2.values, "less"), "mde_site_mean": round(mde(s2.values), 4)}
# ---- H3 and TOST anchors ----
def lr(a, x, y):
    return np.log(a[x] / a[y]).replace([np.inf, -np.inf], np.nan).dropna()
for x, y in [("cgA", "pjmA"), ("caisoA", "pjmA"), ("nyA", "pjmA"), ("dmA", "pjmA"), ("isoneA", "pjmA"), (best_r, "pjmA"), (best_c, "pjmA")]:
    v = lr(a0, x, y); sv = site_median(v)
    est, ci = two_stage_ci(a0, lambda a: lr(a, x, y))
    res["contrast_%s_vs_%s" % (x, y)] = {"median_over_sites": round(float(sv.median()), 4), "mean_over_sites": round(float(sv.mean()), 4),
                                          "two_stage_est": round(est, 4), "two_stage_90ci": [round(c, 4) for c in ci],
                                          "site_sd": round(float(sv.std(ddof=1)), 4), "mde_site_mean": round(mde(sv.values), 4),
                                          "site_values": sv.round(4).to_dict()}
# best official adjusted rule on 2016 (by pooled median building relMAE)
off = ["pjmA", "caisoA", "nyA", "isoneA"]
res["best_official_adjusted_2016"] = min(off, key=lambda k: tab["R1"][k]["median_relMAE"])
# ---- pre-cooling p* ----
pg = np.round(np.arange(0, 0.3001, 0.005), 3)
pmeth = ["pjmA", "caisoA", "nyA", "isoneA", "dmA", "wmA", "cgA", "cg0", best_r, best_c, "pjm0"]
curves = {}
for hours, tag in [(P4, "4h"), (P2, "2h")]:
    cur = {k: [] for k in pmeth}
    site_cur = {k: [] for k in pmeth}
    for p in pg:
        bp = adjusted(R1, p, hours)
        _, ap = per_building(R1, {k: bp[k] for k in pmeth})
        for k in pmeth:
            cur[k].append(float(ap[k].median()))
            site_cur[k].append(ap[k].groupby(level=0).median())
    curves[tag] = {k: [round(v, 4) for v in cur[k]] for k in pmeth}
    def pstar(vals):
        vals = np.asarray(vals)
        if vals[0] >= 0.10:
            return 0.0
        idx = np.where(vals >= 0.10)[0]
        if len(idx) == 0:
            return float("inf")
        i = idx[0]
        return float(pg[i - 1] + (0.10 - vals[i - 1]) * (pg[i] - pg[i - 1]) / (vals[i] - vals[i - 1]))
    res["pstar_pooled_" + tag] = {k: pstar(cur[k]) for k in pmeth}
    sp = {}
    for k in pmeth:
        mat = pd.concat(site_cur[k], axis=1)
        sp[k] = {s: pstar(mat.loc[s].values) for s in mat.index}
    res["pstar_site_" + tag] = sp
    # H4 dev: site p*(SCM best ridge) - p*(pjmA), p* censored at 0.30
    cap = lambda v: min(v, 0.30)
    dif = np.array([cap(sp[best_r][s]) - cap(sp["pjmA"][s]) for s in sp["pjmA"]])
    res["H4_dev_" + tag] = {"site_diff_capped": dict(zip(sp["pjmA"].keys(), np.round(dif, 4).tolist())),
                            "mean": round(float(dif.mean()), 4), "signflip_p_greater": signflip_p(dif, "greater")}
    # break-even crossing p_x: pre-cooling at which each I-morn method's relMAE equals the primary donor
    # baseline's relMAE (unaffected by construction); per site and pooled; capped at 0.30
    def cross(v_morn, v_donor0):
        v = np.asarray(v_morn)
        if v[0] >= v_donor0:
            return 0.0
        idx = np.where(v >= v_donor0)[0]
        if len(idx) == 0:
            return 0.30
        i = idx[0]
        return float(pg[i - 1] + (v_donor0 - v[i - 1]) * (pg[i] - pg[i - 1]) / (v[i] - v[i - 1]))
    res["pcross_pooled_" + tag] = {k: cross(cur[k], cur[best_r][0]) for k in ["pjmA", "caisoA", "nyA", "isoneA", "dmA", "wmA", "cgA"]}
    matP = pd.concat(site_cur["pjmA"], axis=1); matS = pd.concat(site_cur[best_r], axis=1)
    pxs = pd.Series({s_: cross(matP.loc[s_].values, matS.loc[s_].values[0]) for s_ in matP.index})
    res["pcross_site_pjmA_" + tag] = pxs.round(4).to_dict()
    res["H4x_dev_" + tag] = {"median_site_px": round(float(pxs.median()), 4),
                             "signflip_p_less_than_0.10": signflip_p((pxs - 0.10).values, "less"),
                             "mde_site": round(mde(pxs.values), 4)}
res["precool_curves_grid"] = pg.tolist()
res["precool_curves"] = curves
for tag in ["4h", "2h"]:
    res["relMAE_at_grid_" + tag] = {k: {str(p): curves[tag][k][int(round(p / 0.005))] for p in [0, .02, .05, .10, .20, .30]} for k in pmeth}
json.dump(res, open(os.path.join(OUT, "summary.json"), "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k not in ("precool_curves", "precool_curves_grid", "pstar_site_4h", "pstar_site_2h")}, indent=1, default=str))
