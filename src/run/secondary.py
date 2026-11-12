"""Secondary / exploratory analyses (outside the confirmatory family; never carry p_holm): R2-LOO, 16:00-20:00 window,
rebound, donor contamination, heat-wave dispatch, heterogeneous p, c = 0.05 / 0.20, TOWT, LightGBM (fixed parameters,
HPO not run), alternative DST mapping. NOT implemented here (declared in the report): MLP, gscm, H6 portfolio, screening
tree, ablations."""
import json
import os
import time

import numpy as np
import pandas as pd

from . import adjust, analysis as AN, baselines as BL, data as D, events as EV, inject as IJ, stats as ST
from . import config as C
from . import leakage as LK

TOWT_BINS = 6


# ---------------- TOWT (Mathieu 2011 as in PREREG s3) ----------------
def _towt_design(hw, T, occ, edges):
    """hw: hour-of-week index (0..119); T: temperature; occ: bool occupied hour-of-week mask (120)."""
    n = len(hw)
    X = np.zeros((n, 120 + TOWT_BINS + 1))
    X[np.arange(n), hw] = 1.0
    o = occ[hw]
    for i in range(TOWT_BINS):
        X[:, 120 + i] = np.clip(T - edges[i], 0, edges[i + 1] - edges[i]) * o
    X[:, 120 + TOWT_BINS] = T * (~o)
    return X


def towt_predict(site, Tmat, j, d, evset, recent=None, span=70):
    """Prediction (24 hours) for building j on day d from eligible non-event weekdays: those within `span` calendar days
    before d, or the `recent` most recent eligible weekdays (towt7)."""
    ks = [k for k in range(d - 1, max(d - span - 1, -1), -1) if site.wk[k] and site.complete[k, j] and k not in evset]
    if recent:
        ks = [k for k in range(d - 1, -1, -1) if site.wk[k] and site.complete[k, j] and k not in evset][:recent]
    LK.a1_lookback_before(d, ks)
    LK.a2_no_event_days(evset, ks)
    if len(ks) < 5:
        return None
    ks = np.array(ks)
    dow = np.array([site.days[k].dayofweek for k in ks])
    hw = (dow[:, None] * 24 + np.arange(24)[None, :]).reshape(-1)
    y = site.Ys[ks][:, :, j].reshape(-1)
    T = Tmat[ks].reshape(-1)
    prof = np.array([y[hw == q].mean() if (hw == q).any() else np.nan for q in range(120)])
    p10, p90 = np.nanpercentile(prof, 10), np.nanpercentile(prof, 90)
    occ = np.nan_to_num(prof, nan=0.0) > (p10 + p90) / 2
    edges = np.linspace(T.min(), T.max() + 1e-9, TOWT_BINS + 1)
    X = _towt_design(hw, T, occ, edges)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    hwd = site.days[d].dayofweek * 24 + np.arange(24)
    Xd = _towt_design(hwd, Tmat[d], occ, edges)
    return Xd @ beta


def run_towt(site, Tmat, evset, ev_score, part):
    rows = []
    s, WIN = site.s, site.WIN
    mh = BL.morning_hours(s)
    for d in sorted(ev_score):
        for j in part:
            if not site.complete[d, j]:
                continue
            r = dict(site=site.name, b=site.meters[j], day=str(site.days[d].date()))
            ok = False
            for nm, kw in (("towt70", dict(span=70)), ("towt7", dict(recent=7))):
                pr = towt_predict(site, Tmat, j, d, evset, **kw)
                if pr is not None:
                    r[nm] = float(pr[WIN].sum())
                    r[nm + "_m"] = pr[mh].tolist()
                    ok = True
            if ok:
                rows.append(r)
    return rows


