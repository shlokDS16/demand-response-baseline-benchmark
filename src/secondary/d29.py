"""D29 analysis additions (research/panel/RISK_SYNTHESIS_D29.md items 1, 2, 4, 6, 7, 8, 9). Definitions: logs/IMPL_D29_keys.md.

Writes results/secondary/2017/d29.rows.csv (family_id 'secondary', empty p_holm, status derived | secondary | exploratory |
descriptive as stated per key) and, with --collect, rebuilds tables/summary_secondary.csv. Also relabels the status of the PREREG s10
secondary reruns (h4_win1620, h5_win1620, dst_alt, nonevent, flat) to 'secondary' (--relabel; idempotent; the change list goes to
results/secondary/2017/d29_relabel_log.csv, which collect() does not read).

Inputs are read-only: tables/summary*.csv, results/frozen/event_dates.csv, results/run/{events_R1.pkl,results_state.pkl}. The 16:00-20:00
dispatch frame is rebuilt in process with the exploratory code path (the frozen dispatch code is imported, not edited) because its
per-building table is not stored; the rebuild must reproduce the ledger's 16-20 site values exactly or the script stops.

Run (project root): python -I src/secondary/d29.py [--relabel] [--collect]
"""
import argparse
import math
import os
import site
import sys

up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../src, needed under python -I

import numpy as np   # noqa: E402
import pandas as pd   # noqa: E402
from scipy.stats import beta as _beta, spearmanr   # noqa: E402

from run import config as C, ledger as LD, stats as ST   # noqa: E402
from secondary import common as CM   # noqa: E402

SOURCE = "src/secondary/d29.py"
OUT_NAME = "d29.rows.csv"
SECONDARY_FILES = ("expl_h4_win1620", "expl_h5_win1620", "expl_dst_alt", "nonevent", "flat")
LEDGERS = ("summary.csv", "summary_secondary.csv", "summary_exploratory.csv", "summary_derived.csv")
SITES = ("Bear", "Bull", "Cockatoo", "Eagle", "Fox", "Hog", "Lamb", "Peacock", "Rat", "Robin", "Wolf")
KS = (10, 20, 30, 40)
EPISODE_GAP_DAYS = 3        # consecutive event days <= 3 calendar days apart belong to one heat episode


# ----------------------------------------------------------------------------- pure helpers (unit-tested)
def cp_lower(k, n, alpha=0.05):
    """One-sided Clopper-Pearson lower confidence bound (level 1 - alpha) for a binomial share, k successes of n."""
    if k <= 0:
        return 0.0
    if k >= n:
        return float(alpha ** (1.0 / n))
    return float(_beta.ppf(alpha, k, n - k + 1))


def pred_int(x):
    """Distribution-free prediction interval [min, max] for one new exchangeable draw; coverage (n - 1) / (n + 1)."""
    x = np.asarray(x, float)
    n = len(x)
    return float(x.min()), float(x.max()), (n - 1.0) / (n + 1.0)


def episodes(dates, gap=EPISODE_GAP_DAYS):
    """Number of heat episodes: sorted distinct dates, a new episode starts when the gap to the previous date exceeds `gap` days."""
    d = sorted(set(pd.to_datetime(list(dates))))
    if not d:
        return 0
    return 1 + sum(1 for a, b in zip(d[:-1], d[1:]) if (b - a).days > gap)


def holm_adjust(p):
    """Holm step-down adjusted p-values (dict name -> p), the frozen src/run/stats.holm."""
    return ST.holm(p)


def xwin_contrast(v1418, v1620):
    """Per-site difference d_s = v1418_s - v1620_s of the H5 site slope contrasts (negative = SCM-ridge's growth is the larger one
    at 14-18 relative to 16-20). Exact two-sided signed-rank (frozen stats), HL estimate and exact interval."""
    sites = sorted(v1418)
    assert sites == sorted(v1620)
    d = np.array([v1418[s] - v1620[s] for s in sites])
    sr = ST.signed_rank(d, "two")
    est, lo, hi, conf = ST.hl_ci(d)
    a = np.array([v1418[s] for s in sites])
    b = np.array([v1620[s] for s in sites])
    rho = float(spearmanr(a, b).statistic)
    return dict(sites=sites, d=d, est=est, lo=lo, hi=hi, conf=conf, p=sr["p"], n=sr["n"], n_zero=sr["n_zero"],
                n_stronger_1418=int((d < 0).sum()), n_sign_agree=int((np.sign(a) == np.sign(b)).sum()), spearman=rho)


