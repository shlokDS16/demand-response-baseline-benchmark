"""PREREG Revision 2 development values (2016 only, _v0) with the frozen Revision 2 definitions (DECISIONS T3).
Reads results/prereg2016/events_R1.pkl, events_R3.pkl, events_erosion.pkl (self-written by prereg_2016.py and
prereg_2016_erosion.py; trusted). Writes results/prereg2016/summary_rev2.json.
Conventions implemented here are the ones the PREREG fixes for 2017 (src/run must reproduce them):
  signed-rank: exact, full enumeration of 2^n sign patterns, zeros (|x| < 1e-12) dropped and counted, average ranks;
  HL: median of Walsh averages; CI by exact inversion of the signed-rank distribution (no-tie distribution);
  sign test: exact binomial; median CI: order statistics; support: >= 10 building-events per method pair per site.
"""
import json, os, site, sys
from itertools import product
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd
from scipy.stats import rankdata, binom

OUT = __import__("os").path.join(__import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "..")), "results", "prereg2016")
MIN_SUPPORT = 10
DELTA = float(np.log(1.10))
P4 = [10, 11, 12, 13]
GRID = np.round(np.arange(0, 0.3001, 0.005), 3)
SCM = "scmr_W7_l3"
R1 = pd.read_pickle(os.path.join(OUT, "events_R1.pkl"))
R3 = pd.read_pickle(os.path.join(OUT, "events_R3.pkl"))
ER = pd.read_pickle(os.path.join(OUT, "events_erosion.pkl"))
res = {"definitions": "PREREG Revision 2", "n_events_R1": len(R1), "n_events_R3": len(R3), "n_rows_erosion": len(ER)}

# ---------------- exact tests and intervals ----------------
def signed_rank(x, alternative):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    nz = np.abs(x) < 1e-12; n_zero = int(nz.sum()); x = x[~nz]; n = len(x)
    if n == 0:
        return {"p": 1.0, "n": 0, "n_zero": n_zero}
    rk = rankdata(np.abs(x))
    obs = rk[x > 0].sum()
    tot = 0; cnt = 0
    for signs in product([0, 1], repeat=n):
        w = rk[np.array(signs, bool)].sum()
        tot += 1
        if (alternative == "greater" and w >= obs - 1e-9) or (alternative == "less" and w <= obs + 1e-9):
            cnt += 1
    return {"p": cnt / tot, "n": n, "n_zero": n_zero, "W_plus": float(obs)}

def wplus_dist(n):
    M = n * (n + 1) // 2; c = np.zeros(M + 1); c[0] = 1
    for k in range(1, n + 1):
        c2 = c.copy(); c2[k:] += c[:-k]; c = c2
    return c / c.sum()

def hl_ci(x, conf):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    wal = np.sort([(x[i] + x[j]) / 2 for i in range(n) for j in range(i, n)])
    est = float(np.median(wal)); M = len(wal)
    cdf = np.cumsum(wplus_dist(n)); a = (1 - conf) / 2
    ok = np.where(cdf <= a)[0]
    if len(ok) == 0:
        return est, [None, None]
    k = int(ok[-1]) + 1  # P(W+ <= k-1) <= a  -> CI = [wal_(k), wal_(M+1-k)] (1-indexed)
    return est, [float(wal[k - 1]), float(wal[M - k])]

def sign_test(x, alternative):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    nz = x != 0; n = int(nz.sum()); n_zero = int((~nz).sum())
    k = int((x < 0).sum()) if alternative == "less" else int((x > 0).sum())
    return {"p": float(binom.sf(k - 1, n, 0.5)) if n else 1.0, "k": k, "n": n, "n_zero": n_zero}

def median_os_ci(x, conf=0.95):
    x = np.sort(np.asarray(x, float)); n = len(x); a = (1 - conf) / 2
    r = max([r for r in range(1, n + 1) if binom.cdf(r - 1, n, 0.5) <= a], default=None)
    fmt = lambda v: ">0.30" if not np.isfinite(v) else round(float(v), 4)
    if r is None:
        return [None, None]
    return [fmt(x[r - 1]), fmt(x[n - r])]

def fmt_c(v, cap, label):
    return label if not np.isfinite(v) else round(float(v), 4)

# ---------------- baselines with pre-cooling ----------------
def prof(df, c):
    return np.vstack([v if isinstance(v, list) else [np.nan] * 6 for v in df[c].values])
def mean_h(a, hs):
    return a[:, [h - 8 for h in hs]].mean(1)
def baselines(df, p=0.0, hours=P4):
    mult = np.ones(6); mult[[h - 8 for h in hours]] += p
    m = np.vstack(df.morning.values) * mult
    out = {"pjm0": df.pjm0.values, SCM: df[SCM].values if SCM in df else np.full(len(df), np.nan)}
    out["pjmA"] = df.pjm0.values + 4 * (mean_h(m, [10, 11, 12]) - mean_h(prof(df, "pjm0_m"), [10, 11, 12]))
    out["caisoA"] = df.caiso0.values * np.clip(mean_h(m, [10, 11, 12]) / mean_h(prof(df, "caiso0_m"), [10, 11, 12]), .8, 1.2)
    out["cgA"] = out["pjmA"] * df.don_L.values / df.don_pjmA.values
    return out

