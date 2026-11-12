"""Estimands, site-level values, tests and ledger rows for H1-H5 and the method tables (PREREG s6-s7, Revision 2).
Unit of estimation: building-event; unit of inference: the site (median over its buildings). The support rule is applied
per contrast: events where both methods exist; a site with < 10 such building-events is dropped from that
hypothesis and reported."""
import numpy as np
import pandas as pd

from . import adjust
from . import config as C
from . import leakage as LK
from . import stats as ST


# ---------------- building values on a common support ----------------
def rel_err(df, base, m):
    return (base[m] - df.L.values) / df.L.values


def pair_events(df, base, methods):
    """Events on the common support of `methods` (all present and finite)."""
    ok = np.ones(len(df), bool)
    for m in methods:
        ok &= np.isfinite(base[m]) if m in base else False
    return ok


def apply_site_support(df, ok, min_n=C.MIN_SUPPORT):
    """Drop sites with fewer than `min_n` supported building-events. Returns (mask, dropped dict site->n)."""
    cnt = pd.Series(ok).groupby(df.site.values).sum()
    drop = cnt[cnt < min_n]
    keep = ~df.site.isin(drop.index).values
    return ok & keep, {s: int(n) for s, n in drop.items()}


def bld_stat(df, base, m, ok, kind):
    """Per-building statistic over supported events. kind: relMAE | bias | rmse | nmbe."""
    e = pd.DataFrame({"site": df.site.values, "b": df.b.values, "e": rel_err(df, base, m), "L": df.L.values,
                      "B": base[m]})[ok]
    g = e.groupby(["site", "b"])
    if kind == "relMAE":
        return g.e.apply(lambda x: np.mean(np.abs(x)))
    if kind == "bias":
        return g.e.mean()
    if kind == "rmse":
        return g.e.apply(lambda x: float(np.sqrt(np.mean(x ** 2))))
    if kind == "nmbe":   # Granderson sign: positive = under-prediction
        s_ = g[["L", "B"]].sum()
        return (s_.L - s_.B) / s_.L
    raise ValueError(kind)


def site_median(v):
    return v.dropna().groupby(level=0).median()


# ---------------- test bundle on site values ----------------
def bundle(sv, bv, side, center=0.0, alpha=0.05):
    """sv: Series site -> site value; bv: Series (site,b) -> building value (for the wild cluster bootstrap)."""
    x = sv.values
    sr = ST.signed_rank(x, side, center)
    est, lo, hi, conf = ST.hl_ci(x, alpha)
    sm = bv.groupby(level=0).mean().reindex(sv.index)
    p_wcb = ST.wcb_p(sm.values, center, side)
    lo_s = ST.loso(sv.to_dict(), lambda d: (ST.hl_ci(list(d.values()))[0], ST.signed_rank(list(d.values()), side, center)["p"]))
    ests = [v[0] for v in lo_s.values()]
    ps = [v[1] for v in lo_s.values()]
    sign_ok = all(np.sign(e - center) == np.sign(est - center) for e in ests)
    return dict(est=est, ci_low=lo, ci_high=hi, conf=conf, p=sr["p"], n_sites=sr["n"], n_zero=sr["n_zero"], p_wcb=p_wcb,
                loso_min=min(ests), loso_max=max(ests), loso_pmax=max(ps), site_robust=bool(sign_ok),
                median_over_sites=float(np.median(x)), site_values=sv.to_dict())


def boot_cond(bv, B=None):
    groups = {s: g.values for s, g in bv.dropna().groupby(level=0)}
    return ST.two_stage_boot(groups, ST.median_of_site_medians, B=B)


