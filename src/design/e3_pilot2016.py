"""E3 design pilot, DEVELOPMENT YEAR 2016 ONLY (pilot, _v0; not a result for the paper).
Purpose: size the effects for the design (MDE), check the circularity of event rules, check the within-site
shared error component that a comparison-group (CG) baseline exploits, and the timestamp convention.
Run: python -I e3_pilot2016.py   Writes results/e3_profile/pilot2016_v0_*.csv/json.
Simplifications (pilot only): US/UK/IE public holidays hard-coded for May-Sep 2016; buildings with a missing hour in
the window or adjustment hours on a candidate day treat that day as ineligible; no fallback to event days.
Event window hours (local, hour-beginning) 14,15,16,17. Adjustment hours 10,11,12 (s-4..s-2).
"""
import json, os, site, sys
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd

ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw", "bdg2")
OUT = os.path.join(ROOT, "results", "e3_profile")
rng = np.random.default_rng(20161111)
cov = pd.read_csv(os.path.join(OUT, "building_coverage.csv"), index_col=0)
elig = cov[(cov.year16_cov >= 0.9) & (cov.zero16 < 0.05)]
cols = elig.index.tolist()
chunks = []
for ch in pd.read_csv(os.path.join(RAW, "electricity_cleaned.csv"), chunksize=2000, index_col=0, parse_dates=True,
                      usecols=lambda c: c == "timestamp" or c in set(cols)):
    chunks.append(ch.astype(np.float32))
E = pd.concat(chunks).loc["2016"]; del chunks
E = E[cols]
days = pd.date_range("2016-01-01", "2016-12-31", freq="D")
X = E.values.reshape(len(days), 24, len(cols))  # day, hour, building
W = pd.read_csv(os.path.join(RAW, "weather.csv"), usecols=["timestamp", "site_id", "airTemperature"], parse_dates=["timestamp"])
W = W[W.timestamp.dt.year == 2016]
W["date"] = W.timestamp.dt.normalize()
tmax = W.groupby(["site_id", "date"]).airTemperature.max().unstack(0).reindex(days)

HOL = {"US": ["2016-01-01", "2016-01-18", "2016-02-15", "2016-05-30", "2016-07-04", "2016-09-05", "2016-10-10",
              "2016-11-11", "2016-11-24", "2016-12-26"],
       "UK": ["2016-01-01", "2016-03-25", "2016-03-28", "2016-05-02", "2016-05-30", "2016-08-29", "2016-12-26", "2016-12-27"],
       "IE": ["2016-01-01", "2016-03-17", "2016-03-28", "2016-05-02", "2016-06-06", "2016-08-01", "2016-10-31", "2016-12-26", "2016-12-27"]}
def country(tz):
    return "UK" if tz == "Europe/London" else ("IE" if tz == "Europe/Dublin" else "US")
WIN = [14, 15, 16, 17]; ADJ = [10, 11, 12]; ADJN = [10, 11]
season = (days >= "2016-05-15") & (days <= "2016-09-30")
rows = []
FLAT_STATS = []
# DST check: hour at which the mean weekday profile first exceeds its (min+max)/2, 2 weeks before vs after the
# spring transition (US 2016-03-13, UK/IE 2016-03-27). A shift of -1 h means stamps are standard time (no DST).
DST = {}
for s in elig.site_id.unique():
    bi_ = [cols.index(b) for b in elig.index[elig.site_id == s]]
    tz_ = elig.timezone[elig.site_id == s].iloc[0]
    t0 = pd.Timestamp("2016-03-27" if tz_.startswith("Europe") else "2016-03-13")
    def ramp(a, b_):
        idx = [i for i, d in enumerate(days) if a <= d < b_ and d.dayofweek < 5]
        prof = np.nanmean(np.nanmean(X[idx][:, :, bi_], 0) / np.nanmean(X[idx][:, :, bi_], (0, 1)), 1)
        mid = (prof.min() + prof.max()) / 2
        k = int(np.argmax(prof[3:] > mid)) + 3
        return k - 1 + (mid - prof[k - 1]) / (prof[k] - prof[k - 1])
    DST[s] = round(float(ramp(t0, t0 + pd.Timedelta(days=14)) - ramp(t0 - pd.Timedelta(days=14), t0)), 2)
