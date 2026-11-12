# PREREG: pre-event load shaping and the settlement error of demand-response baselines (Paper B)
DRAFT, Revision 2, for the controller. NOT frozen, NOT hashed. Author: E3 (ml-expert), 2026-11-11.
Status: Revision 2 complete (DECISIONS T3 merged, P3 audit F1-F15 applied, 2016 values recomputed).

## Revision 2 changes (for the src/run implementer; audit item / decision answered in brackets)
| # | section | change | answers |
|---|---|---|---|
| 1 | 6 | explicit line: confirmatory family = 5 (H1-H5); T1.5 "family of 6" superseded by T2.4 | T3 1.1, F1 |
| 2 | 1 (E5), 6 | support rule: per hypothesis and site, >= 10 building-events with both methods present, else the site is dropped from that hypothesis and reported; exclusion counts by site and reason in the ledger | T3 1.2, F1 |
| 3 | 2 | R1 and R3 dates for 2016 and 2017 frozen in results/frozen/event_dates.csv (weather + holidays only, Tmax rounded 0.1 C, E8 applied); R3 = 5 draws excluding R1 days; building value = mean over draws first, then site median | T3 1.3, F1, F3, F10 |
| 4 | 1 (E6) | DST primary mapping final; ambiguous sites = CLOCK; alternative mapping always reported as sensitivity; 2017-DST trigger clause deleted | T3 1.4, F1, F8 |
| 5 | 6 | p-cross rule (first upward crossing, no interpolation across unsupported grid points, censored ">0.30", never set to 0.30); D_tau rule (censored ">40") | T3 1.5, 1.6, F1 |
| 6 | 6 | H4 primary test = exact sign test; signed-rank = sensitivity | T3 2.1 |
| 7 | 6 | exact signed-rank by full enumeration, average ranks, zeros dropped and counted | T3 2.2 |
| 8 | 6 | source for every one-sided direction | T3 2.3 |
| 9 | 6 | TOST: intersection-union p_TOST enters Holm; decision on the Holm-adjusted p only; 90 % interval descriptive | T3 2.4, F2 |
| 10 | 6, 7 | primary intervals: Hodges-Lehmann + exact signed-rank inversion (H1-H3, H5), order-statistic interval for the median (H4); two-stage bootstrap labelled conditional; wild cluster bootstrap = sensitivity | T3 2.5, F13 |
| 11 | 6 | H4 co-estimand: incremental sensitivity; 0.10 threshold justified from field studies | T3 3.1 |
| 12 | 6 | H5 eta = least-squares slope over K = 10/20/30/40 on fixed common support; per-K curves and fallback rates | T3 3.2, F1 |
| 13 | 3 | folds frozen in results/frozen/folds.csv from all E1 meter IDs (before the flatline filter), one mapping for both years | T3 4.1, F1, F15 |
| 14 | 6 | screening tree: depth 2, minimum leaf 20 buildings, no pruning, 2016 training, exploratory | T3 4.2 |
| 15 | 4 | injection order and unit tests | T3 4.3 |
| 16 | 9 | wording: donor forecasts are not independent counterfactual evidence | T3 4.4 |
| 17 | 10 | new ledger columns; secondary keys can never carry a confirmatory p_holm | T3 5 |
| 18 | 12 | freeze order: after the pipeline reproduces 2016; md5 over PREREG.md, results/frozen/*.csv, src/run/*.py | T3 freeze, D11 |
| 19 | 5 | scmR re-tuned on 2016 with the frozen folds: W = 7, lambda = 3 (Revision 1: W = 5, lambda = 1 with development folds) | consequence of 13 |
| 20 | 6, 8 | all 2016 development values recomputed with the Revision 2 definitions (H1 5-draw R3; H3 exact p_TOST; H4 sign test; H5 slope; HL intervals); expected-outcome text follows the numbers | F2, F3 |
| 21 | 6 | p*(pjmA) site range includes Lamb at 0 | F4 |
| 22 | 1 (E2, E3) | Wolf r = 3 share 0.0061; wording of the 20 % cut | F5, F6 |
| 23 | 4 | unsourced "all buildings curtailed" pilot claim replaced by a code-history note | F7 |
| 24 | header | exact statement of what 2017 data the eligibility step read | F9 |
| 25 | 3 | PJM 25 % filter order stated as implemented | F11 |
| 26 | 3 (M5) | caiso0, dm0, isone0, mid8 coincide in 2016 | F12 |
| 27 | 9 | leakage assertions 16-18 (early stopping, feature selection, 2017-dependent eligibility) | F14 |
| 28 | 7 | Webb 2023 citation verified (D10) | D10 |
| 29 | 6, 8, 12 | H5 uses absolute erosion (slope of the site median of abs(rho - 1)); signed rho secondary; 2016 values and Holm table recomputed (src/design/prereg_2016_h5abs.py -> results/prereg2016/summary_h5abs.json); holidays closed | D12 |
| 30 | 6, 8, 12 | H5 two-sided (exact enumerated signed-rank, HL 95 % CI, two-sided p in Holm); statement "we quantify the difference in the absolute-erosion slope between pjmA and scmR"; lookback-age diagnostic added (pjm_age, scm_age_W7 in events_erosion.pkl) | D13 |
| 31 | 1, 6, 8, 9 | Pre-freeze (D14): the s9.12 duplicate-meter drop stays (5 Eagle meters; 1,091 buildings with R1 events in 2016). The 2016 development reference values are those of the frozen pipeline with the drop on, results/run_v0/summary_v0.csv (tests/validate_2016.py, logs/IMPL_pipeline.md); they differ from the values quoted above in the 3rd-4th decimal and change no 2016 Holm decision (Holm-adjusted p: H4 0.0024, H2 0.0039, H5 0.0039, H1 0.0537, H3 0.0537). Secondary analyses not yet coded (Optuna HPO for lgbM/lgbD, MLP, gscm, H6, screening tree, most ablations, non-event-day sensitivity) are written after the freeze in a separate package src/secondary/ that imports the frozen modules unchanged; their specification in this file is frozen; each is run on 2016 first, then 2017, and logged in section 11 | D14 |

## Inputs and provenance
research/DECISIONS.md T1-T3; progress.md D8-D11; research/team/E2_cbl_rules.md; E2b_baseline_defs.md (Granderson
2021/2023, Mathieu 2011, Sievers and Roozbehani 2026); E4_novelty_gaming.md; E3_design.md; research/DATA_EIA930.md;
results/data_audit/; audits/P3_audit.md; research/codex/round03_resp.md.
2016 development numbers (tagged `_v0`, never paper results) come from `src/design/`:
`freeze_inputs.py` -> `results/frozen/{event_dates.csv, folds.csv, holidays.csv}` (reads weather.csv, metadata.csv and
the A3 meter audit only; an audit hook aborts if any electricity file is opened);
`prereg_2016.py` -> `results/prereg2016/{dst_table.csv, flatline.json, summary_part1.json, events_R1.pkl, events_R3.pkl}`;
`prereg_2016_analyse.py` -> `summary.json` (method table, scmR grid, anchors, p* curves, conditional bootstrap);
`prereg_2016_erosion.py` + `prereg_2016_erosion_analyse.py` -> `events_erosion.pkl`, `erosion_summary.json`;
`prereg_2016_rev2.py` -> `summary_rev2.json` (all Revision 2 confirmatory definitions).
2017 data read so far: only for meter eligibility, never for a load level, error or parameter: e3_profile.py:33-46
(2017 hourly coverage share, share of zero readings, longest NaN-or-zero run) and audit_bdg2_v2.py:93 (count of 2017
valid days: 24 non-missing readings and day sum > 0). No 2017 load value enters any number below.

## 0. Claim type and scope
The paper measures properties of settlement formulas: how much each baseline's settlement error moves when a
specified pre-event load change, curtailment or repeated dispatch is injected into real metered load. It does not
measure customer behaviour (T2.2). Every claim is "we quantify" (E4_novelty_gaming: the mechanism is known).
Inference is limited to the analysed sites (T2.3). The observed 2017 load on proxy event days is the
no-curtailment counterfactual; injected quantities are stress-test values, labelled as such.
Sign convention: e = B - L (baseline minus true no-curtailment window load, kWh); e > 0 is over-payment.
Granderson et al. report the opposite sign (E2b M7).

## 1. Data, units, eligibility (thresholds fixed from 2016)
- Data: BDG2 cleaned hourly electricity, metadata, site weather (data CC BY-SA 4.0, A3). 2016 development; 2017
  confirmatory, scored once after the freeze.
- Unit of estimation: building-event. Unit of inference: the site (site statistics of building values).
- E1 meter: A3 `usable` (>= 300 valid days in 2016 and in 2017) and not all-zero; 1,208 meters at 14 sites
  (results/frozen/folds.csv).
- E2 flatline day: invalid if >= 4 identical consecutive non-missing readings in clock hours 10:00-20:00
  ([s-4, e+2)). From 2016 (flatline.json): at the cleanest sites (Bobcat, Cockatoo, Peacock, Wolf) the share of
  warm-season weekday building-days flagged is 0.0000-0.0009 at r = 4 and up to 0.0061 (Wolf) at r = 3; r = 3 flags
  13.6 % of Bull days (coarse readings), r = 4 4.2 %.
- E3 flatline meter: excluded as target and donor if > 20 % of its warm-season (15 May-30 Sep) weekdays are flat in
  the scored year. 2016 per-meter flat share (summary_part1.json): 914 meters <= 2 %, 110 in (2, 5] %, 38 in (5, 10] %,
  44 in (10, 20] %, 19 in (20, 50] %, 83 > 50 %: the 20 % cut lies in the thinly populated region between the main
  mass (<= 10 %: 1,062 meters) and the fully flat meters (> 50 %: 83). 2016 exclusions: Gator 61, Moose 8, Bull 8,
  Eagle 8, Robin 7, Lamb 5, Rat 3, Bear 1, Fox 1. E3 uses the scored year's raw readings including event-day hours
  (flatness, not level); assertion 18 adds a sensitivity with E3 computed on non-event days only.
- E4 site: >= 12 meters after E1-E3. 2016: 11 sites (Bear, Bull, Cockatoo, Eagle, Fox, Hog, Lamb, Peacock, Rat,
  Robin, Wolf; 1,096 buildings with R1 events); Bobcat, Gator, Moose fail. The 2017 list is recomputed by the same
  rule and reported.
- E5 building-event and support: event day complete (24 h) and not flat; L > 0; the method's lookback forms under its
  own fallback text; donors complete on d. For each hypothesis, a site enters only if it has >= 10 building-events
  with both compared methods present (for H5: present at all four K); otherwise it is dropped from that hypothesis and
  listed. Exclusion counts by site and reason go to the ledger (`sample.excl.<site>.<reason>`).
- E6 DST, primary mapping FINAL (dst_table.csv; rule: STD if the site-median morning-ramp shift is <= -0.5 h at the
  spring change and >= +0.5 h at the autumn change; CLOCK if both |shift| < 0.3 h; otherwise AMBIGUOUS):
  STD (stamps stay on standard time; during DST clock hour h = stamp h - 1): Eagle, Moose, Rat, Wolf.
  CLOCK: Bear, Bull, Fox, Hog, Peacock. AMBIGUOUS, mapped as CLOCK: Bobcat (spring 0.21 h, autumn -0.47 h), Cockatoo
  and Gator (no spring data; Gator no autumn data), Lamb (-0.50 / 0.10 h), Robin (-1.04 / -0.03 h); for Lamb and Robin
  the coincidence of the UK spring change with Easter (27 Mar 2016) is a hypothesis, not a measured confounder.
  Sensitivity, reported in every case: the alternative mapping (each AMBIGUOUS site as STD). No 2017 DST check can
  change the primary mapping.
- E7 holidays: results/frozen/holidays.csv (US federal; England and Wales bank holidays for Lamb, Robin; Ireland for
  Wolf; 2016 and 2017). 2017 dates derived by the controller from the statutes (5 U.S.C. 6103; Banking and Financial Dealings Act 1971
  Sch. 1; Organisation of Working Time Act 1997 Sch. 2), reproducing every 2016 date (D12): CLOSED. In-season 2017 dates
  in the file, checked: US 29 May, 4 Jul, 4 Sep; UK 29 May, 28 Aug; IE 5 Jun, 7 Aug.
- E8 weather: a day enters the R1/R3 candidate set only with >= 20 hourly air-temperature values (implemented in
  freeze_inputs.py); Tmax rounded to 0.1 C; ties broken by the earlier date.

## 2. Event rules (dates frozen in results/frozen/event_dates.csv: 2,520 rows)
| rule | definition | status |
|---|---|---|
| R1 | per site and year, the 10 non-holiday weekdays between 15 May and 30 Sep with the highest Tmax (E8); ranks 1-40 stored for H5 | PRIMARY |
| R3 | 10 non-holiday weekdays drawn from the same candidate set excluding the site-year's R1 days; 5 draws, numpy default_rng([year, site index in the sorted 14-site list, draw]) | CONTROL (H1) |
| R2-ISO | per US site, the 10 top-ranked weekdays by day-ahead forecast BA peak (results/r2iso/r2iso_days.csv), after removing E7 holidays; 7 sites (Bear CISO, Bull ERCO, Cockatoo NYIS, Fox SRP, Hog MISO, Peacock PJM, Rat PJM); Fox and Hog medium-confidence mappings | SECONDARY (D9), US subset, outside the Holm family |
| R2-LOO | 10 weekdays with the highest site load excluding the target | EXPLORATORY (selection on donor outcomes) |
Each rule (and each R3 draw) is its own world: its event days are excluded from all later lookbacks, SCM
pre-periods and ML training sets (NYISO also the day before). R3 aggregation: per building, the statistic is computed
in each draw and averaged over the draws in which the building has events; then the site median is taken.
Windows: primary 14:00-18:00 clock (hour-beginning 14-17; s = 14, e = 18); secondary 16:00-20:00.

## 3. Methods, information sets, labels
Information sets: I-hist = own history before d; I-morn = I-hist + own event-day hours up to s-2; I-donor = I-hist +
donors' same-day load (all hours) + own event-day hours before s-4 only.
Folds (FROZEN, results/frozen/folds.csv): all 1,208 E1 meters, per site sorted by meter_id and permuted with
numpy default_rng(20171 + site index in the sorted 14-site list); first half A, rest B; one mapping for both years;
never reshuffled. Fold-A targets use fold-B donors and vice versa. All eligible buildings act as hypothetical
participants of their fold; donors are never participants of the same contrast.
| id | method | info | definition (source; deviation) | label |
|---|---|---|---|---|
| prev | previous eligible weekday | I-hist | trivial | core (trivial baseline) |
| pjm0 / pjmA | PJM weekday CBL; implemented order: the 5 most recent eligible weekdays in 45 days, then drop days whose window mean is < 25 % of the 5-day mean, then the highest 4 remaining (E2 s1 applies the 25 % exclusion before taking 5; the orders differ only when a near-zero day occurs; kept as implemented, stated); fallback if < 4 eligible days: add highest-window-load event days; pjmA adds the SAA over s-4..s-2, additive, uncapped | I-hist / I-morn | E2 s1 | core; PRIMARY RULE |
| caiso0 / caisoA | CAISO 10-in-10 within 45 days (min 5; fallback: highest-DR-hour-load excluded days); ratio over s-4..s-2 clipped [0.8, 1.2] | I-hist / I-morn | E2 s3 | core |
| ny0 / nyA | NYISO average-day: up to 10 weekdays in 30 days, day-before exclusion, 25 % seed, top 5 by window mean; ratio over s-4, s-3 clipped [0.8, 1.2] | I-hist / I-morn | E2 s2 (current Manual 7 text) | core |
| isone0 / isoneA | ISO-NE 10 most recent of the previous 30 weekdays; additive over s-3, s-2 (hourly approximation), floor 0 | I-hist / I-morn | E2 s4 | secondary |
| mid8 | ERCOT-style middle 8 of 10, unadjusted | I-hist | E2 s5, T1.3 | secondary |
| dm0 / dmA | Granderson day matching (10 working days immediately before d); dmA multiplicative over hours 10, 11, clip [0.8, 1.2] | I-hist / I-morn | E2b 1a | secondary (named LBNL) |
| wm0 / wmA | Granderson weather matching 4 of the prior 90 days (closest Tmax; non-event, non-holiday weekdays; ties more recent); clip [0.6, 1.4] | I-hist / I-morn | E2b 1a (M11) | secondary (named LBNL) |
| m3 / m3A | Mathieu 3 of 10; m3A as dmA | I-hist / I-morn | E2b 3 | secondary |
| towt70 / towt70A / towt7 | TOWT (Mathieu 2011) as in Revision 1: 120 weekday hour-of-week terms, 6 equal-width temperature bins, occupancy = hour-of-week whose mean training load exceeds the midpoint of the 10th and 90th percentiles of the hour-of-week mean profile, OLS on eligible non-event weekdays in the 70 calendar days before d (towt7: 7 most recent eligible weekdays); towt70A multiplicative over hours 10, 11, clip [0.6, 1.4] | I-hist / I-morn | E2b 1a, 3 (M9) | towt70 core; others secondary |
| cgA | adjusted comparison group: pjmA(target) x sum_donors L(d, window) / sum_donors pjmA(donor) | I-donor + I-morn | project | core (H3) |
| cg0 | pjm0(target) x sum_donors L / sum_donors pjm0 | I-donor | project | secondary |
| scmR | Sievers and Roozbehani 2026 (arXiv:2604.18469) linear "SCM+S1+R": ridge, weights sum to one, no non-negativity, no intercept; adapted: hourly, each series divided by its pre-period mean, pre-period = W most recent eligible non-event weekdays x 24 h + event-day hours 0..s-5; FIXED W = 7, lambda = 3 (section 5) | I-donor | E2b 2 (M2, M3) | core; PRIMARY DONOR METHOD (H4, H5) |
| scmC | non-negative weights summing to one (NNLS with a penalty row of 1000), same normalisation; FIXED W = 5 | I-donor | arXiv:2604.18469 Eq 3 | secondary |
| gscm | augmented SCM (+F weather, +R lagged donors), sum-to-one on the donor block, no lagged-target block | I-donor | arXiv:2604.18469 s II-B; cut if not faithful by Thu 18:00 (T1.4) | secondary |
| lgbM / lgbD | LightGBM learned adjustment as in Revision 1 (day-level samples, y = window load / dm0 window; monthly refit; objective l1) | I-morn / I-donor | project | core |
| mlpM / mlpD | MLP, same features, targets, refits and budget | same | project | secondary |
Coincident estimators (F12): in 2016 R1, caiso0, dm0 and isone0 have identical medians (relMAE 0.0886, bias -0.0256)
and mid8 nearly so (0.0886, -0.0255); they select the same recent days unless a fallback applies. Tables show them
as one estimator family, not four independent baselines.
E2b mismatches M1-M11: resolved as in Revision 1 (M1 author; M2 linear S1+R form followed, deviations on resolution,
pre-period, normalisation and lambda; M3 no lagged-target block; M4 intervals, pre-period and H5 are ours; M5
Granderson DM/WM from source text; M6 no own-load selection; M7 sign flip, NMBE reported in Granderson's convention as
secondary; M8 H5 is our own design, Granderson 2023 cited only as the lookback-shift precedent, prior framing from
Nexant BAWG 2017 and NAESB 2009; M9 TOWT settings; M10 3-of-10 from Mathieu 2011; M11 WM added).

## 4. Injection grids and order (fixed; never tuned to favour a method)
Order of operations (every run, both years): (1) DST mapping -> (2) filters E2, E3, E5 on raw readings -> (3) injection
on the target (and on donors only in the q scenario) -> (4) lookback and training-set construction from the injected
series -> (5) baseline -> (6) metrics against the true (uninjected) L. Filters never see injected values.
Unit tests (must pass before 2017): zero injection reproduces the uninjected baselines exactly; rebound changes no
baseline; donor contamination alters only the designated donors; injected hours are exactly the declared ones.
- Curtailment c in {0.05, 0.10, 0.20}; primary c = 0.10; PER = |e| / (c L).
- Pre-event increase p (multiplicative, target only, uniform over the shaping hours): realistic band {0.02, 0.05,
  0.10}; stress tail {0.20, 0.30} (stress values); zero control; fine grid 0-0.30 step 0.005. Shapes: 4 h [s-4, s)
  (primary), 2 h [s-2, s) (secondary).
- Heterogeneous p_bd ~ Uniform(0, 2p), one draw, seed 2017, reported for p in the realistic band (secondary).
- Rebound r in {0, 0.10} on [e, e+2) (secondary; asserted to change no baseline).
- Donor contamination q in {0, 0.25, 0.5, 1.0}, donors drawn with seed 2017 (secondary); q = 1.0 = whole-site
  participation. Code-history note: an early 2016 erosion run (overwritten; no file kept) curtailed donors as well as
  participants, and the comparison-group estimate of curtailment then collapsed; this motivated q = 1.0 and is not cited
  as a result.
- Repeated dispatch (H5): dispatched days = R1 ranks 1..K, K in {10, 20, 30, 40}; c = 0.10 on every dispatched day for
  participants only; lookbacks see curtailed load and apply each rule's fallback; scored days = R1 ranks 1-10.
  Secondary: heat-wave runs (each run of >= 3 consecutive weekdays above the site's 2016 80th percentile of season Tmax).

## 5. Hyperparameters and seeds (fixed)
- scmR: grid W in {2, 3, 5, 7, 10, 20, 40} x lambda in {0.01, 0.1, 0.3, 1, 3, 10, 100} (49), objective = median building
  relMAE on 2016 R1 with the frozen folds. Result (summary.json): W = 7, lambda = 3 (0.0612); W = 5/lambda = 3 0.0618,
  W = 3/lambda = 1 0.0620, W = 5/lambda = 1 0.0622: interior, flat. FIXED W = 7, lambda = 3. scmC: FIXED W = 5 (0.0665;
  W = 3 0.0670, W = 7 0.0682).
- LightGBM, MLP: spaces, budgets (40 TPE trials each, Optuna seed 2016), inner early stopping, final seeds as in
  Revision 1 (unchanged): LightGBM learning_rate [0.01, 0.2] log, num_leaves [7, 127] log int, min_child_samples
  [5, 200] log int, lambda_l2 [1e-3, 10] log, feature_fraction [0.5, 1], bagging_fraction [0.5, 1] (freq 1); objective
  l1; early stopping on the chronologically last 20 % of each refit's training days (patience 50, max 3,000 rounds).
  MLP depth {1, 2, 3}, width {32, 64, 128, 256}, dropout [0, 0.3], AdamW lr [1e-4, 3e-3] log, weight decay
  [1e-6, 1e-2] log, batch 256, cosine, 200 epochs, patience 15, L1 loss; 5 final seeds (0-4), mean reported.
  Feature sets are fixed as listed in section 3; no feature selection.
- Budget: LightGBM 40, MLP 40, scmR 49 (exhaustive), scmC 7; rules and TOWT have no free parameters.
- Seeds: folds 20171 + site index; R3 [year, site index, draw]; injection 2017; bootstrap 2017; portfolio 7; HPO 2016.

## 6. Hypotheses, estimands, tests
Confirmatory family = 5 hypotheses (H1-H5), Holm, FWER 0.05. The "Holm family of 6" in DECISIONS T1.5 is superseded by
T2.4 (H6 moved to secondary). No secondary or exploratory key can carry a confirmatory p_holm.
Site value: for each site, the median over its buildings of the building value. Tests and intervals at site level:
- Exact signed-rank: statistic W+ = sum of the average ranks of |x| over positive x; site values with |x| < 1e-12 are
  dropped and their number reported; the null distribution is the full enumeration of the 2^n sign patterns of the
  remaining n values with their (average) ranks; one-sided p = share of patterns at least as extreme. Implemented in
  our code (prereg_2016_rev2.py `signed_rank`; src/run must reproduce it and test it on an enumerated case).
- Hodges-Lehmann estimate = median of the Walsh averages; 95 % interval by exact inversion of the signed-rank
  distribution (no-tie distribution of W+); 90 % for H3.
- Exact sign test (H4): binomial(n, 0.5) on the number of sites below the threshold; zeros dropped and counted.
- Order-statistic 95 % interval for the median site value (H4), censored values sorted as largest.
- Conditional two-stage bootstrap (sites, then buildings within sites; 10,000 replicates, seed 2017): reported as
  uncertainty conditional on these sites, never as the primary interval.
Directions (one-sided) come from prior work, not from 2016 results: H1 hot-day under-prediction (Coughlin et al. 2009,
10.1016/j.enbuild.2008.11.002; Granderson et al. 2021, 10.1016/j.enbuild.2021.111031); H2 adjustment reduces error
(Granderson et al. 2021); H4 pre-event load inflates day-of adjusted baselines (E4_novelty_gaming.md s1-2: LBNL-4984E,
Braithwait 2010, CPUC D.09-08-027); H5 is two-sided (D13; prior work, E4_novelty_gaming.md s5, predicts rule erosion, 2016 development data show the
reverse). H3 is two-sided (equivalence).

| H | statement (we quantify ...) | primary estimand and site value | test and decision | 2016 development value (summary_rev2.json; not a result) |
|---|---|---|---|---|
| H1 | the hot-day under-prediction of the unadjusted primary rule relative to random weekdays | building: bias(R1) - mean over R3 draws of bias(R3), pjm0; site median | signed-rank, one-sided (< 0) | HL -0.026, 95 % CI [-0.076, 0.069]; signed-rank p = 0.027 (10 of 11 sites negative; Lamb +0.277); R3 = 5 draws excluding R1 days, building-first |
| H2 | the reduction of hot-day error by the primary rule's day-of adjustment | log(relMAE(pjmA)/relMAE(pjm0)), R1; site median | signed-rank, one-sided (< 0) | HL -0.394, 95 % CI [-0.567, -0.165]; p = 0.001 (10 of 11 negative) |
| H3 | the difference between the adjusted comparison group and the primary adjusted rule for single buildings | log(relMAE(cgA)/relMAE(pjmA)), R1, p = 0; site median | TOST, margin delta = log 1.10 = 0.0953: p_TOST = max(p_lower, p_upper), p_lower = signed-rank on (x + delta) > 0, p_upper = signed-rank on (x - delta) < 0 (intersection-union); p_TOST enters Holm; equivalence declared only if Holm-adjusted p_TOST < 0.05; the 90 % HL interval is descriptive; otherwise the direction of the HL estimate is reported as "not shown equivalent" | HL 0.035, 90 % CI [-0.002, 0.098] (upper end beyond 0.0953); p_lower = 0.0005, p_upper = 0.051, p_TOST = 0.051: not shown equivalent even before Holm (Hog +0.315, Lamb +0.128) |
| H4 | the pre-event increase at which the primary rule loses its accuracy advantage over the primary donor baseline (break-even p-cross), 4-h shape | site p-cross: on the 0.005 grid, the site-median curve over buildings of relMAE(pjmA, p) is linearly interpolated; p-cross = first upward crossing of the site-median relMAE(scmR) (scmR is unaffected by construction); p-cross = 0 if pjmA is not better at p = 0; no crossing up to 0.30 = right-censored ">0.30" (never set to 0.30); non-monotone curves use the first crossing; no interpolation across a grid point without support (then missing, reported) | exact sign test on the number of sites with p-cross < 0.10 (one-sided); signed-rank on (p-cross - 0.10) with censored values ranked largest = sensitivity; order-statistic 95 % interval for the median site p-cross. Threshold 0.10 = top of the realistic pre-cooling band from field studies (E4_novelty_gaming.md s3: morning load "slightly higher", +2.4 % daily energy, about 5 % energy penalty), not the curtailment depth | site median p-cross 0.030, order-statistic 95 % CI [0.007, 0.060]; 11 of 11 sites < 0.10, sign-test p = 0.0005 (signed-rank sensitivity p = 0.0005); pooled 0.042; incremental sensitivity at p = 0.02/0.05/0.10/0.20/0.30: 0.005/0.019/0.060/0.155/0.252; p* pooled pjmA 0.092 (sites: Lamb 0, others 0.075-0.114), caisoA 0.105, cgA 0.089, pjm0 and scmR >0.30 |
| H5 | we quantify the difference in the absolute-erosion slope between pjmA and scmR (not causal; D12, D13) | per site and method: a(K) = site median over buildings of |rho_b - 1|, rho_b = mean over the 10 scored days of estimated / true curtailment (c = 0.10), on the fixed common support of building-events present at all four K for both methods; eta = least-squares slope of a(K) on K in {10, 20, 30, 40} (positive = the error grows); site value eta(pjmA) - eta(scmR) | exact enumerated signed-rank, TWO-SIDED (D13); HL estimate with 95 % CI; enters Holm with its two-sided p | summary_h5abs.json: HL -0.0022 per dispatch, 95 % CI [-0.0038, -0.0013]; two-sided p = 0.00098 (0 of 11 sites positive): scmR's absolute error grows faster than pjmA's at every site (pooled a(K) pjmA 0.180/0.198/0.217/0.236, eta 0.0019; scmR 0.320/0.347/0.400/0.433, eta 0.0039; caisoA 0.0037; pjm0 0.0085; cgA 0.0023). Secondary signed rho (summary_rev2.json): pooled rho pjmA 0.983/0.964/0.956/0.934, scmR 1.083 -> 1.099; signed contrast HL 0.0021, p = 0.016 (superseded as primary by D12: it credits scmR's upward drift as negative erosion). D_tau (signed rho) pjmA >40 at 9 sites, 35.5 and 37.6 at 2; pjm0 finite at 7 sites (14-40); fallback rate at K = 40: PJM 4.7 %, CAISO 4.8 %, CAISO with < 10 days 18.2 % (K = 10: < 0.1 %); common support 10,462 building-events per K |
H5 direction (D13): prior work predicts that rules erode through lookback contamination (Nexant BAWG 2017; NAESB 2009), while the 2016 development evidence shows scmR eroding more, plausibly because excluding past event days pushes its pre-period onto older days; and the H5 definition changed under D12 after the signed version was seen. Fixing either direction now would be a forking path, so H5 is two-sided and commits to no direction. Secondary mechanism diagnostic: median over building-events of the mean age (days before d) of the PJM lookback days and of the scmR pre-period days at each K (2016, summary_h5abs.json: PJM 5.5/7.5/9.3/12.0; scmR 7.3/9.0/12.3/16.0 at K = 10/20/30/40).

Holm: the five p values (H1, H2, H3 = p_TOST, H4 = sign-test p, H5 = two-sided signed-rank p) are ordered and compared with 0.05/5, 0.05/4,
0.05/3, 0.05/2, 0.05; each decision reported with raw and adjusted p.
Co-reported estimands (no test, with intervals): p* for every method (smallest p at which the pooled median building
relMAE reaches 0.10, i.e. the settlement error equals the value of a 10 % curtailment; same crossing and censoring rules,
">0.30"); incremental sensitivity Delta(p) = [E_pjmA(p) - E_pjmA(0)] - [E_scmR(p) - E_scmR(0)] (E = pooled median
building relMAE; the scmR term is 0 by construction); per-method eta (absolute, primary definition) and per-K signed rho curves (secondary); D_tau = first K at which a
site's rho falls tau = 0.10 below its K = 10 value, linear interpolation between K = 10, 20, 30, 40, censored ">40";
fallback rates per K (share of building-events using the PJM or CAISO fallback, and CAISO with < 10 days).
H3 margin (summary.json anchors): official adjusted rules differ from pjmA by site-median log ratios 0.001 (CAISO),
-0.060 (ISO-NE approximation), 0.088 (Granderson DM), 0.149 (NYISO); delta = 0.0953 lies inside that range and equals
about 0.005 relMAE at the 2016 pjmA level (0.047), 5 % of a 10 % curtailment. Fixed.

Secondary (outside the Holm family; labelled):
- H6 portfolio (T2.4): change in median absolute portfolio payment error from n = 1 to n = 20, cgA vs pjmA, disjoint
  folds, against load-matched random portfolios (total 2016 window load within +/-10 %), 20 draws per site-day, seed 7.
- Secondary rule family (NYISO, CAISO, ISO-NE) for H1 and H2 endpoints, Holm within that family.
- R2-ISO, R2-LOO, 16:00-20:00, 2-h shape, rebound, contamination, heterogeneous p, heat waves, c = 0.05 and 0.20, lgb,
  mlp, towt, gscm, scmC, m3, mid8, prev; the alternative DST mapping; E3 on non-event days.
- Screening tree (exploratory): depth 2, minimum leaf 20 buildings, no pruning, trained on 2016 only, features fixed
  (use, slope of window load on Tmax, window CV, log size, correlation of the building's daily window load with its
  site mean), classes pjmA, cgA, scmR; tested in 2017 against pjmA by the site-median log ratio.
- Ablations: adjustment on/off; cap on/off; adjustment hours; donor pool same-use vs whole site; donor count; scmR
  neighbours; lgb with/without donor features; flatline filter on/off; DST mapping; excluding the 10 % of donors most
  correlated with the target.

## 7. Site sensitivity (every confirmatory estimand)
- Leave-one-site-out: estimand and test recomputed S times; "site-robust" only if the sign holds in all S runs.
- Wild cluster bootstrap (sensitivity): regression of the building value on an intercept with equal total weight per
  site, Webb six-point weights (Webb 2023, Canadian Journal of Economics, doi 10.1111/caje.12661, verified D10), null
  imposed, 9,999 replicates, seed 2017.
- All site values shown; residual same-day target-donor correlation reported (T2.6).

## 8. Minimum detectable effects and expected outcomes (2016, 11 sites)
MDE (2.8 x SD / sqrt(S), approximate): H1 0.089; H2 0.22; H3 0.084 (log scale); H4 0.021 (p-cross); H5 0.0015 per dispatch (absolute erosion).
Holm on the 2016 development p values (ordered H4 0.0005, H2 0.00098, H5 0.00098 two-sided, H1 0.027, H3 0.051 against 0.010, 0.0125, 0.0167, 0.025, 0.05): H4, H2 and H5 would be rejected (H5 in the direction scmR erodes faster); Holm stops at H1 (0.027 > 0.025), so H1 and H3 (p_TOST 0.051, not equivalent even unadjusted) would not be supported. Expected 2017 outcome on this evidence: H2 and H4 well powered; H1 borderline; a two-sided H5 is expected to show scmR eroding faster than pjmA (absolute error growing faster with dispatch count, HL -0.0022 per dispatch in 2016); H3 likely not shown equivalent (site log ratios: within +/-0.03 at 6 of 11 sites, 0.04-0.08 in absolute value at Cockatoo, Rat and Robin, and +0.128 and +0.315 at Lamb and Hog). Effects below the MDEs are not resolvable with 11 sites; the paper says so.

## 9. Leakage assertions (code assertions; failures stop the run)
1. max(lookback or training day) < d for every method and event.
2. No event day of the current world (or the day before, NYISO) in any later lookback, SCM pre-period or ML training set.
3. Target event-day hours only within the information set (I-morn <= s-2; I-donor < s-4); target window hours never.
4. No 2017 load value in HPO, grids, thresholds, DST mapping, margin, screening tree, K or windows; the frozen manifest
   md5 is checked at the start of every 2017 run.
5. ML normalisers and encoders fitted on training rows of each refit only.
6. Donor eligibility from data < d plus completeness on d; weights fitted on pre-period rows only.
7. Folds from results/frozen/folds.csv; no target in its own donor pool; no participant in any donor pool.
8. Event dates from results/frozen/event_dates.csv only (made without load data).
9. Filters use raw readings only and are identical across methods; injection happens after filtering.
10. Same-day observed weather only in weather baselines (ex-post settlement), labelled.
11. DST mapping applied before window construction in both years.
12. Duplicate meters (identical series or correlation > 0.999) flagged, one copy dropped.
13. Injections touch only the declared hours of the target (donors only in the q scenario).
14. Support rule applied identically to both methods of a contrast.
15. 2017 scripts default to final mode; development outputs carry `_v0`.
16. ML early stopping uses an inner split inside each refit's training rows only.
17. Feature sets fixed before 2017; no feature selection on 2017 data.
18. Disclosure: E1 (2017 valid-day count) and E3 (2017 flat share, including event-day hours) are the only
    2017-dependent selections; sensitivity with E3 computed on non-event days only.
Donor-based forecasts share site weather, occupancy and site-wide interventions with the target; disjoint folds
prevent overlap, not shared shocks, so donor baselines are not independent counterfactual evidence.

## 10. Ledger (`tables/summary.csv`)
Columns: key, value, ci_low, ci_high, p_raw, p_holm, n_sites, n_buildings, n_events, source_file, status
(confirmatory | secondary | exploratory), family_id (C5 | S-rules | none), hypothesis_id (H1..H5 | none),
estimand_version (PREREG-R2), data_year (2016 | 2017), freeze_hash, support_rule (S10 | none).
p_holm is filled only for family_id C5 rows. Keys as in Revision 1: sample.*, sample.excl.<site>.<reason>,
H1.* .. H5.* (est, ci, p_signedrank or p_sign, p_holm, p_wcb, loso_min, loso_max, site.<site>), H3.p_tost, H3.decision,
H3.margin, H4.pcross.*, pstar.<method>.<shape>, incr_sens.<p>, H5.eta.<method>, H5.rho.<method>.K<k>, H5.Dtau.<method>,
H5.fallback.<rule>.K<k>, method.<id>.<world>.*, precool.*, H6.*, screen.*, ablation.*, contam.*, rebound.*, heatwave.*,
r2iso.*, r2loo.*, dst_alt.*, hpo.*, compute.*. R2-ISO and screening outputs never use H1-H5 keys.

## 11. Deviations from this plan (empty at freeze)
| # | date | section | change | reason | effect on results (both shown) |
|---|---|---|---|---|---|

## 12. Freeze procedure and open items
Freeze order (D11): the src/run pipeline first reproduces the 2016 development values of section 6 from the frozen
inputs; then md5 over PREREG.md, results/frozen/*.csv and src/run/*.py is written to the manifest; only then is 2017
scored. Open items: 
1. H5 CLOSED by D12 (absolute erosion) and D13 (two-sided test, no direction committed). 2016: contrast negative at all
   11 sites, two-sided p = 0.00098; signed rho and the lookback-age diagnostic are secondary.
2. H3 is expected to fail equivalence on 2016 evidence; no change proposed (changing the margin after seeing 2016
   values would be a forking path).
3. Holidays CLOSED (D12); in-season 2017 dates in results/frozen/holidays.csv checked.
4. scmR changed from W = 5/lambda = 1 to W = 7/lambda = 3 because the folds changed to the frozen mapping; the surface is
   flat (0.0612-0.0622 over the four best configurations). The src/run implementer must use W = 7, lambda = 3.
5. Development numbers used one fold mapping and one R3 draw set (the frozen ones); the R1 run used E8 and rounded Tmax
   through event_dates.csv; earlier Revision 1 values are superseded and not quoted.