# ---------------- LightGBM learned adjustment ----------------
def _roll_offset(site, evset, j):
    """For every eligible non-event weekday k of building j (>= 10 previous eligible days): offset quantities from the
    10 previous eligible non-event weekdays (= dm0): window mean, 0-9 hour mean, 10-12 hour mean, mean Tmax, window CV."""
    s = site.s
    el = np.array([k for k in range(site.Ys.shape[0]) if site.wk[k] and site.complete[k, j] and k not in evset])
    W = site.Ys[el][:, site.WIN, j].sum(1)
    m1012 = site.Ys[el][:, [s - 4, s - 3, s - 2], j].mean(1)
    m09 = site.Ys[el][:, :s - 4, j].mean(1)
    tm = site.tm[el]
    out = {}
    for pos in range(10, len(el)):
        sl = slice(pos - 10, pos)
        out[el[pos]] = (W[sl].mean(), m09[sl].mean(), m1012[sl].mean(), np.nanmean(tm[sl]), W[sl].std() / max(W[sl].mean(), 1e-9),
                        el[sl].max())
    return out, el, W, m09, m1012


def lgb_site(site, evset, ev_score, folds, rows_R1, params=None, rounds=None):
    """lgbM / lgbD for one site and one world. Day-level samples; y = window load / dm0 window (offset); one model per
    (site, event month, variant); training rows = eligible non-event weekdays of the site BEFORE the first day of the event
    month (monthly refit); early stopping on the chronologically last 20 % of the training days (s9.16). Features are
    fixed (no feature selection, s9.17)."""
    import lightgbm as lgb
    params = params or C.LGB_FIXED
    rounds = rounds or 3000
    s, nb, WIN = site.s, site.nb, site.WIN
    ND = site.Ys.shape[0]
    fold = site.fold
    base = {j: _roll_offset(site, evset, j)[0] for j in range(nb)}   # day -> offset tuple, eligible non-event days
    # event days: offsets from the 10 previous eligible non-event weekdays (dm0 lookback; strictly before d)
    for d in ev_score:
        for j in range(nb):
            el = [k for k in range(d - 1, -1, -1) if site.wk[k] and site.complete[k, j] and k not in evset][:10]
            LK.a1_lookback_before(d, el)
            if len(el) == 10 and site.complete[d, j]:
                W = np.array([site.Ys[k, WIN, j].sum() for k in el])
                base[j][d] = (W.mean(), np.mean([site.Ys[k, :s - 4, j].mean() for k in el]),
                              np.mean([site.Ys[k, [s - 4, s - 3, s - 2], j].mean() for k in el]),
                              np.nanmean(site.tm[el]), W.std() / max(W.mean(), 1e-9), max(el))
    DW = np.full((ND, nb), np.nan)
    DM = np.full((ND, nb), np.nan)
    D09 = np.full((ND, nb), np.nan)
    DM09 = np.full((ND, nb), np.nan)
    for j in range(nb):
        for k, v in base[j].items():
            if site.complete[k, j]:
                DW[k, j] = site.Ys[k, WIN, j].sum()
                DM[k, j] = v[0] * len(WIN)
                D09[k, j] = site.Ys[k, :s - 4, j].mean()
                DM09[k, j] = v[1]

    def donor_feats(k, j):
        dm = np.where(fold != fold[j])[0]       # donors = the other fold
        a, b = DW[k, dm], DM[k, dm]
        okk = np.isfinite(a) & np.isfinite(b)
        c, dd = D09[k, dm], DM09[k, dm]
        ok2 = np.isfinite(c) & np.isfinite(dd)
        return (a[okk].sum() / b[okk].sum() if okk.sum() >= 5 else np.nan,
                c[ok2].sum() / dd[ok2].sum() if ok2.sum() >= 5 else np.nan)

    def feats(k, j, variant):
        v = base[j].get(k)
        if v is None:
            return None
        Wm, m09o, m1012o, tmo, cv, _ = v
        tmk = site.tm[k]
        f = [tmk, tmk - tmo, site.days[k].month, site.days[k].dayofweek, j, np.log(max(Wm, 1e-9)), cv]
        if variant == "M":
            return [site.Ys[k, [s - 4, s - 3, s - 2], j].mean() / max(m1012o, 1e-9)] + f
        dw, d09 = donor_feats(k, j)
        return [site.Ys[k, :s - 4, j].mean() / max(m09o, 1e-9), dw, d09] + f

    out = {}
    months = sorted({site.days[d].month for d in ev_score})
    for variant in ("M", "D"):
        cat = 4 if variant == "M" else 6
        for mo in months:
            first = int(np.where(np.array([dd.month == mo for dd in site.days]))[0][0])
            Xtr, ytr, dtr = [], [], []
            for j in range(nb):
                for k, v in base[j].items():
                    if k < first and k not in evset and site.complete[k, j]:
                        f = feats(k, j, variant)
                        if f is None or not np.isfinite(f).all():
                            continue
                        Xtr.append(f)
                        ytr.append(site.Ys[k, WIN, j].sum() / (v[0] * len(WIN)))
                        dtr.append(k)
            if len(ytr) < 500:
                continue
            Xtr, ytr, dtr = np.array(Xtr, float), np.array(ytr, float), np.array(dtr)
            LK.a5_fit_rows_before(dtr, first)
            LK.a5_feature_selection_train_only(dtr, first)
            cut = np.quantile(dtr, 0.8)
            tr_i, va_i = np.where(dtr <= cut)[0], np.where(dtr > cut)[0]
            LK.a5_val_inside_train(range(len(dtr)), va_i)
            LK.a5_fit_rows_before(dtr[tr_i], dtr[va_i].min())      # validation days follow the fitting days (chronological)
            dset = lgb.Dataset(Xtr[tr_i], ytr[tr_i], categorical_feature=[cat], free_raw_data=False)
            vset = lgb.Dataset(Xtr[va_i], ytr[va_i], reference=dset)
            mdl = lgb.train(params, dset, num_boost_round=rounds, valid_sets=[vset],
                            callbacks=[lgb.early_stopping(50, verbose=False)])
            for d in [d for d in ev_score if site.days[d].month == mo]:
                for j in range(nb):
                    f = feats(d, j, variant)
                    if f is None or not np.isfinite(f).all():
                        continue
                    out[(j, d, variant)] = float(mdl.predict(np.array([f], float))[0] * base[j][d][0] * len(WIN))
    return out