def holm_h4_tip(p_other, n_sites=11):
    """Smallest k (sites with p-cross below the threshold, of n_sites, no ties) for which H4's sign-test p still passes Holm
    together with the other four frozen raw p-values (dict name -> p). Returns (k_min, p_at_k_min)."""
    for k in range(0, n_sites + 1):
        p = ST.sign_test(np.array([0.0] * k + [1.0] * (n_sites - k)), 0.5, "less")["p"]     # k sites below, rest above
        allp = dict(p_other)
        allp["H4"] = p
        adj = ST.holm(allp)
        if adj["H4"] < 0.05 and all(adj[n] < 0.05 for n in allp):
            return k, float(p)
    return None, float("nan")


# ----------------------------------------------------------------------------- ledger access and output rows
def read_ledgers():
    fr = [pd.read_csv(C.ROOT / "tables" / f) for f in LEDGERS]
    df = pd.concat(fr, ignore_index=True).drop_duplicates("key")
    return df.set_index("key")


class Rows:
    """Collects ledger rows with the frozen column set; p_holm is never filled."""

    def __init__(self, fh):
        self.fh = fh
        self.r = {}

    def add(self, key, value, status, ci_low=None, ci_high=None, p_raw=None, n_sites=None, n_buildings=None, n_events=None):
        assert status in ("derived", "secondary", "exploratory", "descriptive"), status
        assert key not in self.r, "duplicate key " + key
        if isinstance(value, (np.floating, np.integer)):
            value = value.item()
        self.r[key] = dict(key=key, value=value, ci_low=ci_low, ci_high=ci_high, p_raw=p_raw, p_holm=None, n_sites=n_sites,
                           n_buildings=n_buildings, n_events=n_events, source_file=SOURCE, status=status, family_id=CM.FAMILY,
                           hypothesis_id="none", estimand_version=LD.ESTIMAND_VERSION, data_year=2017, freeze_hash=self.fh,
                           support_rule="none")

    def frame(self):
        return pd.DataFrame(list(self.r.values()), columns=LD.COLUMNS)


def site_vals(L, prefix):
    out = {}
    for s in SITES:
        k = "%s.site.%s" % (prefix, s)
        out[s] = float(L.loc[k, "value"])
    return out


# ----------------------------------------------------------------------------- item 1 and 8: H5 levels, relative growth
def h5_tabs_1620(L):
    """Rebuild the 16-20 dispatch frame, run the frozen analysis.h5, and require the ledger values to be reproduced exactly."""
    from run import analysis as AN, data as D
    from secondary import exploratory as EX
    Y = D.build_year(2017)
    w16 = C.WINDOWS["w1620"]
    ER = EX.erosion_frame(Y, w16, list(C.SITES))
    res = AN.h5(ER, w16[0], w16[1])
    c = res["contrast_abs"]["pjmA"]
    for s, v in c["site_values"].items():
        assert v == float(L.loc["exploratory.h5_win1620.site." + s, "value"]), ("16-20 site value not reproduced", s)
    assert c["est"] == float(L.loc["exploratory.h5_win1620.eta_diff.pjmA_minus_scmR", "value"])
    for m in ("pjmA", "scmR"):
        for K, v in res["methods"][m]["abs_dev_pooled"].items():
            assert abs(v - float(L.loc["exploratory.h5_win1620.absdev.%s.K%d" % (m, K), "value"])) < 1e-12, (m, K)
    return res["tab"]


def sitemedian_table(tab, m):
    """site x K table of the site median of |rho_b - 1| (the construction of derived.H5.absdev_sitemedian.*)."""
    return (tab[m] - 1).abs().groupby(level=0).median()


