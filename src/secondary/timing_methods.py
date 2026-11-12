"""Per-method computational cost of the baselines on the 2017 R1 building-events (referee R-D).
Frozen code (src/run) is imported UNCHANGED and read-only. The per-method selection logic below is a line-for-line copy of
run.baselines.run_rule (split by method so each can be timed); run.baselines.ridge_s1 / classic / leakage checks and
run.adjust helpers are called directly. VALIDATION: every produced value is compared with results/run/events_R1.pkl.
Single process, CPU only, 3 timed repeats (median), then one tracemalloc pass for the working-memory peak of each method.
Timed cost of a method = its own steps + the prerequisite steps it needs when run alone (shared steps are also reported
separately as compute.method.shared_*). Data loading and site construction are reported as compute.shared.*.
CLI: python -I src/secondary/timing_methods.py [--sites Bear,Fox] [--reps 3] [--out file]  (writes the rows file only for all sites)"""
import argparse
import json
import os
import platform
import site as _site
import sys
import time
import tracemalloc

up = _site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np   # noqa: E402
import pandas as pd   # noqa: E402

from run import adjust, baselines as BL, config as C, data as D, events as EV, freeze, leakage as LK   # noqa: E402
from run import ledger as LD   # noqa: E402

pc = time.perf_counter


class Acc:
    def __init__(self, mem=False):
        self.t = {}
        self.mem = mem
        self.peak = {}

    def start(self):
        if self.mem:
            tracemalloc.reset_peak()
            self.b0 = tracemalloc.get_traced_memory()[0]
        return pc()

    def stop(self, name, t0):
        dt = pc() - t0
        self.t[name] = self.t.get(name, 0.0) + dt
        if self.mem:
            self.peak[name] = max(self.peak.get(name, 0), tracemalloc.get_traced_memory()[1] - self.b0)


