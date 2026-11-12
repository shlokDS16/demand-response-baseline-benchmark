#!/usr/bin/env python
"""exploratory_keys.py - decision D22 additions (X2, X4, X6) -> tables/summary_exploratory.csv.

Read-only inputs: tables/summary.csv, tables/summary_secondary.csv, results/run/events_R1.pkl
(frozen result file of this project; own data, md5-checked) and the frozen package src/run
(adjust, analysis, stats; imported read-only, same calls as src/figures/fig_03_accuracy.py).
Memory: events_R1 is about 20 MB in RAM; the script stops if free RAM is below 0.5 GB.

Keys
  derived.T4.<m>.relMAE.{value,ci_low,ci_high}, derived.T4.<m>.bias.*   (X2; status derived)
      value = median over the 11 site medians of the building statistic, interval = order-statistic
      95 % interval of the 11 site medians (stats.median_ci_order, the H4 construction). The T4 value
      is the building-pooled median, so the two differ slightly; the key says which is which.
  derived.X4.<m>.share_overpaid / share_underpaid (+ n_events)             (X4; status secondary)
      share of supported R1 building-events with e > 0 (over-paid) or e < 0, e = (B - L) / L.
  exploratory.x6.rho, exploratory.x6.p_perm, exploratory.x6.n_sites        (X6; status exploratory)
      Spearman correlation across the sites of H4.site.* p-cross and the site's relMAE gap at p = 0
      (median over buildings of relMAE, pjmA minus scmR, on their common support); exact two-sided
      permutation p over all 11! pairings (average ranks for ties).
  derived.H5.absdev_sitemedian.<m>.K<k>  (R4; status derived; m in pjmA scmR cgA caisoA pjm0, K = 10..40)
      median over sites of the per-site median |rho - 1| (fig 8a); computed from results_state.pkl
      ["erosion"]["tab"] (read-only), the table the figure asserts its recomputation against.
  method.<m>.R1.PER_c05_median / PER_c20_median, method.<m>.R1.share_PER_gt_0.5_c05 / _c20  (R4; secondary)
      same definition as the frozen PER_c10 (src/run/analysis.method_table): building-median relMAE / c and
      the share of supported R1 events with |e| / c > 0.5. The c = 0.10 values are recomputed first and must
      equal the ledger rows method.<m>.R1.PER_c10_median and share_PER_gt_0_5 (else the script stops).
"""
import csv
import itertools
import math
import os
import site
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SELF = "src/paper/exploratory_keys.py"
COLS = ["key", "value", "ci_low", "ci_high", "p_raw", "p_holm", "n_sites", "n_buildings",
        "n_events", "source_file", "status", "family_id", "hypothesis_id",
        "estimand_version", "data_year", "freeze_hash", "support_rule"]
MIN_FREE_GB = 0.5


def need_ram():
    import psutil
    free = psutil.virtual_memory().available / 1e9
    if free < MIN_FREE_GB:
        raise SystemExit("free RAM %.2f GB below %.1f GB; stopping" % (free, MIN_FREE_GB))


def rank_avg(x):
    import numpy as np
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman_exact(x, y):
    """Spearman rho (Pearson on average ranks) and exact two-sided permutation p over all n! pairings."""
    import numpy as np
    n = len(x)
    rx, ry = rank_avg(x), rank_avg(y)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    # sum_i rx_i ry_pi(i) is monotone in rho (all rank sums and sums of squares are fixed)
    obs = float(rx @ ry)
    mean = n * rx.mean() * ry.mean()
    k = 2                                    # enumerate ordered pairs, permute the other n-2 by table
    perms = np.array(list(itertools.permutations(range(n - k))), dtype=np.int8)
    cnt = 0
    tot = 0
    tol = 1e-9
    for pos in itertools.permutations(range(n), k):
        rest = [i for i in range(n) if i not in pos]
        base = sum(rx[pos[j]] * ry[j] for j in range(k))
        # assign ry[k:] (as values) to rx[rest] in every order
        vals = ry[k:][perms]                          # (m!, n-k)
        s = base + vals @ rx[rest]
        cnt += int((np.abs(s - mean) >= abs(obs - mean) - tol).sum())
        tot += len(s)
    assert tot == math.factorial(n)
    return rho, cnt / tot


ABS_METHODS = ("pjmA", "scmR", "cgA", "caisoA", "pjm0")
ABS_KS = (10, 20, 30, 40)


def absdev_sitemedian(state_path):
    """{m: {K: value}}: median over sites of the per-site median |rho - 1| (fig_08_dispatch.py panel a)."""
    import pickle
    with open(state_path, "rb") as fh:          # own frozen result file, read-only
        tab = pickle.load(fh)["erosion"]["tab"]
    out = {}
    for m in ABS_METHODS:
        sm = (tab[m] - 1).abs().groupby(level=0).median().median(axis=0)
        out[m] = {int(k): float(v) for k, v in sm.items()}
    return out


