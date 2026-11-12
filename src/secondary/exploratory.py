"""EXPLORATORY robustness of the two stress-test findings (expert panel SYNTHESIS section (c)). Outside the Holm family:
ledger status 'exploratory', keys `exploratory.<name>.*`, never H1-H5 key names, never p_holm.

CLI (run from the project root):
  python -I src/secondary/exploratory.py --analysis {h4_win1620,h5_win1620,dst_alt,early_shape} --year {2016,2017}
         [--out rows.csv] [--sites Bear,Fox] [--early {a,b}] [--p-stride k] [--collect]
2016 (dev) rows carry the `_v0` suffix and go to results/exploratory_v0/ unless --out is given. 2017 aborts unless
run.freeze.check_manifest() passes, writes to results/secondary/2017/expl_<analysis>.rows.csv and, with --collect, rebuilds
tables/summary_secondary.csv. With --sites or --p-stride != 1 the keys are prefixed `exploratory_slice.` (never collected,
2017 refused): such runs only measure memory and time.

Frozen code (src/run) is imported UNCHANGED. Nothing here edits it. The definitions are in logs/IMPL_exploratory.md and were
written before the first run:
 * h4_win1620 : R1 rebuilt with make_site(win=WINDOWS['w1620']) (pattern of the frozen secondary), then the frozen analysis.h4
                (adjustment and shaping hours are derived from s inside the frozen code, so s = 16).
 * h5_win1620 : dispatch rerun under the same window, then the frozen analysis.h5.
 * dst_alt    : data.build_year(dst_alt=True) (frozen parameter: AMBIGUOUS sites mapped as STD); H4 and H5 at 14-18.
 * early_shape: pre-event increase on a 4-h block that does not coincide with the 4 h before s. variant a = hours s-7..s-4,
                variant b = hours s-8..s-5. scmR sees the target's own event-day hours 0..s-5, so R1 is rerun per p with the
                injected target load (analysis.h4's 'scmR is constant' shortcut does not apply). frozen adjust.shaped_morning
                wraps for hours < s-6 and is NOT used for these shapes; pjmA is read from the observed morning (obs=True)."""
import argparse
import json
import os
import site
import sys
import time

up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../src, needed under python -I

import numpy as np   # noqa: E402
import pandas as pd   # noqa: E402

from run import adjust, analysis as AN, baselines as BL, config as C, data as D, events as EV, inject as IJ   # noqa: E402
from run import stats as ST   # noqa: E402
from secondary import common as CM   # noqa: E402

ANALYSES = ("h4_win1620", "h5_win1620", "dst_alt", "early_shape", "x5", "x7", "neg_p")
SECONDARY_ANALYSES = ("h4_win1620", "h5_win1620", "dst_alt")   # D29: listed in PREREG s10 as secondary; keys keep the exploratory.* names
X7_W = 10   # longer SCM-ridge pre-period: best W above 7 in the 2016 grid (0.06288 vs 0.06179 at W=7); chosen on 2016 accuracy
SCM = (C.SCM_W, C.SCM_LAM)
EARLY = {"a": (-7, -3), "b": (-8, -4)}     # hours [s+a, s+b), 4 h each
H4_METHODS = ("pjmA", "scmR")


# ---------------------------------------------------------------- sample building
def site_names(sites):
    names = list(C.SITES) if not sites else [s for s in sites.split(",") if s]
    assert all(n in C.SITES for n in names), names
    return names


def r1_frame(Y, win, names):
    """R1 event rows (frozen run_rule, scmR at the fixed (W, lambda), scmC at its fixed W) for the given window."""
    rows = []
    for name in names:
        site, _ = D.make_site(Y, name, win=win)
        if site is None:
            continue
        A_, B_ = site.part_idx("A"), site.part_idx("B")
        r1 = EV.r1_days(site)
        ev1 = set(r1.tolist())
        for f, part, dpool in (("A", A_, B_), ("B", B_, A_)):
            rr = BL.run_rule(site, site.Ys, site.Ys, ev1, r1, part, dpool, scm=SCM, do_scm=True)
            for r in rr:
                r["fold"] = f
            rows += rr
        print(name, "R1 done", flush=True)
    return pd.DataFrame(rows)


