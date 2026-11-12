"""Tables T1-T4 (CSV + booktabs LaTeX). Numbers from tables/summary.csv (and per-site event counts from events_R1.pkl)."""
import pandas as pd
from common import *

L = Ledger()
f = lambda v, d=3: ("%." + str(d) + "f") % v
# ---------------- T1 data and eligibility ----------------
sites11 = L.v("sample.sites").split(",")
all14 = sorted(sites11 + ["Bobcat", "Gator", "Moose"])
R1 = pd.read_pickle(RUN / "events_R1.pkl", )[["site"]]
ev = R1.site.value_counts().to_dict()
assert sum(ev.values()) == int(L.v("sample.n_events.R1"))
rows = []
for s in all14:
    e1 = int(L.v("sample.excl.%s.e1" % s)); fl = int(L.v("sample.excl.%s.e3_flat_meter" % s))
    dup = int(L.v("sample.excl.%s.dup_dropped" % s)); na = int(L.v("sample.excl.%s.n_after" % s))
    in11 = s in sites11
    rows.append([s, L.v("sample.dst.%s" % s), e1, fl, dup, na, "yes" if in11 else "no (E4)", ev.get(s, 0) if in11 else 0])
TS = lambda n: format(int(n), ",").replace(",", "{,}")   # thousands separator, as in the text (REVISION_1)
tot = ["All sites", "", int(L.v("sample.n_meters_e1")), int(L.v("sample.n_excl_flat_meter")), int(L.v("sample.n_dup_dropped")),
       int(sum(r[5] for r in rows)), "11 of 14", int(L.v("sample.n_events.R1"))]
assert tot[5] == int(L.v("sample.n_buildings")) + sum(r[5] for r in rows if r[6] != "yes")
rows.append(tot)
hdr = ["Site", "Timestamp convention", "E1 meters", "Flat-meter excl. (E3)", "Duplicates dropped", "Meters after E3", "In sample (E4)", "R1 building-events"]
write_csv(TAB / "T1.csv", hdr, rows)
rows_tex = [r[:2] + [TS(x) for x in r[2:6]] + [r[6], TS(r[7])] for r in rows]
write_tex(TAB / "T1.tex", hdr, rows_tex, r">{\raggedright\arraybackslash}p{1.6cm}>{\raggedright\arraybackslash}p{2.3cm}>{\raggedleft\arraybackslash}p{1.4cm}>{\raggedleft\arraybackslash}p{1.9cm}>{\raggedleft\arraybackslash}p{1.7cm}>{\raggedleft\arraybackslash}p{1.5cm}>{\raggedright\arraybackslash}p{1.9cm}>{\raggedleft\arraybackslash}p{2.0cm}")

# ---------------- T2 methods (design table; information set from the ledger) ----------------
S2 = Ledger("summary_secondary.csv")
D = Ledger("summary_derived.csv")
E = Ledger("summary_exploratory.csv")
EXTRA = {"m3A": "M3-adj", "towt70": "TOWT-70", "towt70A": "TOWT-70-adj", "towt7": "TOWT-7",
         "lgbM": "LightGBM-morn", "lgbD": "LightGBM-donor", "mlpM": "MLP-morn", "mlpD": "MLP-donor", "gscm": "GSCM"}
