"""Supplement analysis inventory (D29 item 7): tables/S_inventory.tex, a longtable with booktabs.
Labels only, no numbers. One row per analysis unit; status per PREREG s10 and D29 item 2:
  confirmatory | secondary (pre-specified) | exploratory (post-2017 decision) | descriptive.
Rows follow the analysis-coverage audit (65 units, progress.md 09:14), rebuilt from PREREG s6/s10 and the ledger key
prefixes because audits/ANALYSIS_COVERAGE.md is not on disk. Dates and what was known: research/DEVIATIONS_POST.md.
Requires in the including document: longtable, booktabs, array (all standard)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tables" / "S_inventory.tex"

C, S, E, D = "confirmatory", "secondary (pre-specified)", "exploratory (post-2017 decision)", "descriptive"
MAIN, SUP = "Main, ", "Suppl., "

# (analysis, status, where reported, key prefix)
ROWS = [
    # --- confirmatory family (Holm, five tests) ---
    ("H1 hot-day minus random-weekday bias of unadjusted PJM", C, MAIN + "Results, confirmatory table", "H1.*"),
    ("H2 PJM-adj against PJM, log relMAE ratio", C, MAIN + "Results, confirmatory table", "H2.*"),
    ("H3 CG-adj against PJM-adj, equivalence (TOST, 10 % margin)", C, MAIN + "Results, confirmatory table", "H3.*"),
    ("H4 break-even pre-event increase p-cross, 4 h shape", C, MAIN + "Results, H4 section, figure", "H4.median_site_pcross, H4.p_*"),
    ("H5 absolute-error slope difference, 14:00 to 18:00", C, MAIN + "Results, H5 section, figure", "H5.eta_diff, H5.p_*"),
    ("Holm adjustment over H1 to H5", C, MAIN + "Results, confirmatory table", "family.holm_members, *.p_holm"),
    # --- sensitivity of the confirmatory estimands (PREREG s7) ---
    ("Leave-one-site-out ranges, five tests", S, SUP + "sensitivity figure", "H*.loso_*"),
    ("Site-level wild cluster bootstrap, five tests", S, SUP + "sensitivity figure", "H*.p_wcb"),
    ("Conditional two-stage bootstrap intervals", S, MAIN + "Results, confirmatory table", "H*.ci_boot_conditional"),
    ("Site-level values and robustness flags, five tests", S, SUP + "H1, H2 site figures", "H*.site.*, H*.site_robust"),
    # --- co-reported estimands (PREREG s6) ---
    ("Break-even level p* per method (settlement error equals a 10 % curtailment)", S, MAIN + "Results, H4 section, figure", "pstar.*"),
    ("Pooled break-even per method, building-pooled", S, MAIN + "Results, H4 section", "pcross.*, H4.pcross.*"),
    ("Incremental sensitivity at p = 0.10", S, MAIN + "Results, H4 section", "H4.sens_increment_p10, incr_sens.*"),
    ("Per-method absolute-error slope, building-pooled", S, MAIN + "Results, H5 section", "H5.eta_abs_pooled.*, H5.eta.*"),
    ("Per-method absolute-error slope, median of site slopes (D19 label fix)", S, MAIN + "Results, H5 section", "H5.eta_abs.median_of_site_slopes.*"),
    ("Signed rho curves by K and signed-slope contrast", S, MAIN + "Results, H5 section, figure", "H5.rho.*, H5.eta_signed_pooled.*, H5s.eta_signed_diff.*"),
    ("Site-median absolute deviation level by K (matches the H5 figure)", D, MAIN + "Results, H5 section", "derived.H5.absdev_sitemedian.*"),
    ("Fallback rates by K", S, SUP + "fallback table", "H5.fallback.*"),
    ("Age of information read by each rule by K", S, SUP + "age figure", "H5.age_days.*"),
    ("D_tau: first K at which rho falls 0.10 below its K = 10 value", S, SUP + "inventory section", "H5.Dtau.*"),
    ("H5 two-point slope (K = 10 and K = 40)", S, SUP + "inventory section", "H5.eta_2pt.*"),
    # --- accuracy and descriptive layers ---
    ("Method accuracy and bias, hot days (R1) and random weekdays (R3), all baselines", D, MAIN + "Results, accuracy table, figure", "method.<m>.R1.*, method.<m>.R3.*"),
    ("Previous-day naive baseline against unadjusted PJM on hot days", D, MAIN + "Results, accuracy table", "method.prev.*"),
    ("Pre-event increase curves of relMAE and bias, all methods", D, MAIN + "Results, H4 section, figure", "precool.*"),
    ("Sample, exclusions, support shares and DST table", D, SUP + "data and eligibility table", "sample.*"),
    ("Development-year (2016) estimates", D, SUP + "development table", "*_v0 (summary_dev)"),
    # --- secondary rule family and event definitions ---
    ("Secondary rule family (NYISO, CAISO, ISO-NE): H1 and H2 endpoints, per-rule H5", S, SUP + "inventory section", "H1s.*, H2s.*, H5s.*"),
    ("Within-family Holm for the secondary rule family (promised in the pre-registration)", S, MAIN + "Results, H1 and H2; " + SUP + "inventory section", "H1s.p_holm_family*, H2s.p_holm_family*"),
    ("R2-ISO event definition (7 US sites)", S, SUP + "sensitivity figure and table", "method.<m>.R2ISO.*"),
    ("R2-LOO event definition (leave-one-out site load)", S, SUP + "inventory section", "method.<m>.R2LOO.*"),
    ("16:00 to 20:00 window: accuracy and H4", S, SUP + "sensitivity figure and table", "method.<m>.w1620.*, exploratory.h4_win1620.*"),
    ("16:00 to 20:00 window: H5 slope contrast (inconclusive)", S, MAIN + "Results, H5 section and H5 window table", "exploratory.h5_win1620.*"),
    ("H5 level ordering and relative growth K = 10 to 40, both windows", D, MAIN + "Results, H5 section and H5 window table", "derived.H5.absdev_sitemedian_w1620.*, derived.H5.levels_*, derived.H5.n_sites_pjmA_lower.*, derived.H5.relgrowth_*"),
    ("Alternative DST mapping: accuracy, H2, H4, H5", S, SUP + "sensitivity table", "dst_alt.*, exploratory.dst_alt.*"),
    ("Event rules on non-event E3 days: H1 to H3 and accuracy", S, SUP + "secondary table", "nonevent.*"),
    ("Flatline filter off: H1 to H3 and accuracy", S, SUP + "secondary table", "flatoff.*"),
    # --- stress-test variants (PREREG s4) ---
    ("Two-hour pre-event shape", S, SUP + "sensitivity figure", "incr_sens.2h.*, pstar.*.2h"),
    ("Rebound after the event (0 and 10 %)", S, SUP + "secondary table", "rebound.*"),
    ("Donor contamination q in {0, 0.25, 0.5, 1}", S, MAIN + "Results, H4 section; Discussion", "contam.*, derived.contam.*"),
    ("Heterogeneous increase p_bd ~ U(0, 2p)", S, SUP + "inventory section", "hetp.*"),
    ("Heat-wave subset of repeated dispatch", S, SUP + "secondary table", "heatwave.*"),
    ("Payment error ratio at c = 0.05, 0.10, 0.20", S, SUP + "payment table", "method.<m>.PER.*, derived.PER.*"),
    # --- learned and alternative baselines ---
    ("Fixed-parameter LightGBM (morning and donor features)", S, MAIN + "Results, accuracy table", "method.lgbM.*, method.lgbD.*"),
    ("TOWT (70, 7) and TOWT-adj", S, MAIN + "Results, accuracy table", "method.towt*"),
    ("Classic SCM and ridge SCM (W, lambda grid on 2016)", S, MAIN + "Results, H4 and H5 sections", "method.scmC.*, method.scmR.*, hpo.scm.*"),
    ("M3 and Mid8 rules", S, SUP + "bridge and accuracy tables", "method.m3.*, method.mid8.*"),
    ("LightGBM tuned (40 TPE trials, 2016 tuning)", S, MAIN + "Results, accuracy table", "hpo.lgbM.*, hpo.lgbD.*, method.lgb*_hpo.*"),
    ("MLP tuned (40 TPE trials, 2016 tuning)", S, MAIN + "Results, accuracy table", "hpo.mlpM.*, hpo.mlpD.*, method.mlp*.*"),
    ("HPO tuning-score choice (objective on non-event 2016 months)", E, MAIN + "Methods; " + SUP + "deviations", "hpo.<m>.choice.*"),
    ("Per-method computational cost", D, SUP + "cost table", "compute.method.*"),
    # --- H6, screening, ablations ---
    ("H6 portfolio payment error, n = 1 to 20, against load-matched random portfolios", S, SUP + "portfolio figure, secondary table", "H6.*"),
    ("Screening tree (depth 2, 2016 training; the plan labels it exploratory)", S, SUP + "screening table", "screen.*"),
    ("Ablation: PJM-adj adjustment on or off", S, SUP + "secondary table", "ablation.adjustment.*"),
    ("Ablation: PJM adjustment cap on or off", S, SUP + "secondary table", "ablation.cap.*"),
    ("Ablation: adjustment hours", S, SUP + "secondary table", "ablation.adjhours.*"),
    ("Ablation: donor pool (same use or whole site) and donor count", S, SUP + "secondary table", "ablation.donor.*"),
    ("Ablation: drop the 10 % of donors most correlated with the target", S, SUP + "inventory section", "ablation.donor.drop_corr10.*"),
    # --- post-2017 decisions (research/DEVIATIONS_POST.md) ---
    ("X1 bridge to LBNL metrics (NMBE with Granderson sign, relative RMSE)", D, SUP + "bridge table", "method.<m>.R1.nmbe_granderson, rmse_median"),
    ("X2 site-level order-statistic intervals on method medians", D, MAIN + "Results, accuracy table", "derived.T4.*"),
    ("X3 sites inside the H3 margin at 5, 10, 15 %", D, MAIN + "Results, H3 text", "derived.H3.*"),
    ("X4 share of hot-day building-events over- and under-paid", D, MAIN + "Results, payment section", "derived.X4.*"),
    ("X5 break-even as a pre-event energy increase in kWh", E, MAIN + "Results, exploratory section", "exploratory.x5.*"),
    ("X6 rank correlation of site break-even with site gap at p = 0", E, MAIN + "Results, H4 section", "exploratory.x6.*"),
    ("X7 ridge SCM with the longer window W = 10 (H5)", E, MAIN + "Results, exploratory section", "exploratory.x7.*"),
    ("X8 mirror stress test with a pre-event decrease", E, MAIN + "Results, exploratory section", "exploratory.neg_p.*"),
    ("X10 example building-event panel (plot only)", D, SUP + "figure", "(none)"),
    ("Early-shaping variants (shaping shifted earlier so that it overlaps only the first of the three adjustment hours; no-overlap variant invariant by construction)", E, MAIN + "Results, exploratory section; " + SUP + "shaping-placement panel", "exploratory.early_shape.*"),
    ("Cross-window contrast of the H5 slope difference (14:00 to 18:00 against 16:00 to 20:00)", E, MAIN + "H5 window table note; " + SUP + "inventory section", "exploratory.h5_window_contrast.*"),
    ("Clopper-Pearson lower bounds for site shares", D, MAIN + "Discussion, limitations", "derived.H*.prev_share_*"),
    ("Distribution-free prediction interval for a new site", D, MAIN + "Discussion, limitations", "derived.H*.pred_int"),
    ("H4 threshold tipping value", D, MAIN + "Discussion, limitations", "derived.H4.tip_*"),
    ("Per-site event-day table with heat-episode counts", D, MAIN + "Results, sample; " + SUP + "event-day table", "sample.event_days*, sample.heat_episodes*"),
    ("Practitioner units: break-even as a share of shed energy, over-payment multiplier", D, MAIN + "Results, H4 section; Discussion", "derived.H4.energy_offset_share.*, derived.H4.overpay_multiplier.*"),
]

NOTES = (
    "Status follows the pre-registration and the post-freeze register (Supplement Section S1). Confirmatory: the five Holm tests. Secondary (pre-specified): "
    "named in the pre-registration before any 2017 result and run on 2017 without a Holm adjustment of the confirmatory family. "
    "Exploratory (post-2017 decision): designed or chosen after the 2017 confirmatory results were seen. "
    "Descriptive: summaries of existing quantities; those chosen after the 2017 results are listed with dates in "
    "the post-freeze register (Supplement Section S1). The screening tree is called exploratory in the pre-registration only in the sense that it carries no test of its own. "
    "A key prefix with * stands for several keys; \textless m\textgreater{} stands for a method code."
)


def esc(s):
    s = (s.replace("\\", r"\textbackslash{}").replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")
          .replace("_", r"\_").replace("{", r"\{").replace("}", r"\}"))
    # "<" and ">" print as inverted marks in an OT1 text font, and "~" would become a space: write them as symbols
    return (s.replace("*", r"{*}").replace("<", r"\textless{}").replace(">", r"\textgreater{}")
             .replace("~", r"$\sim$"))


def key(s):
    return r"\texttt{" + esc(s).replace(".", r".\allowbreak ").replace(",", r",\allowbreak ") + "}"


def build():
    head = " & ".join(["Analysis", "Status", "Where reported", "Key prefix"]) + r" \\"
    L = [r"{\footnotesize",
         r"\setlength{\tabcolsep}{3pt}",
         r"\renewcommand{\arraystretch}{1.0}",   # 1.05 left the two-line note alone on the last page
         r"\begin{longtable}{@{}>{\raggedright\arraybackslash}p{0.34\textwidth}>{\raggedright\arraybackslash}p{0.17\textwidth}"
         r">{\raggedright\arraybackslash}p{0.21\textwidth}>{\raggedright\arraybackslash}p{0.24\textwidth}@{}}",
         r"\caption{Analysis inventory: every analysis unit with its status, where it is reported and its ledger key prefix.}\label{tabS:inventory}\\",
         r"\toprule", head, r"\midrule", r"\endfirsthead",
         r"\toprule", head, r"\midrule", r"\endhead",
         r"\midrule \multicolumn{4}{r}{\emph{continued on the next page}} \\ \endfoot",
         r"\bottomrule \endlastfoot"]
    for a, st, wh, k in ROWS:
        L.append(" & ".join([esc(a), esc(st), esc(wh), key(k)]) + r" \\")
    L.append(r"\end{longtable}")
    L.append(r"\par\smallskip{\footnotesize " + NOTES + r"\par}")
    L.append("}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    statuses = {r[1] for r in ROWS}
    assert statuses <= {C, S, E, D}, statuses
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build(), encoding="utf-8", newline="\n")
    from collections import Counter
    print("rows", len(ROWS), dict(Counter(r[1] for r in ROWS)), "->", OUT)