def erosion_frame(Y, win, names, scm=None):
    """Dispatch rerun, a copy of pipeline.run_erosion with the window as a parameter (frozen code is not edited)."""
    from run import pipeline as PL   # noqa: F401  (frozen; imported for parity of dependencies only)
    rows = []
    for name in names:
        site, _ = D.make_site(Y, name, win=win)
        if site is None:
            continue
        order = EV.r1_order(site)
        score = order[:C.K_EVENTS]
        A_, B_ = site.part_idx("A"), site.part_idx("B")
        assert sorted(score.tolist()) == sorted(EV.r1_days(site).tolist())
        for K in C.DISPATCH_K:
            disp = order[:K]
            evset = set(disp.tolist())
            for f, part, dpool in (("A", A_, B_), ("B", B_, A_)):
                Ys = IJ.dispatch(site.Ys, disp, part, site.win)
                IJ.assert_touched_only(site.Ys, Ys, disp, part, site.win)
                rr = BL.run_rule(site, Ys, site.Ys, evset, score, part, dpool, scm=scm or SCM, do_scm=True)
                for r in rr:
                    r["K"] = K
                    r["fold"] = f
                rows += rr
        print(name, "erosion done", flush=True)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- H4 / H5 through the frozen analysis
def h4_run(R1, win, stride=1):
    """Frozen analysis.h4 on the given event frame (scmR constant in p, pjmA shaped analytically). Bootstrap not run.
    stride > 1 thins the grid (timing slices only): analysis.h4 reads C.P_FINE at call time, patched in this process."""
    s, e = win
    old = C.P_FINE
    try:
        if stride != 1:
            C.P_FINE = tuple(old[::stride])
        return AN.h4(R1, s, e, "4h", methods=H4_METHODS, do_boot=False)
    finally:
        C.P_FINE = old


def h5_run(ER, win):
    return AN.h5(ER, win[0], win[1])


def emit_h4(led, pre, r, win):
    pc = r["pooled"]
    led.add(pre + ".window", "%d-%d" % win)
    led.add(pre + ".pcross.pjmA_scmR.pooled", AN.fmt_cens(pc) if np.isinf(pc) else pc, n_sites=r["n_sites"], n_buildings=r["n_b"],
            n_events=r["n_events"])
    led.add(pre + ".median_site_pcross", r["median_site"], ci_low=r["ci_low"], ci_high=r["ci_high"], n_sites=r["n_sites"])
    led.add(pre + ".median_site_pcross.ci_conf", r["conf"])
    led.add(pre + ".p_sign_unadjusted", r["p"], p_raw=r["p"], n_sites=r["n_sites"])
    led.add(pre + ".sign_k_below_0.10", r["k"], n_sites=r["n_sites"])
    led.add(pre + ".n_tied", r["n_tied"])
    led.add(pre + ".p_signedrank_capped", r["p_signedrank_capped"], p_raw=r["p_signedrank_capped"])
    led.add(pre + ".loso_min", r["loso_min"])
    led.add(pre + ".loso_max", r["loso_max"])
    led.add(pre + ".loso_pmax", r["loso_pmax"])
    led.add(pre + ".site_robust", str(r["site_robust"]))
    led.add(pre + ".sens_increment_p10", r["sens_increment_p10"])
    for st, v in r["site_pcross"].items():
        led.add(pre + ".site." + st, AN.fmt_cens(v) if np.isinf(v) else v)
    if r["dropped"]:
        led.add(pre + ".sites_dropped_support", json.dumps(r["dropped"]))
    ps = r["pstar"]["pjmA"]
    led.add(pre + ".pstar.pjmA.pooled", AN.fmt_cens(ps) if np.isinf(ps) else ps)


