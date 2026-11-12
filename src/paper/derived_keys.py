#!/usr/bin/env python
"""derived_keys.py - count and derived keys for the manuscript (SPEC s9.2).

Reads ONLY tables/summary.csv and tables/summary_secondary.csv (plus, for two keys,
the frozen result pickle results/run/events_R1.pkl, read-only) and writes
tables/summary_derived.csv with the same columns as summary.csv.

Thresholds are the frozen design's:
  H3  margin  = the ledger row H3.margin (log 1.10)
  H4  threshold 0.10 (PREREG tau; the break-even p-cross is compared with 10 %)
  H5  sign of the per-site slope difference (below 0 = SCM-ridge erodes faster)
Usage: python src/paper/derived_keys.py [--no-pickle]
"""
import argparse
import csv
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLES = os.path.join(ROOT, "tables")
H4_THRESHOLD = 0.10
SELF = "src/paper/derived_keys.py"
COLS = ["key", "value", "ci_low", "ci_high", "p_raw", "p_holm", "n_sites", "n_buildings",
        "n_events", "source_file", "status", "family_id", "hypothesis_id",
        "estimand_version", "data_year", "freeze_hash", "support_rule"]


def read_rows(paths):
    rows = {}
    for p in paths:
        with open(p, "r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows.setdefault(r["key"], r)
    return rows


def site_values(rows, prefix):
    out = {}
    for k, r in rows.items():
        if k.startswith(prefix + ".site.") and r["data_year"].strip() == "2017":
            out[k[len(prefix) + 6:]] = float(r["value"])
    return out


def pickle_counts(root):
    """(n_dm0_differ, eagle_events_without_cg) from the frozen R1 pickle; None if unavailable."""
    path = os.path.join(root, "results", "run", "events_R1.pkl")
    if not os.path.isfile(path):
        return None
    import site
    up = site.getusersitepackages()
    if os.path.isdir(up) and up not in sys.path:
        sys.path.append(up)
    import numpy as np
    import pandas as pd
    # the project's own frozen result file (md5-checked in FREEZE_MANIFEST), not untrusted input
    d = pd.read_pickle(path)
    differ = int((~np.isclose(d["dm0"].astype(float), d["caiso0"].astype(float),
                              rtol=0, atol=1e-12)).sum())
    no_cg = d[d["ndon"] < 5]            # donor minimum 5 (PREREG; SPEC D1)
    eagle = int((no_cg["site"] == "Eagle").sum())
    return differ, eagle, int(len(no_cg))


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def clopper_pearson(k, n, alpha=0.05):
    """Exact two-sided (1-alpha) interval for a binomial proportion (bisection, stdlib only)."""
    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    # lower: P(X >= k | p) = alpha/2 ; upper: P(X <= k | p) = alpha/2
    low = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) >= alpha / 2)
    up = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) <= alpha / 2)
    return low, up