site_list = elig.site_id.unique()
for s in site_list:
    bi = [cols.index(b) for b in elig.index[elig.site_id == s]]
    if len(bi) < 5 or s not in tmax.columns:
        continue
    tz = elig.timezone[elig.site_id == s].iloc[0]
    hol = set(pd.to_datetime(HOL[country(tz)]))
    wk = np.array([(d.dayofweek < 5) and (d not in hol) for d in days])
    Xs = X[:, :, bi]                                   # day, hour, b
    win = Xs[:, WIN, :].sum(1)                          # day, b
    complete = ~np.isnan(Xs[:, WIN + ADJ, :]).any(1)    # day, b
    # flatline filter: >= 3 consecutive zero first-differences (4 identical readings) within hours 10..17
    dz = (np.diff(Xs[:, 10:18, :], axis=1) == 0).astype(int)   # day, 7, b
    flat = np.zeros((Xs.shape[0], Xs.shape[2]), dtype=bool)
    cur = np.zeros_like(flat, dtype=int)
    for h in range(dz.shape[1]):
        cur = np.where(dz[:, h, :] == 1, cur + 1, 0)
        flat |= cur >= 3
    FLAT_STATS.append((s, int((flat & wk[:, None] & season[:, None]).sum()), int((wk[:, None] & season[:, None]).sum() * flat.shape[1])))
    complete &= ~flat
    site_load = np.nansum(win, 1)
    cand = np.where(wk & season & ~np.isnan(tmax[s].values))[0]
    R = {"R1": cand[np.argsort(-tmax[s].values[cand])][:10],
         "R3": rng.choice(cand, 10, replace=False)}
    # R2 per target: leave-one-out site load (computed on the fly below)
    for rule in ["R1", "R2", "R3"]:
        for j, b in enumerate(bi):
            if rule == "R2":
                loo = site_load[cand] - np.nan_to_num(win[cand, j])
                ev = cand[np.argsort(-loo)][:10]
            else:
                ev = R[rule]
            evset = set(ev.tolist())
            for d in sorted(ev):
                if not complete[d, j]:
                    continue
                L = win[d, j]
                if not L > 0:
                    continue
                def past(maxback, excl_daybefore=False):
                    out = []
                    for k in range(d - 1, max(d - maxback - 1, -1), -1):
                        if not wk[k] or k in evset or not complete[k, j]:
                            continue
                        if excl_daybefore and (k + 1) in evset:
                            continue
                        out.append(k)
                    return out
                p45 = past(45)
                if len(p45) < 5:
                    continue
                # CAISO 10-in-10
                c10 = p45[:10]
                cbl0 = Xs[c10][:, :, j].mean(0)
                r = Xs[d, ADJ, j].mean() / cbl0[ADJ].mean()
                rc = min(max(r, 0.8), 1.2)
                caiso0 = cbl0[WIN].sum(); caisoA = rc * caiso0; caisoU = r * caiso0
                # PJM high 4 of 5 + SAA (additive, uncapped)
                p5 = p45[:5]
                m5 = win[p5, j]
                p5 = [k for k, v in zip(p5, m5) if v >= 0.25 * m5.mean()]
                p4 = sorted(p5, key=lambda k: -win[k, j])[:4]
                pc = Xs[p4][:, :, j].mean(0)
                A = Xs[d, ADJ, j].mean() - pc[ADJ].mean()
                pjm0 = pc[WIN].sum(); pjmA = pjm0 + 4 * A
                # NYISO 5 of 10 in 30 days, day-before exclusion, seed 25% of 30-day max window-hour load
                p30 = past(30, excl_daybefore=True)
                if len(p30) >= 5:
                    P = np.nanmax(Xs[max(d - 30, 0):d, WIN, j])
                    p30 = [k for k in p30 if Xs[k, WIN, j].mean() >= 0.25 * P][:10]
                ny0 = nyA = np.nan
                if len(p30) >= 5:
                    p5n = sorted(p30, key=lambda k: -win[k, j])[:5]
                    nc = Xs[p5n][:, :, j].mean(0)
                    G = Xs[d, ADJN, j].mean() / nc[ADJN].mean()
                    ny0 = nc[WIN].sum(); nyA = min(max(G, 0.8), 1.2) * ny0
                # weather matching: OLS of window load on Tmax over up to 60 prior eligible weekdays (pilot TOWT proxy)
                p90 = past(120)[:60]
                tm = tmax[s].values
                ok = [k for k in p90 if not np.isnan(tm[k])]
                wreg = np.nan
                if len(ok) >= 20 and not np.isnan(tm[d]):
                    A_ = np.c_[np.ones(len(ok)), tm[ok]]
                    coef = np.linalg.lstsq(A_, win[ok, j], rcond=None)[0]
                    wreg = coef[0] + coef[1] * tm[d]
                # CG ratio: target CAISO-0 x (donor event-day window / donor CAISO-0), donors = same-site others,
                # donors' baseline days = target's c10 days (pilot simplification); donors need complete data
                don = [q for q in range(len(bi)) if q != j and complete[d, q] and complete[c10, q].all()]
                cg = np.nan
                if len(don) >= 5:
                    dnum = win[d, don].sum(); dden = win[c10][:, don].mean(0).sum()
                    cg = caiso0 * dnum / dden
                rows.append(dict(site=s, b=cols[b], use=elig.primaryspaceusage[cols[b]], rule=rule, day=str(days[d].date()),
                                 tmax=tm[d], L=L, caiso0=caiso0, caisoA=caisoA, caisoU=caisoU, pjm0=pjm0, pjmA=pjmA,
                                 ny0=ny0, nyA=nyA, wreg=wreg, cg=cg, ndon=len(don), r_unclipped=r))