NAME.update(EXTRA)
NOT_RUN = "not run (see Limitations)"
PJM_SRC = "PJM Manual 11, s10.4.2; Tariff Att. K App. s3.3A"
M = [("prev", "Previous eligible weekday", "1 day", "none", "none", "trivial baseline"),
     ("pjm0", "PJM weekday baseline (highest 4 of 5 recent weekdays)", "45 days", "none", "none", PJM_SRC + " (as implemented)"),
     ("pjmA", "PJM with day-of adjustment (primary rule)", "45 days", "additive, hours s-4..s-2", "none", PJM_SRC),
     ("caiso0", "CAISO 10-in-10", "45 days", "none", "none", "CAISO BPM"),
     ("caisoA", "CAISO 10-in-10 with adjustment", "45 days", "ratio, hours s-4..s-2", "[0.8, 1.2]", "CAISO BPM"),
     ("ny0", "NYISO average-day", "30 days", "none", "none", "NYISO Manual 7"),
     ("nyA", "NYISO with adjustment", "30 days", "ratio, hours s-4, s-3", "[0.8, 1.2]", "NYISO Manual 7"),
     ("isone0", "ISO-NE 10 most recent weekdays", "30 days", "none", "none", "ISO-NE"),
     ("isoneA", "ISO-NE with adjustment", "30 days", "additive, hours s-3, s-2", "floor 0", "ISO-NE"),
     ("dm0", "Day matching (10 working days)", "10 days", "none", "none", "Granderson et al."),
     ("dmA", "Day matching with adjustment", "10 days", "ratio, hours s-4, s-3", "[0.8, 1.2]", "Granderson et al."),
     ("wm0", "Weather matching (4 of 90 days)", "90 days", "none", "none", "Granderson et al."),
     ("wmA", "Weather matching with adjustment", "90 days", "ratio, hours s-4, s-3", "[0.6, 1.4]", "Granderson et al."),
     ("m3", "Mathieu 3 of 10", "10 days", "none", "none", "Mathieu et al."),
     ("mid8", "Middle 8 of 10", "10 days", "none", "none", "ERCOT-style"),
     ("towt70", "Time-of-week and temperature regression (6 temperature bins)", "70 days", "none", "none", "Mathieu et al."),
     ("towt70A", "Time-of-week and temperature regression with adjustment", "70 days", "ratio, hours s-4, s-3", "[0.6, 1.4]", "Mathieu et al."),
     ("towt7", "Time-of-week and temperature regression, short training", "7 days", "none", "none", "Mathieu et al."),
     ("cg0", "Comparison group, unadjusted PJM ratio", "45 days + donors", "none", "none", "this study"),
     ("cgA", "Comparison group, PJM-adj ratio", "45 days + donors", "additive, hours s-4..s-2", "none", "this study"),
     ("scmR", "Ridge synthetic control (primary donor method)", "7 weekdays + morning", "donor weights", "weights sum to one", "Sievers and Roozbehani"),
     ("scmC", "Classic non-negative synthetic control", "5 weekdays + morning", "donor weights", "non-negative, sum to one", "Sievers and Roozbehani"),
     ("lgbM", "LightGBM learned adjustment, morning information", "day-level samples, monthly refit", "learned ratio to DM window", "none", "this study"),
     ("lgbD", "LightGBM learned adjustment, donor information", "day-level samples, monthly refit", "learned ratio to DM window", "none", "this study"),
     ("mlpM", "MLP learned adjustment, morning information", "day-level samples, monthly refit", "learned ratio to DM window", "none", "this study"),
     ("mlpD", "MLP learned adjustment, donor information", "day-level samples, monthly refit", "learned ratio to DM window", "none", "this study")]
INFO_FIX = {"mlpM": "I-morn", "mlpD": "I-donor"}   # no method.mlp*.info key in the ledger; same information sets as LightGBM
# preregistered (PREREG s3) but not run; listed only in Table B.1 (table_TB1.py), never in T2/T4
NOTRUN = [("gscm", "Augmented synthetic control", "I-donor", "Sievers and Roozbehani")]
rows2 = [[NAME[m], INFO_FIX.get(m) or L.v("method.%s.info" % m), d, lb, adj, cap, src] for m, d, lb, adj, cap, src in M]
# Methods without results (M3-adj, GSCM) are NOT rows of T2 or T4; Table B.1 lists them as "not evaluated" (table_TB1.py).
hdr2 = ["Method", "Information set", "Definition", "Lookback", "Adjustment", "Cap", "Source"]
write_csv(TAB / "T2.csv", hdr2, rows2)
notes2 = [r"PJM sources: PJM Manual 11, Energy \& Ancillary Services Market Operations, s10.4.2 "
          r"(\url{https://www.pjm.com/-/media/DotCom/documents/manuals/m11.pdf}), and PJM Open Access Tariff, "
          r"Attachment K Appendix, s3.3A.2 and s3.3A.3 "
          r"(\url{https://www.pjm.com/-/media/DotCom/committees-groups/committees/mic/20151202/20151202-item-06f-oatt-att-k-appx-sec-3-3a.pdf}). "
          r"The adjustment is additive and uncapped; ``as implemented'' notes that the 25\,\% exclusion is applied after taking the five most recent weekdays.",
          r"CAISO and ISO-NE unadjusted baselines coincide (main-text Table~\ref{tab:accuracy}). Hours $s-4,\dots$ are relative to the window start $s$."]
