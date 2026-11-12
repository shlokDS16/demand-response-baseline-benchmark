"""Validation of src/run against the 2016 development values (results/prereg2016/summary_rev2.json, summary_h5abs.json,
summary.json) and the development event tables. Not a pytest module. Usage: python -I tests/validate_2016.py
Reads results/run_v0/results_state.pkl and results/run_v0/events_*.pkl (self-written by src/run; trusted)."""
import json
import os
import pickle
import site
import sys

up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(ROOT, "results", "prereg2016")
RUN = os.path.join(ROOT, "results", "run_v0", *(sys.argv[1:2] or []))
st = pickle.load(open(os.path.join(RUN, "results_state.pkl"), "rb"))
rev2 = json.load(open(os.path.join(DEV, "summary_rev2.json")))
h5a = json.load(open(os.path.join(DEV, "summary_h5abs.json")))
summ = json.load(open(os.path.join(DEV, "summary.json")))
rows = []


def cmp(name, dev, new, tol=1e-6):
    if isinstance(dev, str) or isinstance(new, str):
        ok = str(dev) == str(new)
        diff = "" if ok else "differs"
    else:
        diff = abs(float(dev) - float(new)) if np.isfinite(dev) and np.isfinite(new) else (0.0 if dev == new else np.inf)
        ok = diff <= tol
    rows.append((name, dev, new, diff if not isinstance(diff, float) else "%.2e" % diff, "OK" if ok else "DIFF"))
    return ok


def events(name):
    a = pd.read_pickle(os.path.join(DEV, "events_%s.pkl" % name))
    b = pd.read_pickle(os.path.join(RUN, "events_%s.pkl" % name))
    return a, b


# ---------------- event-level ----------------
for nm in ("R1", "R3"):
    a, b = events(nm)
    keys = ["site", "b", "day"] + (["draw"] if nm == "R3" else [])
    if nm == "R3":
        b = b.assign(draw=b.draw)
    a = a.set_index(keys)
    b = b.set_index(keys)
    cmp("events_%s rows" % nm, len(a), len(b))
    cmp("events_%s key sets equal" % nm, int(a.index.sort_values().equals(b.index.sort_values())), 1)
    b = b.reindex(a.index)
    worst, wcol, nanbad = 0.0, "", 0
    for c in a.columns:
        if c in b and pd.api.types.is_float_dtype(a[c]):
            x, y = a[c].values, b[c].values
            nanbad += int((np.isnan(x) != np.isnan(y)).sum())
            if np.isfinite(x).any():
                dd = np.nanmax(np.abs(x - y))
                if dd > worst:
                    worst, wcol = dd, c
    cmp("events_%s max abs diff over all float columns (%s)" % (nm, wcol), 0.0, worst, 1e-6)
    cmp("events_%s NaN-pattern mismatches" % nm, 0, nanbad)
a, b = pd.read_pickle(os.path.join(DEV, "events_erosion.pkl")), pd.read_pickle(os.path.join(RUN, "events_erosion.pkl"))
a = a.set_index(["site", "b", "day", "K"])
b = b.set_index(["site", "b", "day", "K"])
cmp("events_erosion rows", len(a), len(b))
b = b.reindex(a.index)
worst = max(np.nanmax(np.abs(a[c].values - b[c].values)) for c in a.columns if c in b and pd.api.types.is_float_dtype(a[c]) and a[c].notna().any() and c not in ("pjm_age",) and not c.startswith("scm_age"))
cmp("events_erosion max abs diff", 0.0, worst, 1e-6)

# ---------------- hypotheses ----------------
core = st["core"]


def sites(name, dev_sv, new_sv, tol=1e-4):
    for s_ in dev_sv:
        cmp("%s site %s" % (name, s_), dev_sv[s_], new_sv.get(s_, np.nan), tol)


for H, key in (("H1", "H1"), ("H2", "H2"), ("H3", "H3")):
    d, n = rev2[H], core[H]
    sites(H, d["site_values"], n["site_values"])
    cmp(H + " HL", d["HL"], n["est"], 1e-4)
    ci = d.get("HL_ci95") or d.get("HL_ci90")
    cmp(H + " CI low", ci[0], n["ci_low"], 1e-4)
    cmp(H + " CI high", ci[1], n["ci_high"], 1e-4)
cmp("H1 signed-rank p", rev2["H1"]["signed_rank"]["p"], core["H1"]["p"])
cmp("H2 signed-rank p", rev2["H2"]["signed_rank"]["p"], core["H2"]["p"])
cmp("H3 p_lower", rev2["H3"]["p_lower"], core["H3"]["p_lower"])
cmp("H3 p_upper", rev2["H3"]["p_upper"], core["H3"]["p_upper"])
cmp("H3 p_TOST", rev2["H3"]["p_TOST"], core["H3"]["p"])
# H4
pre = st["precool"]["4h"]
d4 = rev2["H4"]
for s_, v in d4["site_pcross"].items():
    nv = pre["site_pcross"].get(s_)
    nv = ">0.30" if (nv is not None and np.isinf(nv)) else nv
    cmp("H4 site p-cross %s" % s_, v, nv if isinstance(nv, str) else round(float(nv), 4), 1e-4)
