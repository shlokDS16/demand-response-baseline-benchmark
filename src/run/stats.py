"""Inference of PREREG s6-s7 (Revision 2): exact signed-rank test by full enumeration of 2^S sign patterns (average ranks
for ties, zeros dropped and counted), exact sign test, Hodges-Lehmann estimate with exact signed-rank inversion
interval, order-statistic interval, TOST (intersection-union), Holm, two-stage bootstrap (conditional, labelled),
leave-one-site-out, Webb six-point wild cluster bootstrap (sites as clusters)."""
import math

import numpy as np
from scipy.stats import rankdata

from . import config as C


# ---------------- exact signed-rank ----------------
def _tplus_null_counts(rk2, chunk=1 << 16):
    """All 2^n sign patterns; returns sorted unique statistic values (doubled ranks) and their counts."""
    n = len(rk2)
    tot = 1 << n
    vals = {}
    for start in range(0, tot, chunk):
        idx = np.arange(start, min(tot, start + chunk), dtype=np.int64)
        bits = ((idx[:, None] >> np.arange(n)) & 1).astype(np.int64)
        t = bits @ rk2
        u, c = np.unique(t, return_counts=True)
        for a, b in zip(u.tolist(), c.tolist()):
            vals[a] = vals.get(a, 0) + b
    return vals, tot


def _tplus_null_dp(rk2):
    mx = int(rk2.sum())
    pr = np.zeros(mx + 1)
    pr[0] = 1.0
    for r in rk2.tolist():
        new = pr * 0.5
        new[r:] += pr[: mx + 1 - r] * 0.5
        pr = new
    return {i: p for i, p in enumerate(pr) if p > 0}, 1.0


def signed_rank(x, side="less", center=0.0, enum_max=22):
    """Exact one-sided Wilcoxon signed-rank test of H0: symmetric about `center`.
    side 'less' (alternative: values below center), 'greater' or 'two' (two-sided, D13). Zeros (after centring) are dropped and counted.
    Returns dict(p, n, n_zero, tplus)."""
    x = np.asarray(x, float) - center
    x = x[~np.isnan(x)]
    nz = int((x == 0).sum())
    x = x[x != 0]
    n = len(x)
    if n == 0:
        return dict(p=np.nan, n=0, n_zero=nz, tplus=np.nan)
    rk2 = np.rint(2 * rankdata(np.abs(x))).astype(np.int64)
    obs = int(rk2[x > 0].sum())
    vals, tot = _tplus_null_counts(rk2) if n <= enum_max else _tplus_null_dp(rk2)
    R2 = int(rk2.sum())
    if side == "less":
        num = sum(c for v, c in vals.items() if v <= obs)
    elif side == "two":   # D13: |W+ - M/2| at least as large as observed (statistic symmetric under the null)
        num = sum(c for v, c in vals.items() if abs(2 * v - R2) >= abs(2 * obs - R2))
    else:
        num = sum(c for v, c in vals.items() if v >= obs)
    return dict(p=float(num / tot), n=n, n_zero=nz, tplus=obs / 2.0)


def _null_cdf_nties(n):
    """Exact null distribution of T+ for ranks 1..n (no ties): array P(T+ = t)."""
    mx = n * (n + 1) // 2
    pr = np.zeros(mx + 1)
    pr[0] = 1.0
    for r in range(1, n + 1):
        new = pr * 0.5
        new[r:] += pr[: mx + 1 - r] * 0.5
        pr = new
    return pr


def hl_ci(x, alpha=0.05):
    """Hodges-Lehmann estimate (median of Walsh averages) and the exact signed-rank inversion interval.
    Returns (est, lo, hi, achieved_confidence)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n == 0:
        return np.nan, np.nan, np.nan, np.nan
    i, j = np.triu_indices(n)
    w = np.sort((x[i] + x[j]) / 2)
    M = len(w)
    pr = _null_cdf_nties(n)
    cdf = np.cumsum(pr)
    ok = np.where(cdf <= alpha / 2 + 1e-12)[0]
    t = int(ok.max()) if len(ok) else -1
    # interval [W_(t+1), W_(M-t)] with 1-based order statistics; t = -1 means the whole range
    lo = w[t] if t >= 0 else w[0]
    hi = w[M - t - 1] if t >= 0 else w[-1]
    # 1-based W_(t+1) is w[t]; W_(M-t) is w[M-t-1]
    conf = 1 - 2 * (cdf[t] if t >= 0 else 0.0)
    return float(np.median(w)), float(lo), float(hi), float(conf)


# ---------------- sign test and order-statistic interval ----------------
def sign_test(x, thr, side="less"):
    """Exact sign test of median < thr (side 'less'). Values equal to thr are dropped; +inf (right-censored) counts as
    above. Returns dict(p, n, k, n_tied)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    tied = int((x == thr).sum())
    x = x[x != thr]
    n = len(x)
    k = int((x < thr).sum()) if side == "less" else int((x > thr).sum())
    if n == 0:
        return dict(p=np.nan, n=0, k=0, n_tied=tied)
    p = sum(math.comb(n, i) for i in range(k, n + 1)) / 2.0 ** n
    return dict(p=float(p), n=n, k=k, n_tied=tied)