def item1(R, L, tab1418, tab1620):
    for w, tab in (("w1418", tab1418), ("w1620", tab1620)):
        sm = {m: sitemedian_table(tab, m) for m in ("pjmA", "scmR")}
        med = {m: sm[m].median(axis=0) for m in sm}
        if w == "w1418":                                       # existing keys must be reproduced
            for m in sm:
                for K in KS:
                    k = "derived.H5.absdev_sitemedian.%s.K%d" % (m, K)
                    assert abs(float(med[m][K]) - float(L.loc[k, "value"])) < 1e-9, k
        else:
            for m in sm:
                for K in KS:
                    R.add("derived.H5.absdev_sitemedian_w1620.%s.K%d" % (m, K), float(med[m][K]), "derived", n_sites=len(sm[m]))
        lower_sm = int(sum(med["pjmA"][K] < med["scmR"][K] for K in KS))
        R.add("derived.H5.levels_pjmA_lower_all_K." + w, lower_sm, "derived", n_sites=len(sm["pjmA"]))
        for K in KS:
            R.add("derived.H5.n_sites_pjmA_lower.K%d.%s" % (K, w), int((sm["pjmA"][K] < sm["scmR"][K]).sum()), "derived",
                  n_sites=len(sm["pjmA"]))
        pooled_pre = "H5.absdev.%s.K%d" if w == "w1418" else "exploratory.h5_win1620.absdev.%s.K%d"
        pool = {m: {K: float(L.loc[pooled_pre % (m, K), "value"]) for K in KS} for m in ("pjmA", "scmR")}
        R.add("derived.H5.levels_pjmA_lower_all_K_pooled." + w, int(sum(pool["pjmA"][K] < pool["scmR"][K] for K in KS)), "derived")
        for m in ("pjmA", "scmR"):
            R.add("derived.H5.relgrowth_K10_K40_pooled.%s.%s" % (m, w), pool[m][40] / pool[m][10] - 1.0, "derived")
            R.add("derived.H5.relgrowth_K10_K40_sitemedian.%s.%s" % (m, w), float(med[m][40] / med[m][10] - 1.0), "derived",
                  n_sites=len(sm[m]))
    # C3 (FIX_audit_v3): sites where SCM-ridge's error grows faster = site slope contrast < 0 (same rule as derived.H5.n_sites_scmR_faster)
    for w, pre in (("w1418", "H5"), ("w1620", "exploratory.h5_win1620")):
        R.add("derived.H5.n_sites_scmR_faster." + w, int(sum(v < 0 for v in site_vals(L, pre).values())), "derived", n_sites=len(SITES))


# ----------------------------------------------------------------------------- item 2: cross-window contrast
def item2(R, L):
    v1 = site_vals(L, "H5")
    v2 = site_vals(L, "exploratory.h5_win1620")
    x = xwin_contrast(v1, v2)
    pre = "exploratory.h5_window_contrast."
    R.add(pre + "eta_diff_1418_minus_1620", x["est"], "exploratory", ci_low=x["lo"], ci_high=x["hi"], n_sites=x["n"])
    R.add(pre + "ci_conf", x["conf"], "exploratory")
    R.add(pre + "p_signedrank_two_sided_unadjusted", x["p"], "exploratory", p_raw=x["p"], n_sites=x["n"])
    R.add(pre + "n_sites_stronger_1418", x["n_stronger_1418"], "exploratory", n_sites=x["n"])
    R.add(pre + "n_sign_agree", x["n_sign_agree"], "exploratory", n_sites=x["n"])
    R.add(pre + "spearman_rho", x["spearman"], "exploratory", n_sites=x["n"])
    R.add(pre + "definition", "per-site H5 slope contrast (pjmA minus scmR, site-median |rho-1| slope over K) at 14-18 minus at 16-20; "
          "exact two-sided signed-rank, HL estimate with exact interval; stronger at 14-18 = site difference < 0", "exploratory")
    for s, d in zip(x["sites"], x["d"]):
        R.add(pre + "site." + s, float(d), "exploratory")
    return x


