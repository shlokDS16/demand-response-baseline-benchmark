"""Orchestration of the parts core / precool / erosion (secondary.py holds the rest) and ledger emission."""
import json
import pickle
import time

import numpy as np
import pandas as pd

from . import adjust, analysis as AN, baselines as BL, data as D, events as EV, inject as IJ, stats as ST
from . import config as C
from . import leakage as LK


def peak_mem_gb():
    try:
        import psutil
        return psutil.Process().memory_info().peak_wset / 1e9
    except Exception:
        return float("nan")


def fold_arrays(site):
    """Returns (A, B, r1, r3list): frozen folds and frozen event dates only (T3 4.1, 1.3)."""
    return site.part_idx("A"), site.part_idx("B"), EV.r1_days(site), EV.r3_draws(site)


def run_core(Y, outdir, scm="grid"):
    t0 = time.time()
    R1, R3, ISO = [], [], []
    sample = {"sites": [], "excl": {}, "n_b": {}}
    for name in C.SITES:
        site, excl = D.make_site(Y, name)
        sample["excl"][name] = excl
        if site is None:
            continue
        A_, B_, r1, r3list = fold_arrays(site)
        sample["sites"].append(name)
        folds = [("A", A_, B_), ("B", B_, A_)]
        ev1 = set(r1.tolist())
        for f, part, dpool in folds:
            rr = BL.run_rule(site, site.Ys, site.Ys, ev1, r1, part, dpool, scm=scm, do_scm=True)
            for r in rr:
                r["fold"] = f
            R1 += rr
        for k, r3 in enumerate(r3list, start=1):
            ev3 = set(r3.tolist())
            for f, part, dpool in folds:
                rr = BL.run_rule(site, site.Ys, site.Ys, ev3, r3, part, dpool, do_scm=False)
                for r in rr:
                    r["fold"] = f
                    r["draw"] = k
                R3 += rr
        if True:
            iso = EV.r2iso_days(site)
            if iso is not None:
                evi = set(iso.tolist())
                for f, part, dpool in folds:
                    rr = BL.run_rule(site, site.Ys, site.Ys, evi, iso, part, dpool, scm=(C.SCM_W, C.SCM_LAM), do_scm=True)
                    for r in rr:
                        r["fold"] = f
                    ISO += rr
        print(name, "core done", round(time.time() - t0), "s", flush=True)
    frames = {"R1": pd.DataFrame(R1), "R3": pd.DataFrame(R3), "R2ISO": pd.DataFrame(ISO)}
    outdir.mkdir(parents=True, exist_ok=True)
    for k, v in frames.items():
        v.to_pickle(outdir / ("events_%s.pkl" % k))   # self-written intermediate, read back by this package only
    sample["n_b_R1"] = int(frames["R1"].b.nunique())
    sample["dup_dropped"] = {n: x["dup_dropped"] for n, x in sample["excl"].items()}
    with open(outdir / "sample.json", "w") as fh:
        json.dump(sample, fh, indent=1, default=str)
    return frames, sample, {"time_s": time.time() - t0, "peak_gb": peak_mem_gb()}


def load_frames(outdir):
    return {k: pd.read_pickle(outdir / ("events_%s.pkl" % k)) for k in ("R1", "R3", "R2ISO")}   # self-written