# ---------------- hypotheses ----------------
def h1(R1, R3s, s, e, B=None, m="pjm0"):
    """Delta-bias = bias_b(R1) - bias_b(R3, mean over draws), pjm0; site median; one-sided less."""
    b1 = adjust.adjusted(R1, s, e)
    ok1 = pair_events(R1, b1, [m])
    drops = {}
    ok1, d1 = apply_site_support(R1, ok1, C.MIN_SUPPORT)
    draws = []
    ok3s = []
    for R3 in R3s:
        b3 = adjust.adjusted(R3, s, e)
        ok3 = pair_events(R3, b3, [m])
        ok3, d3 = apply_site_support(R3, ok3, 1)
        ok3s.append(ok3)
        draws.append(bld_stat(R3, b3, m, ok3, "bias"))
    a = bld_stat(R1, b1, m, ok1, "bias")
    r3 = pd.concat(draws, axis=1).mean(axis=1, skipna=True)   # mean over draws first (T3 1.3)
    d = (a - r3).dropna()
    # site support on the pair: R3 events pooled over draws per site must also be >= 10
    n3 = pd.concat([pd.Series(o).groupby(R.site.values).sum() for o, R in zip(ok3s, R3s)], axis=1).sum(axis=1)
    bad = set(n3[n3 < C.MIN_SUPPORT].index)
    d = d[[s_ not in bad for s_ in d.index.get_level_values(0)]]
    sv = site_median(d)
    out = bundle(sv, d, "less", 0.0)
    out.update(dropped={**d1, **{k: int(n3[k]) for k in bad}}, n_b=int(len(d)), n_events=int(ok1.sum()), cond=boot_cond(d, B))
    out["R1_bias_site"] = site_median(a).to_dict()
    return out



def h1_rule(R1, R3s, s, e, m, B=None):
    return h1(R1, R3s, s, e, B, m)


def h2(R1, s, e, B=None, xa="pjmA", xb="pjm0"):
    b = adjust.adjusted(R1, s, e)
    ok, dr = apply_site_support(R1, pair_events(R1, b, [xa, xb]), C.MIN_SUPPORT)
    x = bld_stat(R1, b, xa, ok, "relMAE")
    y = bld_stat(R1, b, xb, ok, "relMAE")
    d = np.log(x / y).replace([np.inf, -np.inf], np.nan).dropna()
    sv = site_median(d)
    out = bundle(sv, d, "less", 0.0)
    out.update(dropped=dr, n_b=int(len(d)), n_events=int(ok.sum()), cond=boot_cond(d, B))
    return out


def h3(R1, s, e, B=None):
    b = adjust.adjusted(R1, s, e)
    m1, m2 = pair_events(R1, b, ["cgA", "pjmA"]), None
    ok, dr = apply_site_support(R1, m1, C.MIN_SUPPORT)
    x = bld_stat(R1, b, "cgA", ok, "relMAE")
    y = bld_stat(R1, b, "pjmA", ok, "relMAE")
    d = np.log(x / y).replace([np.inf, -np.inf], np.nan).dropna()
    sv = site_median(d)
    t = ST.tost(sv.values, C.TOST_DELTA)
    est, lo, hi, conf = ST.hl_ci(sv.values, 0.10)   # 90 % interval, descriptive (T3 2.4)
    sm = d.groupby(level=0).mean().reindex(sv.index)
    # LOSO on the TOST
    lo_s = ST.loso(sv.to_dict(), lambda dd: (ST.hl_ci(list(dd.values()))[0], ST.tost(list(dd.values()), C.TOST_DELTA)["p"]))
    ests = [v[0] for v in lo_s.values()]
    out = dict(est=est, ci_low=lo, ci_high=hi, conf=conf, p=t["p"], p_lower=t["p_lower"], p_upper=t["p_upper"],
               n_sites=len(sv), n_zero=0, p_wcb=np.nan, loso_min=min(ests), loso_max=max(ests),
               loso_pmax=max(v[1] for v in lo_s.values()), median_over_sites=float(sv.median()),
               site_values=sv.to_dict(), dropped=dr, n_b=int(len(d)), n_events=int(ok.sum()), cond=boot_cond(d, B))
    out["site_robust"] = bool(all(abs(v) < C.TOST_DELTA for v in ests))
    return out


