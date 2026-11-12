"""PREREG numbers from the DEVELOPMENT YEAR 2016 ONLY (no 2017 load is read; the eligibility list uses the A3
meter audit flag `usable`, which was computed earlier from coverage counts of both years).
Outputs (results/prereg2016/): flatline.json, dst_table.csv, events_R1.csv, events_R3.csv, scm_grid.json,
summary.json. Run: python -I prereg_2016.py   (from src/design)
Conventions: window = clock 14:00-18:00 = hour-beginning 14..17 (s=14, e=18); hours are CLOCK hours after the DST
table is applied. All tags _v0 (development; not paper results).
"""
import json, os, site, sys, time
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd
from scipy.optimize import nnls

T0 = time.time()
ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw", "bdg2")
OUT = os.path.join(ROOT, "results", "prereg2016")
os.makedirs(OUT, exist_ok=True)
SEED = 20161
rng = np.random.default_rng(SEED)
SITES = ["Bear", "Bobcat", "Bull", "Cockatoo", "Eagle", "Fox", "Gator", "Hog", "Lamb", "Moose", "Peacock", "Rat", "Robin", "Wolf"]
aud = pd.read_csv(os.path.join(ROOT, "results", "data_audit", "bdg2_meter_audit.csv"))
aud = aud[aud.usable & aud.site_id.isin(SITES) & ~aud.all_zero_meter].set_index("meter_id")
cols = aud.index.tolist()
chunks = []
for ch in pd.read_csv(os.path.join(RAW, "electricity_cleaned.csv"), chunksize=1500, index_col=0, parse_dates=True,
                      usecols=lambda c: c == "timestamp" or c in set(cols)):
    ch = ch.loc[ch.index.year == 2016]
    if len(ch):
        chunks.append(ch.astype(np.float32))
E = pd.concat(chunks)[cols]; del chunks
assert E.index.min() >= pd.Timestamp("2016-01-01") and E.index.max() < pd.Timestamp("2017-01-01")
days = pd.date_range("2016-01-01", "2016-12-31", freq="D")
ND = len(days)
X0 = E.values.astype(np.float64)  # hour, building (stamps)
del E
W = pd.read_csv(os.path.join(RAW, "weather.csv"), usecols=["timestamp", "site_id", "airTemperature"], parse_dates=["timestamp"])
W = W[W.timestamp.dt.year == 2016]; W["date"] = W.timestamp.dt.normalize()
tmax = W.groupby(["site_id", "date"]).airTemperature.max().unstack(0).reindex(days)
HOL = {"US": ["2016-01-01", "2016-01-18", "2016-02-15", "2016-05-30", "2016-07-04", "2016-09-05", "2016-10-10", "2016-11-11", "2016-11-24", "2016-12-26"],
       "UK": ["2016-01-01", "2016-03-25", "2016-03-28", "2016-05-02", "2016-05-30", "2016-08-29", "2016-12-26", "2016-12-27"],
       "IE": ["2016-01-01", "2016-03-17", "2016-03-28", "2016-05-02", "2016-06-06", "2016-08-01", "2016-10-31", "2016-12-26", "2016-12-27"]}
DSTD = {"US": ("2016-03-13", "2016-11-06"), "UK": ("2016-03-27", "2016-10-30"), "IE": ("2016-03-27", "2016-10-30")}
ctry = lambda tz: "UK" if tz == "Europe/London" else ("IE" if tz == "Europe/Dublin" else "US")
season = (days >= "2016-05-15") & (days <= "2016-09-30")
summ = {"n_buildings_loaded": len(cols)}

# ---------------- 1. DST table (2016 transitions, per building ramp shift) ----------------
def ramp_hour(P):
    """P: days x 24 x b -> ramp hour per building (first crossing of (min+max)/2 after 03:00)."""
    prof = np.nanmean(P, 0)  # 24 x b
    out = np.full(prof.shape[1], np.nan)
    for j in range(prof.shape[1]):
        p = prof[:, j]
        if np.isnan(p).any() or p.max() - p.min() <= 0:
            continue
        mid = (p.min() + p.max()) / 2
        ks = np.where(p[3:] > mid)[0]
        if len(ks) == 0:
            continue
        k = ks[0] + 3
        out[j] = k - 1 + (mid - p[k - 1]) / (p[k] - p[k - 1])
    return out