def analyse_core(frames, win, B=None):
    s, e = win
    R1, R3 = frames["R1"], frames["R3"]
    res = {}
    r3s = [g.reset_index(drop=True) for _, g in R3.groupby("draw")]
    res["H1"] = AN.h1(R1, r3s, s, e, B)
    res["H2"] = AN.h2(R1, s, e, B)
    res["H3"] = AN.h3(R1, s, e, B)
    b0 = adjust.adjusted(R1, s, e)
    meths = [m for m in ["prev", "pjm0", "pjmA", "caiso0", "caisoA", "ny0", "nyA", "isone0", "isoneA", "dm0", "dmA", "wm0", "wmA",
                         "m3", "mid8", "cg0", "cgA", "scmR", "scmC"] if m in b0]
    res["methods"] = {"R1": AN.method_table(R1, s, e, meths)}
    res["methods"]["R3"] = AN.method_table(R3, s, e, [m for m in meths if m not in ("cg0", "cgA", "scmR", "scmC")])
    if len(frames["R2ISO"]):
        res["methods"]["R2ISO"] = AN.method_table(frames["R2ISO"], s, e, meths)
    # scm grid (dev tuning reproduction): median building relMAE per configuration
    sc = [c for c in b0 if c.startswith("scm")]
    if sc:
        grid = {}
        for c in sc:
            ok = AN.pair_events(R1, b0, [c])
            grid[c] = float(AN.bld_stat(R1, b0, c, ok, "relMAE").median())
        res["scm_grid"] = grid
    # secondary rule family H1s / H2s
    sec = {}
    for rule in ("ny", "caiso", "isone"):
        try:
            sec["H1s." + rule] = AN.h1_rule(R1, r3s, s, e, rule + "0", B)
        except Exception as ex:   # pragma: no cover
            sec["H1s." + rule] = {"error": str(ex)}
    for rule, (xa, xb) in {"ny": ("nyA", "ny0"), "caiso": ("caisoA", "caiso0"), "isone": ("isoneA", "isone0")}.items():
        sec["H2s." + rule] = AN.h2(R1, s, e, B, xa, xb)
    res["secondary_rules"] = sec
    # H3 anchors: official adjusted rules vs pjmA
    anch = {}
    for m in ("caisoA", "nyA", "isoneA", "dmA"):
        ok, _ = AN.apply_site_support(R1, AN.pair_events(R1, b0, [m, "pjmA"]), C.MIN_SUPPORT)
        x = AN.bld_stat(R1, b0, m, ok, "relMAE")
        y = AN.bld_stat(R1, b0, "pjmA", ok, "relMAE")
        anch[m] = float(AN.site_median(np.log(x / y).replace([np.inf, -np.inf], np.nan).dropna()).median())
    res["anchors"] = anch
    return res


def run_precool(frames, win, B=None, do_boot=True):
    s, e = win
    R1 = frames["R1"]
    out = {sh: AN.h4(R1, s, e, sh, B=B, do_boot=do_boot) for sh in ("4h", "2h")}
    # heterogeneous variant (secondary): p_bd ~ Uniform(0, 2p) per building-event, one draw, seed 2017
    het = {}
    for p in (0.02, 0.05, 0.10):
        pv = np.random.default_rng(C.INJ_SEED).uniform(0, 2 * p, len(R1))
        b = adjust.adjusted(R1, s, e, pv, "4h")
        het[p] = {}
        for m in ("pjmA", "caisoA", "cgA", "scmR"):
            ok = AN.pair_events(R1, b, [m])
            het[p][m] = float(AN.bld_stat(R1, b, m, ok, "relMAE").median())
    out["hetp"] = het
    return out


def run_erosion(Y, outdir):
    t0 = time.time()
    rows = []
    sites_used = []
    for name in C.SITES:
        site, _ = D.make_site(Y, name)
        if site is None:
            continue
        order = EV.r1_order(site)
        score = order[:C.K_EVENTS]
        A_, B_ = site.part_idx("A"), site.part_idx("B")
        assert sorted(score.tolist()) == sorted(EV.r1_days(site).tolist())
        sites_used.append(name)
        for K in C.DISPATCH_K:
            disp = order[:K]
            evset = set(disp.tolist())
            for f, part, dpool in (("A", A_, B_), ("B", B_, A_)):
                Ys = IJ.dispatch(site.Ys, disp, part, site.win)
                IJ.assert_touched_only(site.Ys, Ys, disp, part, site.win)
                rr = BL.run_rule(site, Ys, site.Ys, evset, score, part, dpool, scm=(C.SCM_W, C.SCM_LAM), do_scm=True)
                for r in rr:
                    r["K"] = K
                    r["fold"] = f
                rows += rr
        print(name, "erosion done", round(time.time() - t0), "s", flush=True)
    df = pd.DataFrame(rows)
    df.to_pickle(outdir / "events_erosion.pkl")
    return df, {"time_s": time.time() - t0, "peak_gb": peak_mem_gb()}