write_tex(TAB / "T2.tex", hdr2, rows2, r">{\raggedright\arraybackslash}p{1.9cm}>{\raggedright\arraybackslash}p{1.6cm}>{\raggedright\arraybackslash}p{2.8cm}>{\raggedright\arraybackslash}p{1.9cm}>{\raggedright\arraybackslash}p{2.2cm}>{\raggedright\arraybackslash}p{1.7cm}>{\raggedright\arraybackslash}p{2.3cm}", notes2)

# ---------------- T3 confirmatory results ----------------
def prow(h, key, pkey, label, dec, dd=4):
    r = L.row(key); ph = L.row(pkey)
    lo, hi = float(r["ci_low"]), float(r["ci_high"])
    loso = "[%s, %s]" % (f(L.v("%s.loso_min" % h), dd), f(L.v("%s.loso_max" % h), dd))
    return [h, label, f(float(r["value"]), dd), "[%s, %s]" % (f(lo, dd), f(hi, dd)), f(float(ph["p_raw"]), 5), f(float(ph["p_holm"]), 5), dec, loso]

def dec(h):
    return "supported" if float(L.row("%s.p_holm" % h)["p_holm"]) < 0.05 else "not supported"

rows3 = [prow("H1", "H1.delta_bias.pjm0", "H1.p_holm", r"$\Delta$ bias, PJM (hot day minus random weekday)", dec("H1")),
         prow("H2", "H2.logratio.pjmA_pjm0", "H2.p_holm", "Log ratio relMAE, PJM-adj / PJM", dec("H2")),
         prow("H3", "H3.logratio.cgA_pjmA", "H3.p_holm", "Log ratio relMAE, CG-adj / PJM-adj (margin log 1.10)", "equivalent (TOST)" if str(L.v("H3.decision")) == "equivalent" else str(L.v("H3.decision"))),
         prow("H4", "H4.median_site_pcross", "H4.p_holm", "Median of the site break-even pre-event increases, PJM-adj vs SCM-ridge, four-hour stress test (order-statistic interval, coverage at least 95 %; exact sign test)", dec("H4")),
         prow("H5", "H5.eta_diff", "H5.p_holm", "Absolute-error growth per dispatch, PJM-adj minus SCM-ridge (negative: SCM-ridge grows faster)", dec("H5"))]
hdr3 = ["Test", "Estimand", "Estimate", "Interval", "Raw p", "Holm p", "Decision", "LOSO range"]
write_csv(TAB / "T3.csv", hdr3, rows3)
pool = L.row("H4.pcross.pjmA_scmR.4h")
notes3 = ["Intervals are 95\,\%% except for H3 (90\,\%%); the H3 raw p is the TOST p-value. H4 is the median of the %d site-level break-even pre-event increases; its LOSO range is on site medians. Building-pooled "
          "(secondary): break-even %s, 95\,\%% interval [%s, %s]; this value pools buildings and is not the confirmatory statistic."
          % (int(float(L.v("sample.n_sites"))), f(float(pool["value"]), 4), f(float(pool["ci_low"]), 4), f(float(pool["ci_high"]), 4))]
write_tex(TAB / "T3.tex", hdr3, rows3, r"l>{\raggedright\arraybackslash}p{4.3cm}rlrrll", notes3)

# ---------------- T4 method accuracy R1 / R3 ----------------
def get(k):
    for led in (L, S2):
        if led.has(k):
            return led.v(k)
    return None

def ivl(m, kind):
    k = "derived.T4.%s.%s" % (m, kind)
    if not E.has(k):
        return "n/a"
    lo, hi = E.ci(k)
    return "[%s, %s]" % (f(lo), f(hi))

def cells(m):
    out = []
    for rg in ("R1", "R3"):
        k = "method.%s.%s.relMAE_median" % (m, rg)
        if get(k) is not None:
            per = get("method.%s.%s.PER_c10_median" % (m, rg))
            out += [f(get(k)), f(get("method.%s.%s.bias_median" % (m, rg))), f(per, 2) if per is not None else "n/a"]
        else:
            out += ["n/a", "n/a", "n/a"]
    return out

