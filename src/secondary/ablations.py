"""Ablations of PREREG s6 'Secondary' (exploratory; no p_holm):
 part 'abl'   (frame-based, from the frozen R1 events): adjustment on/off, cap on/off, adjustment hours;
 part 'donor' (donor aggregation engine): donor pool same-use vs whole site, donor count, excluding the 10 % of donors most
               correlated with the target.
Not run: 'scmR neighbours' (PREREG s3/s5 define no neighbour parameter for scmR; nothing to ablate without inventing one),
'lgb with/without donor features' (= lgbM vs lgbD of the frozen secondary part), DST mapping (frozen dst_alt part),
'flatline filter on/off' (variants.py).

CHOICE_AFTER_FREEZE:
 * cap on/off: the frozen clips [0.8, 1.2] (caisoA, nyA, dmA, m3A) and [0.6, 1.4] (wmA) are removed ('off'); pjmA is uncapped
   in the frozen run, so its 'cap on' variant clips the additive adjustment at +-20 % of pjm0 (the PJM-manual style cap).
 * adjustment hours for pjmA (all <= s-2, assertion 3): {s-4,s-3,s-2} (frozen), {s-2}, {s-3,s-2}, {s-4,s-3}, {s-6..s-2}.
 * donor pool 'same use': donors of the other fold with the target's primary space usage (>= 5 needed, else no value).
 * donor count k in {5, 10, 20}: one random subset of k donors of the other fold per (site, fold, day), seed 7.
 * correlation exclusion: correlation of the daily window load of target and donor over the site's non-event weekdays before
   the first R1 day (history only), the ceil(10 %) most correlated donors of each target are dropped (>= 5 must remain).
 * all donor variants are computed with cgA = pjmA(target) * sum(L_donors) / sum(pjmA_donors) (adjust.py definition) and
   reproduce the frozen cgA exactly for the whole-site pool (asserted)."""
import math

import numpy as np
import pandas as pd

from run import adjust, analysis as AN, baselines as BL, config as C, data as D, events as EV
from run import leakage as LK
from run import stats as ST


def _stat(df, base, m, ok):
    rel = AN.bld_stat(df, base, m, ok, "relMAE")
    return dict(relMAE_median=float(rel.median()), bias_median=float(AN.bld_stat(df, base, m, ok, "bias").median()),
                n_b=int(len(rel)), n_events=int(ok.sum()), support_share=float(ok.mean()))


def _emit_stat(led, prefix, d):
    led.add(prefix + ".relMAE_median", d["relMAE_median"], n_buildings=d["n_b"], n_events=d["n_events"], status="secondary")
    led.add(prefix + ".bias_median", d["bias_median"], n_buildings=d["n_b"], n_events=d["n_events"], status="secondary")