# ---------------- driver ----------------
def _tab(df, s, e, methods):
    return AN.method_table(df, s, e, methods)


def run_secondary(Y, out, boot_b=None, which=None):
    t0 = time.time()
    s, e = C.WINDOWS["primary"]
    R1 = pd.read_pickle(out / "events_R1.pkl")          # self-written by core (trusted)
    only = os.environ.get("PAPERB_SITES")
    only = only.split(",") if only else None
    which = which or ["loo", "w1620", "rebound", "contam", "heat", "towt", "lgb", "dstalt"]
    acc = {k: [] for k in ("loo", "w1620", "contam", "heat", "towt", "lgb")}
    rebound = {"max_abs_change": 0.0, "n_baselines": 0}
    thr = None
    if "heat" in which:
        W16 = D.read_weather(2016) if Y.year != 2016 else Y.weather
        tm16 = D.daily_tmax(W16, pd.date_range("2016-01-01", "2016-12-31"))
        thr = {}
        for nm in C.SITES:
            if nm in tm16.columns:
                se = tm16[nm][D.season_mask(tm16.index)]
                thr[nm] = float(se.quantile(C.HEATWAVE_Q))
    for name in C.SITES:
        if only and name not in only:
            continue
        site, _ = D.make_site(Y, name)
        if site is None:
            continue
        A_, B_ = site.part_idx("A"), site.part_idx("B")
        folds = [("A", A_, B_), ("B", B_, A_)]
        r1 = EV.r1_days(site)
        ev1 = set(r1.tolist())
        if "loo" in which:
            for evd, targets in EV.r2loo_groups(site):
                evs = set(evd.tolist())
                for f, part, dpool in folds:
                    pt = [j for j in targets if j in set(part.tolist())]
                    if not pt:
                        continue
                    rr = BL.run_rule(site, site.Ys, site.Ys, evs, evd, pt, dpool, do_scm=False)
                    acc["loo"] += rr
        if "w1620" in which:
            s2, _ = D.make_site(Y, name, win=C.WINDOWS["w1620"])
            if s2 is not None:
                for f, part, dpool in [("A", s2.part_idx("A"), s2.part_idx("B")), ("B", s2.part_idx("B"), s2.part_idx("A"))]:
                    acc["w1620"] += BL.run_rule(s2, s2.Ys, s2.Ys, ev1, r1, part, dpool, scm=(C.SCM_W, C.SCM_LAM), do_scm=True)
        if "rebound" in which:
            for f, part, dpool in folds:
                y0 = IJ.inject(site.Ys, r1, part, site.win, c=C.C_PRIMARY, r=0.0)
                y1 = IJ.inject(site.Ys, r1, part, site.win, c=C.C_PRIMARY, r=0.10)
                IJ.assert_touched_only(site.Ys, y1, r1, part, site.win)
                a = BL.run_rule(site, y0, site.Ys, ev1, r1, part, dpool, do_scm=False)
                b = BL.run_rule(site, y1, site.Ys, ev1, r1, part, dpool, do_scm=False)
                for ra, rb in zip(a, b):
                    for k in ("pjm0", "caiso0", "ny0", "isone0", "dm0", "wm0", "m3", "mid8", "prev", "don_pjm0", "don_L"):
                        if k in ra:
                            LK.a13_rebound_zero(np.array([ra[k]]), np.array([rb[k]]))
                            rebound["max_abs_change"] = max(rebound["max_abs_change"], abs(ra[k] - rb[k]))
                            rebound["n_baselines"] += 1
        if "contam" in which:
            for q in C.CONTAM_Q:
                for f, part, dpool in folds:
                    sel = IJ.select_donors(dpool, q, site.index)
                    Yc = IJ.contaminated(site.Ys, r1, part, sel, site.win, C.C_PRIMARY, C.CONTAM_P)
                    rr = BL.run_rule(site, Yc, site.Ys, ev1, r1, part, dpool, scm=(C.SCM_W, C.SCM_LAM), do_scm=True)
                    for r in rr:
                        r["q"] = q
                    acc["contam"] += rr
        if "heat" in which and thr and name in thr:
            hw = EV.heatwave_days(site, thr[name])
            if len(hw):
                order = EV.r1_order(site)
                disp = np.array(sorted(set(hw.tolist()) | set(r1.tolist())))   # scored days are dispatched too
                evs = set(disp.tolist())
                for f, part, dpool in folds:
                    Yh = IJ.dispatch(site.Ys, disp, part, site.win)
                    rr = BL.run_rule(site, Yh, site.Ys, evs, r1, part, dpool, scm=(C.SCM_W, C.SCM_LAM), do_scm=True)
                    for r in rr:
                        r["n_dispatched"] = len(disp)
                    acc["heat"] += rr
        if "towt" in which:
            Tm = D.hourly_temp(Y.weather, name, site.days)
            for f, part, dpool in folds:
                acc["towt"] += run_towt(site, Tm, ev1, r1, part)
        if "lgb" in which:
            try:
                res = lgb_site(site, ev1, r1, folds, None)
                for (j, d, v), val in res.items():
                    acc["lgb"].append(dict(site=name, b=site.meters[j], day=str(site.days[d].date()), variant=v, pred=val))
            except Exception as ex:   # reported, never silent
                acc["lgb_error"] = acc.get("lgb_error", []) + ["%s: %r" % (name, ex)]
        print(name, "secondary done", round(time.time() - t0), "s", flush=True)
    res = {"rebound": rebound, "errors": acc.get("lgb_error", [])}
    meths = ["pjm0", "pjmA", "caiso0", "caisoA", "ny0", "nyA", "cgA", "scmR"]
    if acc["loo"]:
        df = pd.DataFrame(acc["loo"])
        res["r2loo"] = _tab(df, s, e, meths)
    if acc["w1620"]:
        df = pd.DataFrame(acc["w1620"])
        w = C.WINDOWS["w1620"]
        res["w1620"] = _tab(df, w[0], w[1], ["prev", "pjm0", "pjmA", "caiso0", "caisoA", "ny0", "nyA", "cgA", "scmR"])
    if acc["contam"]:
        df = pd.DataFrame(acc["contam"])
        res["contam"] = {}
        for q, g in df.groupby("q"):
            g = g.reset_index(drop=True)
            b = adjust.adjusted(g, s, e, 0.0, "4h", obs=True)   # target morning as observed (pre-shaped by p)
            res["contam"][float(q)] = {}
            for m in ("pjmA", "cgA", "scmR", "pjm0"):
                ok = AN.pair_events(g, b, [m])
                v = AN.bld_stat(g, b, m, ok, "relMAE")
                res["contam"][float(q)][m] = dict(relMAE_median=float(v.median()), bias_median=float(AN.bld_stat(g, b, m, ok, "bias").median()))
    if acc["heat"]:
        df = pd.DataFrame(acc["heat"])
        b = adjust.adjusted(df, s, e)
        res["heatwave"] = {}
        for m in ("pjmA", "scmR", "pjm0", "caisoA", "cgA"):
            ok = AN.pair_events(df, b, [m])
            if ok.any():
                rho = (b[m] - df.Lobs.values) / (C.C_PRIMARY * df.L.values)
                res["heatwave"][m] = dict(relMAE_median=float(AN.bld_stat(df, b, m, ok, "relMAE").median()),
                                          rho_median=float(pd.Series(rho[ok]).median()),
                                          fallback_pjm=float(df.pjm_fb[ok].mean()))
        res["heatwave_n_dispatched_median"] = float(df.n_dispatched.median())
    # TOWT and LightGBM merged onto R1
    key = ["site", "b", "day"]
    if acc["towt"]:
        tw = pd.DataFrame(acc["towt"])
        R1t = R1.merge(tw, on=key, how="left")
        bt = adjust.adjusted(R1t, s, e)
        H = [s + a for a in C.ADJ["dm"]]
        m = adjust.shaped_morning(R1t, s, 0.0)
        off = s - 6
        pm = adjust._prof(R1t, "towt70")
        lo, hi = C.CLIP["towt"]
        bt["towt70"] = R1t["towt70"].values
        bt["towt7"] = R1t["towt7"].values if "towt7" in R1t else np.nan
        bt["towt70A"] = R1t["towt70"].values * np.clip(m[:, [h - off for h in H]].mean(1) / pm[:, [h - off for h in H]].mean(1), lo, hi)
        res["towt"] = _method_tab_from(R1t, bt, ["towt70", "towt70A", "towt7", "pjmA", "pjm0"])
    if acc["lgb"]:
        lg = pd.DataFrame(acc["lgb"]).pivot_table(index=key, columns="variant", values="pred").reset_index()
        lg = lg.rename(columns={"M": "lgbM", "D": "lgbD"})
        R1l = R1.merge(lg, on=key, how="left")
        bl = adjust.adjusted(R1l, s, e)
        for c in ("lgbM", "lgbD"):
            bl[c] = R1l[c].values if c in R1l else np.nan
        res["lgb"] = _method_tab_from(R1l, bl, ["lgbM", "lgbD", "pjmA", "dm0"])
        res["lgb_params"] = C.LGB_FIXED
    # alternative DST mapping (sensitivity reported in every case): each AMBIGUOUS site as STD; R1 rules only
    if "dstalt" in which:
        Y2 = D.build_year(Y.year, dst_alt=True)
        rows_alt = []
        for name in C.SITES:
            if only and name not in only:
                continue
            site, _ = D.make_site(Y2, name)
            if site is None:
                continue
            r1 = EV.r1_days(site)
            for part, dpool in ((site.part_idx("A"), site.part_idx("B")), (site.part_idx("B"), site.part_idx("A"))):
                rows_alt += BL.run_rule(site, site.Ys, site.Ys, set(r1.tolist()), r1, part, dpool, do_scm=False)
        dfa = pd.DataFrame(rows_alt)
        h2a = AN.h2(dfa, s, e, boot_b or 200)
        res["dst_alt"] = {"methods": _tab(dfa, s, e, ["pjm0", "pjmA", "caiso0", "caisoA", "cgA"]),
                          "H2": {k_: v_ for k_, v_ in h2a.items() if k_ in ("est", "ci_low", "ci_high", "p", "n_sites")}}
    res["timing_s"] = time.time() - t0
    return res


