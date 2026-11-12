"""Baselines of PREREG s3 with their information-set tags. run_rule() is the development logic of
src/design/prereg_2016.py (run_rule) with the window and hours parametrised and the s9 leakage assertions inline.
Adjustments of the I-morn variants (pjmA, caisoA, ...) are applied in adjust.py from the stored morning hours."""
import numpy as np
from scipy.optimize import nnls

from . import config as C
from . import leakage as LK

# information-set tag per method (PREREG s3 table)
INFO = {"prev": "I-hist", "pjm0": "I-hist", "pjmA": "I-morn", "caiso0": "I-hist", "caisoA": "I-morn", "ny0": "I-hist",
        "nyA": "I-morn", "isone0": "I-hist", "isoneA": "I-morn", "mid8": "I-hist", "dm0": "I-hist", "dmA": "I-morn",
        "wm0": "I-hist", "wmA": "I-morn", "m3": "I-hist", "m3A": "I-morn", "towt70": "I-hist", "towt70A": "I-morn",
        "towt7": "I-hist", "cgA": "I-donor+I-morn", "cg0": "I-donor", "scmR": "I-donor", "scmC": "I-donor",
        "lgbM": "I-morn", "lgbD": "I-donor"}
LABEL = {"prev": "core (trivial)", "pjm0": "core", "pjmA": "core, primary rule", "caiso0": "core", "caisoA": "core",
         "ny0": "core", "nyA": "core", "cgA": "core (H3)", "scmR": "core, primary donor method", "towt70": "core",
         "lgbM": "core", "lgbD": "core"}


def ridge_s1(Xm, y, lam):
    """Linear SCM: ridge, weights sum to one, no non-negativity, no intercept (Sievers and Roozbehani 2026)."""
    A = Xm.T @ Xm + lam * np.eye(Xm.shape[1])
    Ai = np.linalg.solve(A, np.c_[Xm.T @ y, np.ones(Xm.shape[1])])
    a, b = Ai[:, 0], Ai[:, 1]
    return a - b * (a.sum() - 1) / b.sum()


def classic(Xm, y):
    M = C.SCM_CLASSIC_PENALTY
    w, _ = nnls(np.vstack([Xm, M * np.ones(Xm.shape[1])]), np.r_[y, M], maxiter=5000)
    return w


def morning_hours(s):
    return list(range(s - 6, s))


def hrs(s, key):
    return [s + a for a in C.ADJ[key]]