def h3_decision(res, p_holm):
    """Equivalence only if the Holm-adjusted p_TOST < 0.05 (T3 2.4); the 90 % HL interval is descriptive. Otherwise the
    direction of the HL estimate is reported as 'not shown equivalent'."""
    if p_holm < C.ALPHA:
        return "equivalent"
    return "not shown equivalent (HL estimate %s: comparison group %s)" % (
        "%+.4f" % res["est"], "worse" if res["est"] > 0 else "better")


# ---------------- pre-event increase: p*, p-cross (H4) ----------------
def first_cross(curve, target, grid):
    """First upward crossing of `target` by the linearly interpolated curve on the grid. 0.0 if already >= target at the
    first grid point; inf (right-censored, reported '>0.30') if never; NaN grid points are not interpolated across."""
    v = np.asarray(curve, float)
    if np.isnan(v[0]):
        return np.nan
    if v[0] >= target:
        return 0.0
    for i in range(1, len(v)):
        if np.isnan(v[i]):
            return np.nan
        if v[i] >= target:
            return float(grid[i - 1] + (target - v[i - 1]) * (grid[i] - grid[i - 1]) / (v[i] - v[i - 1]))
    return float("inf")


def fmt_cens(x, cap=0.30):
    return ">%.2f" % cap if np.isinf(x) else x


def precool_tables(R1, s, e, methods, shape, grid=C.P_FINE):
    """Per method: DataFrame (site,b) x grid of building relMAE and bias (own supports)."""
    rm = {m: [] for m in methods}
    bi = {m: [] for m in methods}
    for p in grid:
        b = adjust.adjusted(R1, s, e, p, shape)
        for m in methods:
            ok = pair_events(R1, b, [m])
            rm[m].append(bld_stat(R1, b, m, ok, "relMAE"))
            bi[m].append(bld_stat(R1, b, m, ok, "bias"))
    return ({m: pd.concat(v, axis=1, keys=list(grid)) for m, v in rm.items()},
            {m: pd.concat(v, axis=1, keys=list(grid)) for m, v in bi.items()})