def _method_tab_from(df, base, methods):
    out = {}
    for m in methods:
        if m not in base or not np.isfinite(base[m]).any():
            continue
        ok = AN.pair_events(df, base, [m])
        rel = AN.bld_stat(df, base, m, ok, "relMAE")
        out[m] = dict(relMAE_median=float(rel.median()), bias_median=float(AN.bld_stat(df, base, m, ok, "bias").median()),
                      n_b=int(len(rel)), n_events=int(ok.sum()), support_share=float(ok.mean()))
    return out


def emit_secondary(led, sec):
    if not sec:
        return
    src = "secondary.py"
    st = "secondary"
    for tag, key in (("R2LOO", "r2loo"), ("w1620", "w1620")):
        for m, d in sec.get(key, {}).items():
            for stat in ("relMAE_median", "bias_median", "rmse_median", "PER_c10_median", "share_PER_gt_0_5", "nmbe_granderson"):
                led.add("method.%s.%s.%s" % (m, tag, stat), d[stat], n_buildings=d["n_b"], n_events=d["n_events"], source_file=src,
                        status="exploratory" if key == "r2loo" else st)
    for q, d in sec.get("contam", {}).items():
        for m, v in d.items():
            led.add("contam.q%g.%s.relMAE_median" % (q, m), v["relMAE_median"], source_file=src, status=st)
            led.add("contam.q%g.%s.bias_median" % (q, m), v["bias_median"], source_file=src, status=st)
    rb = sec.get("rebound")
    if rb:
        led.add("rebound.max_abs_change_kwh", rb["max_abs_change"], n_events=rb["n_baselines"], source_file=src, status=st)
    for m, v in sec.get("heatwave", {}).items():
        for k, x in v.items():
            led.add("heatwave.%s.%s" % (m, k), x, source_file=src, status=st)
    if "heatwave_n_dispatched_median" in sec:
        led.add("heatwave.n_dispatched_median", sec["heatwave_n_dispatched_median"], source_file=src, status=st)
    for key in ("towt", "lgb"):
        for m, d in sec.get(key, {}).items():
            led.add("method.%s.R1.relMAE_median" % m, d["relMAE_median"], n_buildings=d["n_b"], n_events=d["n_events"], source_file=src,
                    status=st) if not led.has("method.%s.R1.relMAE_median" % m) else None
            led.add("method.%s.R1.bias_median" % m, d["bias_median"], source_file=src, status=st) if not led.has("method.%s.R1.bias_median" % m) else None
            if m.startswith(("towt", "lgb")):
                led.add("method.%s.R1.support_share" % m, d["support_share"], source_file=src, status=st) if not led.has("method.%s.R1.support_share" % m) else None
    if sec.get("lgb_params"):
        led.add("hpo.lgb.trials", 0, source_file=src, status=st)
        led.add("hpo.lgb.note", "Optuna not installed; fixed parameters %s; 40-trial HPO not run" % json.dumps({k: v for k, v in sec["lgb_params"].items() if k != "num_threads"}), source_file=src, status=st)
    da = sec.get("dst_alt")
    if da:
        for m, d in da["methods"].items():
            led.add("dst_alt.%s.R1.relMAE_median" % m, d["relMAE_median"], n_buildings=d["n_b"], n_events=d["n_events"], source_file=src, status=st)
            led.add("dst_alt.%s.R1.bias_median" % m, d["bias_median"], source_file=src, status=st)
        h = da["H2"]
        led.add("dst_alt.H2.logratio.pjmA_pjm0", h["est"], ci_low=h["ci_low"], ci_high=h["ci_high"], p_raw=h["p"], n_sites=h["n_sites"], source_file=src, status=st)
    for er in sec.get("errors", []):
        led.add("secondary.error.%d" % (len(led.rows)), er, source_file=src, status=st)