order = [m for m, *_ in M]
order = order[:order.index("lgbM") + 1] + ["lgbM_hpo"] + order[order.index("lgbM") + 1:]
order = order[:order.index("lgbD") + 1] + ["lgbD_hpo", "mlpM", "mlpD"]
NAME.update({"lgbM": "LightGBM-morn (fixed)", "lgbD": "LightGBM-donor (fixed)",
             "lgbM_hpo": "LightGBM-morn (tuned)", "lgbD_hpo": "LightGBM-donor (tuned)",
             "mlpM": "MLP-morn (tuned)", "mlpD": "MLP-donor (tuned)"})
hdr4 = ["Method", "Information set", "R1 relMAE", "R1 bias", "R1 PER", "R3 relMAE", "R3 bias", "R3 PER", "R1 relMAE interval", "R1 bias interval"]
rows4, csv4, seen = [], [], {}
for m in order:
    c = cells(m)
    info = INFO_FIX.get(m) or L.v("method.%s.info" % m.replace("_hpo", ""))
    seen[m] = c
    if m == "isone0":
        continue                       # merged into the CAISO row (RESULTS_NOTES D19)
    if m == "caiso0":
        assert seen["caiso0"] == cells("isone0"), "CAISO and ISO-NE rows differ in the ledger"
        assert L.v("method.caiso0.info") == L.v("method.isone0.info")
        for kd in ("relMAE", "bias"):
            assert ivl("caiso0", kd) == ivl("isone0", kd)
        rows4.append(["CAISO / ISO-NE (identical)", info] + c + [ivl("caiso0", "relMAE"), ivl("caiso0", "bias")])
        continue
    if all(x == "n/a" for x in c):
        rows4.append(["MC", NAME[m], info, "no result in the ledger"])
        continue
    rows4.append([NAME[m], info] + c + [ivl(m, "relMAE"), ivl(m, "bias")])
csv4 = [r[1:3] + [r[3]] + [""] * 7 if r[0] == "MC" else r for r in rows4]
write_csv(TAB / "T4.csv", hdr4, csv4)
n_r1 = int(float(L.v("sample.n_events.R1")))
n_dm = int(float(D.v("derived.dm0.n_events_differ")))
notes4 = ["CAISO and ISO-NE unadjusted baselines are the same ten-day mean and are shown as one row. "
          "DM differs from them in %d of %s hot-day events" % (n_dm, format(n_r1, ",").replace(",", "{,}"))
          + (" but has the same medians at the printed precision." if seen["dm0"] == seen["caiso0"] else ".")
          + r" PER is relMAE divided by $c=0.10$; it is not in the ledger for TOWT, LightGBM and MLP, so it is shown as n/a. "
            r"The interval columns are order-statistic 95\,\% intervals of the 11 site medians (the construction used for H4); the point estimates in the first columns are building-pooled medians, so they need not equal the interval center. R3 (random weekdays) results exist for the rule-based baselines without donors and for the tuned LightGBM and MLP variants. "
          + "Tuned rows (LightGBM and MLP) use the pre-registered %d-trial search on 2016 and %d training seeds."
            % (int(float(S2.v("hpo.lgbM.trials"))), int(float(S2.v("method.lgbM_hpo.R1.n_seeds"))))]
assert S2.v("hpo.mlpM.trials") == S2.v("hpo.lgbM.trials") and S2.v("method.mlpM.R1.n_seeds") == S2.v("method.lgbM_hpo.R1.n_seeds")
write_tex(TAB / "T4.tex", hdr4, rows4, r">{\raggedright\arraybackslash}p{3.0cm}>{\raggedright\arraybackslash}p{1.5cm}>{\raggedleft\arraybackslash}p{1.0cm}>{\raggedleft\arraybackslash}p{1.0cm}>{\raggedleft\arraybackslash}p{1.0cm}>{\raggedleft\arraybackslash}p{1.0cm}>{\raggedleft\arraybackslash}p{1.0cm}>{\raggedleft\arraybackslash}p{1.0cm}>{\raggedleft\arraybackslash}p{2.1cm}>{\raggedleft\arraybackslash}p{2.1cm}", notes4)
L.report(); D.report(); E.report()
print("tables written")