# ----------------------------------------------------------------------------- item 4: event days and heat episodes
def item4(R, R1):
    ev = pd.read_csv(C.ROOT / "results" / "frozen" / "event_dates.csv", parse_dates=["date"])
    e = ev[(ev.year == 2017) & (ev.rule == "R1") & (ev["primary"])]
    out = {}
    for s in SITES:
        des = e[e.site_id == s]
        sc = R1[R1.site == s]
        days = sorted(pd.to_datetime(sc.day.unique()))
        assert set(days) <= set(des.date), s
        nb = sc.groupby("day").b.nunique()
        tmax = des.set_index("date").tmax_c
        R.add("sample.event_days." + s, len(days), "descriptive", n_sites=1)
        R.add("sample.event_days_designated." + s, int(des.date.nunique()), "descriptive", n_sites=1)
        R.add("sample.heat_episodes." + s, episodes(days), "descriptive", n_sites=1)
        R.add("sample.heat_episodes_designated." + s, episodes(des.date), "descriptive", n_sites=1)
        R.add("sample.event_days_table." + s, ";".join("%s:%.1fC:%db" % (d.date(), tmax[d], nb[d.strftime("%Y-%m-%d")] if d.strftime("%Y-%m-%d") in nb.index else nb[d])
                                                        for d in days), "descriptive", n_sites=1)
        out[s] = (len(days), int(des.date.nunique()), episodes(days), episodes(des.date))
    R.add("sample.event_days.total", sum(v[0] for v in out.values()), "descriptive", n_sites=len(out))
    R.add("sample.heat_episodes.definition", "event days of a site sorted by date; a new heat episode starts when the gap to the previous event day exceeds %d "
          "calendar days (so days at most %d days apart share an episode). event_days = distinct R1 days with at least one scored building-event "
          "(results/run/events_R1.pkl); event_days_designated = the 10 R1 days of results/frozen/event_dates.csv (primary flag), of which Lamb has "
          "only 4 with scored buildings" % (EPISODE_GAP_DAYS, EPISODE_GAP_DAYS), "descriptive")
    return out


# ----------------------------------------------------------------------------- item 5: 11-site floor
def item5(R, L):
    n = len(SITES)
    k_h4 = int(L.loc["derived.H4.n_sites_pcross_lt_threshold", "value"])
    k_h5 = int(L.loc["derived.H5.n_sites_scmR_faster", "value"])
    k_h1 = int(L.loc["derived.H1.n_sites_negative", "value"])
    k_h2 = int(L.loc["derived.H2.n_sites_negative", "value"])
    for h, k in (("H1", k_h1), ("H2", k_h2), ("H4", k_h4), ("H5", k_h5)):
        R.add("derived.%s.prev_share_k" % h, k, "derived", n_sites=n)
        R.add("derived.%s.prev_share_lb" % h, cp_lower(k, n), "derived", n_sites=n)
    R.add("derived.prev_share_lb.definition", "one-sided 95 % Clopper-Pearson lower bound for the share of exchangeable sites showing the stated "
          "direction (H1, H2: delta/log-ratio below 0; H4: site p-cross below 0.10; H5: slope contrast below 0 = SCM-ridge error grows faster); "
          "BDG2 sites are not a random sample, so the bound is conditional on exchangeability", "derived")
    for h, pre in (("H3", "H3"), ("H4", "H4"), ("H5", "H5")):
        v = np.array(list(site_vals(L, pre).values()))
        lo, hi, cov = pred_int(v)
        R.add("derived.%s.pred_int" % h, cov, "derived", ci_low=lo, ci_high=hi, n_sites=n)
    R.add("derived.pred_int.definition", "value = coverage (n-1)/(n+1) = 10/12 of [min, max] of the 11 site values for one new exchangeable site; "
          "ci_low = min, ci_high = max", "derived")
    pc = np.array(list(site_vals(L, "H4").values()))
    mx = float(pc.max())
    assert abs(mx - float(L.loc["derived.H4.max_site_pcross", "value"])) < 1e-6
    R.add("derived.H4.tip_threshold", mx, "derived", n_sites=n)
    pother = {h: float(L.loc[k, "value"]) for h, k in (("H1", "H1.p_signedrank"), ("H2", "H2.p_signedrank"), ("H3", "H3.p_tost"),
                                                        ("H5", "H5.p_signedrank"))}
    kmin, pk = holm_h4_tip(pother)
    srt = np.sort(pc)
    R.add("derived.H4.tip_k_min_holm", kmin, "derived", n_sites=n)
    R.add("derived.H4.tip_p_sign_at_k_min", pk, "derived")
    R.add("derived.H4.tip_threshold_holm", float(srt[kmin - 1]), "derived", n_sites=n)
    R.add("derived.H4.tip.definition", "tip_threshold = largest site p-cross: for any pre-set threshold above it all 11 sites are below and the sign test "
          "is unchanged (2^-11). tip_k_min_holm = fewest sites below the threshold for which the H4 sign-test p still passes Holm with the other four "
          "frozen p-values; tip_threshold_holm = that k-th smallest site p-cross: the Holm decision for H4 is unchanged for any threshold above it", "derived")