Xd_stamp = X0.reshape(ND, 24, -1)
dst_rows = []
for s in SITES:
    bi = [cols.index(b) for b in aud.index[aud.site_id == s]]
    if not bi:
        continue
    c = ctry(aud.timezone[aud.site_id == s].iloc[0])
    hol = set(pd.to_datetime(HOL[c]))
    row = {"site": s, "country": c, "n_b": len(bi)}
    for name, t0 in zip(["spring", "autumn"], DSTD[c]):
        t0 = pd.Timestamp(t0)
        bef = [i for i, d in enumerate(days) if t0 - pd.Timedelta(days=14) <= d < t0 and d.dayofweek < 5 and d not in hol]
        aft = [i for i, d in enumerate(days) if t0 <= d < t0 + pd.Timedelta(days=14) and d.dayofweek < 5 and d not in hol]
        sh = ramp_hour(Xd_stamp[aft][:, :, bi]) - ramp_hour(Xd_stamp[bef][:, :, bi])
        sh = sh[~np.isnan(sh)]
        row[name + "_median_shift_h"] = round(float(np.median(sh)), 2) if len(sh) else np.nan
        row[name + "_share_lt_m05"] = round(float((sh < -0.5).mean()), 3) if len(sh) else np.nan
        row[name + "_share_gt_p05"] = round(float((sh > 0.5).mean()), 3) if len(sh) else np.nan
        row[name + "_n"] = int(len(sh))
    sp, au = row["spring_median_shift_h"], row["autumn_median_shift_h"]
    if sp <= -0.5 and au >= 0.5:
        row["convention"] = "STD"   # stamps stay on standard time; clock hour = stamp + 1 during DST
    elif abs(sp) < 0.3 and abs(au) < 0.3:
        row["convention"] = "CLOCK"
    else:
        row["convention"] = "AMBIGUOUS"  # treated as CLOCK, flagged
    dst_rows.append(row)
dst = pd.DataFrame(dst_rows)
dst.to_csv(os.path.join(OUT, "dst_table.csv"), index=False)
print(dst.to_string()); sys.stdout.flush()

# apply: for STD sites shift stamps +1 h inside the DST period (clock[t] = stamp[t-1])
ts = pd.date_range("2016-01-01", periods=ND * 24, freq="h")
X = X0.copy(); del X0
for _, r in dst.iterrows():
    if r.convention != "STD":
        continue
    a, b_ = DSTD[r.country]
    inside = (ts >= pd.Timestamp(a) + pd.Timedelta(hours=2)) & (ts < pd.Timestamp(b_) + pd.Timedelta(hours=2))
    bi = [cols.index(b) for b in aud.index[aud.site_id == r.site]]
    idx = np.where(inside)[0]
    X[np.ix_(idx, bi)] = X[np.ix_(idx - 1, bi)]
X = X.reshape(ND, 24, -1)

# ---------------- 2. Flatline thresholds ----------------
def flat_mask(Xs, hours, r):
    dz = (np.diff(Xs[:, hours, :], axis=1) == 0)
    flat = np.zeros((Xs.shape[0], Xs.shape[2]), bool); cur = np.zeros_like(flat, int)
    for h in range(dz.shape[1]):
        cur = np.where(dz[:, h, :], cur + 1, 0); flat |= cur >= r - 1
    return flat
FH = list(range(10, 20))  # [s-4, e+2)
flat_tab = {}
flat_share_meter = {}
for s in SITES:
    bi = [cols.index(b) for b in aud.index[aud.site_id == s]]
    if not bi:
        continue
    c = ctry(aud.timezone[aud.site_id == s].iloc[0]); hol = set(pd.to_datetime(HOL[c]))
    wk = np.array([(d.dayofweek < 5) and (d not in hol) for d in days])
    m = wk & season
    Xs = X[:, :, bi]
    flat_tab[s] = {}
    for r in [3, 4, 5, 6]:
        f = flat_mask(Xs, FH, r)
        flat_tab[s]["r%d" % r] = round(float(f[m].mean()), 4)
        if r == 4:
            for k, b in enumerate(bi):
                flat_share_meter[cols[b]] = float(f[m, k].mean())
