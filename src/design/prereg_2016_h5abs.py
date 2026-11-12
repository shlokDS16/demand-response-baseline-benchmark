"""H5 with ABSOLUTE erosion (controller decision D12), 2016 development only (_v0).
eta_m(site) = least-squares slope over K = 10, 20, 30, 40 of the site median over buildings of |rho_b - 1|, where
rho_b = mean over the 10 scored days of estimated / true curtailment (c = 0.10), on the fixed common support of
building-events present at all four K for both pjmA and scmR. Site value = eta(pjmA) - eta(scmR); one-sided (> 0).
Reuses the test/interval functions and baselines of prereg_2016_rev2.py (executed up to its H1 block only).
Writes results/prereg2016/summary_h5abs.json.
"""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "prereg_2016_rev2.py"), encoding="utf-8").read().split("# ---------------- H1 ----------------")[0]
exec(compile(src, "prereg_2016_rev2.py", "exec"))   # defines R1, R3, ER (self-written pickles, trusted), tests, baselines

C = 0.10
Bm = baselines(ER)
Lobs = ER.L.values; Lt = Lobs / (1 - C)
te = pd.DataFrame({m: (Bm[m] - Lobs) / (C * Lt) for m in ["pjmA", SCM, "caisoA", "pjm0", "cgA"]})
te[["site", "b", "day", "K"]] = ER[["site", "b", "day", "K"]].values
te = te.dropna(subset=["pjmA", SCM])
Ks = [10, 20, 30, 40]
full = te.groupby(["site", "b", "day"]).K.nunique()
keep = full[full == 4].index
te = te.set_index(["site", "b", "day"]).loc[keep].reset_index()
out = {"definition": "D12 absolute erosion", "support_events_per_K": int(len(keep)), "scm": SCM}
eta, curves = {}, {}
for m in ["pjmA", SCM, "caisoA", "pjm0", "cgA"]:
    eta[m], curves[m] = {}, {}
    for s, g in te.groupby("site"):
        if g[g.K == 10].shape[0] < MIN_SUPPORT:
            continue
        y = [float((g[g.K == k].groupby("b")[m].mean() - 1).abs().median()) for k in Ks]
        curves[m][s] = [round(v, 4) for v in y]
        eta[m][s] = float(np.polyfit(Ks, y, 1)[0])
pool = {m: [float((te[te.K == k].groupby("b")[m].mean() - 1).abs().median()) for k in Ks] for m in eta}
d = pd.Series(eta["pjmA"]) - pd.Series(eta[SCM])
sr = signed_rank(d.values, "greater")
def signed_rank_two_sided(x):
    """D13: exact two-sided signed-rank by full enumeration; zeros dropped and counted; average ranks."""
    from itertools import product
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    nz = np.abs(x) < 1e-12; x = x[~nz]; n = len(x)
    rk = rankdata(np.abs(x)); M = rk.sum(); obs = abs(rk[x > 0].sum() - M / 2)
    tot = cnt = 0
    for sg in product([0, 1], repeat=n):
        tot += 1
        cnt += abs(rk[np.array(sg, bool)].sum() - M / 2) >= obs - 1e-9
    return {"p": cnt / tot, "n": n, "n_zero": int(nz.sum())}
sr2 = signed_rank_two_sided(d.values)
est, ci = hl_ci(d.values, 0.95)
v = d.values
out["H5abs"] = {"site_values": d.round(5).to_dict(), "n_sites": int(len(d)), "n_positive": int((v > 0).sum()),
                "HL": round(est, 5), "HL_ci95": [round(c, 5) for c in ci], "signed_rank_one_sided_greater": sr, "signed_rank_two_sided": sr2,
                "mde_site": round(float(2.8 * d.std(ddof=1) / np.sqrt(len(d))), 5)}
out["eta_abs_site"] = {m: {s: round(x, 5) for s, x in e.items()} for m, e in eta.items()}
out["eta_abs_pooled"] = {m: round(float(np.polyfit(Ks, pool[m], 1)[0]), 5) for m in pool}
out["abs_err_pooled_by_K"] = {m: [round(x, 4) for x in pool[m]] for m in pool}
out["site_curves"] = curves
# D13 mechanism diagnostic: median over building-events of the mean age (days) of the PJM lookback and scmR pre-period
ag = ER.set_index(["site", "b", "day"]).loc[keep].reset_index()
scol = "scm_age_W" + SCM.split("_W")[1].split("_")[0]
out["age_days_median_by_K"] = {"pjm_lookback": {str(k): round(float(ag[ag.K == k].pjm_age.median()), 2) for k in Ks},
                               "scmR_preperiod": {str(k): round(float(ag[ag.K == k][scol].median()), 2) for k in Ks}}
json.dump(out, open(os.path.join(OUT, "summary_h5abs.json"), "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k != "site_curves"}, indent=1, default=str))