# ----------------------------------------------------------------------------- item 6: within-family Holm
def item6(R, L):
    for tag, pre in (("H2s", "H2s.logratio."), ("H1s", "H1s.delta_bias.")):
        rules = ("ny", "caiso", "isone")
        p = {r: float(L.loc[pre + r, "p_raw"]) for r in rules}
        adj = holm_adjust(p)
        for r in rules:
            R.add("%s.p_holm_family.%s" % (tag, r), adj[r], "secondary", p_raw=p[r], n_sites=11)
    p6 = {}
    for tag, pre in (("H2s", "H2s.logratio."), ("H1s", "H1s.delta_bias.")):
        for r in ("ny", "caiso", "isone"):
            p6[tag + "." + r] = float(L.loc[pre + r, "p_raw"])
    adj6 = holm_adjust(p6)
    for k, v in adj6.items():
        tag, r = k.split(".")
        R.add("%s.p_holm_family6.%s" % (tag, r), v, "secondary", p_raw=p6[k], n_sites=11)
    R.add("H2s.p_holm.definition", "PREREG s6: 'Secondary rule family (NYISO, CAISO, ISO-NE) for H1 and H2 endpoints, Holm within that family'. "
          "p_holm_family = Holm over the three rules of one endpoint (m = 3); p_holm_family6 = sensitivity reading, one family of six (3 rules x "
          "H1s, H2s, m = 6). Inputs: exact one-sided signed-rank p of the ledger rows H1s.delta_bias.<rule> and H2s.logratio.<rule>; "
          "the value column is the adjusted p, p_raw the raw p; no confirmatory p_holm is touched", "secondary")