def emit_h5(led, pre, res, win):
    c = res["contrast_abs"]["pjmA"]
    led.add(pre + ".window", "%d-%d" % win)
    led.add(pre + ".eta_diff.pjmA_minus_scmR", c["est"], ci_low=c["ci_low"], ci_high=c["ci_high"], n_sites=c["n_sites"],
            n_events=res["n_events_common"])
    led.add(pre + ".p_signedrank_two_sided_unadjusted", c["p"], p_raw=c["p"], n_sites=c["n_sites"])
    led.add(pre + ".median_over_sites", c["median_over_sites"], n_sites=c["n_sites"])
    led.add(pre + ".loso_min", c["loso_min"])
    led.add(pre + ".loso_max", c["loso_max"])
    led.add(pre + ".loso_pmax", c["loso_pmax"])
    led.add(pre + ".site_robust", str(c["site_robust"]))
    led.add(pre + ".p_wcb_sensitivity", c["p_wcb"], p_raw=c["p_wcb"])
    for st, v in c["site_values"].items():
        led.add(pre + ".site." + st, v)
    for m in ("pjmA", "scmR"):
        d = res["methods"][m]
        led.add(pre + ".eta_abs_pooled." + m, d["eta_abs"])
        for K, v in d["abs_dev_pooled"].items():
            led.add(pre + ".absdev.%s.K%d" % (m, K), v)
    if res["dropped"]:
        led.add(pre + ".sites_dropped_support", json.dumps(res["dropped"]))
    led.add(pre + ".eta_definition", "slope of site-median |rho-1| over K (pjmA minus scmR), exact two-sided signed-rank")


# ---------------------------------------------------------------- early shape
def early_site(site, shape_key, grid):
    """For one site: per p in `grid`, the estimates pjmA and scmR of every building-event under the injected target load.
    Returns (keys DataFrame site,b,day,L ; pjmA array [len(grid), n] ; scmR array [len(grid), n])."""
    A_, B_ = site.part_idx("A"), site.part_idx("B")
    r1 = EV.r1_days(site)
    ev1 = set(r1.tolist())
    s, e = site.win
    keys, P, S = None, [], []
    for p in grid:
        rows = []
        for f, part, dpool in (("A", A_, B_), ("B", B_, A_)):
            Ys = IJ.inject(site.Ys, r1, part, site.win, c=0.0, p=float(p), shape=shape_key)
            if p > 0:
                IJ.assert_touched_only(site.Ys, Ys, r1, part, site.win, shape_key)
            rows += BL.run_rule(site, Ys, site.Ys, ev1, r1, part, dpool, scm=SCM, do_scm=True)
        df = pd.DataFrame(rows)
        b = adjust.adjusted(df, s, e, 0.0, "4h", obs=True)    # morning_obs = injected target morning
        k = df[["site", "b", "day", "L"]].reset_index(drop=True)
        if keys is None:
            keys = k
        else:
            assert keys.equals(k), "event rows changed with p (support must not depend on p)"
        P.append(np.asarray(b["pjmA"], float))
        S.append(np.asarray(b["scmR"], float))
    return keys, np.array(P), np.array(S)


def early_run(Y, win, names, shape_key, grid):
    K_, P_, S_ = [], [], []
    for name in names:
        site, _ = D.make_site(Y, name, win=win)
        if site is None:
            continue
        k, P, S = early_site(site, shape_key, grid)
        K_.append(k)
        P_.append(P)
        S_.append(S)
        print(name, "early-shape done", flush=True)
    return pd.concat(K_, ignore_index=True), np.concatenate(P_, axis=1), np.concatenate(S_, axis=1)