fsm = pd.Series(flat_share_meter)
summ["flat_by_site_share_building_days"] = flat_tab
summ["flat_meter_share_r4_quantiles"] = fsm.quantile([.5, .75, .9, .95, .99]).round(4).to_dict()
summ["flat_meter_share_r4_bins"] = pd.cut(fsm, [-0.001, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]).value_counts().sort_index().astype(int).rename(index=str).to_dict()
summ["flat_meters_excluded_gt20pct_by_site"] = fsm[fsm > 0.2].groupby(aud.site_id).size().to_dict()
json.dump({"by_site": flat_tab, "meter_share_r4": fsm.round(4).to_dict()}, open(os.path.join(OUT, "flatline.json"), "w"), indent=0)
print(json.dumps(summ, indent=1, default=str)); sys.stdout.flush()

# ---------------- 3. Methods on R1 and R3 (2016) ----------------
WIN = [14, 15, 16, 17]
H_PJM = [10, 11, 12]; H_CAISO = [10, 11, 12]; H_NY = [10, 11]; H_DM = [10, 11]; H_ISONE = [11, 12]
PRE_DONOR = list(range(0, 10))  # target event-day hours usable by I-donor methods: < s-4
LAM = [0.01, 0.1, 0.3, 1.0, 3.0, 10.0, 100.0]; WIND = [2, 3, 5, 7, 10, 20, 40]
keepb = fsm[fsm <= 0.2].index

def ridge_s1(Xm, y, lam):
    A = Xm.T @ Xm + lam * np.eye(Xm.shape[1])
    Ai = np.linalg.solve(A, np.c_[Xm.T @ y, np.ones(Xm.shape[1])])
    a, b = Ai[:, 0], Ai[:, 1]
    return a - b * (a.sum() - 1) / b.sum()

def classic(Xm, y):
    M = 1000.0
    w, _ = nnls(np.vstack([Xm, M * np.ones(Xm.shape[1])]), np.r_[y, M], maxiter=5000)
    return w