# ----------------------------------------------------------------------------- item 7: practitioner units
def item7(R, L, R1):
    from run import adjust, analysis as AN
    s, e = C.WINDOWS["primary"]
    c = C.C_PRIMARY
    m = np.vstack(R1["morning"].values).astype(float)
    shaped = m[:, 2:6].sum(1)
    d = pd.DataFrame({"site": R1.site.values, "b": R1.b.values, "S": shaped, "W": R1.L.values.astype(float)})
    bl = d.groupby(["site", "b"])[["S", "W"]].median()
    site_S = bl.S.groupby(level=0).median()
    site_W = bl.W.groupby(level=0).median()
    for st in SITES:                                            # reproduce X5's shaped-hours load
        assert abs(site_S[st] - float(L.loc["exploratory.x5.site_shaped_load_kwh." + st, "value"])) < 1e-6, st
    pcs = site_vals(L, "H4")
    pool_p = float(L.loc["H4.pcross.pjmA_scmR.4h", "value"])
    share = {st: pcs[st] * site_S[st] / (c * site_W[st]) for st in SITES}
    pooled_share = pool_p * float(bl.S.median()) / (c * float(bl.W.median()))
    sv = np.array(list(share.values()))
    R.add("derived.H4.energy_offset_share.median_site", float(np.median(sv)), "derived", n_sites=11)
    R.add("derived.H4.energy_offset_share.min_site", float(sv.min()), "derived")
    R.add("derived.H4.energy_offset_share.max_site", float(sv.max()), "derived")
    R.add("derived.H4.energy_offset_share.pooled", pooled_share, "derived")
    R.add("derived.H4.window_load_kwh.pooled", float(bl.W.median()), "derived")
    for st in SITES:
        R.add("derived.H4.energy_offset_share.site." + st, float(share[st]), "derived")
        R.add("derived.H4.window_load_kwh.site." + st, float(site_W[st]), "derived")
    R.add("derived.H4.energy_offset_share.definition", "p-cross x shaped-hours load (hours s-4..s-1, kWh, as X5) / (c x window load, hours s..e-1 = 14-18, "
          "kWh) with c = 0.10: the share of the shed energy that a pre-event load increase of the break-even size adds back. Site load = median over "
          "buildings of the median over events (X5 construction, window load = frozen R1 column L); pooled = building-pooled medians with the pooled "
          "p-cross; sites with p-cross 0 (Eagle, Lamb) give 0", "derived")
    # (b) over-payment multiplier: payment = B - (1 - c) L, true shed = c L  =>  payment / true shed = 1 + bias / c
    b0 = adjust.adjusted(R1, s, e)
    okp = AN.pair_events(R1, b0, ["pjmA", "scmR"])
    okp, _ = AN.apply_site_support(R1, okp, C.MIN_SUPPORT)
    Rp = R1[okp].reset_index(drop=True)
    grid = sorted(set([0.0, 0.1, pool_p] + [float(v) for v in pcs.values()]))
    tabs, bi = AN.precool_tables(Rp, s, e, ["pjmA"], "4h", grid)
    B = bi["pjmA"]
    # reproduce the ledger's pooled bias at p = 0 and p = 0.10
    assert abs(float(B[0.0].median()) - float(L.loc["precool.bias.pjmA.4h.p0", "value"])) < 1e-9
    assert abs(float(B[0.1].median()) - float(L.loc["precool.bias.pjmA.4h.p0.1", "value"])) < 1e-9
    b_pool0, b_pool = float(B[0.0].median()), float(B[pool_p].median())
    sb = B.groupby(level=0).median()
    mult_site = {st: 1.0 + float(sb.loc[st, pcs[st]]) / c for st in SITES}
    phan_site = {st: float(sb.loc[st, pcs[st]] - sb.loc[st, 0.0]) / c for st in SITES}
    R.add("derived.H4.overpay_multiplier.pooled", 1.0 + b_pool / c, "derived", n_buildings=len(B))
    R.add("derived.H4.overpay_multiplier.median_site", float(np.median(list(mult_site.values()))), "derived", n_sites=11)
    R.add("derived.H4.overpay_multiplier.min_site", float(min(mult_site.values())), "derived")
    R.add("derived.H4.overpay_multiplier.max_site", float(max(mult_site.values())), "derived")
    R.add("derived.H4.phantom_payment_share.pooled", (b_pool - b_pool0) / c, "derived", n_buildings=len(B))
    R.add("derived.H4.phantom_payment_share.median_site", float(np.median(list(phan_site.values()))), "derived", n_sites=11)
    R.add("derived.H4.pjmA_bias.pooled_at_pcross", b_pool, "derived")
    R.add("derived.H4.pjmA_bias.pooled_at_p0", b_pool0, "derived")
    for st in SITES:
        R.add("derived.H4.overpay_multiplier.site." + st, mult_site[st], "derived")
    R.add("derived.H4.overpay_multiplier.definition", "PJM-adj payment divided by the true shed energy for a participant that curtails c = 0.10 of the window "
          "load and raises the 4 h before the event by the break-even p: payment energy = B - (1 - c) L, true shed = c L, so the multiplier is 1 + bias / c "
          "with bias = median over buildings of the building mean of (B - L) / L at p (frozen analysis.precool_tables, H4 pair support, pooled p-cross "
          "for the pooled value, each site's own p-cross for the site values; reproduces precool.bias.pjmA.4h.p0 and p0.1). phantom_payment_share = "
          "(bias(p) - bias(0)) / c = the extra payment from the increase alone, as a share of the true shed. Linear in B; assumes the curtailment does not "
          "move the adjustment hours and a payment proportional to B - L_obs", "derived")


