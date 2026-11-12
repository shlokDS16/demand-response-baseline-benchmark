VERDICT: PASS-WITH-FIXES - freeze, recomputation (79 of 79 values), ledger and leakage all verified; fixes are wording and disclosure items only

# P4 audit (2017 confirmatory run), Paper B. Auditor: research audit agent, 2026-11-11. Nothing outside audits/ was edited.

Artifacts written to audits/: P4_audit.md (this file), recompute_2017.py + recompute_2017_output.txt, leakage_spot.py + leakage_spot_output.txt, donor_mismatch.py (small diagnostic). Scripts do not import src.run; pandas needed the user site-packages path appended (python -I otherwise cannot see numpy). The .pkl frames are this project's own outputs (trusted).

## 1. Freeze integrity: PASS
- `md5sum -c` of every manifest entry (20 files: PREREG.md, DEVIATIONS.md, 3 frozen CSVs, 15 src/run/*.py): all OK.
- PREREG.md md5 = 02a36872d674647eb8fcbf8632c5663e (matches). Manifest file md5 = 8bc576292eb91fd5c00e416a7452a230 (matches the value in every ledger row).
- Timing: manifest mtime 18:56:05 IST (header "18:56 IST"); logs/run2017_confirmatory_v2.log starts 18:56:11 IST; pkl/summary mtimes 18:58-19:03. Run began 6 s after the manifest (thin margin but correct order).
- Disclosed earlier 2017 attempt (logs/run2017_confirmatory.log, 18:44:44-18:46:41, under manifest v1, created 18:44:27): it died with KeyError 'scmC' in the pre-cooling step; the log shows only meter counts and timings, no statistic. DEV-1 documents this and the code-only fix. I cannot verify the statement "the pkl frames were not opened"; it is an attestation. src/run mtimes (latest 18:47:39) all precede manifest v2.

## 2. Independent recomputation: PASS (79 compared, 0 differences)
Own code (exact enumerated signed-rank with average ranks and zeros dropped, HL with exact inversion, TOST, exact sign test, Holm) applied to events_R1/R3/erosion.pkl. All site values, estimates, CIs and p-values equal the ledger to <= 1e-16 (tolerances were 1e-9 for p, 1e-6 relative for estimates). Details of what was done:
- H1 (pjm0 delta-bias, building-first, 5 R3 draws averaged per building): HL -0.04847, 95% CI [-0.0956, -0.0098], p = 0.00146 (10 of 11 sites negative; Lamb +0.0035).
- H2 (log relMAE pjmA/pjm0): HL -0.3976, CI [-0.6253, -0.2232], p = 0.000488 (11 of 11 negative).
- H3 (log relMAE cgA/pjmA; margin log 1.10 = 0.0953): HL -0.0089, 90% CI [-0.0824, 0.0564]; p_lower = 0.01611 (binding), p_upper = 0.00342, p_TOST = 0.01611; ledger decision "equivalent" is correct under the PREREG rule (Holm 0.01611 < 0.05).
- H4: recomputed from the pkl (pre-event 4-h shaping on morning hours s-4..s-1 re-applied on the 0.005 grid; the pkl holds morning hours and the pjm0 profile, so it is possible): 11 of 11 sites below 0.10, exact sign p = 0.000488, median site p-cross 0.04484, pooled 0.04241, all 11 site values match.
- H5 (slope of site-median |rho-1| over K = 10/20/30/40, pjmA minus scmR, two-sided enumerated): HL -0.002808, CI [-0.004625, -0.001022], p = 0.004883 (10 of 11 negative; Bull +0.0009); 9,479 common-support events, no site dropped.
- Holm: H2 0.002441, H4 0.002441, H1 0.004395, H5 0.009766, H3 0.016113, identical to the ledger.

## 3. Support and exclusions: PASS (two minor disclosure points)
- 11 sites, 1,005 buildings, 9,550 R1 building-events (frame rows), 48,118 R3 rows; site n_after in sample.json sums to 1,005. Bobcat 9, Moose 9, Gator 0 fail E4 (>= 12). Lamb passes with 22 meters.
- Support rule (>= 10 per site per contrast): zero sites dropped for H1-H5 (my own recomputation gives empty drop dicts; R3 minimum 819 events per site). The ledger has support_share keys but no explicit "dropped sites = none" row (minor).
- No 2017-specific threshold: grep of src/run for 2017 finds only year plumbing, the freeze lock and the injection seed; thresholds are in config.py; DST table is read from the 2016 table (data.py L222). E1 and E3 are the declared 2017-dependent selections (PREREG s9.18).
- Disclosure points: (a) a minimum of 5 donors for cgA/cg0 (baselines.py L158, `len(don) >= 5`) is not stated in PREREG; it is frozen code, not 2017-tuned, and affects 6 Eagle events on day 193 (ndon 2 and 4), explaining H3 n_events 9,544 against 9,550. State it in the paper. (b) E3 removes 99 of 121 Lamb meters in 2017 (5 in 2016); Lamb stands on 22 buildings but weighs 1/11 in every site test.

## 4. Leakage spot-check: PASS
- Donors, all 9,550 events: frame fold equals results/frozen/folds.csv for every row; ndon equals the count, and don_L the sum of true window load, of opposite-fold buildings with an event row on that site-day (0 mismatches on count; the only 6 don_L differences are the NaN rows above, not leaks). No same-fold donor, no target in its own pool.
- 20 random R1 building-events (seed 20261111, CLOCK-mapped sites Bear, Bull, Fox, Hog, Peacock; STD sites skipped because DST re-mapping would duplicate the pipeline): pjm0 lookback re-derived from raw 2017 readings with my own eligibility code (weekday, non-holiday, non-event day of the site's R1 world, 24 complete hours, no >= 4 flat run in hours 10-19, first 5 in 45 days, 25% drop, top 4). All 80 lookback days are before the event day, none is an event day, all are non-holiday weekdays, and pjm0 and the 6-hour morning profile match the frame (rtol 1e-4; observed exact). 20 of 20 pass.

## 5. Ledger hygiene: PASS
1,090 rows, no duplicate keys. Confirmatory rows (196) all family C5, status confirmatory, freeze_hash 8bc576292eb91fd5c00e416a7452a230, data_year 2017. All 1,090 rows carry the hash and 2017. p_holm is non-null only on H1-H5 p rows (family C5, confirmatory). Secondary rows with H1-H5 key prefixes (p_wcb, ci_boot_conditional, anchors, H5.Dtau/rho/absdev/eta_*, H4.p_signedrank, ...) are status secondary, family none, with no p_holm. No non-confirmatory row has family C5. Cosmetic: sample.* rows are labelled confirmatory/C5 with hypothesis none; harmless.

## 6. Reporting risks (fix in the manuscript wording)
1. H3 "equivalent" is a statement about the site-median log ratio, not about sites or buildings. The 90% HL interval [-0.0824, 0.0564] sits inside +-0.0953 with room of 0.013 on the lower side only; p_TOST = 0.0161 is driven by the lower bound (p_lower); leave-one-site-out worst p is 0.0322. Five of 11 site values lie outside the margin (Hog +0.189, Lamb +0.122, Robin -0.182, Fox -0.156, Peacock -0.125). The conditional two-stage bootstrap 95% interval [-0.1093, 0.0141] extends beyond the lower margin; wild-cluster p is empty for H3. 2016 gave HL +0.035, p_TOST 0.051 (not equivalent); say 2017 reversed that and that equivalence is margin-dependent (margin fixed at 10% relMAE ratio, about 0.005 relMAE). cgA and pjmA share the donor-side shocks and site weather (PREREG s9 note), so "equivalent" is not independent evidence. Do not write "the comparison group is equivalent for single buildings".
2. H5 direction opposes the original theory-based prediction (rule erosion by lookback contamination, Nexant BAWG 2017, NAESB 2009). Result: scmR's absolute error grows faster than pjmA's (eta difference -0.0028 per dispatch; 10 of 11 sites negative; Bull positive; Eagle and Lamb about -0.0005 to -0.0006, near zero). pjmA still erodes in absolute terms (site-median |rho-1| 0.233 at K = 10 to 0.265 at K = 40, eta about +0.0013), so do not write "no erosion". PREREG fixed H5 as two-sided after the D12/D13 redefinition from the signed version seen in 2016; report it as not causal and as a contrast of two slopes. scmR is also worse at K = 10 (0.332 against 0.233), and the PREREG age diagnostic (scmR pre-period uses older days) is the stated mechanism, not a tested one.
3. H4: sign test with 11 of 11 sites cannot go below 2^-11 = 0.000488, so p and Holm 0.00244 sit at the floor (same for H2); they show unanimity, not magnitude. Two sites (Eagle, Lamb) have p-cross = 0, meaning pjmA is not better than scmR even without pre-event increase, so "pjmA loses its advantage at p-cross" is not an advantage-loss at those sites; the order-statistic CI lower end is 0.0. The 0.10 threshold is from field studies of pre-cooling, and the shaping is injected (synthetic), so H4 is a sensitivity analysis, not observed gaming. scmR is itself a donor method exposed to shared shocks.
4. H1 is small (-0.048 of window load, CI upper end -0.0098) with Lamb the exception; H2 Eagle effect is -0.0008 (sign only). Say "10 of 11" and "11 of 11 negative" with those magnitudes.
5. Five Holm p-values are all small, but with S = 11 sites and a convenience sample, inference is conditional on these sites (PREREG s6); the MDEs in s8 apply. Lamb has 22 buildings after E3.
6. Frame/ledger secondary items I did not audit: LOSO min/max, WCB and conditional bootstrap values (only confirmatory keys were recomputed).

## Required fixes before drafting
- State the 5-donor minimum, the 6 excluded Eagle events, and the Lamb E3 loss (99 of 121) in methods or supplement.
- Add a ledger row or sentence "no site dropped by the S10 support rule for H1-H5".
- Use the H3, H4 and H5 wording in section 6 above.

Agent ledger: this audit agent, model Sonnet 5.5, no sub-agents; value: useful (independent confirmation).
