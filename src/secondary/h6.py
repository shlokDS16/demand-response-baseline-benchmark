"""H6 portfolio analysis (PREREG s6 'Secondary', T2.4): change in the median absolute portfolio payment error from n = 1
to n = 20, cgA vs pjmA, disjoint folds, against load-matched random portfolios, 20 draws per site-day, seed 7.

PREREG leaves the following open; CHOICE_AFTER_FREEZE (simplest option each):
 * Error unit: PER = |sum_i baseline_i - sum_i L_i| / (c * sum_i L_i), c = 0.10 (payment error as a share of the value of a
   10 % curtailment), per portfolio and event day; L = true (uncurtailed) window load of the R1 events of the frozen run.
 * Portfolios live inside one fold (participants of fold F; cgA donors are the other fold, as in the frozen run), so
   portfolio cgA = sum of the building cgA (the donor ratio is common to a site-day-fold): additive, no refit.
 * Disjoint portfolios (n = 20): per (site, fold, day) the buildings with both baselines present are permuted (seed 7) and cut
   into consecutive blocks of 20 (a remainder < 20 is dropped); n = 1 uses every building as a portfolio of its own.
 * Reference load for matching: the building's mean pjm0 window baseline over its R1 events (an ex-ante quantity; the
   'total 2016 window load' of PREREG would need 2016 load in a 2017 run, which the frozen modules do not load).
 * Load-matched random portfolios: for each disjoint n = 20 block with reference total R, 20 random portfolios of buildings of
   the same site-day-fold (random size, built along a random permutation by adding buildings until the running total is inside
   [0.9 R, 1.1 R]; up to 50 permutations per draw; unmatched draws are discarded and counted).
 * Site value = median over the site's portfolios; the contrast between methods is tested over sites (two-sided exact
   signed-rank, Hodges-Lehmann interval); no Holm, secondary."""
import numpy as np
import pandas as pd

from run import adjust, config as C
from run import stats as ST

SEED = 7
N_BIG = 20
N_DRAW = 20
TOL = 0.10
MAX_TRIES = 50


def per(B, L, c=C.C_PRIMARY):
    """Absolute portfolio payment error share |sum B - sum L| / (c sum L)."""
    return abs(float(np.sum(B)) - float(np.sum(L))) / (c * float(np.sum(L)))