def early_stats(keys, P, S, grid):
    """Building relMAE curves of pjmA and scmR on the common support, site medians, p-cross statistics."""
    g = np.asarray(grid, float)
    ok = np.isfinite(P).all(0) & np.isfinite(S).all(0)
    cnt = pd.Series(ok).groupby(keys.site.values).sum()
    drop = cnt[cnt < C.MIN_SUPPORT]
    ok &= ~keys.site.isin(drop.index).values
    kk = keys[ok].reset_index(drop=True)
    L = kk.L.values

    def curve(M):
        cols = []
        for i in range(len(g)):
            e = pd.Series(np.abs((M[i][ok] - L) / L))
            cols.append(e.groupby([kk.site.values, kk.b.values]).mean())
        return pd.concat(cols, axis=1, keys=list(g))
    rp, rs = curve(P), curve(S)
    sp, ss = rp.groupby(level=0).median(), rs.groupby(level=0).median()
    pp, ps = rp.median(axis=0).values, rs.median(axis=0).values
    out = {"dropped": {s_: int(n) for s_, n in drop.items()}, "n_events": int(ok.sum()), "n_b": int(len(rp)), "grid": g}
    out["curve_pooled"] = {"pjmA": pp, "scmR": ps}
    out["samep_site"] = {st: AN.first_cross(sp.loc[st].values - ss.loc[st].values, 0.0, g) for st in sp.index}
    out["frozenstyle_site"] = {st: AN.first_cross(sp.loc[st].values, ss.loc[st].values[0], g) for st in sp.index}
    out["samep_pooled"] = AN.first_cross(pp - ps, 0.0, g)
    out["frozenstyle_pooled"] = AN.first_cross(pp, ps[0], g)
    out["scmR_span_pooled"] = float(np.nanmax(ps) - np.nanmin(ps))        # how much scmR moves with p
    for tag in ("samep", "frozenstyle"):
        x = np.array(list(out[tag + "_site"].values()), float)
        st_ = ST.sign_test(x, C.PCROSS_THRESHOLD, "less")
        lo, hi, conf = ST.median_ci_order(x, C.ALPHA)
        out[tag + "_stat"] = dict(median=float(np.median(x)), ci_low=lo, ci_high=hi, conf=conf, p=st_["p"], k=st_["k"],
                                  n=st_["n"], n_tied=st_["n_tied"])
    return out


def emit_early(led, pre, r, shape):
    led.add(pre + ".shape_hours", "s%+d..s%+d (4 h)" % (shape[0], shape[1] - 1))
    led.add(pre + ".n_events", r["n_events"], n_buildings=r["n_b"])
    if r["dropped"]:
        led.add(pre + ".sites_dropped_support", json.dumps(r["dropped"]))
    for tag, label in (("samep", "pjmA relMAE reaches scmR relMAE at the same p"),
                       ("frozenstyle", "pjmA relMAE reaches scmR relMAE at p = 0")):
        s_ = r[tag + "_stat"]
        pool = r[tag + "_pooled"]
        led.add(pre + ".pcross_%s.pooled" % tag, AN.fmt_cens(pool) if np.isinf(pool) else pool)
        led.add(pre + ".pcross_%s.median_site" % tag, s_["median"], ci_low=s_["ci_low"], ci_high=s_["ci_high"], n_sites=s_["n"] + s_["n_tied"])
        led.add(pre + ".pcross_%s.p_sign_unadjusted" % tag, s_["p"], p_raw=s_["p"], n_sites=s_["n"] + s_["n_tied"])
        led.add(pre + ".pcross_%s.sign_k_below_0.10" % tag, s_["k"])
        led.add(pre + ".pcross_%s.definition" % tag, label)
        for st, v in r[tag + "_site"].items():
            led.add(pre + ".pcross_%s.site.%s" % (tag, st), AN.fmt_cens(v) if np.isinf(v) else v)
    led.add(pre + ".scmR.pooled_curve_span", r["scmR_span_pooled"])
    g = r["grid"]
    for pv in C.P_BAND:
        if any(abs(pv - x) < 1e-9 for x in g):
            i = int(np.argmin(np.abs(g - pv)))
            led.add(pre + ".relMAE.pjmA.p%g" % pv, float(r["curve_pooled"]["pjmA"][i]))
            led.add(pre + ".relMAE.scmR.p%g" % pv, float(r["curve_pooled"]["scmR"][i]))


