"""E3 design pilot c, DEVELOPMENT YEAR 2016 ONLY (_v0). R1 days, window 14-18.
Per site, buildings are split at random (seed) into participants (50 %) and donors (50 %); only participants are
targets, only donors are comparison units (no circularity). Methods:
  caisoU (adjusted, unclipped), caisoA (clipped 0.8-1.2), pjmA (additive SAA), cgnaive (target unadjusted CAISO x
  donor observed/donor unadjusted), cgadj (target caisoU x donor observed/donor caisoU), scmpre (NNLS on 20 prior
  days + event-day hours 0..9, i.e. before adjustment hours).
Pre-cooling stress: target load x (1+p) in hours 10..13 (4 h before a 14:00 start); analytic effect on each method.
Portfolio: random portfolios of n participants within site-day; relative abs error of summed baseline.
Shared component: share of variance of building errors explained by the site-day mean, per method.
"""
import json, os, site, sys
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd
from scipy.optimize import nnls

ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw", "bdg2")
OUT = os.path.join(ROOT, "results", "e3_profile")
rng = np.random.default_rng(7)
cov = pd.read_csv(os.path.join(OUT, "building_coverage.csv"), index_col=0)
elig = cov[(cov.year16_cov >= 0.9) & (cov.zero16 < 0.05)]
cols = elig.index.tolist()
chunks = []
for ch in pd.read_csv(os.path.join(RAW, "electricity_cleaned.csv"), chunksize=2000, index_col=0, parse_dates=True,
                      usecols=lambda c: c == "timestamp" or c in set(cols)):
    chunks.append(ch.astype(np.float32))
E = pd.concat(chunks).loc["2016"][cols]; del chunks
days = pd.date_range("2016-01-01", "2016-12-31", freq="D")
X = E.values.reshape(len(days), 24, len(cols)).astype(np.float64); del E
W = pd.read_csv(os.path.join(RAW, "weather.csv"), usecols=["timestamp", "site_id", "airTemperature"], parse_dates=["timestamp"])
W = W[W.timestamp.dt.year == 2016]; W["date"] = W.timestamp.dt.normalize()
tmax = W.groupby(["site_id", "date"]).airTemperature.max().unstack(0).reindex(days)
HOL = {"US": ["2016-01-01", "2016-01-18", "2016-02-15", "2016-05-30", "2016-07-04", "2016-09-05", "2016-10-10", "2016-11-11", "2016-11-24", "2016-12-26"],
       "UK": ["2016-01-01", "2016-03-25", "2016-03-28", "2016-05-02", "2016-05-30", "2016-08-29", "2016-12-26", "2016-12-27"],
       "IE": ["2016-01-01", "2016-03-17", "2016-03-28", "2016-05-02", "2016-06-06", "2016-08-01", "2016-10-31", "2016-12-26", "2016-12-27"]}