cmp("H4 sign-test p", d4["sign_test_less_0.10"]["p"], pre["p"])
cmp("H4 signed-rank sensitivity p (censored ranked largest)", d4["signed_rank_sensitivity"]["p"], pre["p_signedrank_capped"])
cmp("H4 median site p-cross", d4["median_site_pcross"], round(pre["median_site"], 4), 1e-4)
cmp("H4 order-stat CI low", d4["median_ci95_order_stat"][0], round(pre["ci_low"], 4), 1e-4)
cmp("H4 order-stat CI high", d4["median_ci95_order_stat"][1], round(pre["ci_high"], 4), 1e-4)
cmp("H4 pooled p-cross", d4["pooled_pcross"], ">0.30" if np.isinf(pre["pooled"]) else round(pre["pooled"], 4), 1e-4)
for m, v in rev2["pstar_pooled"].items():
    nm = {"scmr_W7_l3": "scmR"}.get(m, m)
    nv = pre["pstar"][nm]
    cmp("p* pooled %s" % m, v, ">0.30" if np.isinf(nv) else round(nv, 4), 1e-4)
# H5 (D12/D13)
e = st["erosion"]
h = h5a["H5abs"]
cmp("H5 support events per K", h5a["support_events_per_K"], e["n_events_common"])
sites("H5abs", h["site_values"], e["contrast"]["pjmA"]["site_values"], 1e-4)
cmp("H5abs HL", h["HL"], e["contrast"]["pjmA"]["est"], 1e-4)
cmp("H5abs HL ci low", h["HL_ci95"][0], e["contrast"]["pjmA"]["ci_low"], 1e-4)
cmp("H5abs HL ci high", h["HL_ci95"][1], e["contrast"]["pjmA"]["ci_high"], 1e-4)
cmp("H5abs two-sided p", h["signed_rank_two_sided"]["p"], e["contrast"]["pjmA"]["p"])
for m, v in h5a["eta_abs_pooled"].items():
    cmp("H5abs pooled eta %s" % m, v, round(e["methods"]["scmR" if m.startswith("scmr") else m]["eta_abs"], 5), 1e-4)
for K, (dv, nv) in enumerate(zip(["10", "20", "30", "40"], [10, 20, 30, 40])):
    for kind, nk in (("pjm_lookback", "pjm_lookback"), ("scmR_preperiod", "scmR_preperiod")):
        cmp("age days %s K=%s" % (kind, dv), h5a["age_days_median_by_K"][kind][dv], round(e["age_days_median_by_K"][nk][nv], 2), 0.011)
# rev2 signed H5 (secondary): pooled signed rho by K and etas
for m in ("pjmA", "caisoA", "pjm0", "cgA"):
    for i, K in enumerate((10, 20, 30, 40)):
        cmp("H5 signed rho %s K=%d" % (m, K), rev2["H5"]["rho_pooled_by_K"][m][i], round(e["methods"][m]["rho_pooled"][K], 4), 1e-4)
    cmp("H5 signed pooled eta %s" % m, rev2["H5"]["eta_pooled"][m], round(e["methods"][m]["eta"], 5), 1e-4)
cmp("H5 signed contrast HL (secondary)", rev2["H5"]["HL"], e["contrast_signed"]["pjmA"]["est"], 1e-4)
for K in (10, 40):
    cmp("fallback PJM K=%d" % K, rev2["H5"]["fallback_rate_by_K"][str(K)]["pjm_fb"], round(e["fallback_by_rule"][K]["PJM"], 4), 1e-4)
    cmp("fallback CAISO K=%d" % K, rev2["H5"]["fallback_rate_by_K"][str(K)]["caiso_fb"], round(e["fallback_by_rule"][K]["CAISO"], 4), 1e-4)
# SCM grid and method table (summary.json)
g = core.get("scm_grid", {})
for c in ("scmr_W7_l3", "scmr_W5_l3", "scmr_W3_l1", "scmr_W5_l1", "scmc_W5", "scmc_W3", "scmc_W7"):
    if c in summ["scm_grid_median_relMAE"]:
        cmp("scm grid %s" % c, summ["scm_grid_median_relMAE"][c], round(g[c], 4), 1e-4)
best = min([k for k in g if k.startswith("scmr_")], key=lambda k: g[k])
cmp("scm grid best ridge config", summ["scm_best_ridge"], best)
for rule in ("R1", "R3"):
    for m, v in summ["methods_2016"].get(rule, {}).items():
        mm = {"scmr_W7_l3": "scmR", "scmc_W5": "scmC"}.get(m, m)
        if mm in core["methods"].get(rule, {}):
            cmp("method %s %s relMAE median" % (rule, mm), v["median_relMAE"], round(core["methods"][rule][mm]["relMAE_median"], 4), 1e-4)
            cmp("method %s %s bias median" % (rule, mm), v["median_bias"], round(core["methods"][rule][mm]["bias_median"], 4), 1e-4)
# DST table
dst_new = pd.read_csv(os.path.join(RUN, "dst_table_recomputed.csv"))
dst_dev = pd.read_csv(os.path.join(DEV, "dst_table.csv"))
cmp("DST table identical", int(dst_new.fillna(-9).round(6).equals(dst_dev.fillna(-9).round(6))), 1)

df = pd.DataFrame(rows, columns=["check", "dev", "src/run", "abs diff", "status"])
out = os.path.join(RUN, "validation_2016.md")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(df.to_markdown(index=False) if hasattr(df, "to_markdown") else df.to_string())
print(df.to_string())
print("\nchecks: %d, OK: %d, DIFF: %d" % (len(df), (df.status == "OK").sum(), (df.status == "DIFF").sum()))