def build(root=ROOT):
    up = site.getusersitepackages()
    if os.path.isdir(up) and up not in sys.path:
        sys.path.append(up)
    sys.path.insert(0, os.path.join(root, "src"))
    import numpy as np
    import pandas as pd
    from run import adjust, analysis as AN, config as C, stats as ST
    need_ram()
    rows = {}
    for f in ("summary.csv", "summary_secondary.csv"):
        with open(os.path.join(root, "tables", f), encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                rows.setdefault(r["key"], r)
    fh_ = rows["H3.margin"]["freeze_hash"]
    out = []

    def add(key, value, status, hyp="none", ci=("", ""), n_s="", n_e=""):
        out.append({"key": key, "value": repr(float(value)) if not float(value).is_integer() else repr(int(value)),
                    "ci_low": "" if ci[0] == "" else repr(float(ci[0])),
                    "ci_high": "" if ci[1] == "" else repr(float(ci[1])),
                    "p_raw": "", "p_holm": "", "n_sites": n_s, "n_buildings": "", "n_events": n_e,
                    "source_file": SELF, "status": status, "family_id": "none", "hypothesis_id": hyp,
                    "estimand_version": "PREREG-R2", "data_year": "2017", "freeze_hash": fh_,
                    "support_rule": "none"})

    R1 = pd.read_pickle(os.path.join(root, "results", "run", "events_R1.pkl"))   # frozen own result file
    s, e = C.WINDOWS["primary"]
    b = adjust.adjusted(R1, s, e)
    methods = [m for m in ("prev pjm0 pjmA caiso0 caisoA ny0 nyA isone0 isoneA dm0 dmA wm0 wmA m3 mid8 "
                           "cg0 cgA scmR scmC").split()
               if m in b and "method.%s.R1.relMAE_median" % m in rows]
    gap = {}
    for m in methods:
        need_ram()
        ok = AN.pair_events(R1, b, [m])
        rel = AN.bld_stat(R1, b, m, ok, "relMAE")
        assert abs(np.median(rel.values) - float(rows["method.%s.R1.relMAE_median" % m]["value"])) < 1e-9, m
        for kind in ("relMAE", "bias"):
            v = rel if kind == "relMAE" else AN.bld_stat(R1, b, m, ok, "bias")
            sm = v.dropna().groupby(level=0).median()
            lo, hi, conf = ST.median_ci_order(sm.values)
            add("derived.T4.%s.%s" % (m, kind), float(np.median(sm.values)), "derived", ci=(lo, hi),
                n_s=str(len(sm)))
        err = (b[m] - R1.L.values) / R1.L.values
        ee = err[ok]
        add("derived.X4.%s.share_overpaid" % m, float((ee > 0).mean()), "secondary", n_e=str(int(ok.sum())))
        add("derived.X4.%s.share_underpaid" % m, float((ee < 0).mean()), "secondary", n_e=str(int(ok.sum())))
        if m in ("pjmA", "scmR"):
            gap[m] = rel
        # R4: PER at c = 0.05 and 0.20 (definition of analysis.method_table); c = 0.10 must reproduce the ledger
        e_ev = np.abs(err)[ok]
        c10 = float(np.median(rel.values) / C.C_PRIMARY)
        s10 = float((e_ev / C.C_PRIMARY > 0.5).mean())
        assert abs(c10 - float(rows["method.%s.R1.PER_c10_median" % m]["value"])) < 1e-12, ("PER c10 median", m)
        assert abs(s10 - float(rows["method.%s.R1.share_PER_gt_0_5" % m]["value"])) < 1e-12, ("PER c10 share", m)
        n_ev = str(int(ok.sum()))
        for tag, c in (("c05", 0.05), ("c20", 0.20)):
            add("method.%s.R1.PER_%s_median" % (m, tag), float(np.median(rel.values) / c), "secondary", n_e=n_ev)
            add("method.%s.R1.share_PER_gt_0.5_%s" % (m, tag), float((e_ev / c > 0.5).mean()), "secondary", n_e=n_ev)
    # R4: site-median absolute estimation error by K (fig 8a)
    ad = absdev_sitemedian(os.path.join(root, "results", "run", "results_state.pkl"))
    for m in ABS_METHODS:
        for k in ABS_KS:
            add("derived.H5.absdev_sitemedian.%s.K%d" % (m, k), ad[m][k], "derived", n_s="11")
    # X6 (common support of pjmA and scmR)
    ok = AN.pair_events(R1, b, ["pjmA", "scmR"])
    rp = AN.bld_stat(R1, b, "pjmA", ok, "relMAE").groupby(level=0).median()
    rs = AN.bld_stat(R1, b, "scmR", ok, "relMAE").groupby(level=0).median()
    sites = sorted(set(k[len("H4.site."):] for k in rows if k.startswith("H4.site.")))
    pc = np.array([float(rows["H4.site.%s" % t]["value"]) for t in sites])
    g = np.array([float(rp[t] - rs[t]) for t in sites])
    rho, p = spearman_exact(pc, g)
    add("exploratory.x6.rho", rho, "exploratory", n_s=str(len(sites)))
    add("exploratory.x6.p_perm", p, "exploratory", n_s=str(len(sites)))
    add("exploratory.x6.n_sites", len(sites), "exploratory")
    return out


def main():
    out = build()
    path = os.path.join(ROOT, "tables", "summary_exploratory.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    for r in out:
        if r["key"].startswith(("exploratory", "derived.H5.absdev_sitemedian.pjmA", "derived.H5.absdev_sitemedian.scmR",
                                "method.pjmA.R1.PER_c05", "method.pjmA.R1.share_PER_gt_0.5_c05", "derived.X4.pjmA", "derived.X4.scmR", "derived.X4.cgA",
                                "derived.X4.pjm0", "derived.T4.pjmA")):
            print(r["key"], r["value"], r["ci_low"], r["ci_high"])
    print("wrote", path, len(out), "keys")


if __name__ == "__main__":
    main()