# ------------------------------------------------------------------ frame-based ablations
def run_frame_ablations(R1, led):
    s, e = C.WINDOWS["primary"]
    nw = e - s
    off = s - 6
    m = adjust.shaped_morning(R1, s, 0.0)
    b0 = adjust.adjusted(R1, s, e)

    def mh(arr, hs):
        for h in hs:
            assert h <= s - 2 and h >= s - 6, "adjustment hour outside the information set"
        LK.a3_hours(hs, s, "I-morn")
        return arr[:, [h - off for h in hs]].mean(1)

    # 1. adjustment on / off (the frozen H2 contrast, as method medians)
    for nm_on, nm_off in (("pjmA", "pjm0"), ("caisoA", "caiso0"), ("nyA", "ny0"), ("isoneA", "isone0"), ("dmA", "dm0"), ("wmA", "wm0")):
        ok = AN.pair_events(R1, b0, [nm_on, nm_off])
        for nm, tag in ((nm_on, "on"), (nm_off, "off")):
            _emit_stat(led, "ablation.adjustment.%s.%s" % (nm_on, tag), _stat(R1, b0, nm, ok))
    # 2. cap on / off
    cases = {"caisoA": ("caiso", "caiso0", "caiso"), "nyA": ("ny", "ny0", "ny"), "dmA": ("dm", "dm0", "dm"),
             "wmA": ("wm", "wm0", "wm")}
    for nm, (key, base0, ck) in cases.items():
        H = [s + a for a in C.ADJ[key]]
        pr = adjust._prof(R1, base0)
        raw = R1[base0].values * (mh(m, H) / mh(pr, H))
        bb = {"on": b0[nm], "off": raw}
        ok = AN.pair_events(R1, bb, ["on", "off"])
        lo, hi = C.CLIP[ck]
        for tag in ("on", "off"):
            _emit_stat(led, "ablation.cap.%s.%s" % (nm, tag), _stat(R1, bb, tag, ok))
        led.add("ablation.cap.%s.share_clipped" % nm, float(((raw < b0[base0] * lo) | (raw > b0[base0] * hi))[ok].mean()), status="secondary")
    H = [s + a for a in C.ADJ["pjm"]]
    pj = adjust._prof(R1, "pjm0")
    adj = nw * (mh(m, H) - mh(pj, H))
    capped = R1.pjm0.values + np.clip(adj, -0.2 * R1.pjm0.values, 0.2 * R1.pjm0.values)
    bb = {"off": b0["pjmA"], "on": capped}      # frozen pjmA is uncapped = cap OFF
    ok = AN.pair_events(R1, bb, ["on", "off"])
    for tag in ("off", "on"):
        _emit_stat(led, "ablation.cap.pjmA.%s" % tag, _stat(R1, bb, tag, ok))
    led.add("ablation.cap.pjmA.share_clipped", float((np.abs(adj) > 0.2 * R1.pjm0.values)[ok].mean()), status="secondary")
    # 3. adjustment hours for pjmA
    sets = {"s-4..s-2 (frozen)": [s - 4, s - 3, s - 2], "s-2": [s - 2], "s-3..s-2": [s - 3, s - 2], "s-4..s-3": [s - 4, s - 3],
            "s-6..s-2": [s - 6, s - 5, s - 4, s - 3, s - 2]}
    bb = {}
    for nm, hs in sets.items():
        bb[nm] = R1.pjm0.values + nw * (mh(m, hs) - mh(pj, hs))
    ok = AN.pair_events(R1, bb, list(sets))
    for nm in sets:
        _emit_stat(led, "ablation.adjhours.pjmA.%s" % nm.replace(" ", ""), _stat(R1, bb, nm, ok))
    assert np.allclose(bb["s-4..s-2 (frozen)"][ok], b0["pjmA"][ok]), "frozen pjmA not reproduced"


# ------------------------------------------------------------------ donor aggregation engine
def site_matrix(site, r1):
    """All-building R1 frame (every building a target, no donors) -> arrays per (site-day): window L, pjmA, present mask."""
    ev1 = set(r1.tolist())
    allb = np.arange(site.nb)
    rows = BL.run_rule(site, site.Ys, site.Ys, ev1, r1, allb, [], do_scm=False)
    fr = pd.DataFrame(rows)
    s, e = C.WINDOWS["primary"]
    b = adjust.adjusted(fr, s, e)
    pos = {m: i for i, m in enumerate(site.meters)}
    fr["j"] = fr.b.map(pos)
    fr["pjmA"] = b["pjmA"]
    return fr


def cg(P_t, L_d, P_d):
    return P_t * L_d.sum() / P_d.sum()


def donor_variants(site, r1, fr, seed=7, ks=(5, 10, 20), min_don=5):
    """Return dict variant -> DataFrame(site, b, d, L, cgA) for all variants of the donor ablations."""
    nb = site.nb
    fold = site.fold
    use = np.array(site.use)
    # history correlation (days strictly before the first R1 day, weekdays, complete)
    first = int(min(r1))
    W = np.where(site.complete, site.Ys[:, site.WIN, :].sum(1), np.nan)
    hist = [k for k in range(first) if site.wk[k]]
    LK.a1_lookback_before(first, hist)
    Cm = pd.DataFrame(W[hist]).corr(min_periods=20).values
    out = {v: [] for v in ["pool_all", "pool_same_use"] + ["k%d" % k for k in ks] + ["drop_corr10"]}
    for d, g in fr.groupby("d"):
        g = g.dropna(subset=["pjmA"])
        g = g[g.L > 0]
        J = g.j.values.astype(int)
        L = dict(zip(J, g.L.values))
        P = dict(zip(J, g.pjmA.values))
        for F in ("A", "B"):
            tg = [j for j in J if fold[j] == F]
            dn = np.array([j for j in J if fold[j] != F])
            if len(dn) < min_don:
                continue
            rng = np.random.default_rng([seed, site.index, int(d), 0 if F == "A" else 1])
            subsets = {"k%d" % k: (rng.choice(dn, size=k, replace=False) if len(dn) >= k else None) for k in ks}
            Ld, Pd = np.array([L[q] for q in dn]), np.array([P[q] for q in dn])
            for j in tg:
                rec = dict(site=site.name, b=site.meters[j], d=int(d), L=L[j])
                out["pool_all"].append(dict(rec, cgA=cg(P[j], Ld, Pd)))
                su = dn[use[dn] == use[j]]
                if len(su) >= min_don:
                    out["pool_same_use"].append(dict(rec, cgA=cg(P[j], np.array([L[q] for q in su]), np.array([P[q] for q in su]))))
                for k, sub in subsets.items():
                    if sub is not None:
                        out[k].append(dict(rec, cgA=cg(P[j], np.array([L[q] for q in sub]), np.array([P[q] for q in sub]))))
                cj = Cm[j, dn]
                order = np.argsort(-np.nan_to_num(cj, nan=-2.0), kind="stable")
                n_drop = math.ceil(0.10 * len(dn))
                keep = dn[order[n_drop:]]
                if len(keep) >= min_don:
                    out["drop_corr10"].append(dict(rec, cgA=cg(P[j], np.array([L[q] for q in keep]), np.array([P[q] for q in keep]))))
    return {k: pd.DataFrame(v) for k, v in out.items()}