def building_table(df, meth, value="absrel", p=0.0):
    B = baselines(df, p)
    t = pd.DataFrame({k: (B[k] - df.L.values) / df.L.values for k in meth})
    if value == "absrel":
        t = t.abs()
    t["site"] = df.site.values; t["b"] = df.b.values; t["day"] = df.day.values
    if "draw" in df:
        t["draw"] = df.draw.values
    return t

def support_sites(t, pair):
    ok = t.dropna(subset=list(pair)).groupby("site").size()
    return ok[ok >= MIN_SUPPORT].index.tolist(), ok.to_dict()

def summarise(site_vals, alternative, conf=0.95):
    sv = pd.Series(site_vals).dropna()
    sr = signed_rank(sv.values, alternative)
    est, ci = hl_ci(sv.values, conf)
    return {"site_values": sv.round(4).to_dict(), "n_sites": int(len(sv)), "HL": round(est, 4),
            "HL_ci%d" % int(conf * 100): [None if c is None else round(c, 4) for c in ci],
            "median_of_sites": round(float(sv.median()), 4), "signed_rank": sr}

# ---------------- H1 ----------------
t1 = building_table(R1, ["pjm0"], "signed").dropna()
t3 = building_table(R3, ["pjm0"], "signed").dropna()
b1 = t1.groupby(["site", "b"]).pjm0.mean()
b3 = t3.groupby(["site", "b", "draw"]).pjm0.mean().groupby(level=[0, 1]).mean()  # building-first over draws
d1 = (b1 - b3).dropna()
sup1 = t1.groupby("site").size()
sites1 = [s for s in d1.index.get_level_values(0).unique() if sup1.get(s, 0) >= MIN_SUPPORT]
res["H1"] = summarise(d1.loc[sites1].groupby(level=0).median(), "less")
res["H1"]["source_direction"] = "Coughlin 2009 (10.1016/j.enbuild.2008.11.002); Granderson 2021 (10.1016/j.enbuild.2021.111031)"
# ---------------- H2 ----------------
ta = building_table(R1, ["pjmA", "pjm0"]).dropna()
sites2, sup2 = support_sites(ta, ("pjmA", "pjm0"))
bl = ta.groupby(["site", "b"])[["pjmA", "pjm0"]].mean()
lr2 = np.log(bl.pjmA / bl.pjm0).replace([np.inf, -np.inf], np.nan)
res["H2"] = summarise(lr2.loc[sites2].groupby(level=0).median(), "less")
# ---------------- H3 (TOST, intersection-union) ----------------
tc = building_table(R1, ["cgA", "pjmA"]).dropna()
sites3, sup3 = support_sites(tc, ("cgA", "pjmA"))
blc = tc.groupby(["site", "b"])[["cgA", "pjmA"]].mean()
lr3 = np.log(blc.cgA / blc.pjmA).replace([np.inf, -np.inf], np.nan).loc[sites3].groupby(level=0).median()
p_lo = signed_rank(lr3.values + DELTA, "greater"); p_hi = signed_rank(lr3.values - DELTA, "less")
est3, ci90 = hl_ci(lr3.values, 0.90)
res["H3"] = {"site_values": lr3.round(4).to_dict(), "n_sites": int(len(lr3)), "HL": round(est3, 4),
             "HL_ci90": [round(c, 4) for c in ci90], "p_lower": p_lo["p"], "p_upper": p_hi["p"],
             "p_TOST": max(p_lo["p"], p_hi["p"]), "delta": round(DELTA, 4)}
# ---------------- H4: p-cross, sign test; p*; incremental sensitivity ----------------
curves = {}
for p in GRID:
    t = building_table(R1, ["pjmA", SCM, "caisoA", "cgA", "pjm0"], p=p)
    curves[p] = t
t0 = curves[0.0].dropna(subset=["pjmA", SCM])
sites4, sup4 = support_sites(t0, ("pjmA", SCM))
def first_cross(vals, ref):
    vals = np.asarray(vals, float)
    if vals[0] >= ref:
        return 0.0                       # the rule is not better even without pre-cooling
    for i in range(1, len(vals)):
        if np.isnan(vals[i]) or np.isnan(vals[i - 1]):
            return float("nan")          # no interpolation across a grid point without support
        if vals[i] >= ref:
            return float(GRID[i - 1] + (ref - vals[i - 1]) * (GRID[i] - GRID[i - 1]) / (vals[i] - vals[i - 1]))
    return float("inf")                  # right-censored: ">0.30"
keys = t0[["site", "b", "day"]]
def site_curve(meth, s):
    return [float(curves[p].loc[keys.index][keys.site == s].groupby("b")[meth].mean().median()) for p in GRID]
pcs = {}
for s in sites4:
    ref = float(curves[0.0].loc[keys.index][keys.site == s].groupby("b")[SCM].mean().median())
    pcs[s] = first_cross(site_curve("pjmA", s), ref)
