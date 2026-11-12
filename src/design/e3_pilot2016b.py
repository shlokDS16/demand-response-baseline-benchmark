"""E3 design pilot b, DEVELOPMENT YEAR 2016 ONLY (_v0). R1 days only.
Adds stronger comparison-group (CG) variants to check whether any CG has headroom over day-of adjusted CBLs:
  cgadj : CAISO-unclipped-adjusted target CBL x (donor observed window / donor CAISO-unclipped-adjusted window)
  scm   : NNLS synthetic control on levels, fitted on the target's 20 most recent eligible weekdays (all 24 h) plus
          event-day hours 0..12 (pre-notification), predicting event-window load from donors' same-day load
  scmadj: scm with additive day-of correction on hours 10..12
Also: DST check at spring and autumn 2016 transitions (ramp hour shift), Office/Education only.
Run: python -I e3_pilot2016b.py
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
cov = pd.read_csv(os.path.join(OUT, "building_coverage.csv"), index_col=0)
elig = cov[(cov.year16_cov >= 0.9) & (cov.zero16 < 0.05)]
cols = elig.index.tolist()
chunks = []
for ch in pd.read_csv(os.path.join(RAW, "electricity_cleaned.csv"), chunksize=2000, index_col=0, parse_dates=True,
                      usecols=lambda c: c == "timestamp" or c in set(cols)):
    chunks.append(ch.astype(np.float32))
E = pd.concat(chunks).loc["2016"][cols]; del chunks
days = pd.date_range("2016-01-01", "2016-12-31", freq="D")
X = E.values.reshape(len(days), 24, len(cols)).astype(np.float64)
W = pd.read_csv(os.path.join(RAW, "weather.csv"), usecols=["timestamp", "site_id", "airTemperature"], parse_dates=["timestamp"])
W = W[W.timestamp.dt.year == 2016]; W["date"] = W.timestamp.dt.normalize()
tmax = W.groupby(["site_id", "date"]).airTemperature.max().unstack(0).reindex(days)
HOL = {"US": ["2016-01-01", "2016-01-18", "2016-02-15", "2016-05-30", "2016-07-04", "2016-09-05", "2016-10-10", "2016-11-11", "2016-11-24", "2016-12-26"],
       "UK": ["2016-01-01", "2016-03-25", "2016-03-28", "2016-05-02", "2016-05-30", "2016-08-29", "2016-12-26", "2016-12-27"],
       "IE": ["2016-01-01", "2016-03-17", "2016-03-28", "2016-05-02", "2016-06-06", "2016-08-01", "2016-10-31", "2016-12-26", "2016-12-27"]}
ctry = lambda tz: "UK" if tz == "Europe/London" else ("IE" if tz == "Europe/Dublin" else "US")
WIN = [14, 15, 16, 17]; ADJ = [10, 11, 12]
season = (days >= "2016-05-15") & (days <= "2016-09-30")
res = {"dst": {}}
rows = []
for s in elig.site_id.unique():
    bi = [cols.index(b) for b in elig.index[elig.site_id == s]]
    tz = elig.timezone[elig.site_id == s].iloc[0]
    # DST ramp check (office + education)
    bo = [cols.index(b) for b in elig.index[(elig.site_id == s) & elig.primaryspaceusage.isin(["Office", "Education"])]]
    if len(bo) >= 3:
        def ramp(a, b_):
            idx = [i for i, d in enumerate(days) if a <= d < b_ and d.dayofweek < 5]
            P = X[idx][:, :, bo]
            prof = np.nanmean(np.nanmean(P, 0) / np.nanmean(P, (0, 1)), 1)
            mid = (prof.min() + prof.max()) / 2
            k = int(np.argmax(prof[3:] > mid)) + 3
            return k - 1 + (mid - prof[k - 1]) / (prof[k] - prof[k - 1])
        out = {}
        for name, t0 in ([("spring", "2016-03-27"), ("autumn", "2016-10-30")] if tz.startswith("Europe") else [("spring", "2016-03-13"), ("autumn", "2016-11-06")]):
            t0 = pd.Timestamp(t0)
            out[name] = round(float(ramp(t0, t0 + pd.Timedelta(days=7)) - ramp(t0 - pd.Timedelta(days=7), t0)), 2)
        res["dst"][s] = out
    if len(bi) < 6 or s not in tmax.columns:
        continue
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
    # meter-level flat exclusion: > 20 % of season weekdays flat -> not a target and not a donor
    fshare = (flat & (wk & season)[:, None]).sum(0) / (wk & season).sum()
    keep = fshare <= 0.2
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
        P10 = {j: past(j, 10) for j in range(len(bi)) if keep[j] and complete[d, j]}
        caU = {}
        for j, p in P10.items():
            if len(p) >= 5:
                c0 = Xs[p][:, :, j].mean(0)
                caU[j] = (c0[WIN].sum() * Xs[d, ADJ, j].mean() / c0[ADJ].mean(), c0)
        for j in caU:
            L = win[d, j]
            if not L > 0:
                continue
            don = [q for q in caU if q != j]
            if len(don) < 5:
                continue
            bU = caU[j][0]
            cgadj = bU * win[d, don].sum() / sum(caU[q][0] for q in don)
            # SCM on levels: training rows = 20 recent days where target and all donors complete, 24 h each,
            # plus event-day hours 0..12
            pd20 = [k for k in range(d - 1, max(d - 90, -1), -1) if wk[k] and k not in evset and complete[k, j]
                    and complete[k, don].all()][:20]
            scm = scmadj = np.nan
            if len(pd20) >= 10:
                A = np.vstack([Xs[pd20][:, :, don].reshape(-1, len(don)), Xs[d, :13, :][:, don]])
                y = np.concatenate([Xs[pd20][:, :, j].reshape(-1), Xs[d, :13, j]])
                sc = np.nanmax(A, 0); sc[sc <= 0] = 1
                w, _ = nnls(A / sc, y, maxiter=2000)
                w = w / sc
                pred = Xs[d][:, don] @ w
                scm = pred[WIN].sum()
                scmadj = scm + len(WIN) * (Xs[d, ADJ, j].mean() - pred[ADJ].mean())
            rows.append(dict(site=s, b=cols[bi[j]], use=elig.primaryspaceusage[cols[bi[j]]], day=str(days[d].date()),
                             L=L, caisoU=bU, cgadj=cgadj, scm=scm, scmadj=scmadj, ndon=len(don)))
df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, "pilot2016b_v0_events.csv"), index=False)
meth = ["caisoU", "cgadj", "scm", "scmadj"]
for m in meth:
    df["re_" + m] = (df[m] - df.L) / df.L
d = df.dropna(subset=["re_" + m for m in meth])
bl = d.groupby("b")[["re_" + m for m in meth]].agg(lambda x: np.mean(np.abs(x)))
bb = d.groupby("b")[["re_" + m for m in meth]].mean()
res["n_events"] = len(d); res["n_b"] = int(bl.shape[0])
res["median_relMAE"] = bl.median().round(4).to_dict()
res["median_bias"] = bb.median().round(4).to_dict()
for m in meth[1:]:
    diff = bl["re_caisoU"] - bl["re_" + m]
    res["paired_caisoU_minus_" + m] = {"median": round(float(diff.median()), 4), "sd": round(float(diff.std()), 4),
                                       "share_improved": round(float((diff > 0).mean()), 3)}
site_of = d.groupby("b").site.first()
res["by_site_median_relMAE"] = bl.groupby(site_of).median().round(4).to_dict()
# pooled kWh-weighted relative abs error per site-day portfolio (all eligible buildings of the site)
port = d.groupby(["site", "day"])[["L"] + meth].sum()
res["site_portfolio_median_abs_rel_err"] = {m: round(float(((port[m] - port.L).abs() / port.L).median()), 4) for m in meth}
json.dump(res, open(os.path.join(OUT, "pilot2016b_v0_summary.json"), "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