df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, "pilot2016_v0_events.csv"), index=False)
meth = ["caiso0", "caisoA", "caisoU", "pjm0", "pjmA", "ny0", "nyA", "wreg", "cg"]
for mth in meth:
    df["re_" + mth] = (df[mth] - df.L) / df.L
res = {}
for rule in ["R1", "R2", "R3"]:
    d = df[df.rule == rule]
    bl = d.groupby("b")[["re_" + m for m in meth]].agg(["mean", lambda x: np.mean(np.abs(x))])
    out = {}
    for mth in meth:
        sb = bl[("re_" + mth, "mean")]; ab = bl[("re_" + mth, "<lambda_0>")]
        out[mth] = {"n_b": int(sb.notna().sum()), "median_bias": round(float(sb.median()), 4),
                    "median_relMAE": round(float(ab.median()), 4), "share_neg_bias": round(float((sb < 0).mean()), 3),
                    "pooled_bias": round(float(d["re_" + mth].median()), 4)}
    res[rule] = out
    res[rule]["n_events"] = int(len(d))
# shared site-day component of CAISO-0 errors (ICC within site-day), R1 and R3
for rule in ["R1", "R3"]:
    d = df[df.rule == rule].dropna(subset=["re_caiso0"])
    d = d[np.abs(d.re_caiso0) < 2]
    g = d.groupby(["site", "day"]).re_caiso0
    between = g.transform("mean").var(); total = d.re_caiso0.var()
    res[rule]["share_var_site_day_caiso0"] = round(float(between / total), 3)
# paired differences per building for MDE (R1): |caisoA| - |cg|
d = df[df.rule == "R1"].dropna(subset=["re_cg", "re_caisoA", "re_wreg"])
pb = d.groupby(["site", "b"]).apply(lambda x: pd.Series({
    "dA_cg": np.mean(np.abs(x.re_caisoA)) - np.mean(np.abs(x.re_cg)),
    "dA_w": np.mean(np.abs(x.re_caisoA)) - np.mean(np.abs(x.re_wreg)),
    "dpjm_cg": np.mean(np.abs(x.re_pjmA)) - np.mean(np.abs(x.re_cg))})).reset_index()
pb.to_csv(os.path.join(OUT, "pilot2016_v0_paired_R1.csv"), index=False)
for c in ["dA_cg", "dA_w", "dpjm_cg"]:
    sd = pb[c].std(); site_means = pb.groupby("site")[c].mean()
    res["R1"]["paired_" + c] = {"n_b": int(pb[c].notna().sum()), "median": round(float(pb[c].median()), 4),
                                 "mean": round(float(pb[c].mean()), 4), "sd": round(float(sd), 4),
                                 "share_positive": round(float((pb[c] > 0).mean()), 3),
                                 "site_means": site_means.round(4).to_dict()}
res["by_site_R1_median_relMAE"] = df[df.rule == "R1"].groupby("site")[["re_caisoA", "re_pjmA", "re_cg", "re_wreg"]].apply(
    lambda x: x.abs().median()).round(4).to_dict()
res["by_site_R1_median_bias"] = df[df.rule == "R1"].groupby("site")[["re_caiso0", "re_caisoA", "re_pjmA", "re_cg"]].median().round(4).to_dict()
res["clip_share_caisoA_R1"] = round(float(((df.rule == "R1") & ((df.r_unclipped > 1.2) | (df.r_unclipped < 0.8))).sum() / (df.rule == "R1").sum()), 3)
res["R1_R2_day_overlap_share"] = None
r1 = df[df.rule == "R1"][["b", "day"]].drop_duplicates(); r2 = df[df.rule == "R2"][["b", "day"]].drop_duplicates()
res["R1_R2_day_overlap_share"] = round(float(len(r1.merge(r2)) / max(len(r2), 1)), 3)
res["R1_event_month_counts"] = df[df.rule == "R1"].drop_duplicates(["site", "day"]).day.str[5:7].value_counts().sort_index().to_dict()
res["dst_ramp_shift_h_after_minus_before"] = DST
res["flat_share_summer_weekday_building_days"] = {s: round(a / max(b, 1), 3) for s, a, b in FLAT_STATS}
json.dump(res, open(os.path.join(OUT, "pilot2016_v0_summary.json"), "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