def h4(R1, s, e, shape="4h", methods=("pjmA", "caisoA", "nyA", "isoneA", "dmA", "wmA", "cgA", "cg0", "scmR", "scmC", "pjm0"),
       B=None, do_boot=True):
    grid = list(C.P_FINE)
    g = np.array(grid)
    b0 = adjust.adjusted(R1, s, e)
    # H4 pair support: pjmA and scmR both present (T3 1.2), site min 10 building-events
    okp = pair_events(R1, b0, ["pjmA", "scmR"])
    okp, drop = apply_site_support(R1, okp, C.MIN_SUPPORT)
    Rp = R1[okp].reset_index(drop=True)
    tabs, biases = precool_tables(Rp, s, e, list(methods), shape, grid)
    out = {"shape": shape, "dropped": drop, "n_events": int(okp.sum()), "curves_site": {}, "pstar": {}, "pcross": {}}
    target = C.PCROSS_THRESHOLD
    pooled_curve = {m: tabs[m].median(axis=0).values for m in methods}
    for m in methods:
        out["pstar"][m] = first_cross(pooled_curve[m], target, g)
        if m != "scmR":
            out["pcross"][m] = first_cross(pooled_curve[m], pooled_curve["scmR"][0], g)
    # site curves and site p-cross for pjmA vs scmR
    sc_p = tabs["pjmA"].groupby(level=0).median()
    sc_s = tabs["scmR"].groupby(level=0).median()
    px = pd.Series({st: first_cross(sc_p.loc[st].values, sc_s.loc[st].values[0], g) for st in sc_p.index})
    out["site_pcross"] = px.to_dict()
    out["site_pstar_pjmA"] = pd.Series({st: first_cross(sc_p.loc[st].values, target, g) for st in sc_p.index}).to_dict()
    x = px.values
    st = ST.sign_test(x, C.PCROSS_THRESHOLD, "less")
    lo, hi, conf = ST.median_ci_order(x, C.ALPHA)
    capped = np.where(np.isinf(x), 0.30, x)
    sr = ST.signed_rank(capped, "less", C.PCROSS_THRESHOLD)
    out["curve_bias_pooled"] = {m: biases[m].median(axis=0).values for m in methods}
    out.update(p=st["p"], k=st["k"], n_sites=st["n"], n_tied=st["n_tied"], ci_low=lo, ci_high=hi, conf=conf,
               median_site=float(np.median(x)), p_signedrank_capped=sr["p"], pooled=out["pcross"]["pjmA"],
               curve_pooled={m: pooled_curve[m] for m in methods}, grid=grid, n_b=int(len(tabs["pjmA"])))
    # LOSO for H4: median site p-cross and sign test p
    ls = ST.loso(px.to_dict(), lambda d: (float(np.median(list(d.values()))), ST.sign_test(list(d.values()), C.PCROSS_THRESHOLD)["p"]))
    out["loso_min"] = min(v[0] for v in ls.values())
    out["loso_max"] = max(v[0] for v in ls.values())
    out["loso_pmax"] = max(v[1] for v in ls.values())
    out["site_robust"] = bool(all(v[0] < C.PCROSS_THRESHOLD for v in ls.values()))
    # WCB (sensitivity) on site p-cross minus threshold with censored at 0.30
    out["p_wcb"] = ST.wcb_p(capped - 0.0, C.PCROSS_THRESHOLD, "less")
    # incremental sensitivity contrast at p = 0.10 (co-reported): E_pjmA(0.10) - E_pjmA(0) (scmR is invariant)
    inc = (tabs["pjmA"][0.1] - tabs["pjmA"][0.0]).dropna()
    out["sens_increment_p10"] = float(site_median(inc).median())
    if do_boot:
        # conditional bootstrap CI of the pooled p-cross and of p* (site, then building resampling)
        idx = {s_: np.where(tabs["pjmA"].index.get_level_values(0) == s_)[0] for s_ in sc_p.index}
        M = {m: tabs[m].reindex(tabs["pjmA"].index).values for m in ("pjmA", "scmR", "caisoA", "nyA", "isoneA", "dmA", "wmA", "cgA")}
        rng = np.random.default_rng(C.BOOT_SEED)
        sites = list(idx)
        Bn = B or C.BOOT_B
        res = {m: [] for m in M if m != "scmR"}
        res_star = {m: [] for m in M if m != "scmR"}
        for _ in range(Bn):
            ss = rng.integers(0, len(sites), len(sites))
            ii = np.concatenate([idx[sites[k]][rng.integers(0, len(idx[sites[k]]), len(idx[sites[k]]))] for k in ss])
            tgt = np.nanmedian(M["scmR"][ii, 0])
            for m in res:
                cur = np.nanmedian(M[m][ii], axis=0)
                res[m].append(first_cross(cur, tgt, g))
                res_star[m].append(first_cross(cur, target, g))
        out["pcross_ci"] = {m: _cens_ci(v) for m, v in res.items()}
        out["pstar_ci"] = {m: _cens_ci(v) for m, v in res_star.items()}
    return out


def _cens_ci(v, alpha=0.05):
    v = np.array([x for x in v if not (isinstance(x, float) and np.isnan(x))], float)
    return (float(np.quantile(v, alpha / 2)), float(np.quantile(v, 1 - alpha / 2)))


# ---------------- repeated dispatch (H5) ----------------
def _slope(y, Ks):
    return float(np.polyfit(Ks, np.asarray(y, float), 1)[0])