# ---------------------------------------------------------------- X8 mirror (signed p) and X5 (kWh)
def signed_h4(R1, win, sign=-1):
    """Replica of the analytic part of analysis.h4 on the grid sign * P_FINE (sign=+1 must reproduce h4; sign=-1 is the pre-event decrease).
    Curves are indexed by the magnitude m = |p|. scmR is invariant (reads no hour >= s-4)."""
    s, e = win
    g = np.array(C.P_FINE)
    b0 = adjust.adjusted(R1, s, e)
    okp, drop = AN.apply_site_support(R1, AN.pair_events(R1, b0, ["pjmA", "scmR"]), C.MIN_SUPPORT)
    Rp = R1[okp].reset_index(drop=True)
    tabs, biases = AN.precool_tables(Rp, s, e, list(H4_METHODS), "4h", grid=[float(sign * x) for x in g])
    sp, ss = tabs["pjmA"].groupby(level=0).median(), tabs["scmR"].groupby(level=0).median()
    bp = biases["pjmA"].groupby(level=0).median()
    pool = {m: tabs[m].median(axis=0).values for m in H4_METHODS}
    poolb = {m: biases[m].median(axis=0).values for m in H4_METHODS}
    px = pd.Series({st: AN.first_cross(sp.loc[st].values, ss.loc[st].values[0], g) for st in sp.index})
    x = px.values
    st_ = ST.sign_test(x, C.PCROSS_THRESHOLD, "less")
    lo, hi, conf = ST.median_ci_order(x, C.ALPHA)
    return dict(sign=sign, grid=g, dropped=drop, n_events=int(okp.sum()), n_b=int(len(tabs["pjmA"])), site_pcross=px.to_dict(),
                pooled=AN.first_cross(pool["pjmA"], pool["scmR"][0], g), median_site=float(np.median(x)), ci_low=lo, ci_high=hi,
                conf=conf, p=st_["p"], k=st_["k"], n_sites=st_["n"], n_tied=st_["n_tied"], curve_pooled=pool, bias_pooled=poolb,
                site_bias_pjmA=bp.values, site_curve_pjmA=sp, site_curve_scmR=ss)


def emit_neg(led, pre, r):
    pc = r["pooled"]
    led.add(pre + ".definition", "pre-event DECREASE p=-m on the H4 magnitude grid, 4h shape s-4..s-1, window 14-18; break-even: pjmA relMAE reaches scmR relMAE at m=0")
    led.add(pre + ".pcross_magnitude.pjmA_scmR.pooled", AN.fmt_cens(pc) if np.isinf(pc) else pc, n_sites=r["n_sites"], n_buildings=r["n_b"],
            n_events=r["n_events"])
    led.add(pre + ".median_site_pcross_magnitude", r["median_site"], ci_low=r["ci_low"], ci_high=r["ci_high"], n_sites=r["n_sites"])
    led.add(pre + ".p_sign_unadjusted", r["p"], p_raw=r["p"], n_sites=r["n_sites"])
    led.add(pre + ".sign_k_below_0.10", r["k"])
    for st, v in r["site_pcross"].items():
        led.add(pre + ".site." + st, AN.fmt_cens(v) if np.isinf(v) else v)
    if r["dropped"]:
        led.add(pre + ".sites_dropped_support", json.dumps(r["dropped"]))
    g = r["grid"]
    for pv in C.P_BAND:
        i = int(np.argmin(np.abs(g - pv)))
        for m in H4_METHODS:
            led.add(pre + ".relMAE.%s.m%g" % (m, pv), float(r["curve_pooled"][m][i]))
            b = float(r["bias_pooled"][m][i])
            led.add(pre + ".bias_pooled.%s.m%g" % (m, pv), b)
            led.add(pre + ".bias_sign.%s.m%g" % (m, pv), "negative (B<L)" if b < 0 else "positive (B>L)")
    i10 = int(np.argmin(np.abs(g - 0.10)))
    led.add(pre + ".sites_with_pjmA_bias_negative_at_m0.10", int((r["site_bias_pjmA"][:, i10] < 0).sum()) if r["site_bias_pjmA"].ndim == 2 else -1)
    cp = r["curve_pooled"]["pjmA"]
    led.add(pre + ".pjmA_relMAE_min_over_grid", float(np.min(cp)))
    led.add(pre + ".pjmA_relMAE_argmin_m", float(g[int(np.argmin(cp))]))