def run_rule(evset, ev_score, s, bi, wk, complete, Xs, win, part, dpool, tm, pre=None, curt=None, do_scm=True, scm_cfg=None):
    """Return list of dict rows. pre: dict p -> multiplier on hours; handled outside via recompute."""
    rows = []
    for d in sorted(ev_score):
        def past(j, n, maxback, excl_daybefore=False, allow_events=False):
            out = []
            for k in range(d - 1, max(d - maxback - 1, -1), -1):
                if not wk[k] or not complete[k, j]:
                    continue
                if (k in evset) and not allow_events:
                    continue
                if excl_daybefore and (k + 1) in evset:
                    continue
                out.append(k)
                if n and len(out) == n:
                    break
            return out
        L_obs = lambda j: (Xs[d, :, j] if curt is None else Xs[d, :, j] * curt)
        base = {}
        for j in list(part) + list(dpool):
            if not complete[d, j]:
                continue
            p45 = past(j, 0, 45)
            r = {}
            # PJM high 4 of 5 (fallback: <4 -> add highest-window-load event days within 45 days)
            p5 = p45[:5]
            if len(p5) < 4:
                evd = [k for k in range(max(d - 45, 0), d) if k in evset and wk[k] and complete[k, j]]
                evd = sorted(evd, key=lambda k: -Lc[k, j])[: 4 - len(p5)]
                p5 = p5 + evd
            if len(p5) >= 4:
                m5 = np.array([Lc[k, j] for k in p5])
                p5k = [k for k, v in zip(p5, m5) if v >= 0.25 * m5.mean()]
                p4 = sorted(p5k, key=lambda k: -Lc[k, j])[:4]
                pc = Ys[p4][:, :, j].mean(0)
                r["pjm0_prof"] = pc
                r["pjm_age"] = float(np.mean([d - k for k in p4]))   # D13 diagnostic: mean lookback age (days)
            r["pjm_fb"] = int(len(p45[:5]) < 4)
            # CAISO 10-in-10 (min 5; fallback: highest-DR-hour-load excluded days in 45 days)
            c10 = p45[:10]
            r["caiso_fb"] = int(len(c10) < 5); r["caiso_n"] = len(c10)
            if len(c10) < 5:
                evd = [k for k in range(max(d - 45, 0), d) if k in evset and wk[k] and complete[k, j]]
                c10 = c10 + sorted(evd, key=lambda k: -Lc[k, j])[: 5 - len(c10)]
            if len(c10) >= 5:
                r["caiso0_prof"] = Ys[c10][:, :, j].mean(0)
            # NYISO 5 of 10 in 30 days, day-before exclusion, 25 % seed
            p30 = past(j, 0, 30, excl_daybefore=True)
            if len(p30) >= 5:
                P = np.nanmax(Ys[max(d - 30, 0):d, WIN, j])
                p30 = [k for k in p30 if Ys[k, WIN, j].mean() >= 0.25 * P][:10]
                if len(p30) >= 5:
                    r["ny0_prof"] = Ys[sorted(p30, key=lambda k: -Lc[k, j])[:5]][:, :, j].mean(0)
            # ISO-NE 10 most recent of previous 30 weekdays (hourly approx; no fallback)
            wd30 = [k for k in range(d - 1, -1, -1) if wk[k]][:30]
            ine = [k for k in wd30 if k not in evset and complete[k, j]][:10]
            if len(ine) >= 5:
                r["isone0_prof"] = Ys[ine][:, :, j].mean(0)
            # Granderson DM: 10 working days immediately before (non-event), plain mean
            dm = past(j, 10, 90)
            if len(dm) == 10:
                r["dm0_prof"] = Ys[dm][:, :, j].mean(0)
            # Granderson WM: 4 of the prior 90 days with closest Tmax (non-event working days)
            p90 = [k for k in past(j, 0, 90) if not np.isnan(tm[k])]
            if len(p90) >= 4 and not np.isnan(tm[d]):
                wm = sorted(p90, key=lambda k: (abs(tm[k] - tm[d]), d - k))[:4]
                r["wm0_prof"] = Ys[wm][:, :, j].mean(0)
            # Mathieu 3 of 10 (highest daily energy of the last 10 business days)
            b10 = p45[:10]
            if len(b10) >= 10:
                r["m3_prof"] = Ys[sorted(b10, key=lambda k: -np.nansum(Ys[k, :, j]))[:3]][:, :, j].mean(0)
            # ERCOT-style middle 8 of 10 (drop highest and lowest window mean), unadjusted
            if len(b10) >= 10:
                srt = sorted(b10, key=lambda k: Lc[k, j])[1:9]
                r["mid8_prof"] = Ys[srt][:, :, j].mean(0)
            # previous eligible weekday
            if p45:
                r["prev_prof"] = Ys[p45[0], :, j]
            base[j] = r
        rows_d = []
        for j in list(part) + list(dpool):
            if j not in base:
                continue
            rows_d.append((j, base[j]))
        base_d = dict(rows_d)
        for j in part:
            if j not in base_d or "pjm0_prof" not in base_d[j]:
                continue
            Ltrue = Ys[d, WIN, j].sum()
            if not Ltrue > 0:
                continue
            rec = dict(site=s, b=cols[bi[j]], use=aud.primaryspaceusage[cols[bi[j]]], day=str(days[d].date()), L=Ltrue,
                       morning=Ys[d, 8:14, j].tolist(), Lobs_win=float((L_obs(j))[WIN].sum()))
            for k_, v in base_d[j].items():
                if not k_.endswith("_prof"):
                    rec[k_] = v
                    continue
                rec[k_.replace("_prof", "")] = v[WIN].sum()
                rec[k_.replace("_prof", "") + "_m"] = v[8:14].tolist()
            # donors (other fold) for CG: PJM-based
            don = [q for q in dpool if q in base_d and "pjm0_prof" in base_d[q] and Ys[d, WIN, q].sum() > 0]
            rec["ndon"] = len(don)
            if len(don) >= 5:
                rec["don_L"] = float(sum(Ys[d, WIN, q].sum() for q in don))
                rec["don_pjm0"] = float(sum(base_d[q]["pjm0_prof"][WIN].sum() for q in don))
                rec["don_pjmA"] = float(sum(base_d[q]["pjm0_prof"][WIN].sum() + 4 * (Ys[d, H_PJM, q].mean() - base_d[q]["pjm0_prof"][H_PJM].mean()) for q in don))
                if do_scm:
                    for Wn in (WIND if scm_cfg is None else [scm_cfg["W"]]):
                        tr = past(j, Wn, 120)
                        if len(tr) < max(2, Wn // 2):
                            continue
                        rec["scm_age_W%d" % Wn] = float(np.mean([d - k for k in tr]))   # D13 diagnostic
                        dd = [q for q in don if complete[tr, q].all() and complete[d, q]]
                        if len(dd) < 5:
                            continue
                        Xm = np.vstack([Ys[tr][:, :, dd].reshape(-1, len(dd)), Ys[d, PRE_DONOR, :][:, dd]])
                        y = np.r_[Ys[tr][:, :, j].reshape(-1), Ys[d, PRE_DONOR, j]]
                        mx = Xm.mean(0); my = y.mean()
                        if (mx <= 0).any() or my <= 0:
                            continue
                        Xn, yn = Xm / mx, y / my
                        Xw = (Ys[d][:, dd] / mx)[WIN]
                        for lam in (LAM if scm_cfg is None else [scm_cfg["lam"]]):
                            w = ridge_s1(Xn, yn, lam)
                            rec["scmr_W%d_l%g" % (Wn, lam)] = float((Xw @ w).sum() * my)
                        w = classic(Xn, yn)
                        rec["scmc_W%d" % Wn] = float((Xw @ w).sum() * my)
            rows.append(rec)
    return rows

all_rows = {"R1": [], "R3": []}
# Revision 2: frozen event dates and folds (results/frozen, made by freeze_inputs.py without load data)
EVF = pd.read_csv(os.path.join(ROOT, "results", "frozen", "event_dates.csv"), parse_dates=["date"])
EVF = EVF[EVF.year == 2016]
FOLD = pd.read_csv(os.path.join(ROOT, "results", "frozen", "folds.csv")).set_index("meter_id").fold
didx = {d: i for i, d in enumerate(days)}
fold_seed = {}
for s in SITES:
    bi_all = [cols.index(b) for b in aud.index[aud.site_id == s] if b in keepb]
    if len(bi_all) < 12 or s not in tmax.columns:
        summ.setdefault("sites_dropped_lt12_after_flat", []).append(s)
        continue
    c = ctry(aud.timezone[aud.site_id == s].iloc[0]); hol = set(pd.to_datetime(HOL[c]))
    wk = np.array([(d.dayofweek < 5) and (d not in hol) for d in days])
    Ys = X[:, :, bi_all]
    complete = ~np.isnan(Ys).any(1) & ~flat_mask(Ys, FH, 4)
    Lc = np.where(complete, Ys[:, WIN, :].sum(1), np.nan)
    tm = tmax[s].values
    cand = np.where(wk & season & ~np.isnan(tm))[0]
    fl = np.array([FOLD[cols[b]] for b in bi_all])
    A_, B_ = np.where(fl == "A")[0], np.where(fl == "B")[0]
    e_s = EVF[EVF.site_id == s]
    worlds = [("R1", 0)] + [("R3", k) for k in range(1, 6)]
    for rule, draw in worlds:
        sel = e_s[(e_s.rule == rule) & (e_s.draw == draw) & e_s.primary]
        ev = np.array(sorted(didx[d] for d in sel.date))
        assert len(ev) == 10
        evset = set(ev.tolist())
        bi = bi_all
        for part, dpool in [(A_, B_), (B_, A_)]:
            rr = run_rule(evset, ev, s, bi, wk, complete, Ys, None, part, dpool, tm, do_scm=(rule == "R1"))
            for r_ in rr:
                r_["draw"] = draw
            all_rows[rule] += rr
    print(s, "done", round(time.time() - T0), "s"); sys.stdout.flush()

for rule in all_rows:
    pd.DataFrame(all_rows[rule]).to_pickle(  # self-written intermediate, read only by prereg_2016_analyse.py
        os.path.join(OUT, "events_%s.pkl" % rule))
print("events saved", {k: len(v) for k, v in all_rows.items()}, round(time.time() - T0), "s")
json.dump(summ, open(os.path.join(OUT, "summary_part1.json"), "w"), indent=1, default=str)