def order_stat_coverage(n, alpha=0.05):
    """Exact coverage of the order-statistic median interval [x_(k), x_(n+1-k)] used by stats.median_ci_order."""
    k = 0
    for kk in range(1, n // 2 + 1):
        if sum(math.comb(n, i) for i in range(0, kk)) / 2.0 ** n <= alpha / 2 + 1e-12:
            k = kk
    if k == 0:
        return 1.0
    return 1 - 2 * sum(math.comb(n, i) for i in range(0, k)) / 2.0 ** n


def build(root=ROOT, use_pickle=True):
    tdir = os.path.join(root, "tables")
    rows = read_rows([os.path.join(tdir, "summary.csv"),
                      os.path.join(tdir, "summary_secondary.csv")])
    fh = rows["H3.margin"]["freeze_hash"]
    margin = float(rows["H3.margin"]["value"])
    n_sites = int(float(rows["sample.n_sites"]["value"]))
    out = []

    def add(key, value, hyp, n_s="", n_e="", note="derived", ci=("", "")):
        out.append({"key": key, "value": repr(int(value)) if float(value) == int(value) else repr(value),
                    "ci_low": ci[0] if ci[0] == "" else repr(ci[0]), "ci_high": ci[1] if ci[1] == "" else repr(ci[1]), "p_raw": "", "p_holm": "",
                    "n_sites": n_s, "n_buildings": "", "n_events": n_e,
                    "source_file": SELF, "status": "derived", "family_id": "none",
                    "hypothesis_id": hyp, "estimand_version": "PREREG-R2",
                    "data_year": "2017", "freeze_hash": fh, "support_rule": "none"})

    h3 = site_values(rows, "H3")
    h4 = site_values(rows, "H4")
    h5 = site_values(rows, "H5")
    h1 = site_values(rows, "H1")
    h2 = site_values(rows, "H2")
    for name, d in (("H1", h1), ("H2", h2), ("H3", h3), ("H4", h4), ("H5", h5)):
        assert len(d) == n_sites, (name, len(d), n_sites)
    add("derived.H3.n_sites_outside_margin", sum(abs(v) > margin for v in h3.values()), "H3", n_sites)
    add("derived.H4.n_sites_pcross_zero", sum(v == 0.0 for v in h4.values()), "H4", n_sites)
    add("derived.H4.n_sites_pcross_lt_threshold", sum(v < H4_THRESHOLD for v in h4.values()), "H4", n_sites)
    add("derived.H5.n_sites_scmR_faster", sum(v < 0 for v in h5.values()), "H5", n_sites)
    add("derived.H1.n_sites_negative", sum(v < 0 for v in h1.values()), "H1", n_sites)
    add("derived.H2.n_sites_negative", sum(v < 0 for v in h2.values()), "H2", n_sites)
    n_in = sum(abs(v) <= margin for v in h3.values())
    add("derived.H3.share_sites_inside_margin", n_in / n_sites, "H3", n_sites,
        ci=clopper_pearson(n_in, n_sites))
    for tag, c in (("m05", 0.05), ("m10", 0.10), ("m15", 0.15)):      # X3: descriptive, no TOST rerun
        n_c = sum(abs(v) <= math.log(1 + c) for v in h3.values())
        add("derived.H3.share_inside_margin." + tag, n_c / n_sites, "H3", n_sites, ci=clopper_pearson(n_c, n_sites))
    add("derived.H4.max_site_pcross", max(h4.values()), "H4", n_sites)
    add("derived.H4.ci_exact_coverage", order_stat_coverage(n_sites), "H4", n_sites)
    nk = sum(float(rows["H5.absdev.scmR.K%d" % k]["value"]) > float(rows["H5.absdev.pjmA.K%d" % k]["value"])
             for k in (10, 20, 30, 40))
    add("derived.H5.n_K_scmR_less_accurate", nk, "H5", n_sites)
    add("derived.incr_sens.ratio_2h_4h", float(rows["incr_sens.2h.p0.1"]["value"]) /
        float(rows["incr_sens.4h.p0.1"]["value"]), "H4", n_sites)
    # derived.precool.share_daily_energy_4h: NOT computable (no daily energy in ledgers or result pickles)
    n_r1 = int(float(rows["sample.n_events.R1"]["value"]))
    n_h3 = int(float(rows["H3.logratio.cgA_pjmA"]["n_events"]))
    missing = n_r1 - n_h3
    add("derived.cgA.n_events_missing_eagle", missing, "H3", 1, n_r1)
    if use_pickle:
        pc = pickle_counts(root)
        if pc is not None:
            differ, eagle, total = pc
            assert total == eagle == missing, (
                "pickle (ndon<5: %d, Eagle %d) disagrees with ledger difference %d"
                % (total, eagle, missing))
            add("derived.dm0.n_events_differ", differ, "none", n_sites, n_r1)
    return out


def write(out, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pickle", action="store_true",
                    help="skip derived.dm0.n_events_differ (needs events_R1.pkl)")
    ap.add_argument("--root", default=ROOT)
    a = ap.parse_args(argv)
    out = build(a.root, use_pickle=not a.no_pickle)
    path = os.path.join(a.root, "tables", "summary_derived.csv")
    write(out, path)
    for r in out:
        print("%-45s %s" % (r["key"], r["value"]))
    print("wrote %s (%d keys)" % (path, len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