def median_ci_order(x, alpha=0.05):
    """Distribution-free interval for the median: [x_(k), x_(n+1-k)], k the largest with P(Bin(n,.5) <= k-1) <= alpha/2.
    Returns (lo, hi, achieved confidence); +inf upper bound = right-censored."""
    x = np.sort(np.asarray(x, float)[~np.isnan(np.asarray(x, float))])
    n = len(x)
    k = 0
    for kk in range(1, n // 2 + 1):
        if sum(math.comb(n, i) for i in range(0, kk)) / 2.0 ** n <= alpha / 2 + 1e-12:
            k = kk
    if k == 0:
        return float(x[0]), float(x[-1]), 1.0
    conf = 1 - 2 * sum(math.comb(n, i) for i in range(0, k)) / 2.0 ** n
    return float(x[k - 1]), float(x[n - k]), float(conf)


# ---------------- TOST and Holm ----------------
def tost(x, delta):
    """Intersection-union TOST on site values: p = max of the two one-sided exact signed-rank p-values (H0a: median <= -d,
    H0b: median >= +d)."""
    a = signed_rank(np.asarray(x, float) + delta, "greater")
    b = signed_rank(np.asarray(x, float) - delta, "less")
    return dict(p=float(max(a["p"], b["p"])), p_lower=a["p"], p_upper=b["p"], n=a["n"])


def holm(pvals):
    """pvals: dict name -> raw p. Returns dict name -> Holm-adjusted p (step-down, monotone, capped at 1)."""
    items = sorted(((p, k) for k, p in pvals.items() if not np.isnan(p)))
    m = len(items)
    out, run = {}, 0.0
    for i, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    for k, p in pvals.items():
        out.setdefault(k, np.nan)
    return out


# ---------------- bootstraps ----------------
def two_stage_boot(groups, stat_fn, B=None, seed=None, alpha=0.05):
    """Conditional two-stage percentile bootstrap: sites resampled with replacement, then buildings within each drawn
    site. groups: dict site -> 1-d array of building values (or 2-d array rows = buildings). stat_fn(list of arrays)
    -> scalar. Conditional on the analysed sites; labelled so everywhere."""
    B = B or C.BOOT_B
    rng = np.random.default_rng(C.BOOT_SEED if seed is None else seed)
    sites = list(groups)
    arrs = [np.asarray(groups[s]) for s in sites]
    est = stat_fn(arrs)
    out = np.empty(B)
    for b in range(B):
        ss = rng.integers(0, len(sites), len(sites))
        samp = []
        for si in ss:
            a = arrs[si]
            samp.append(a[rng.integers(0, len(a), len(a))])
        out[b] = stat_fn(samp)
    out = out[~np.isnan(out)]
    return float(est), float(np.quantile(out, alpha / 2)), float(np.quantile(out, 1 - alpha / 2))


def median_of_site_medians(arrs):
    return float(np.median([np.median(a) for a in arrs if len(a)]))


def wcb_p(site_means, null=0.0, side="less", B=None, seed=None):
    """Webb six-point wild cluster bootstrap, null imposed, clusters = sites; regression of the building value on an
    intercept with equal total weight per site (so the fit is the mean of site means). Returns p (one-sided)."""
    B = B or C.WCB_B
    y = np.asarray(site_means, float)
    y = y[~np.isnan(y)]
    S = len(y)
    rng = np.random.default_rng(C.BOOT_SEED if seed is None else seed)
    u = y - null
    est = y.mean()
    se = math.sqrt(((y - est) ** 2).sum()) / S
    t_obs = (est - null) / se if se > 0 else np.nan
    v = rng.choice(np.array(C.WEBB), size=(B, S))
    ys = v * u[None, :]
    es = ys.mean(1)
    ses = np.sqrt(((ys - es[:, None]) ** 2).sum(1)) / S
    with np.errstate(divide="ignore", invalid="ignore"):
        ts = es / ses
    ok = np.isfinite(ts)
    if side == "less":
        return float((ts[ok] <= t_obs).mean())
    if side == "two":
        return float((np.abs(ts[ok]) >= abs(t_obs)).mean())
    return float((ts[ok] >= t_obs).mean())


def loso(values, fn):
    """Leave-one-site-out: values dict site -> site value; fn(dict) -> (estimate, p). Returns dict site -> (est, p)."""
    return {s: fn({k: v for k, v in values.items() if k != s}) for s in values}