# ----------------------------------------------------------------------------- item 9: contamination
def item9(R, L):
    qs = (("0", "q0"), ("0.25", "q0.25"), ("0.5", "q0.5"), ("1", "q1"))
    edge, edge_cg = {}, {}
    for qlab, tag in qs:
        pa = float(L.loc["contam.%s.pjmA.relMAE_median" % tag, "value"])
        sc = float(L.loc["contam.%s.scmR.relMAE_median" % tag, "value"])
        cg = float(L.loc["contam.%s.cgA.relMAE_median" % tag, "value"])
        edge[qlab], edge_cg[qlab] = pa - sc, pa - cg
        R.add("derived.contam.edge_scmR_vs_pjmA.q" + qlab, pa - sc, "derived")
        R.add("derived.contam.edge_cgA_vs_pjmA.q" + qlab, pa - cg, "derived")
    qx = [0.0, 0.25, 0.5, 1.0]

    def cross(ed):
        v = [ed[k] for k in ("0", "0.25", "0.5", "1")]
        for i in range(3):
            if v[i] > 0 >= v[i + 1]:
                return qx[i] + (qx[i + 1] - qx[i]) * v[i] / (v[i] - v[i + 1])
        return float("nan")
    R.add("derived.contam.q_cross_scmR_pjmA", cross(edge), "derived")
    R.add("derived.contam.definition", "edge = relMAE_median(PJM-adj) - relMAE_median(rule) at p = 0.05, c = 0.10 (ledger contam.q<q>.<m>.relMAE_median; key tag "
          "'q0' = q 0, 'q0.25' = 0.25, 'q0.5' = 0.5, 'q1' = 1); positive = the rule is more accurate than PJM-adj. q_cross = linear interpolation of "
          "the first q at which SCM-ridge's edge turns non-positive, on the four-point grid (descriptive)", "derived")


# ----------------------------------------------------------------------------- item 3: status relabel
def relabel_secondary():
    log = []
    d = CM.out_dir(2017)
    for name in SECONDARY_FILES:
        p = d / ("%s.rows.csv" % name)
        df = pd.read_csv(p)
        m = df.status != "secondary"
        for k, old in zip(df.key[m], df.status[m]):
            log.append((name + ".rows.csv", k, old, "secondary"))
        if m.any():
            df.loc[m, "status"] = "secondary"
            df.to_csv(p, index=False)
    lp = d / "d29_relabel_log.csv"
    prev = pd.read_csv(lp) if lp.exists() else pd.DataFrame(columns=["file", "key", "old", "new"])
    new = pd.DataFrame(log, columns=["file", "key", "old", "new"])
    pd.concat([prev, new], ignore_index=True).drop_duplicates(["file", "key"]).to_csv(lp, index=False)
    return log


def check_unique(R, L):
    clash = [k for k in R.r if k in L.index]
    assert not clash, ("keys already in a ledger", clash[:5])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--relabel", action="store_true")
    ap.add_argument("--collect", action="store_true")
    a = ap.parse_args(argv)
    import pickle
    fh = CM.freeze_hash(2017)
    L = read_ledgers()
    R1 = CM.load_R1(2017)
    R = Rows(fh)
    with open(C.ROOT / "results" / "run" / "results_state.pkl", "rb") as f:     # own frozen result file, read-only
        tab1418 = pickle.load(f)["erosion"]["tab"]
    tab1620 = h5_tabs_1620(L)
    item1(R, L, tab1418, tab1620)
    x = item2(R, L)
    ev = item4(R, R1)
    item5(R, L)
    item6(R, L)
    item7(R, L, R1)
    item9(R, L)
    check_unique(R, L)
    out = CM.out_dir(2017) / OUT_NAME
    R.frame().to_csv(out, index=False)
    print("wrote", out, len(R.r), "keys")
    print("xwin", {k: x[k] for k in ("est", "lo", "hi", "conf", "p", "n_stronger_1418", "n_sign_agree", "spearman")})
    print("event days / designated / episodes / episodes_designated:", ev)
    if a.relabel:
        log = relabel_secondary()
        print("relabelled rows:", len(log))
    if a.collect:
        n0 = len(pd.read_csv(CM.SEC_LEDGER))
        df = CM.collect()
        print("summary_secondary rows: %d -> %d" % (n0, len(df)))
        assert len(df) >= n0


if __name__ == "__main__":
    main()