def run_donor(year, led):
    from secondary import common as CM
    s, e = C.WINDOWS["primary"]
    Y = D.build_year(year)
    R1 = CM.load_R1(year)
    acc = {}
    for name in C.SITES:
        site, _ = D.make_site(Y, name)
        if site is None:
            continue
        r1 = EV.r1_days(site)
        fr = site_matrix(site, r1)
        var = donor_variants(site, r1, fr)
        # exact reproduction of the frozen comparison group for the whole-site pool
        ref = R1[R1.site == name].assign(cgA=adjust.adjusted(R1[R1.site == name], s, e)["cgA"])
        mrg = var["pool_all"].merge(ref[["b", "d", "cgA"]], on=["b", "d"], suffixes=("", "_frozen"))
        okk = np.isfinite(mrg.cgA_frozen)
        assert len(mrg) and np.allclose(mrg.cgA[okk], mrg.cgA_frozen[okk], rtol=1e-9), "donor engine does not reproduce cgA at %s" % name
        for k, v in var.items():
            acc.setdefault(k, []).append(v)
        print(name, "donor ablations done", flush=True)
    acc = {k: pd.concat(v, ignore_index=True) for k, v in acc.items()}
    base = acc["pool_all"]
    for k, v in acc.items():
        # common support with the whole-site baseline, per site >= 10 building-events
        mg = base.merge(v, on=["site", "b", "d"], suffixes=("_0", "_v"))
        dfm = pd.DataFrame(dict(site=mg.site, b=mg.b, L=mg.L_0))
        bb = {"base": mg.cgA_0.values, "var": mg.cgA_v.values}
        ok = AN.pair_events(dfm, bb, ["base", "var"])
        ok, dropped = AN.apply_site_support(dfm, ok)
        sb, sv = _stat(dfm, bb, "base", ok), _stat(dfm, bb, "var", ok)
        _emit_stat(led, "ablation.donor.%s.cgA" % k, sv)
        _emit_stat(led, "ablation.donor.%s.cgA_wholepool_same_support" % k, sb)
        led.add("ablation.donor.%s.share_of_baseline_events" % k, float(len(v) / len(base)), status="secondary")
        x = np.log(AN.bld_stat(dfm, bb, "var", ok, "relMAE") / AN.bld_stat(dfm, bb, "base", ok, "relMAE"))
        x = AN.site_median(x.replace([np.inf, -np.inf], np.nan).dropna())
        if len(x) >= 2:
            sr = ST.signed_rank(x.values, "two")
            est, lo, hi, _ = ST.hl_ci(x.values)
            led.add("ablation.donor.%s.logratio_vs_wholepool" % k, est, ci_low=lo, ci_high=hi, p_raw=sr["p"], n_sites=int(sr["n"]),
                    status="secondary")
    return {}


def run(year, led, part):
    from secondary import common as CM
    if part == "abl":
        run_frame_ablations(CM.load_R1(year), led)
    else:
        run_donor(year, led)
    led.add("ablation.note.scmR_neighbours", "not run: PREREG defines no neighbour parameter for scmR", status="secondary")
    return {}