def disjoint_blocks(m, n, rng):
    """Random disjoint blocks of n indices out of range(m); the remainder (< n) is dropped."""
    perm = rng.permutation(m)
    return [perm[i * n:(i + 1) * n] for i in range(m // n)]


def matched_random(ref, target, rng, tol=TOL, tries=MAX_TRIES):
    """One random portfolio (index array) whose reference total lies in [(1-tol) target, (1+tol) target]; None if not found."""
    m = len(ref)
    lo, hi = (1 - tol) * target, (1 + tol) * target
    for _ in range(tries):
        perm = rng.permutation(m)
        cs = np.cumsum(ref[perm])
        ok = np.where((cs >= lo) & (cs <= hi))[0]
        if len(ok):
            return perm[: ok[0] + 1]
    return None


def build_frame(R1, s, e):
    b = adjust.adjusted(R1, s, e)
    df = pd.DataFrame(dict(site=R1.site.values, fold=R1.fold.values, b=R1.b.values, d=R1.d.values, L=R1.L.values,
                           pjm0=R1.pjm0.values, pjmA=b["pjmA"], cgA=b["cgA"]))
    df = df[np.isfinite(df.pjmA) & np.isfinite(df.cgA) & (df.L > 0)].copy()
    df["ref"] = df.groupby(["site", "b"]).pjm0.transform("mean")      # ex-ante reference load of the building
    return df


def run_h6(R1, s, e, seed=SEED, n_big=N_BIG, n_draw=N_DRAW):
    df = build_frame(R1, s, e)
    sites = sorted(df.site.unique())
    rows = []
    n_unmatched = 0
    n_try = 0
    for (site, fold, d), g in df.groupby(["site", "fold", "d"], sort=True):
        g = g.reset_index(drop=True)
        rng = np.random.default_rng([seed, C.SITES.index(site), int(d), 0 if fold == "A" else 1])
        L, P, G, R = g.L.values, g.pjmA.values, g.cgA.values, g.ref.values
        for i in range(len(g)):
            rows.append((site, fold, d, "n1", per(P[i], L[i]), per(G[i], L[i])))
        if len(g) < n_big:
            continue
        for blk in disjoint_blocks(len(g), n_big, rng):
            rows.append((site, fold, d, "n%d" % n_big, per(P[blk], L[blk]), per(G[blk], L[blk])))
            for _ in range(n_draw):
                n_try += 1
                ix = matched_random(R, R[blk].sum(), rng)
                if ix is None:
                    n_unmatched += 1
                    continue
                rows.append((site, fold, d, "rand", per(P[ix], L[ix]), per(G[ix], L[ix])))
    pf = pd.DataFrame(rows, columns=["site", "fold", "d", "kind", "per_pjmA", "per_cgA"])
    sv = pf.groupby(["site", "kind"])[["per_pjmA", "per_cgA"]].median().unstack("kind")
    res = dict(n_sites=len(sites), n_unmatched=n_unmatched, n_tried=n_try, n_portfolios=pf.groupby("kind").size().to_dict())
    big = "n%d" % n_big
    site_tab = {}
    for m in ("pjmA", "cgA"):
        c = "per_" + m
        site_tab[m] = pd.DataFrame({"n1": sv[(c, "n1")], big: sv[(c, big)], "rand": sv[(c, "rand")]})
        site_tab[m]["delta_big"] = site_tab[m][big] - site_tab[m]["n1"]
        site_tab[m]["delta_rand"] = site_tab[m]["rand"] - site_tab[m]["n1"]
    res["site"] = {m: t.to_dict("index") for m, t in site_tab.items()}
    res["pooled"] = {m: dict(n1=float(pf[pf.kind == "n1"]["per_" + m].median()), nbig=float(pf[pf.kind == big]["per_" + m].median()),
                             rand=float(pf[pf.kind == "rand"]["per_" + m].median()),
                             site_median_n1=float(site_tab[m].n1.median()), site_median_nbig=float(site_tab[m][big].median()),
                             site_median_rand=float(site_tab[m].rand.median()))
                     for m in ("pjmA", "cgA")}
    # contrasts over sites: change from n = 1 to n = 20 (cgA minus pjmA), and the same against the load-matched random change
    contr = {}
    for nm, x in (("delta_big", site_tab["cgA"].delta_big - site_tab["pjmA"].delta_big),
                  ("delta_rand", site_tab["cgA"].delta_rand - site_tab["pjmA"].delta_rand),
                  ("big_minus_rand_cgA_minus_pjmA", (site_tab["cgA"][big] - site_tab["cgA"].rand) - (site_tab["pjmA"][big] - site_tab["pjmA"].rand)),
                  ("level_big", site_tab["cgA"][big] - site_tab["pjmA"][big]),
                  ("level_n1", site_tab["cgA"].n1 - site_tab["pjmA"].n1)):
        x = x.dropna()
        sr = ST.signed_rank(x.values, "two")
        est, lo, hi, conf = ST.hl_ci(x.values)
        contr[nm] = dict(est=est, ci_low=lo, ci_high=hi, p=sr["p"], n_sites=sr["n"], n_neg=int((x < 0).sum()))
    res["contrast"] = contr
    return res


def emit(led, res):
    for m, d in res["pooled"].items():
        for k, v in d.items():
            led.add("H6.%s.PER.%s" % (m, k), v, n_sites=res["n_sites"])
    for nm, d in res["contrast"].items():
        led.add("H6.contrast.%s" % nm, d["est"], ci_low=d["ci_low"], ci_high=d["ci_high"], p_raw=d["p"], n_sites=d["n_sites"])
        led.add("H6.contrast.%s.n_negative_sites" % nm, d["n_neg"], n_sites=d["n_sites"])
    for m, t in res["site"].items():
        for site, d in t.items():
            for k, v in d.items():
                led.add("H6.site.%s.%s.%s" % (site, m, k), v)
    for k, v in res["n_portfolios"].items():
        led.add("H6.n_portfolios.%s" % k, int(v))
    led.add("H6.random.n_unmatched", res["n_unmatched"], n_events=res["n_tried"])