ctry = lambda tz: "UK" if tz == "Europe/London" else ("IE" if tz == "Europe/Dublin" else "US")
WIN = [14, 15, 16, 17]; ADJ = [10, 11, 12]
season = (days >= "2016-05-15") & (days <= "2016-09-30")
rows = []
for s in elig.site_id.unique():
    bi = [cols.index(b) for b in elig.index[elig.site_id == s]]
    if len(bi) < 12 or s not in tmax.columns:
        continue
    tz = elig.timezone[elig.site_id == s].iloc[0]
    hol = set(pd.to_datetime(HOL[ctry(tz)]))
    wk = np.array([(d.dayofweek < 5) and (d not in hol) for d in days])
    Xs = X[:, :, bi]
    win = Xs[:, WIN, :].sum(1)
    complete = ~np.isnan(Xs).any(1)
    dz = (np.diff(Xs[:, 10:18, :], axis=1) == 0).astype(int)
    flat = np.zeros(complete.shape, bool); cur = np.zeros(complete.shape, int)
    for h in range(dz.shape[1]):
        cur = np.where(dz[:, h, :] == 1, cur + 1, 0); flat |= cur >= 3
    complete &= ~flat
    keep = np.where((flat & (wk & season)[:, None]).sum(0) / (wk & season).sum() <= 0.2)[0]
    if len(keep) < 12:
        continue
    perm = rng.permutation(keep)
    part, dpool = perm[: len(perm) // 2], perm[len(perm) // 2:]
    cand = np.where(wk & season & ~np.isnan(tmax[s].values))[0]
    ev = cand[np.argsort(-tmax[s].values[cand])][:10]
    evset = set(ev.tolist())
    for d in sorted(ev):
        def past(j, n, maxback=45):
            out = []
            for k in range(d - 1, max(d - maxback - 1, -1), -1):
                if wk[k] and k not in evset and complete[k, j]:
                    out.append(k)
                if len(out) == n:
                    break
            return out
        info = {}
        for j in list(part) + list(dpool):
            if not complete[d, j]:
                continue
            p = past(j, 10)
            if len(p) < 5:
                continue
            c0 = Xs[p][:, :, j].mean(0)
            info[j] = dict(c0w=c0[WIN].sum(), r=Xs[d, ADJ, j].mean() / c0[ADJ].mean(), p=p, c0=c0)
        don = [q for q in dpool if q in info]
        if len(don) < 5:
            continue
        dnum = win[d, don].sum()
        dden0 = sum(info[q]["c0w"] for q in don)
        ddenU = sum(info[q]["c0w"] * info[q]["r"] for q in don)
        for j in part:
            if j not in info or not win[d, j] > 0:
                continue
            I = info[j]
            c0w, r = I["c0w"], I["r"]
            p5 = I["p"][:5]
            m5 = win[p5, j]; p5 = [k for k, v in zip(p5, m5) if v >= 0.25 * m5.mean()]
            p4 = sorted(p5, key=lambda k: -win[k, j])[:4]
            pc = Xs[p4][:, :, j].mean(0)
            mADJ = Xs[d, ADJ, j].mean()
            pjm0 = pc[WIN].sum(); pjmA = pjm0 + 4 * (mADJ - pc[ADJ].mean())
            # SCM-pre: donors complete on the 20 training days
            tr = [k for k in range(d - 1, max(d - 90, -1), -1) if wk[k] and k not in evset and complete[k, j]][:20]
            dd = [q for q in don if complete[tr, q].all()] if len(tr) >= 10 else []
            scmpre = np.nan
            if len(dd) >= 5:
                A = np.vstack([Xs[tr][:, :, dd].reshape(-1, len(dd)), Xs[d, :10, :][:, dd]])
                y = np.concatenate([Xs[tr][:, :, j].reshape(-1), Xs[d, :10, j]])
                sc = np.nanmax(A, 0); sc[sc <= 0] = 1
                w, _ = nnls(A / sc, y, maxiter=3000)
                scmpre = (Xs[d][:, dd] @ (w / sc))[WIN].sum()
            rows.append(dict(site=s, b=cols[bi[j]], use=elig.primaryspaceusage[cols[bi[j]]], day=str(days[d].date()),
                             L=win[d, j], c0w=c0w, r=r, pjm0=pjm0, pjmA_extra=mADJ, pc_adj=pc[ADJ].mean(),
                             caisoU=c0w * r, caisoA=c0w * min(max(r, .8), 1.2), pjmA=pjmA,
                             cgnaive=c0w * dnum / dden0, cgadj=c0w * r * dnum / ddenU, scmpre=scmpre, ndon=len(don)))
df = pd.DataFrame(rows).dropna(subset=["scmpre"])
df.to_csv(os.path.join(OUT, "pilot2016c_v0_events.csv"), index=False)
meth = ["caisoU", "caisoA", "pjmA", "cgnaive", "cgadj", "scmpre"]
res = {"n_events": len(df), "n_b": int(df.b.nunique()), "sites": sorted(df.site.unique().tolist())}

def errs(df, p):
    """relative error of each method when target pre-cools by p in hours 10..13 (adjustment hours 10..12 hit)."""
    out = {}
    L = df.L
    out["caisoU"] = df.c0w * df.r * (1 + p)
    out["caisoA"] = df.c0w * np.clip(df.r * (1 + p), .8, 1.2)
    out["pjmA"] = df.pjm0 + 4 * (df.pjmA_extra * (1 + p) - df.pc_adj)
    out["cgnaive"] = df.cgnaive
    out["cgadj"] = df.cgadj * (1 + p)
    out["scmpre"] = df.scmpre
    return {m: (out[m] - L) / L for m in meth}

res["precool"] = {}
for p in [0, 0.025, 0.05, 0.10, 0.20]:
    e = pd.DataFrame(errs(df, p)); e["b"] = df.b.values
    bl = e.groupby("b")[meth].agg(lambda x: np.mean(np.abs(x)))
    res["precool"][str(p)] = {"median_relMAE": bl.median().round(4).to_dict(),
                              "median_bias": e.groupby("b")[meth].mean().median().round(4).to_dict(),
                              "payment_err_ratio_c10_median": (bl.median() / 0.10).round(3).to_dict()}
e0 = pd.DataFrame(errs(df, 0)); e0[["site", "day", "b"]] = df[["site", "day", "b"]].values
res["shared_share"] = {}
for m in meth:
    x = e0[np.abs(e0[m]) < 1]
    res["shared_share"][m] = round(float(x.groupby(["site", "day"])[m].transform("mean").var() / x[m].var()), 3)
# portfolios
port = {}
for n in [1, 2, 5, 10, 20]:
    acc = {m: [] for m in meth}
    for (s, dday), g in df.groupby(["site", "day"]):
        if len(g) < n:
            continue
        for rep in range(20):
            idx = rng.choice(len(g), n, replace=False)
            gg = g.iloc[idx]
            Ls = gg.L.sum()
            for m in meth:
                acc[m].append(abs(gg[m].sum() - Ls) / Ls)
    port[n] = {m: round(float(np.median(v)), 4) for m, v in acc.items()}
res["portfolio_median_abs_rel_err"] = port
# per-building winner table by use (no pre-cooling)
bl0 = e0.groupby("b")[meth].agg(lambda x: np.mean(np.abs(x)))
use = df.groupby("b").use.first()
res["winner_share_by_use"] = pd.crosstab(use, bl0.idxmin(axis=1), normalize="index").round(2).to_dict()
res["winner_share_all"] = bl0.idxmin(axis=1).value_counts(normalize=True).round(3).to_dict()
json.dump(res, open(os.path.join(OUT, "pilot2016c_v0_summary.json"), "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
