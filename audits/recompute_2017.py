"""Independent recomputation of the 2017 confirmatory statistics from the stored event frames (P4 audit).
Does NOT import src.run. Follows PREREG section 6 directly. Run: python -I audits/recompute_2017.py"""
import sys, math, itertools
sys.path.append("" + __import__("site").getusersitepackages() + "")
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results" / "run"
S, E = 14, 18
NW = E - S
DELTA = math.log(1.10)
MINSUP = 10


# ---------- statistics (own implementation) ----------
def avg_ranks(a):
    order = np.argsort(a, kind="mergesort")
    r = np.empty(len(a))
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and a[order[j + 1]] == a[order[i]]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return r


def signed_rank_p(x, side):
    """exact enumeration; side less / greater / two. zeros (|x|<1e-12) dropped."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    nz = int((np.abs(x) < 1e-12).sum())
    x = x[np.abs(x) >= 1e-12]
    n = len(x)
    rk2 = np.rint(2 * avg_ranks(np.abs(x))).astype(int)  # doubled ranks, exact integers
    obs = int(rk2[x > 0].sum())
    tot2 = int(rk2.sum())
    cnt = {}
    for signs in itertools.product((0, 1), repeat=n):
        v = int(np.dot(signs, rk2))
        cnt[v] = cnt.get(v, 0) + 1
    N = 2 ** n
    if side == "less":
        k = sum(c for v, c in cnt.items() if v <= obs)
    elif side == "greater":
        k = sum(c for v, c in cnt.items() if v >= obs)
    else:
        k = sum(c for v, c in cnt.items() if abs(2 * v - tot2) >= abs(2 * obs - tot2))
    return k / N, n, nz


def hl(x, conf_alpha=0.05):
    x = np.asarray(x, float)
    n = len(x)
    w = np.sort([(x[i] + x[j]) / 2 for i in range(n) for j in range(i, n)])
    est = float(np.median(w))
    pr = np.zeros(n * (n + 1) // 2 + 1)
    pr[0] = 1
    for r in range(1, n + 1):
        new = pr * 0.5
        new[r:] += pr[:len(pr) - r] * 0.5
        pr = new
    cdf = np.cumsum(pr)
    ok = np.where(cdf <= conf_alpha / 2 + 1e-12)[0]
    t = int(ok.max()) if len(ok) else -1
    M = len(w)
    lo, hi = (w[t], w[M - t - 1]) if t >= 0 else (w[0], w[-1])
    return est, float(lo), float(hi)


def tost(x, delta):
    a, _, _ = signed_rank_p(np.asarray(x) + delta, "greater")
    b, _, _ = signed_rank_p(np.asarray(x) - delta, "less")
    return max(a, b), a, b


def sign_test_p(x, thr):
    x = np.asarray(x, float)
    x = x[x != thr]
    n = len(x)
    k = int((x < thr).sum())
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n, k, n


def holm(p):
    names = sorted(p, key=lambda k: p[k])
    m = len(names)
    out = {}
    run = 0.0
    for i, k in enumerate(names):
        run = max(run, (m - i) * p[k])
        out[k] = min(1.0, run)
    return out


# ---------- baselines from stored frames ----------
def prof(df, col):
    return np.vstack([v for v in df[col].values]).astype(float)


def pjmA(df, p=0.0):
    m = np.vstack(df["morning"].values).astype(float)  # hours s-6..s-1 ; index h-(s-6)
    pm = prof(df, "pjm0_m")
    idx = [2, 3, 4]  # s-4, s-3, s-2
    mm = m.copy()
    mm[:, 2:6] *= (1 + p)  # 4 h shape [s-4, s)
    return df.pjm0.values + NW * (mm[:, idx].mean(1) - pm[:, idx].mean(1))


def relerr(base, L):
    return (base - L) / L


def bld(df, base, ok, kind):
    t = pd.DataFrame({"site": df.site.values, "b": df.b.values, "e": relerr(base, df.L.values)})[ok]
    g = t.groupby(["site", "b"]).e
    return g.mean() if kind == "bias" else g.apply(lambda v: np.mean(np.abs(v)))


def site_support(df, ok, mn=MINSUP):
    c = pd.Series(ok).groupby(df.site.values).sum()
    drop = c[c < mn]
    return ok & ~df.site.isin(drop.index).values, {k: int(v) for k, v in drop.items()}


def site_med(v):
    return v.dropna().groupby(level=0).median()


R1 = pd.read_pickle(RUN / "events_R1.pkl")
R3 = pd.read_pickle(RUN / "events_R3.pkl")
ER = pd.read_pickle(RUN / "events_erosion.pkl")
led = pd.read_csv(ROOT / "tables" / "summary.csv").set_index("key")
res = {}


def cmp(name, mine, key, col="value", tol="rel"):
    led_v = float(led.loc[key, col]) if key in led.index else float("nan")
    res[name] = (float(mine), led_v, tol)


print("R1 rows", len(R1), "sites", R1.site.nunique(), "buildings", R1.groupby(["site", "b"]).ngroups)

# ---------- H1 ----------
b1 = R1.pjm0.values
ok1 = np.isfinite(b1)
ok1, d1 = site_support(R1, ok1)
a = bld(R1, b1, ok1, "bias")
draws = []
n3 = []
for dr, g in R3.groupby("draw"):
    g = g.reset_index(drop=True)
    ok3 = np.isfinite(g.pjm0.values)
    draws.append(bld(g, g.pjm0.values, ok3, "bias"))
    n3.append(pd.Series(ok3).groupby(g.site.values).sum())
r3 = pd.concat(draws, axis=1).mean(axis=1, skipna=True)
d = (a - r3).dropna()
n3 = pd.concat(n3, axis=1).sum(axis=1)
d = d[[s not in set(n3[n3 < MINSUP].index) for s in d.index.get_level_values(0)]]
sv1 = site_med(d)
p1, n, nz = signed_rank_p(sv1.values, "less")
e1, l1, h1 = hl(sv1.values)
cmp("H1.est(HL)", e1, "H1.delta_bias.pjm0")
cmp("H1.ci_low", l1, "H1.delta_bias.pjm0", "ci_low")
cmp("H1.ci_high", h1, "H1.delta_bias.pjm0", "ci_high")
cmp("H1.p", p1, "H1.p_signedrank", tol="p")
for s, v in sv1.items():
    cmp("H1.site." + s, v, "H1.site." + s)
print("H1 sites", n, "zeros", nz, "support drops R1", d1, "R3 min events per site", int(n3.min()), "neg sites", int((sv1 < 0).sum()))

# ---------- H2 ----------
A = pjmA(R1)
ok2 = np.isfinite(A) & np.isfinite(R1.pjm0.values)
ok2, d2 = site_support(R1, ok2)
x = bld(R1, A, ok2, "relMAE")
y = bld(R1, R1.pjm0.values, ok2, "relMAE")
dd = np.log(x / y).replace([np.inf, -np.inf], np.nan).dropna()
sv2 = site_med(dd)
p2, n, nz = signed_rank_p(sv2.values, "less")
e2, l2, h2 = hl(sv2.values)
cmp("H2.est", e2, "H2.logratio.pjmA_pjm0")
cmp("H2.ci_low", l2, "H2.logratio.pjmA_pjm0", "ci_low")
cmp("H2.ci_high", h2, "H2.logratio.pjmA_pjm0", "ci_high")
cmp("H2.p", p2, "H2.p_signedrank", tol="p")
for s, v in sv2.items():
    cmp("H2.site." + s, v, "H2.site." + s)
print("H2 n_sites", n, "zeros", nz, "drops", d2, "n_b", len(dd), "n_ev", int(ok2.sum()), "neg sites", int((sv2 < 0).sum()))

# ---------- H3 ----------
cg = A * R1.don_L.values / R1.don_pjmA.values
ok3 = np.isfinite(cg) & np.isfinite(A)
ok3, d3 = site_support(R1, ok3)
x = bld(R1, cg, ok3, "relMAE")
y = bld(R1, A, ok3, "relMAE")
dd3 = np.log(x / y).replace([np.inf, -np.inf], np.nan).dropna()
sv3 = site_med(dd3)
pt, pl, pu = tost(sv3.values, DELTA)
e3, l3, h3 = hl(sv3.values, 0.10)
cmp("H3.est", e3, "H3.logratio.cgA_pjmA")
cmp("H3.ci90_low", l3, "H3.ci90", "ci_low")
cmp("H3.ci90_high", h3, "H3.ci90", "ci_high")
cmp("H3.p_tost", pt, "H3.p_tost", tol="p")
for s, v in sv3.items():
    cmp("H3.site." + s, v, "H3.site." + s)
print("H3 p_lower %.8f p_upper %.8f p_tost %.8f; n_ev %d drops %s; 90pct HL [%.4f, %.4f] margin +-%.4f; max|site| %.4f" % (
    pl, pu, pt, int(ok3.sum()), d3, l3, h3, DELTA, np.abs(sv3.values).max()))

# ---------- H4 ----------
grid = np.round(np.arange(61) * 0.005, 3)
okp = np.isfinite(A) & np.isfinite(R1.scmr_W7_l3.values)
okp, d4 = site_support(R1, okp)
Rp = R1[okp].reset_index(drop=True)
curves = []
allok = np.ones(len(Rp), bool)
for p in grid:
    curves.append(bld(Rp, pjmA(Rp, p), allok, "relMAE"))
tab = pd.concat(curves, axis=1, keys=list(grid))
scm = bld(Rp, Rp.scmr_W7_l3.values, allok, "relMAE")
sc_p = tab.groupby(level=0).median()
sc_s = scm.groupby(level=0).median()


def first_cross(v, target):
    v = np.asarray(v, float)
    if v[0] >= target:
        return 0.0
    for i in range(1, len(v)):
        if v[i] >= target:
            return float(grid[i - 1] + (target - v[i - 1]) * (grid[i] - grid[i - 1]) / (v[i] - v[i - 1]))
    return float("inf")


px = pd.Series({s: first_cross(sc_p.loc[s].values, sc_s.loc[s]) for s in sc_p.index})
pS, k, n = sign_test_p(px.values, 0.10)
cmp("H4.p_sign", pS, "H4.p_sign", tol="p")
cmp("H4.median_site_pcross", float(np.median(px.values)), "H4.median_site_pcross")
pooled = first_cross(tab.median(axis=0).values, scm.median())
cmp("H4.pooled_pcross", pooled, "H4.pcross.pjmA_scmR.4h")
for s, v in px.items():
    cmp("H4.site." + s, v, "H4.site." + s)
print("H4 sites below 0.10: %d of %d, drops %s, n_ev %d; site pcross %s" % (k, n, d4, int(okp.sum()), px.round(4).to_dict()))

# ---------- H5 ----------
Ks = [10, 20, 30, 40]
bb = {}
for K, g in ER.groupby("K"):
    g = g.reset_index(drop=True)
    bb[K] = (g, {"pjmA": pjmA(g), "scmR": g.scmr_W7_l3.values})


def key(g):
    return g.site + "|" + g.b + "|" + g.day.astype(str)


common = set.intersection(*[set(key(g)[np.isfinite(b["pjmA"]) & np.isfinite(b["scmR"])]) for g, b in bb.values()])
cnt = pd.Series([k_.split("|")[0] for k_ in common]).value_counts()
keep = [s for s in cnt.index if cnt[s] >= MINSUP]
etas = {}
absdev = {}
for m in ("pjmA", "scmR"):
    cols = []
    for K in Ks:
        g, b = bb[K]
        ok = key(g).isin(common).values & g.site.isin(keep).values
        rho = (b[m] - g.Lobs.values) / (0.10 * g.L.values)
        t = pd.DataFrame({"site": g.site, "b": g.b, "rho": rho})[ok]
        cols.append(t.groupby(["site", "b"]).rho.mean().rename(K))
    tb = pd.concat(cols, axis=1)
    sa = (tb - 1).abs().groupby(level=0).median()
    absdev[m] = sa
    etas[m] = sa.apply(lambda r: np.polyfit(Ks, r.values, 1)[0], axis=1)
sv5 = (etas["pjmA"] - etas["scmR"]).dropna()
p5, n, nz = signed_rank_p(sv5.values, "two")
e5, l5, h5 = hl(sv5.values)
cmp("H5.eta_diff", e5, "H5.eta_diff")
cmp("H5.ci_low", l5, "H5.eta_diff", "ci_low")
cmp("H5.ci_high", h5, "H5.eta_diff", "ci_high")
cmp("H5.p", p5, "H5.p_signedrank", tol="p")
for s, v in sv5.items():
    cmp("H5.site." + s, v, "H5.site." + s)
print("H5 n_sites %d zeros %d n_common %d dropped %s; sites negative %d; pooled-site eta pjmA %.5f scmR %.5f" % (
    n, nz, len(common), [s for s in cnt.index if s not in keep], int((sv5 < 0).sum()), etas["pjmA"].median(), etas["scmR"].median()))
print("H5 site abs-dev K10 / K40 pjmA median %.4f/%.4f scmR %.4f/%.4f" % (
    absdev["pjmA"][10].median(), absdev["pjmA"][40].median(), absdev["scmR"][10].median(), absdev["scmR"][40].median()))

# ---------- Holm ----------
raw = {"H1": p1, "H2": p2, "H3": pt, "H4": pS, "H5": p5}
ph = holm(raw)
for h, v in ph.items():
    cmp(h + ".p_holm", v, h + ".p_holm", tol="p")
print("raw p", raw)
print("holm", ph)
print("H3 decision (mine):", "equivalent" if ph["H3"] < 0.05 else "not shown equivalent")

# ---------- compare ----------
rows = []
bad = 0
for name, (mine, ledv, tol) in res.items():
    diff = abs(mine - ledv)
    if np.isinf(mine) or np.isinf(ledv):
        ok = mine == ledv
    elif np.isnan(ledv):
        ok = False
    else:
        ok = diff <= (1e-9 if tol == "p" else 1e-6 * abs(ledv) + (1e-12 if ledv == 0 else 0))
    bad += (not ok)
    rows.append("%-24s mine=% .10g ledger=% .10g diff=%.2e %s" % (name, mine, ledv, diff, "OK" if ok else "DIFF"))
print("\n".join(rows))
print("TOTAL compared", len(rows), "DIFFS", bad)