def _dtau(y, Ks, tau=C.TAU):
    """First K at which rho falls tau below its K = 10 value (linear interpolation between the K grid); inf = '>40'."""
    ref = y[0] - tau
    for i in range(1, len(Ks)):
        if y[i] <= ref:
            return float(Ks[i - 1] + (y[i - 1] - ref) * (Ks[i] - Ks[i - 1]) / (y[i - 1] - y[i]))
    return float("inf")


def h5(ER, s, e, methods=("pjmA", "caisoA", "cgA", "pjm0", "scmR"), c=C.C_PRIMARY, B=None):
    """ER: event rows of the dispatch runs (column K). rho = estimated / true curtailment = (B - L_obs) / (c * L_true).
    Building value rho_b(K) = mean over the scored days; site value = median over buildings; fixed common support =
    building-events present at all four K with pjmA and scmR finite (support rule: >= 10 per site, else dropped).
    eta_signed = -(LS slope of the site rho over K); eta_abs = LS slope of the site median of |rho_b - 1| (primary after
    the coordinator's note; the signed version is kept as secondary)."""
    Ks = list(C.DISPATCH_K)
    base_by_K = {}
    for K, g in ER.groupby("K"):
        g = g.reset_index(drop=True)
        base_by_K[K] = (g, adjust.adjusted(g, s, e))
    key = lambda g: g.site + "|" + g.b + "|" + g.day
    sets = []
    for K in Ks:
        g, bb = base_by_K[K]
        ok = np.isfinite(bb["pjmA"]) & np.isfinite(bb["scmR"])
        sets.append(set(key(g)[ok]))
    common = set.intersection(*sets)
    cnt = pd.Series([k.split("|")[0] for k in common]).value_counts()
    drop = cnt[cnt < C.MIN_SUPPORT]
    keep_sites = [s_ for s_ in cnt.index if s_ not in drop.index]
    res = {"n_events_common": len(common), "methods": {}, "dropped": {s_: int(n) for s_, n in drop.items()}}
    tab = {}
    for m in methods:
        rows, fb = [], {}
        for K in Ks:
            g, bb = base_by_K[K]
            ok = key(g).isin(common).values & g.site.isin(keep_sites).values
            rho = (bb[m] - g.Lobs.values) / (c * g.L.values)
            t = pd.DataFrame({"site": g.site, "b": g.b, "rho": rho})[ok]
            rows.append(t.groupby(["site", "b"]).rho.mean().rename(K))
            if m.startswith("pjm") or m == "cgA":
                fb[K] = float(g.pjm_fb[ok].mean())
            else:
                fb[K] = float(g.caiso_fb[ok].mean())
        tab[m] = pd.concat(rows, axis=1)
        res["methods"][m] = {"fallback_rate": fb}
    gK = {K: base_by_K[K][0] for K in Ks}
    res["fallback_by_rule"] = {K: {"PJM": float(gK[K].pjm_fb[key(gK[K]).isin(common).values].mean()),
                                   "CAISO": float(gK[K].caiso_fb[key(gK[K]).isin(common).values].mean()),
                                   "CAISO_lt10": float((gK[K].caiso_n[key(gK[K]).isin(common).values] < 10).mean())} for K in Ks}
    eta_s, eta_a = {}, {}
    for m in methods:
        t = tab[m]
        sm = t.groupby(level=0).median()                           # site x K (signed rho)
        sa = (t - 1).abs().groupby(level=0).median()               # site x K (|rho_b - 1|)
        eta_s[m] = sm.apply(lambda r: -_slope(r.values, Ks), axis=1)
        eta_a[m] = sa.apply(lambda r: _slope(r.values, Ks), axis=1)
        pooled = t.median(axis=0)
        pooled_a = (t - 1).abs().median(axis=0)
        res["methods"][m].update(
            rho_pooled={int(k): float(v) for k, v in pooled.items()}, abs_dev_pooled={int(k): float(v) for k, v in pooled_a.items()},
            eta=float(-_slope(pooled.values, Ks)), eta_abs=float(_slope(pooled_a.values, Ks)),
            eta_2pt=float((pooled[10] - pooled[40]) / 30),
            eta_site=eta_s[m].to_dict(), eta_abs_site=eta_a[m].to_dict(),
            D_tau=_dtau(pooled.values, Ks), D_tau_site={s_: _dtau(sm.loc[s_].values, Ks) for s_ in sm.index},
            rho_site={s_: sm.loc[s_].tolist() for s_ in sm.index})
    res["tab"] = tab

    def contrast(etas, bsign, side="two"):
        out = {}
        for a in methods:
            if a == "scmR":
                continue
            d = (etas[a] - etas["scmR"]).dropna()
            bva = tab[a].apply(lambda r: bsign * _slope(r.values, Ks), axis=1)
            bvs = tab["scmR"].apply(lambda r: bsign * _slope(r.values, Ks), axis=1)
            bv = (bva - bvs).dropna()
            bv = bv[bv.index.get_level_values(0).isin(d.index)]
            out[a] = bundle(d, bv, side, 0.0)
        return out
    res["contrast_signed"] = contrast(eta_s, -1, "two")
    # building-level abs-deviation slope for the wild cluster bootstrap
    tab_abs = {m: (tab[m] - 1).abs() for m in methods}
    res["contrast_abs"] = {}
    for a in methods:
        if a == "scmR":
            continue
        d = (eta_a[a] - eta_a["scmR"]).dropna()
        bva = tab_abs[a].apply(lambda r: _slope(r.values, Ks), axis=1)
        bvs = tab_abs["scmR"].apply(lambda r: _slope(r.values, Ks), axis=1)
        bv = (bva - bvs).dropna()
        bv = bv[bv.index.get_level_values(0).isin(d.index)]
        res["contrast_abs"][a] = bundle(d, bv, "two", 0.0)   # D13: two-sided exact signed-rank
    res["age_days_median_by_K"] = {"pjm_lookback": {K: float(gK[K].pjm_age[key(gK[K]).isin(common).values].median()) for K in Ks},
                                   "scmR_preperiod": {K: float(gK[K]["scm_age_W%d" % C.SCM_W][key(gK[K]).isin(common).values].median()) for K in Ks}}
    res["contrast"] = res["contrast_abs"] if C.H5_PRIMARY == "abs" else res["contrast_signed"]
    res["primary"] = C.H5_PRIMARY
    return res