def analyse_erosion(df, win):
    return AN.h5(df, win[0], win[1])


# ---------------- ledger emission ----------------
def _est_row(led, key, r, hid, holm, src, status="confirmatory", fam="C5"):
    led.add(key, r["est"], ci_low=r["ci_low"], ci_high=r["ci_high"], n_sites=r["n_sites"], n_buildings=r.get("n_b"),
            n_events=r.get("n_events"), source_file=src, status=status, family_id=fam, hypothesis_id=hid)


def emit_H(led, hid, r, est_key, holm, src, p_key="p_signedrank", cens=False):
    fam = "C5"
    _est_row(led, est_key, r, hid, holm, src)
    led.add("%s.%s" % (hid, p_key), r["p"], p_raw=r["p"], n_sites=r["n_sites"], source_file=src, status="confirmatory",
            family_id=fam, hypothesis_id=hid)
    led.add("%s.p_holm" % hid, holm[hid], p_raw=r["p"], p_holm=holm[hid], n_sites=r["n_sites"], source_file=src,
            status="confirmatory", family_id=fam, hypothesis_id=hid)
    led.add("%s.p_wcb" % hid, r["p_wcb"], p_raw=r["p_wcb"], source_file=src, status="secondary", hypothesis_id=hid)
    led.add("%s.loso_min" % hid, r["loso_min"], source_file=src, status="confirmatory", family_id=fam, hypothesis_id=hid)
    led.add("%s.loso_max" % hid, r["loso_max"], source_file=src, status="confirmatory", family_id=fam, hypothesis_id=hid)
    led.add("%s.loso_pmax" % hid, r["loso_pmax"], source_file=src, status="confirmatory", family_id=fam, hypothesis_id=hid)
    led.add("%s.site_robust" % hid, str(r["site_robust"]), source_file=src, status="confirmatory", family_id=fam, hypothesis_id=hid)
    for s_, v in r.get("site_values", {}).items():
        led.add("%s.site.%s" % (hid, s_), AN.fmt_cens(v) if isinstance(v, float) and np.isinf(v) else v, source_file=src,
                status="confirmatory", family_id=fam, hypothesis_id=hid)
    if r.get("dropped"):
        led.add("%s.sites_dropped_support" % hid, json.dumps(r["dropped"]), source_file=src, status="confirmatory", family_id=fam,
                hypothesis_id=hid)
    if r.get("cond"):
        led.add("%s.ci_boot_conditional" % hid, r["cond"][0], ci_low=r["cond"][1], ci_high=r["cond"][2], source_file=src,
                status="secondary", hypothesis_id=hid)


