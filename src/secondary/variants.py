"""Re-runs of the R1/R3 core (H1-H3 and the method tables, via the frozen run_rule and analyse_core) under a changed sample rule:
 part 'nonevent': E3 flat-meter share computed on NON-EVENT days only (PREREG s9.18; sensitivity of the 2017-dependent E3 selection);
 part 'flat'    : flatline filter off (E2 run rule and E3 meter exclusion disabled), ablation of PREREG s6.
Constants of run.config are patched in this process only (the frozen files are not touched) and restored afterwards.

CHOICE_AFTER_FREEZE:
 * 'non-event days' = every frozen event day of the site-year (R1 primary ranks 1-10 and all five R3 draws) is removed from
   the E3 flat-share denominator and numerator; the threshold 0.20, hours, season and weekday rule are unchanged.
 * Only H1-H3 and the method tables are recomputed (they need R1 and R3 only). H4/H5 (precool, erosion) are not repeated: they
   would need the full 40-day injection grids, about 5 min per variant, and add no sample information beyond the buildings.
 * scmR/scmC at the fixed (W, lambda) of PREREG s5 in both years; no bootstrap B change (default 10,000 unless --boot-b)."""
import numpy as np
import pandas as pd

from run import analysis as AN, baselines as BL, config as C, data as D, events as EV
from run import pipeline as PL


def nonevent_flat_share(Y):
    """E3 recomputed over season weekdays that are not frozen event days of the site-year (R1 primary + R3 draws)."""
    ev = EV.frozen_events()
    win = C.WINDOWS["primary"]
    FH = D.flat_hours(win)
    share = {}
    for s in C.SITES:
        bi = [Y.cols.index(b) for b in Y.aud.index[Y.aud.site_id == s]]
        if not bi:
            continue
        c = D.ctry(Y.aud.timezone[Y.aud.site_id == s].iloc[0])
        ed = ev[(ev.site_id == s) & (ev.year == Y.year) & ev.primary & ev.rule.isin(["R1", "R3"])].date
        evmask = Y.days.isin(pd.DatetimeIndex(ed))
        m = D.site_weekday_mask(Y.days, Y.hol[c]) & D.season_mask(Y.days) & ~evmask
        f = D.flat_mask(Y.X[:, :, bi].astype(np.float64), FH)
        for k, b in enumerate(bi):
            share[Y.cols[b]] = float(f[m, k].mean())
    return pd.Series(share)


def core_frames(Y):
    R1, R3 = [], []
    sites = []
    excl = {}
    for name in C.SITES:
        site, ex = D.make_site(Y, name)
        excl[name] = ex
        if site is None:
            continue
        sites.append(name)
        A_, B_, r1, r3list = PL.fold_arrays(site)
        folds = [("A", A_, B_), ("B", B_, A_)]
        ev1 = set(r1.tolist())
        for f, part, dpool in folds:
            R1 += BL.run_rule(site, site.Ys, site.Ys, ev1, r1, part, dpool, scm=(C.SCM_W, C.SCM_LAM), do_scm=True)
        for k, r3 in enumerate(r3list, start=1):
            ev3 = set(r3.tolist())
            for f, part, dpool in folds:
                rr = BL.run_rule(site, site.Ys, site.Ys, ev3, r3, part, dpool, do_scm=False)
                for r in rr:
                    r["draw"] = k
                R3 += rr
        print(name, "variant core done", flush=True)
    return {"R1": pd.DataFrame(R1), "R3": pd.DataFrame(R3), "R2ISO": pd.DataFrame()}, sites, excl


def run(year, led, part, boot_b=None):
    from secondary import common as CM
    s, e = C.WINDOWS["primary"]
    saved = (C.FLAT_RUN, C.FLAT_METER_SHARE)
    try:
        if part == "flat":
            C.FLAT_RUN, C.FLAT_METER_SHARE = 10 ** 9, 2.0       # never flat, no meter excluded
        Y = D.build_year(year)
        if part == "nonevent":
            Y.flat_share = nonevent_flat_share(Y)
        frames, sites, excl = core_frames(Y)
    finally:
        C.FLAT_RUN, C.FLAT_METER_SHARE = saved
    res = PL.analyse_core(frames, (s, e), B=boot_b)
    tag = "nonevent" if part == "nonevent" else "flatoff"
    led.add("%s.sample.n_sites" % tag, len(sites), status="secondary")
    led.add("%s.sample.n_buildings_R1" % tag, int(frames["R1"].b.nunique()), n_events=len(frames["R1"]), status="secondary")
    led.add("%s.sample.n_e3_excluded" % tag, int(sum(v["e3_flat_meter"] for v in excl.values())), status="secondary")
    for n, v in excl.items():
        led.add("%s.sample.excl.%s.e3_flat_meter" % (tag, n), int(v["e3_flat_meter"]), status="secondary")
    for h in ("H1", "H2", "H3"):
        r = res[h]
        led.add("%s.%s.est" % (tag, h), r["est"], ci_low=r["ci_low"], ci_high=r["ci_high"], p_raw=r["p"], n_sites=r["n_sites"],
                n_buildings=r["n_b"], n_events=r["n_events"], status="secondary")
        led.add("%s.%s.median_over_sites" % (tag, h), r["median_over_sites"], n_sites=r["n_sites"], status="secondary")
    for m, d in res["methods"]["R1"].items():
        for stat in ("relMAE_median", "bias_median"):
            led.add("%s.method.%s.R1.%s" % (tag, m, stat), d[stat], n_buildings=d["n_b"], n_events=d["n_events"], status="secondary")
    return res