def run_rule(site, Ys, Ytrue, evset, ev_score, part, dpool, scm="grid", do_scm=True, track=None):
    """Baselines for every (event day in ev_score) x (building in part). Ys: load as the lookbacks see it (after
    injection); Ytrue: counterfactual no-curtailment load (target L); both days x 24 x nb.
    scm: 'grid' (all W x lambda + classic W) or (W, lam). Returns list of dict rows."""
    s, WIN = site.s, site.WIN
    wk, complete, tm = site.wk, site.complete, site.tm
    cols, use = site.meters, site.use
    H_PJM, H_NY, H_DM, H_ISONE = hrs(s, "pjm"), hrs(s, "ny"), hrs(s, "dm"), hrs(s, "isone")
    PRE_DONOR = list(range(0, s - 4))                   # target event-day hours usable by I-donor methods (< s-4)
    mh = morning_hours(s)
    # s9.3 static: adjustment hours <= s-2 and never the window
    for key in C.ADJ:
        LK.a3_hours(hrs(s, key), s, "I-morn")
        LK.a3_window_unused(hrs(s, key), WIN)
    LK.a3_hours(PRE_DONOR, s, "I-donor")
    LK.a7_folds(part, dpool)
    Lc = np.where(complete, Ys[:, WIN, :].sum(1), np.nan)
    rows = []
    # DEV-1 (research/DEVIATIONS.md): final mode must also compute scmC at its own fixed W (C.SCM_C_W, PREREG s5)
    grid_W = C.SCM_GRID_W if scm == "grid" else sorted({scm[0], C.SCM_C_W})
    grid_L = C.SCM_GRID_LAM if scm == "grid" else [scm[1]]
    for d in sorted(ev_score):
        fb = {"pjm": 0, "caiso": 0}

        def past(j, n, maxback, excl_daybefore=False):
            out = []
            for k in range(d - 1, max(d - maxback - 1, -1), -1):
                if not wk[k] or not complete[k, j]:
                    continue
                if k in evset:
                    continue
                if excl_daybefore and (k + 1) in evset:
                    continue
                out.append(k)
                if n and len(out) == n:
                    break
            LK.a1_lookback_before(d, out)
            LK.a2_no_event_days(evset, out, day_before=excl_daybefore)
            return out

        base = {}
        for j in list(part) + list(dpool):
            if not complete[d, j]:
                continue
            p45 = past(j, 0, 45)
            r = {}
            fpj = 0
            p5 = p45[:5]
            if len(p5) < 4:   # declared fallback of the rule text: add highest-window-load event days
                evd = [k for k in range(max(d - 45, 0), d) if k in evset and wk[k] and complete[k, j]]
                evd = sorted(evd, key=lambda k: -Lc[k, j])[: 4 - len(p5)]
                LK.a1_lookback_before(d, evd)
                p5 = p5 + evd
                fpj = 1
            if len(p5) >= 4:
                m5 = np.array([Lc[k, j] for k in p5])
                p5k = [k for k, v in zip(p5, m5) if v >= C.PJM_DROP * m5.mean()]
                p4 = sorted(p5k, key=lambda k: -Lc[k, j])[:4]
                r["pjm0_prof"] = Ys[p4][:, :, j].mean(0)
                r["_pjm_age"] = float(np.mean([d - k for k in p4]))   # D13 diagnostic: mean lookback age (days)
            fcs = 0
            c10 = p45[:10]
            n10 = len(c10)
            if len(c10) < 5:
                evd = [k for k in range(max(d - 45, 0), d) if k in evset and wk[k] and complete[k, j]]
                evd = sorted(evd, key=lambda k: -Lc[k, j])[: 5 - len(c10)]
                LK.a1_lookback_before(d, evd)
                c10 = c10 + evd
                fcs = 1
            if len(c10) >= 5:
                r["caiso0_prof"] = Ys[c10][:, :, j].mean(0)
            p30 = past(j, 0, 30, excl_daybefore=True)
            if len(p30) >= 5:
                P = np.nanmax(Ys[max(d - 30, 0):d, WIN, j])
                p30 = [k for k in p30 if Ys[k, WIN, j].mean() >= 0.25 * P][:10]
                if len(p30) >= 5:
                    r["ny0_prof"] = Ys[sorted(p30, key=lambda k: -Lc[k, j])[:5]][:, :, j].mean(0)
            wd30 = [k for k in range(d - 1, -1, -1) if wk[k]][:30]
            ine = [k for k in wd30 if k not in evset and complete[k, j]][:10]
            LK.a1_lookback_before(d, ine)
            if len(ine) >= 5:
                r["isone0_prof"] = Ys[ine][:, :, j].mean(0)
            dm = past(j, 10, 90)
            if len(dm) == 10:
                r["dm0_prof"] = Ys[dm][:, :, j].mean(0)
            p90 = [k for k in past(j, 0, 90) if not np.isnan(tm[k])]
            if len(p90) >= 4 and not np.isnan(tm[d]):
                wm = sorted(p90, key=lambda k: (abs(tm[k] - tm[d]), d - k))[:4]
                r["wm0_prof"] = Ys[wm][:, :, j].mean(0)
            b10 = p45[:10]
            if len(b10) >= 10:
                r["m3_prof"] = Ys[sorted(b10, key=lambda k: -np.nansum(Ys[k, :, j]))[:3]][:, :, j].mean(0)
                srt = sorted(b10, key=lambda k: Lc[k, j])[1:9]
                r["mid8_prof"] = Ys[srt][:, :, j].mean(0)
            if p45:
                r["prev_prof"] = Ys[p45[0], :, j]
            r["_fb"] = (fpj, fcs)
            r["_n10"] = n10
            base[j] = r
        for j in part:
            if j not in base or "pjm0_prof" not in base[j]:
                continue
            Ltrue = Ytrue[d, WIN, j].sum()
            if not Ltrue > 0:
                continue
            rec = dict(site=site.name, b=cols[j], use=use[j], d=int(d), day=str(site.days[d].date()), L=Ltrue,
                       Lobs=float(Ys[d, WIN, j].sum()), morning=Ytrue[d, mh, j].tolist(),
                       morning_obs=Ys[d, mh, j].tolist(), pjm_fb=base[j]["_fb"][0], caiso_fb=base[j]["_fb"][1], caiso_n=base[j]["_n10"], pjm_age=base[j].get("_pjm_age", np.nan))
            for k_, v in base[j].items():
                if not k_.endswith("_prof"):
                    continue
                rec[k_.replace("_prof", "")] = v[WIN].sum()
                rec[k_.replace("_prof", "") + "_m"] = v[mh].tolist()
            don = [q for q in dpool if q in base and "pjm0_prof" in base[q] and Ys[d, WIN, q].sum() > 0]
            rec["ndon"] = len(don)
            if len(don) >= 5:
                nw = len(WIN)
                rec["don_L"] = float(sum(Ys[d, WIN, q].sum() for q in don))
                rec["don_pjm0"] = float(sum(base[q]["pjm0_prof"][WIN].sum() for q in don))
                rec["don_pjmA"] = float(sum(base[q]["pjm0_prof"][WIN].sum() + nw * (Ys[d, H_PJM, q].mean() - base[q]["pjm0_prof"][H_PJM].mean()) for q in don))
                if do_scm:
                    for Wn in grid_W:
                        tr = past(j, Wn, 120)
                        if len(tr) < max(2, Wn // 2):
                            continue
                        dd = [q for q in don if complete[tr, q].all() and complete[d, q]]
                        if len(dd) < 5:
                            continue
                        LK.a6_donor_pre(tr, d)
                        Xm = np.vstack([Ys[tr][:, :, dd].reshape(-1, len(dd)), Ys[d, PRE_DONOR, :][:, dd]])
                        y = np.r_[Ys[tr][:, :, j].reshape(-1), Ys[d, PRE_DONOR, j]]
                        mx = Xm.mean(0)
                        my = y.mean()
                        if (mx <= 0).any() or my <= 0:
                            continue
                        Xn, yn = Xm / mx, y / my
                        Xw = (Ys[d][:, dd] / mx)[WIN]
                        for lam in grid_L:
                            w = ridge_s1(Xn, yn, lam)
                            rec["scmr_W%d_l%g" % (Wn, lam)] = float((Xw @ w).sum() * my)
                        w = classic(Xn, yn)
                        rec["scmc_W%d" % Wn] = float((Xw @ w).sum() * my)
                        rec["scm_age_W%d" % Wn] = float(np.mean([d - k for k in tr]))   # D13 diagnostic
            rows.append(rec)
    return rows