def x5_kwh(R1, win, h4res):
    """kWh the pre-event increase must add over the shaped hours s-4..s-1 at each site's p-cross: site shaped-hours load = median over buildings of the
    median over events of the true load in hours s-4..s-1 (stored morning index 2..5)."""
    m = np.vstack(R1["morning"].values).astype(float)
    shaped = m[:, 2:6].sum(1)
    d = pd.DataFrame({"site": R1.site.values, "b": R1.b.values, "load": shaped})
    bl = d.groupby(["site", "b"]).load.median()
    site_load = bl.groupby(level=0).median()
    out = {"site_load": site_load.to_dict(), "kwh": {}, "censored": [], "pooled_load": float(bl.median())}
    for st, pc in h4res["site_pcross"].items():
        if np.isinf(pc) or np.isnan(pc):
            out["censored"].append(st)
        else:
            out["kwh"][st] = float(pc * site_load[st])
    v = np.array(list(out["kwh"].values()))
    out["median_kwh"], out["min_kwh"], out["max_kwh"] = float(np.median(v)), float(v.min()), float(v.max())
    out["pooled_kwh"] = float(h4res["pooled"] * out["pooled_load"])
    return out


def emit_x5(led, pre, r):
    led.add(pre + ".definition", "site p-cross (frozen H4, 4h, 14-18) x site shaped-hours load (median over buildings of median over events of true load s-4..s-1), kWh per building-event; no daily share")
    led.add(pre + ".median_over_sites_kwh", r["median_kwh"], n_sites=len(r["kwh"]))
    led.add(pre + ".min_site_kwh", r["min_kwh"])
    led.add(pre + ".max_site_kwh", r["max_kwh"])
    led.add(pre + ".pooled_kwh", r["pooled_kwh"])
    led.add(pre + ".pooled_shaped_hours_load_kwh", r["pooled_load"])
    for st, v in r["kwh"].items():
        led.add(pre + ".site_kwh." + st, v)
    for st, v in r["site_load"].items():
        led.add(pre + ".site_shaped_load_kwh." + st, float(v))
    if r["censored"]:
        led.add(pre + ".sites_censored_no_kwh", ",".join(r["censored"]))


