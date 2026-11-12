import csv
import itertools
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJ, "src", "paper"))
import exploratory_keys as ek  # noqa: E402
import derived_keys as dk  # noqa: E402


def _load(name):
    with open(os.path.join(PROJ, "tables", name), encoding="utf-8", newline="") as f:
        return {r["key"]: r for r in csv.DictReader(f)}


def test_spearman_exact_matches_brute_force():
    x = [1, 2, 2, 4, 5, 7, 8]
    y = [3, 1, 4, 1.5, 9, 2, 6]
    rho, p = ek.spearman_exact(x, y)
    rx, ry = ek.rank_avg(x), ek.rank_avg(y)
    assert abs(rho - np.corrcoef(rx, ry)[0, 1]) < 1e-12
    obs = abs(rho)
    c = sum(abs(np.corrcoef(rx, ry[list(pm)])[0, 1]) >= obs - 1e-9 for pm in itertools.permutations(range(7)))
    assert abs(p - c / 5040) < 1e-12


def test_x3_shares():
    d = _load("summary_derived.csv")
    led = _load("summary.csv")
    h3 = {k[8:]: abs(float(r["value"])) for k, r in led.items() if k.startswith("H3.site.")}
    for tag, c in (("m05", .05), ("m10", .10), ("m15", .15)):
        n = sum(v <= np.log(1 + c) for v in h3.values())
        r = d["derived.H3.share_inside_margin." + tag]
        assert abs(float(r["value"]) - n / 11) < 1e-12
        lo, hi = dk.clopper_pearson(n, 11)
        assert abs(float(r["ci_low"]) - lo) < 1e-12 and abs(float(r["ci_high"]) - hi) < 1e-12
    assert d["derived.H3.share_inside_margin.m10"]["value"] == d["derived.H3.share_sites_inside_margin"]["value"]


def test_x2_x4_x6_file():
    e = _load("summary_exploratory.csv")
    led = _load("summary.csv")
    for r in e.values():
        assert r["data_year"] == "2017" and r["freeze_hash"] != "dev-unfrozen"
        assert r["status"] in ("derived", "secondary", "exploratory")
        assert not r["key"].startswith(("H1", "H2", "H3", "H4", "H5"))
    for m in ("pjmA", "scmR", "cgA", "pjm0", "caiso0", "isone0"):
        for kd in ("relMAE", "bias"):
            r = e["derived.T4.%s.%s" % (m, kd)]
            assert float(r["ci_low"]) <= float(r["value"]) <= float(r["ci_high"]) or kd == "bias"
        o, u = (float(e["derived.X4.%s.share_%s" % (m, t)]["value"]) for t in ("overpaid", "underpaid"))
        assert 0 < o < 1 and 0 < u < 1 and o + u <= 1 + 1e-12
    # sign: unadjusted PJM under-pays on hot days (ledger bias median negative), so under-paid share > 0.5
    assert float(led["method.pjm0.R1.bias_median"]["value"]) < 0
    assert float(e["derived.X4.pjm0.share_underpaid"]["value"]) > 0.5
    assert -1 <= float(e["exploratory.x6.rho"]["value"]) <= 1
    assert 0 < float(e["exploratory.x6.p_perm"]["value"]) <= 1
    assert e["exploratory.x6.n_sites"]["value"] == "11"
    assert e["exploratory.x6.rho"]["status"] == "exploratory"


def test_no_key_overlap_across_sources():
    names = ["summary.csv", "summary_secondary.csv", "summary_derived.csv", "summary_dev.csv", "summary_exploratory.csv"]
    seen = {}
    for n in names:
        for k in _load(n):
            assert k not in seen, (k, n, seen[k])
            seen[k] = n


def test_bridge_table_columns():
    with open(os.path.join(PROJ, "tables", "S_bridge.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    led = _load("summary.csv")
    for m in ("pjmA", "scmR", "cgA", "prev"):
        for k in ("nmbe_granderson", "rmse_median"):
            assert "method.%s.R1.%s" % (m, k) in led
    assert any(r["Method"].startswith("CAISO / ISO-NE") for r in rows)
    assert "\resizebox" not in open(os.path.join(PROJ, "tables", "S_bridge.tex"), encoding="utf-8").read()


def test_r4_absdev_sitemedian_equals_fig8a():
    """Values equal what fig_08_dispatch.py plots (its recomputation from events_erosion.pkl, same code path)."""
    import site
    import pandas as pd
    up = site.getusersitepackages()
    if os.path.isdir(up) and up not in sys.path:
        sys.path.append(up)
    sys.path.insert(0, os.path.join(PROJ, "src"))
    from run import adjust, config as C
    e = _load("summary_exploratory.csv")
    ER = pd.read_pickle(os.path.join(PROJ, "results", "run", "events_erosion.pkl"))
    sw, ew = C.WINDOWS["primary"]
    base = {}
    for K, g in ER.groupby("K"):
        g = g.reset_index(drop=True)
        base[K] = (g, adjust.adjusted(g, sw, ew))
    del ER
    key = lambda g: g.site + "|" + g.b + "|" + g.day
    Ks = [10, 20, 30, 40]
    sets = []
    for K in Ks:
        g, bb = base[K]
        sets.append(set(key(g)[np.isfinite(bb["pjmA"]) & np.isfinite(bb["scmR"])]))
    common = set.intersection(*sets)
    for m in ek.ABS_METHODS:
        rows_ = []
        for K in Ks:
            g, bb = base[K]
            ok = key(g).isin(common).values
            rho = (bb[m] - g.Lobs.values) / (C.C_PRIMARY * g.L.values)
            t = pd.DataFrame({"site": g.site, "b": g.b, "rho": rho})[ok]
            rows_.append(t.groupby(["site", "b"]).rho.mean().rename(K))
        fig_vals = (pd.concat(rows_, axis=1) - 1).abs().groupby(level=0).median().median(axis=0)
        for K in Ks:
            r = e["derived.H5.absdev_sitemedian.%s.K%d" % (m, K)]
            assert abs(float(r["value"]) - float(fig_vals[K])) < 1e-9, (m, K)
            assert r["status"] == "derived"


def test_r4_per_c05_c20_keys():
    e = _load("summary_exploratory.csv")
    led = _load("summary.csv")
    ms = [k.split(".")[1] for k in led if k.endswith(".R1.PER_c10_median")]
    assert len(ms) >= 15
    for m in ms:
        c10 = float(led["method.%s.R1.PER_c10_median" % m]["value"])
        v05 = float(e["method.%s.R1.PER_c05_median" % m]["value"])
        v20 = float(e["method.%s.R1.PER_c20_median" % m]["value"])
        assert abs(v05 - 2 * c10) < 1e-12 and abs(v20 - c10 / 2) < 1e-12     # relMAE / c scaling
        s05, s10, s20 = (float(e["method.%s.R1.share_PER_gt_0.5_c05" % m]["value"]),
                         float(led["method.%s.R1.share_PER_gt_0_5" % m]["value"]),
                         float(e["method.%s.R1.share_PER_gt_0.5_c20" % m]["value"]))
        assert s05 >= s10 >= s20
        assert e["method.%s.R1.PER_c05_median" % m]["status"] == "secondary"