# ---------------- method tables ----------------
def method_table(df, s, e, methods):
    """Per method: medians over buildings of relMAE, bias, rmse, PER(c=0.10), NMBE (Granderson sign); share PER > 0.5;
    on the method's own support (support shares are reported by the caller)."""
    b = adjust.adjusted(df, s, e)
    out = {}
    for m in methods:
        if m not in b or not np.isfinite(b[m]).any():
            continue
        ok = pair_events(df, b, [m])
        if ok.sum() == 0:
            continue
        rel = bld_stat(df, b, m, ok, "relMAE")
        e_ev = np.abs(rel_err(df, b, m))[ok]
        out[m] = dict(relMAE_median=float(rel.median()), bias_median=float(bld_stat(df, b, m, ok, "bias").median()),
                      rmse_median=float(bld_stat(df, b, m, ok, "rmse").median()), PER_c10_median=float(rel.median() / C.C_PRIMARY),
                      PER_c05_median=float(rel.median() / 0.05), PER_c20_median=float(rel.median() / 0.20),
                      share_PER_gt_0_5=float((e_ev / C.C_PRIMARY > 0.5).mean()),
                      nmbe_granderson=float(bld_stat(df, b, m, ok, "nmbe").median()),
                      n_b=int(len(rel)), n_events=int(ok.sum()), support_share=float(ok.mean()))
    return out