# ---------------------------------------------------------------- driver
class ExplLedger(CM.SecLedger):
    """SecLedger whose default status is 'exploratory' and whose keys must start with `exploratory.` or `exploratory_slice.`."""

    def add(self, key, value, status="exploratory", **kw):
        assert key.startswith(("exploratory.", "exploratory_slice.")), key
        assert status == "exploratory"
        super().add(key, value, status=status, **kw)

    def relabel(self, status):
        """D29: set the status column of every row (keys unchanged)."""
        for r in self.L.rows.values():
            r["status"] = status


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", choices=ANALYSES, required=True)
    ap.add_argument("--year", type=int, choices=(2016, 2017), required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--sites", default="")
    ap.add_argument("--early", choices=tuple(EARLY), default="a")
    ap.add_argument("--p-stride", type=int, default=1)
    ap.add_argument("--collect", action="store_true")
    a = ap.parse_args(argv)
    sliced = bool(a.sites) or a.p_stride != 1
    if sliced and a.year == 2017:
        raise SystemExit("--sites / --p-stride are for 2016 timing slices only; 2017 needs the full run")
    fh = CM.freeze_hash(a.year)          # 2017: SystemExit if the manifest does not match
    base = "exploratory_slice" if sliced else "exploratory"
    names = site_names(a.sites)
    tm = CM.Timer()
    led = ExplLedger(a.year, fh)
    prim, w16 = C.WINDOWS["primary"], C.WINDOWS["w1620"]
    stride = a.p_stride

    if a.analysis == "h4_win1620":
        Y = D.build_year(a.year)
        R1 = r1_frame(Y, w16, names)
        r = h4_run(R1, w16, stride)
        emit_h4(led, base + ".h4_win1620", r, w16)
    elif a.analysis == "h5_win1620":
        Y = D.build_year(a.year)
        ER = erosion_frame(Y, w16, names)
        emit_h5(led, base + ".h5_win1620", h5_run(ER, w16), w16)
    elif a.analysis == "dst_alt":
        Y = D.build_year(a.year, dst_alt=True)
        R1 = r1_frame(Y, prim, names)
        emit_h4(led, base + ".dst_alt.h4", h4_run(R1, prim, stride), prim)
        del R1
        ER = erosion_frame(Y, prim, names)
        emit_h5(led, base + ".dst_alt.h5", h5_run(ER, prim), prim)
    elif a.analysis in ("x5", "neg_p"):
        R1 = CM.load_R1(a.year)                  # frozen primary-window R1 frame (self-written by src/run), no rebuild
        if sliced:
            R1 = R1[R1.site.isin(names)].reset_index(drop=True)
        if a.analysis == "x5":
            h4r = h4_run(R1, prim, stride)
            emit_x5(led, base + ".x5", x5_kwh(R1, prim, h4r))
        else:
            emit_neg(led, base + ".neg_p", signed_h4(R1, prim, -1))
    elif a.analysis == "x7":
        Y = D.build_year(a.year)
        old_w = C.SCM_W
        C.SCM_W = X7_W                           # in-process; adjust.adjusted reads C.SCM_W to pick the scmR column
        try:
            ER = erosion_frame(Y, prim, names, scm=(X7_W, C.SCM_LAM))
            res = h5_run(ER, prim)
        finally:
            C.SCM_W = old_w
        emit_h5(led, base + ".x7.h5_W%d" % X7_W, res, prim)
        led.add(base + ".x7.W_choice", "W=%d lambda=%g chosen on 2016 accuracy (best W>7 in the 2016 grid)" % (X7_W, C.SCM_LAM))
    elif a.analysis == "early_shape":
        Y = D.build_year(a.year)
        key = "early_" + a.early
        old, old_c = C.SHAPES.get(key), C.SCM_C_W
        C.SHAPES[key] = EARLY[a.early]          # in-process only; restored below (pattern of secondary.variants)
        C.SCM_C_W = C.SCM_W                     # scmC is not used here: skips the W=5 classic SCM (scmR itself is unchanged)
        try:
            grid = list(C.P_FINE)[::stride]
            keys, P, S = early_run(Y, prim, names, key, grid)
        finally:
            C.SCM_C_W = old_c
            if old is None:
                C.SHAPES.pop(key, None)
            else:
                C.SHAPES[key] = old
        r = early_stats(keys, P, S, grid)
        emit_early(led, base + ".early_shape." + a.early, r, EARLY[a.early])
    t = tm.stop()
    led.add(base + ".compute.%s.time_s" % a.analysis, t["time_s"])
    led.add(base + ".compute.%s.peak_mem_gb" % a.analysis, t["peak_gb"])
    if a.analysis in SECONDARY_ANALYSES:
        led.relabel("secondary")
    if a.out:
        out = os.path.abspath(a.out)
    elif a.year == 2016:
        out = str(C.ROOT / "results" / "exploratory_v0" / ("%s%s_v0.rows.csv" % (a.analysis, "_slice" if sliced else "")))
    else:
        out = str(C.ROOT / "results" / "secondary" / "2017" / ("expl_%s.rows.csv" % a.analysis))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    led.L.to_frame().to_csv(out, index=False)
    print(a.analysis, "done", t, "->", out, flush=True)
    if a.collect and a.year == 2017:
        df = CM.collect()
        print("summary_secondary rows:", None if df is None else len(df))


if __name__ == "__main__":
    main()