pcs = pd.Series(pcs)
st = sign_test(pcs.values - 0.10, "less")
x_sr = np.where(np.isfinite(pcs.values), pcs.values, 1.0) - 0.10   # censored ranked as largest positive
res["H4"] = {"site_pcross": {k: fmt_c(v, 0.30, ">0.30") for k, v in pcs.items()}, "n_sites": int(len(pcs)),
             "median_site_pcross": fmt_c(float(np.median(np.sort(pcs.values))), 0.30, ">0.30"),
             "median_ci95_order_stat": median_os_ci(pcs.values, 0.95),
             "sign_test_less_0.10": st, "signed_rank_sensitivity": signed_rank(x_sr, "less"),
             "source_direction": "E4_novelty_gaming.md s1-2 (LBNL-4984E, Braithwait 2010, CPUC D.09-08-027)",
             "threshold_0.10_source": "top of the realistic pre-cooling band, E4_novelty_gaming.md s3"}
pooled = {m: [float(curves[p].loc[keys.index].groupby("b")[m].mean().median()) for p in GRID] for m in ["pjmA", SCM, "caisoA", "cgA", "pjm0"]}
res["H4"]["pooled_pcross"] = fmt_c(first_cross(pooled["pjmA"], pooled[SCM][0]), 0.30, ">0.30")
res["H4"]["incremental_sensitivity_pooled"] = {str(p): round((pooled["pjmA"][i] - pooled["pjmA"][0]) - (pooled[SCM][i] - pooled[SCM][0]), 4)
                                               for i, p in enumerate(GRID) if p in (0.02, 0.05, 0.10, 0.20, 0.30)}
res["pstar_pooled"] = {m: fmt_c(first_cross(pooled[m], 0.10), 0.30, ">0.30") for m in pooled}
# ---------------- H5: LS slope on fixed common support ----------------
C = 0.10
Bm = baselines(ER)
Lobs = ER.L.values; Lt = Lobs / (1 - C)
te = pd.DataFrame({m: (Bm[m] - Lobs) / (C * Lt) for m in ["pjmA", SCM, "caisoA", "pjm0", "cgA"]})
te[["site", "b", "day", "K", "pjm_fb", "caiso_fb", "caiso_n"]] = ER[["site", "b", "day", "K", "pjm_fb", "caiso_fb", "caiso_n"]].values
te = te.dropna(subset=["pjmA", SCM])
Ks = [10, 20, 30, 40]
full = te.groupby(["site", "b", "day"]).K.nunique()
keep = full[full == 4].index
te = te.set_index(["site", "b", "day"]).loc[keep].reset_index()
res["H5_support_events_per_K"] = int(len(keep))
def slope(y):
    return float(np.polyfit(Ks, y, 1)[0])
eta, dtau, curvesK = {}, {}, {}
for m in ["pjmA", SCM, "caisoA", "pjm0", "cgA"]:
    eta[m], dtau[m], curvesK[m] = {}, {}, {}
    for s, g in te.groupby("site"):
        if g[g.K == 10].shape[0] < MIN_SUPPORT:
            continue
        y = [float(g[g.K == k].groupby("b")[m].mean().median()) for k in Ks]
        curvesK[m][s] = [round(v, 4) for v in y]
        eta[m][s] = -slope(y)
        ref = y[0] - 0.10
        D = float("inf")
        for i in range(1, 4):
            if y[i] <= ref:
                D = Ks[i - 1] + (y[i - 1] - ref) * (Ks[i] - Ks[i - 1]) / (y[i - 1] - y[i]); break
        dtau[m][s] = D
pool_y = {m: [float(te[te.K == k].groupby("b")[m].mean().median()) for k in Ks] for m in eta}
res["H5"] = summarise(pd.Series(eta["pjmA"]) - pd.Series(eta[SCM]), "greater")
res["H5"]["source_direction"] = "Nexant CAISO BAWG 2017 s1.3; NAESB 2009 (E4_novelty_gaming.md s5)"
res["H5"]["eta_pooled"] = {m: round(-slope(pool_y[m]), 5) for m in pool_y}
res["H5"]["rho_pooled_by_K"] = {m: [round(v, 4) for v in pool_y[m]] for m in pool_y}
res["H5"]["Dtau_site"] = {m: {s: fmt_c(v, 40, ">40") for s, v in dtau[m].items()} for m in dtau}
res["H5"]["fallback_rate_by_K"] = {str(k): {"pjm_fb": round(float(te[te.K == k].pjm_fb.astype(float).mean()), 4),
                                            "caiso_fb": round(float(te[te.K == k].caiso_fb.astype(float).mean()), 4),
                                            "caiso_lt10_days": round(float((te[te.K == k].caiso_n.astype(float) < 10).mean()), 4)} for k in Ks}
res["support"] = {"H2": sup2, "H3": sup3, "H4": sup4, "min_per_site": MIN_SUPPORT}
# conditional two-stage bootstrap is reported by prereg_2016_analyse.py (labelled conditional)
json.dump(res, open(os.path.join(OUT, "summary_rev2.json"), "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