def run_site(site, acc, collect=None):
    s, WIN = site.s, site.WIN
    wk, complete, tm = site.wk, site.complete, site.tm
    cols = site.meters
    Ys = site.Ys
    H_PJM = BL.hrs(s, "pjm")
    mh = BL.morning_hours(s)
    A_ = site.part_idx("A")
    B_ = site.part_idx("B")
    r1 = EV.r1_days(site)
    ev1 = set(r1.tolist())
    Lc = np.where(complete, Ys[:, WIN, :].sum(1), np.nan)
    PRE_DONOR = list(range(0, s - 4))
    nrows = 0
    rows = []
    for f, part, dpool in [("A", A_, B_), ("B", B_, A_)]:
        LK.a7_folds(part, dpool)
        for d in sorted(r1):
            def past(j, n, maxback, excl_daybefore=False):
                out = []
                for k in range(d - 1, max(d - maxback - 1, -1), -1):
                    if not wk[k] or not complete[k, j]:
                        continue
                    if k in ev1:
                        continue
                    if excl_daybefore and (k + 1) in ev1:
                        continue
                    out.append(k)
                    if n and len(out) == n:
                        break
                LK.a1_lookback_before(d, out)
                LK.a2_no_event_days(ev1, out, day_before=excl_daybefore)
                return out

            base = {}
            for j in list(part) + list(dpool):
                if not complete[d, j]:
                    continue
                r = {}
                t0 = acc.start()
                p45 = past(j, 0, 45)
                acc.stop("shared_p45", t0)
                # prev
                t0 = acc.start()
                if p45:
                    r["prev_prof"] = Ys[p45[0], :, j]
                acc.stop("prev_own", t0)
                # pjm0
                t0 = acc.start()
                fpj = 0
                p5 = p45[:5]
                if len(p5) < 4:
                    evd = [k for k in range(max(d - 45, 0), d) if k in ev1 and wk[k] and complete[k, j]]
                    evd = sorted(evd, key=lambda k: -Lc[k, j])[: 4 - len(p5)]
                    LK.a1_lookback_before(d, evd)
                    p5 = p5 + evd
                    fpj = 1
                if len(p5) >= 4:
                    m5 = np.array([Lc[k, j] for k in p5])
                    p5k = [k for k, v in zip(p5, m5) if v >= C.PJM_DROP * m5.mean()]
                    p4 = sorted(p5k, key=lambda k: -Lc[k, j])[:4]
                    r["pjm0_prof"] = Ys[p4][:, :, j].mean(0)
                acc.stop("pjm0_own", t0)
                # caiso0
                t0 = acc.start()
                fcs = 0
                c10 = p45[:10]
                if len(c10) < 5:
                    evd = [k for k in range(max(d - 45, 0), d) if k in ev1 and wk[k] and complete[k, j]]
                    evd = sorted(evd, key=lambda k: -Lc[k, j])[: 5 - len(c10)]
                    LK.a1_lookback_before(d, evd)
                    c10 = c10 + evd
                    fcs = 1
                if len(c10) >= 5:
                    r["caiso0_prof"] = Ys[c10][:, :, j].mean(0)
                acc.stop("caiso0_own", t0)
                # ny0 (own lookback of 30 days, day-before excluded)
                t0 = acc.start()
                p30 = past(j, 0, 30, excl_daybefore=True)
                if len(p30) >= 5:
                    P = np.nanmax(Ys[max(d - 30, 0):d, WIN, j])
                    p30 = [k for k in p30 if Ys[k, WIN, j].mean() >= 0.25 * P][:10]
                    if len(p30) >= 5:
                        r["ny0_prof"] = Ys[sorted(p30, key=lambda k: -Lc[k, j])[:5]][:, :, j].mean(0)
                acc.stop("ny0_own", t0)
                # isone0
                t0 = acc.start()
                wd30 = [k for k in range(d - 1, -1, -1) if wk[k]][:30]
                ine = [k for k in wd30 if k not in ev1 and complete[k, j]][:10]
                LK.a1_lookback_before(d, ine)
                if len(ine) >= 5:
                    r["isone0_prof"] = Ys[ine][:, :, j].mean(0)
                acc.stop("isone0_own", t0)
                # dm0
                t0 = acc.start()
                dm = past(j, 10, 90)
                if len(dm) == 10:
                    r["dm0_prof"] = Ys[dm][:, :, j].mean(0)
                acc.stop("dm0_own", t0)
                # wm0
                t0 = acc.start()
                p90 = [k for k in past(j, 0, 90) if not np.isnan(tm[k])]
                if len(p90) >= 4 and not np.isnan(tm[d]):
                    wm = sorted(p90, key=lambda k: (abs(tm[k] - tm[d]), d - k))[:4]
                    r["wm0_prof"] = Ys[wm][:, :, j].mean(0)
                acc.stop("wm0_own", t0)
                # mid8 (and m3, which the frozen run also stores)
                t0 = acc.start()
                b10 = p45[:10]
                if len(b10) >= 10:
                    srt = sorted(b10, key=lambda k: Lc[k, j])[1:9]
                    r["mid8_prof"] = Ys[srt][:, :, j].mean(0)
                acc.stop("mid8_own", t0)
                t0 = acc.start()                      # m3 is not a requested method; computed only so run.adjust.adjusted can be cross-checked
                if len(b10) >= 10:
                    r["m3_prof"] = Ys[sorted(b10, key=lambda k: -np.nansum(Ys[k, :, j]))[:3]][:, :, j].mean(0)
                acc.stop("m3_own", t0)
                r["_fb"] = (fpj, fcs)
                base[j] = r
            for j in part:
                if j not in base or "pjm0_prof" not in base[j]:
                    continue
                Ltrue = Ys[d, WIN, j].sum()          # R1: Ytrue is Ys (no injection)
                if not Ltrue > 0:
                    continue
                rec = dict(site=site.name, b=cols[j], d=int(d), fold=f, L=Ltrue, morning=Ys[d, mh, j].tolist())
                for k_, v in base[j].items():
                    if not k_.endswith("_prof"):
                        continue
                    rec[k_.replace("_prof", "")] = v[WIN].sum()
                    rec[k_.replace("_prof", "") + "_m"] = v[mh].tolist()
                # donor pool
                t0 = acc.start()
                don = [q for q in dpool if q in base and "pjm0_prof" in base[q] and Ys[d, WIN, q].sum() > 0]
                acc.stop("shared_donorlist", t0)
                if len(don) >= 5:
                    nw = len(WIN)
                    t0 = acc.start()
                    rec["don_L"] = float(sum(Ys[d, WIN, q].sum() for q in don))
                    rec["don_pjm0"] = float(sum(base[q]["pjm0_prof"][WIN].sum() for q in don))
                    acc.stop("cg0_own", t0)
                    t0 = acc.start()
                    rec["don_pjmA"] = float(sum(base[q]["pjm0_prof"][WIN].sum() + nw * (Ys[d, H_PJM, q].mean() - base[q]["pjm0_prof"][H_PJM].mean()) for q in don))
                    acc.stop("cgA_own", t0)
                    for Wn, kind in ((C.SCM_W, "scmR"), (C.SCM_C_W, "scmC")):
                        t0 = acc.start()
                        tr = past(j, Wn, 120)
                        if len(tr) < max(2, Wn // 2):
                            acc.stop(kind + "_own", t0)
                            continue
                        dd = [q for q in don if complete[tr, q].all() and complete[d, q]]
                        if len(dd) < 5:
                            acc.stop(kind + "_own", t0)
                            continue
                        LK.a6_donor_pre(tr, d)
                        Xm = np.vstack([Ys[tr][:, :, dd].reshape(-1, len(dd)), Ys[d, PRE_DONOR, :][:, dd]])
                        y = np.r_[Ys[tr][:, :, j].reshape(-1), Ys[d, PRE_DONOR, j]]
                        mx = Xm.mean(0)
                        my = y.mean()
                        if (mx <= 0).any() or my <= 0:
                            acc.stop(kind + "_own", t0)
                            continue
                        Xn, yn = Xm / mx, y / my
                        Xw = (Ys[d][:, dd] / mx)[WIN]
                        if kind == "scmR":
                            w = BL.ridge_s1(Xn, yn, C.SCM_LAM)
                            rec["scmR"] = float((Xw @ w).sum() * my)
                        else:
                            w = BL.classic(Xn, yn)
                            rec["scmC"] = float((Xw @ w).sum() * my)
                        acc.stop(kind + "_own", t0)
                rows.append(rec)
                nrows += 1
    return rows


def time_adjust(df, s, e, reps):
    """Vectorised I-morn adjustments over the whole R1 frame (copy of the formulas of run.adjust.adjusted, split per method).
    Returns {method: median seconds}, plus the value columns for validation against run.adjust.adjusted."""
    nw = e - s
    out_t = {}
    res = {}

    def one(name, fn):
        ts = []
        for _ in range(reps):
            t0 = pc()
            v = fn()
            ts.append(pc() - t0)
        out_t[name] = float(np.median(ts))
        res[name] = v

    H = {k: [s + a for a in C.ADJ[k]] for k in C.ADJ}
    off = s - 6

    def mhf(arr, hs):
        return arr[:, [h - off for h in hs]].mean(1)

    def shared():
        for k in C.ADJ:
            LK.a3_hours(H[k], s, "I-morn")
        return adjust.shaped_morning(df, s, 0.0, "4h", False)
    ts = []
    for _ in range(reps):
        t0 = pc()
        m = shared()
        pj = adjust._prof(df, "pjm0")
        ca = adjust._prof(df, "caiso0")
        ny = adjust._prof(df, "ny0")
        ie = adjust._prof(df, "isone0")
        dm_ = adjust._prof(df, "dm0")
        wm_ = adjust._prof(df, "wm0")
        ts.append(pc() - t0)
    out_t["shared_adjprep"] = float(np.median(ts))
    nwf = float(nw)
    one("pjmA", lambda: df.pjm0.values + nwf * (mhf(m, H["pjm"]) - mhf(pj, H["pjm"])))
    lo, hi = C.CLIP["caiso"]
    one("caisoA", lambda: df.caiso0.values * np.clip(mhf(m, H["caiso"]) / mhf(ca, H["caiso"]), lo, hi))
    lo, hi = C.CLIP["ny"]
    one("nyA", lambda: df.ny0.values * np.clip(mhf(m, H["ny"]) / mhf(ny, H["ny"]), lo, hi))
    one("isoneA", lambda: np.maximum(df.isone0.values + nwf * (mhf(m, H["isone"]) - mhf(ie, H["isone"])), 0))
    lo, hi = C.CLIP["dm"]
    one("dmA", lambda: df.dm0.values * np.clip(mhf(m, H["dm"]) / mhf(dm_, H["dm"]), lo, hi))
    lo, hi = C.CLIP["wm"]
    one("wmA", lambda: df.wm0.values * np.clip(mhf(m, H["wm"]) / mhf(wm_, H["wm"]), lo, hi))
    one("cgA", lambda: (df.pjm0.values + nwf * (mhf(m, H["pjm"]) - mhf(pj, H["pjm"]))) * df.don_L.values / df.don_pjmA.values)
    return out_t, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default=None)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    fh = freeze.check_manifest()
    import psutil
    year = 2017
    win = C.WINDOWS["primary"]
    t0 = pc()
    Y = D.build_year(year, win)
    t_load = pc() - t0
    names = a.sites.split(",") if a.sites else list(C.SITES)
    sites = []
    t0 = pc()
    for n in names:
        st, _ = D.make_site(Y, n)
        if st is not None:
            sites.append(st)
    t_site = pc() - t0
    print("loaded", round(t_load, 1), "s; sites built", round(t_site, 1), "s; n sites", len(sites), flush=True)
    free_gb = psutil.virtual_memory().available / 1e9
    print("free RAM GB", round(free_gb, 2), flush=True)
    assert free_gb > 1.5, "free RAM below 1.5 GB: stop"
    reps = []
    rows = None
    for r in range(a.reps):
        acc = Acc()
        rr = []
        t0 = pc()
        for st in sites:
            rr += run_site(st, acc)
            assert psutil.virtual_memory().available / 1e9 > 1.5, "free RAM below 1.5 GB: stop"
        acc.t["_total"] = pc() - t0
        reps.append(acc.t)
        rows = rr
        print("rep", r, "total s", round(acc.t["_total"], 1), flush=True)
    df = pd.DataFrame(rows)
    n_ev = len(df)
    # validation against the frozen R1 frame
    fr = pd.read_pickle(C.ROOT / "results" / "run" / "events_R1.pkl")
    fr = fr[fr.site.isin(df.site.unique())]
    mrg = df.merge(fr, on=["site", "b", "d", "fold"], suffixes=("", "_f"))
    val = {"n_mine": n_ev, "n_frozen": len(fr), "n_matched": len(mrg)}
    for c, cf in [("pjm0", "pjm0"), ("prev", "prev"), ("caiso0", "caiso0"), ("ny0", "ny0"), ("isone0", "isone0"),
                  ("dm0", "dm0"), ("wm0", "wm0"), ("mid8", "mid8"), ("scmR", "scmr_W%d_l%g" % (C.SCM_W, C.SCM_LAM)),
                  ("scmC", "scmc_W%d" % C.SCM_C_W), ("don_L", "don_L"), ("don_pjm0", "don_pjm0"), ("don_pjmA", "don_pjmA")]:
        if c in mrg and cf in mrg:
            x = mrg[c].values if c != cf else mrg[c].values
            y = mrg[cf + ("_f" if c == cf else "")].values
            ok = np.isclose(x.astype(float), y.astype(float), rtol=1e-9, atol=1e-9, equal_nan=True)
            val[c] = "max_abs_diff=%.3g, all_close=%s" % (np.nanmax(np.abs(x.astype(float) - y.astype(float))), bool(ok.all()))
    print("validation", json.dumps(val), flush=True)
    s_, e_ = win
    adj_t, adj_v = time_adjust(df, s_, e_, a.reps)
    # cross-check A variants vs frozen adjust.adjusted
    ref = adjust.adjusted(df, s_, e_)
    for m in ["pjmA", "caisoA", "nyA", "isoneA", "dmA", "wmA", "cgA"]:
        ok = np.allclose(adj_v[m], ref[m], rtol=1e-9, atol=1e-9, equal_nan=True)
        val["adj_" + m] = bool(ok)
    ts = []
    for _ in range(a.reps):
        t0 = pc()
        adjust.adjusted(df, s_, e_)
        ts.append(pc() - t0)
    adj_total = float(np.median(ts))
    print("adjust checks", {k: v for k, v in val.items() if k.startswith("adj_")}, "adjusted() total s", round(adj_total, 4), flush=True)
    # memory pass (one extra, with tracemalloc)
    tracemalloc.start()
    accm = Acc(mem=True)
    for st in sites:
        run_site(st, accm)
    tracemalloc.stop()
    peak_proc = psutil.Process().memory_info().peak_wset / 1e9
    med = {k: float(np.median([rp[k] for rp in reps])) for k in reps[0]}
    # method totals (own + prerequisites)
    sh = med["shared_p45"]
    don = med.get("shared_donorlist", 0.0)
    tot = {
        "prev": (med["prev_own"] + sh, ["shared_p45", "prev_own"]),
        "pjm0": (med["pjm0_own"] + sh, ["shared_p45", "pjm0_own"]),
        "caiso0": (med["caiso0_own"] + sh, ["shared_p45", "caiso0_own"]),
        "ny0": (med["ny0_own"], ["ny0_own"]),
        "isone0": (med["isone0_own"], ["isone0_own"]),
        "dm0": (med["dm0_own"], ["dm0_own"]),
        "wm0": (med["wm0_own"], ["wm0_own"]),
        "mid8": (med["mid8_own"] + sh, ["shared_p45", "mid8_own"]),
        "cg0": (med["cg0_own"] + med["pjm0_own"] + sh + don, ["shared_p45", "pjm0_own", "shared_donorlist", "cg0_own"]),
        "scmR": (med["scmR_own"] + don + med["pjm0_own"] + sh, ["shared_p45", "pjm0_own", "shared_donorlist", "scmR_own"]),
        "scmC": (med["scmC_own"] + don + med["pjm0_own"] + sh, ["shared_p45", "pjm0_own", "shared_donorlist", "scmC_own"]),
    }
    # adjusted variants: base 0-variant cost + vectorised adjustment (per event the same unit)
    pre = adj_t["shared_adjprep"]
    for m, b in [("pjmA", "pjm0"), ("caisoA", "caiso0"), ("nyA", "ny0"), ("isoneA", "isone0"), ("dmA", "dm0"), ("wmA", "wm0")]:
        tot[m] = (tot[b][0] + adj_t[m] + pre, tot[b][1] + ["adj_" + m, "adj_shared"])
    tot["cgA"] = (tot["cg0"][0] + med["cgA_own"] + adj_t["cgA"] + pre, tot["cg0"][1] + ["cgA_own", "adj_cgA", "adj_shared"])
    # peak working memory (traced, incremental to the loaded data), per method (own steps + prerequisites, max)
    pk = dict(accm.peak)
    peak = {}
    for m, (_, parts) in tot.items():
        peak[m] = max([pk.get(p, 0) for p in parts if not p.startswith("adj_")] + [0])
    adj_rows = n_ev
    # TOWT: not in the frozen core frame
    note_towt = "n/a: towt70, towt7 are listed in baselines.INFO but are not computed by the frozen run_rule (no TOWT column in events_R1.pkl)"
    cpu = platform.processor()
    try:
        import subprocess
        cpu = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"], text=True).strip()
    except Exception:
        pass
    machine = {"cpu_model": cpu, "logical_threads": str(os.cpu_count()), "python": platform.python_version(),
               "numpy": np.__version__, "os": platform.platform(), "mode": "single process, CPU only, 3 repeats median, perf_counter"}
    import scipy
    machine["scipy"] = scipy.__version__
    led = LD.Ledger("final", year, freeze_hash=fh, source_default="src/secondary/timing_methods.py")
    _add = led.add
    led.add = lambda *a_, **k_: _add(*a_, **{"family_id": "secondary", **k_})
    for m, (t, parts) in tot.items():
        led.add("compute.method.%s.time_s_median" % m, round(t, 4), n_events=n_ev, n_sites=len(sites))
        led.add("compute.method.%s.ms_per_event" % m, round(t * 1000.0 / n_ev, 5), n_events=n_ev, n_sites=len(sites))
        led.add("compute.method.%s.peak_mem_gb" % m, round(peak[m] / 1e9, 6), n_events=n_ev, n_sites=len(sites))
    for k in ("shared_p45", "shared_donorlist"):
        led.add("compute.method.%s.time_s_median" % k, round(med[k], 4), n_events=n_ev, n_sites=len(sites))
    led.add("compute.method.shared_adjprep.time_s_median", round(adj_t["shared_adjprep"], 6), n_events=n_ev)
    led.add("compute.method.adjusted_all.time_s_median", round(adj_total, 6), n_events=n_ev)
    led.add("compute.method.all_unique.time_s_median", round(med["_total"], 3), n_events=n_ev)
    led.add("compute.shared.load_year.time_s", round(t_load, 2))
    led.add("compute.shared.make_sites.time_s", round(t_site, 2))
    led.add("compute.shared.process_peak_wset_gb", round(peak_proc, 3))
    led.add("compute.method.towt.note", note_towt)
    led.add("compute.method.lgbM.note", "n/a here: see compute.hpo.lgbM.* and compute.eval.lgbM.* (whole-run times, not per-method medians)")
    led.add("compute.method.definition", "time_s_median = median of %d full passes over all 2017 R1 building-events of the method plus the prerequisite steps it needs when run alone; ms_per_event = time_s*1000/n_events; peak_mem_gb = peak incremental tracemalloc working set of the method steps (data excluded; see compute.shared.process_peak_wset_gb for the whole process)" % a.reps)
    for k, v in machine.items():
        led.add("compute.machine." + k, v)
    out = a.out or str(C.ROOT / "results" / "secondary" / "2017" / "timing_methods.rows.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fr_out = led.to_frame()
    fr_out["p_holm"] = np.nan
    fr_out.to_csv(out, index=False)
    json.dump({"validation": val, "median_steps_s": med, "adj_steps_s": adj_t, "peaks_bytes": pk, "reps_totals": [r["_total"] for r in reps], "n_events": n_ev}, open(os.path.splitext(out)[0] + ".debug.json", "w"), indent=1, default=str)
    print("wrote", out, flush=True)
    for m, (t, _) in tot.items():
        print("%-8s %9.3f s  %8.4f ms/event  peak %.4f MB" % (m, t, t * 1000 / n_ev, peak[m] / 1e6), flush=True)


if __name__ == "__main__":
    main()