def emit_all(led, res, src_dir):
    """res: dict with optional keys core, precool, erosion, secondary. Holm over the available members of H1-H5."""
    p = {}
    core, pre, ero = res.get("core"), res.get("precool"), res.get("erosion")
    if core:
        p["H1"], p["H2"], p["H3"] = core["H1"]["p"], core["H2"]["p"], core["H3"]["p"]
    if pre:
        p["H4"] = pre["4h"]["p"]
    if ero:
        p["H5"] = ero["contrast"]["pjmA"]["p"]
    holm = ST.holm(p)
    smp = res.get("sample")
    if smp:
        def _s(k, v):
            led.add(k, v, status="confirmatory", family_id="C5", source_file="sample.json")
        _s("sample.n_sites", len(smp["sites"]))
        _s("sample.sites", ",".join(smp["sites"]))
        _s("sample.n_buildings", smp["n_b_R1"])
        _s("sample.n_meters_e1", sum(v["e1"] for v in smp["excl"].values()))
        _s("sample.n_excl_flat_meter", sum(v["e3_flat_meter"] for v in smp["excl"].values()))
        _s("sample.n_dup_dropped", sum(v["dup_dropped"] for v in smp["excl"].values()))
        for st_, v in smp["excl"].items():
            for rsn, n_ in v.items():
                _s("sample.excl.%s.%s" % (st_, rsn), n_)
        if res.get("core"):
            _s("sample.n_events.R1", int(res["core"]["methods"]["R1"]["pjm0"]["n_events"]))
            _s("sample.n_events.R3", int(res["core"]["methods"]["R3"]["pjm0"]["n_events"]))
            for m_, d_ in res["core"]["methods"]["R1"].items():
                _s("sample.support_share.%s" % m_, d_["support_share"])
    if res.get("dst"):
        for site_, conv_ in zip(res["dst"]["site"], res["dst"]["convention"]):
            led.add("sample.dst.%s" % site_, conv_, status="confirmatory", family_id="C5", source_file="dst_table")
    led.add("family.holm_members", ",".join(sorted(p)), status="confirmatory", family_id="C5", hypothesis_id="family")
    if core:
        src = "events_R1.pkl"
        emit_H(led, "H1", core["H1"], "H1.delta_bias.pjm0", holm, src)
        emit_H(led, "H2", core["H2"], "H2.logratio.pjmA_pjm0", holm, src)
        r3 = core["H3"]
        emit_H(led, "H3", r3, "H3.logratio.cgA_pjmA", holm, src, p_key="p_tost")
        led.add("H3.ci90", r3["est"], ci_low=r3["ci_low"], ci_high=r3["ci_high"], status="confirmatory", family_id="C5",
                hypothesis_id="H3", source_file=src)
        led.add("H3.margin", C.TOST_DELTA, status="confirmatory", family_id="C5", hypothesis_id="H3", source_file=src)
        led.add("H3.decision", AN.h3_decision(r3, holm["H3"]), status="confirmatory", family_id="C5", hypothesis_id="H3",
                source_file=src)
        for k, v in core["methods"].items():
            for m, d in v.items():
                tag = {"R1": "R1", "R3": "R3", "R2ISO": "R2ISO", "w1620": "w1620"}.get(k, k)
                for stat in ("relMAE_median", "bias_median", "rmse_median", "PER_c10_median", "share_PER_gt_0_5", "nmbe_granderson"):
                    led.add("method.%s.%s.%s" % (m, tag, stat), d[stat], n_buildings=d["n_b"], n_events=d["n_events"],
                            source_file=src, status="secondary")
                led.add("method.%s.%s.support_share" % (m, tag), d["support_share"], source_file=src, status="secondary")
        for m in BL_INFO():
            led.add("method.%s.info" % m, BL.INFO[m], status="secondary", source_file="baselines.py")
        for k, v in core.get("anchors", {}).items():
            led.add("H3.anchor.%s_vs_pjmA" % k, v, status="secondary", source_file=src)
        for k, v in core.get("scm_grid", {}).items():
            led.add("hpo.scm.grid." + k, v, status="secondary", source_file=src)
        for k, v in core.get("secondary_rules", {}).items():
            if "est" in v:
                k = k.replace("H2s.", "H2s.logratio.").replace("H1s.", "H1s.delta_bias.")
                led.add(k, v["est"], ci_low=v["ci_low"], ci_high=v["ci_high"], p_raw=v["p"], n_sites=v["n_sites"],
                        status="secondary", family_id="S-rules", source_file=src)
    if pre:
        src = "events_R1.pkl (analytic recompute)"
        for p_, d_ in pre.get("hetp", {}).items():
            for m_, v_ in d_.items():
                led.add("hetp.p%g.%s.relMAE_median" % (p_, m_), v_, status="secondary", source_file=src)
        for sh, r in {k_: v_ for k_, v_ in pre.items() if k_ != "hetp"}.items():
            fin = "final" if sh == "4h" else "secondary"
            fam = "C5" if sh == "4h" else "secondary"
            if sh == "4h":
                _est_row(led, "H4.pcross.pjmA_scmR.4h", dict(r, est=r["pooled"] if not np.isinf(r["pooled"]) else np.nan,
                                                              ci_low=r["pcross_ci"]["pjmA"][0] if "pcross_ci" in r else None,
                                                              ci_high=r["pcross_ci"]["pjmA"][1] if "pcross_ci" in r else None),
                         "H4", holm, src)
                led.add("H4.pcross.pjmA_scmR.4h.label", AN.fmt_cens(r["pooled"]), status="confirmatory", family_id="C5",
                        hypothesis_id="H4", source_file=src)
                led.add("H4.p_sign", r["p"], p_raw=r["p"], n_sites=r["n_sites"], status="confirmatory", family_id="C5",
                        hypothesis_id="H4", source_file=src)
                led.add("H4.p_holm", holm["H4"], p_raw=r["p"], p_holm=holm["H4"], n_sites=r["n_sites"], status="confirmatory",
                        family_id="C5", hypothesis_id="H4", source_file=src)
                led.add("H4.p_signedrank", r["p_signedrank_capped"], p_raw=r["p_signedrank_capped"], status="secondary",
                        source_file=src, hypothesis_id="H4")
                led.add("H4.p_wcb", r["p_wcb"], p_raw=r["p_wcb"], status="secondary", source_file=src, hypothesis_id="H4")
                led.add("H4.median_site_pcross", r["median_site"], ci_low=r["ci_low"], ci_high=r["ci_high"], n_sites=r["n_sites"],
                        status="confirmatory", family_id="C5", hypothesis_id="H4", source_file=src)
                led.add("H4.loso_min", r["loso_min"], status="confirmatory", family_id="C5", hypothesis_id="H4", source_file=src)
                led.add("H4.loso_max", r["loso_max"], status="confirmatory", family_id="C5", hypothesis_id="H4", source_file=src)
                led.add("H4.loso_pmax", r["loso_pmax"], status="confirmatory", family_id="C5", hypothesis_id="H4", source_file=src)
                led.add("H4.site_robust", str(r["site_robust"]), status="confirmatory", family_id="C5", hypothesis_id="H4",
                        source_file=src)
                led.add("H4.sens_increment_p10", r["sens_increment_p10"], status="secondary", source_file=src, hypothesis_id="H4")
                for s_, v in r["site_pcross"].items():
                    led.add("H4.site.%s" % s_, AN.fmt_cens(v) if np.isinf(v) else v, status="confirmatory", family_id="C5",
                            hypothesis_id="H4", source_file=src)
                if r["dropped"]:
                    led.add("H4.sites_dropped_support", json.dumps(r["dropped"]), status="confirmatory", family_id="C5",
                            hypothesis_id="H4", source_file=src)
            for m, v in r["pstar"].items():
                ci = r.get("pstar_ci", {}).get(m)
                led.add("pstar.%s.%s" % (m, sh), AN.fmt_cens(v) if np.isinf(v) else v, ci_low=ci[0] if ci else None,
                        ci_high=ci[1] if ci else None, n_sites=r["n_sites"], status="secondary", source_file=src)
            for m, v in r["pcross"].items():
                ci = r.get("pcross_ci", {}).get(m)
                led.add("pcross.%s.%s" % (m, sh), AN.fmt_cens(v) if np.isinf(v) else v, ci_low=ci[0] if ci else None,
                        ci_high=ci[1] if ci else None, status="secondary", source_file=src)
            for m, cur in r["curve_pooled"].items():
                for pv in C.P_BAND:
                    led.add("precool.relMAE.%s.%s.p%g" % (m, sh, pv), float(cur[int(round(pv / 0.005))]), status="secondary",
                            source_file=src)
                    led.add("precool.bias.%s.%s.p%g" % (m, sh, pv), float(r["curve_bias_pooled"][m][int(round(pv / 0.005))]),
                            status="secondary", source_file=src)
            for pv in (0.02, 0.05, 0.10, 0.20, 0.30):
                i_ = int(round(pv / 0.005))
                led.add("incr_sens.%s.p%g" % (sh, pv), float(r["curve_pooled"]["pjmA"][i_] - r["curve_pooled"]["pjmA"][0]),
                        status="secondary", source_file=src, hypothesis_id="H4")
    if ero:
        src = "events_erosion.pkl"
        c = ero["contrast"]["pjmA"]
        r = dict(c)
        r["n_b"] = None
        r["n_events"] = ero["n_events_common"]
        prim = ero["primary"]
        ekey = "eta_abs" if prim == "abs" else "eta"
        for m in ("pjmA", "scmR"):
            led.add("H5.eta.%s" % m, ero["methods"][m][ekey], source_file=src, status="confirmatory", family_id="C5",
                    hypothesis_id="H5")
        emit_H(led, "H5", r, "H5.eta_diff", holm, src)
        led.add("H5.eta_definition", "slope of site-median |rho-1| over K" if prim == "abs" else "minus slope of site rho over K",
                status="confirmatory", family_id="C5", hypothesis_id="H5", source_file=src)
        sec = ero["contrast_signed"] if prim == "abs" else ero["contrast_abs"]
        for a, c2 in sec.items():
            led.add("H5s.%s_diff.%s_minus_scmR" % ("eta_signed" if prim == "abs" else "eta_abs", a), c2["est"], ci_low=c2["ci_low"],
                    ci_high=c2["ci_high"], p_raw=c2["p"], n_sites=c2["n_sites"], status="secondary", source_file=src,
                    hypothesis_id="H5s")
        for a, c2 in ero["contrast"].items():
            if a != "pjmA":
                led.add("H5s.eta_diff.%s_minus_scmR" % a, c2["est"], ci_low=c2["ci_low"], ci_high=c2["ci_high"], p_raw=c2["p"],
                        n_sites=c2["n_sites"], status="secondary", source_file=src, hypothesis_id="H5s")
        for m, d in ero["methods"].items():
            led.add("H5.Dtau.%s" % m, AN.fmt_cens(d["D_tau"], 40) if np.isinf(d["D_tau"]) else d["D_tau"], status="secondary",
                    source_file=src, hypothesis_id="H5")
            for s_, v in d["D_tau_site"].items():
                led.add("H5.Dtau.%s.%s" % (m, s_), AN.fmt_cens(v, 40) if np.isinf(v) else v, status="secondary", source_file=src)
            led.add("H5.eta_signed_pooled.%s" % m, d["eta"], status="secondary", source_file=src)
            led.add("H5.eta_abs_pooled.%s" % m, d["eta_abs"], status="secondary", source_file=src)
            led.add("H5.eta_2pt.%s" % m, d["eta_2pt"], status="secondary", source_file=src)
            for K, v in d["rho_pooled"].items():
                led.add("H5.rho.%s.K%d" % (m, K), v, status="secondary", source_file=src)
            for K, v in d["abs_dev_pooled"].items():
                led.add("H5.absdev.%s.K%d" % (m, K), v, status="secondary", source_file=src)
        for kind, dd in ero["age_days_median_by_K"].items():
            for K, v in dd.items():
                led.add("H5.age_days.%s.K%d" % (kind, K), v, status="secondary", source_file=src)
        for K, v in ero["fallback_by_rule"].items():
            for rule, x in v.items():
                led.add("H5.fallback.%s.K%d" % (rule, K), x, status="secondary", source_file=src)
        if ero["dropped"]:
            led.add("H5.sites_dropped_support", json.dumps(ero["dropped"]), status="confirmatory", family_id="C5",
                    hypothesis_id="H5", source_file=src)
    return holm


def BL_INFO():
    return list(BL.INFO)
