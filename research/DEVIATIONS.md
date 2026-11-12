# Deviations from the frozen pre-registration (PREREG.md md5 02a36872d674647eb8fcbf8632c5663e)

PREREG.md stays frozen and read-only; its section 11 table is kept here instead, so the frozen file's hash does not
change. Every deviation lists what was known about 2017 results at the time.

| # | date (IST, from `date`) | section | change | reason | 2017 information seen before the change | effect |
|---|---|---|---|---|---|---|
| DEV-1 | 2026-11-11 18:50 | s3, s5 (scmC); code only | `src/run/baselines.py`: in final mode the SCM loop now computes the frozen scmR (W = 7, lambda = 3) AND the frozen scmC (W = 5); before, final mode computed only W = 7, so scmC (a secondary method in the H4 p* table) was missing. `src/run/main.py`: new dev-only flag `--scm-final` runs 2016 through the final-mode path (output results/run_v0/finalpath/) to test that path before 2017 | the first 2017 run (18:44-18:46) stopped with `KeyError: 'scmC'` in the pre-cooling step, after the core baselines were built and before any statistic or ledger row was computed; the 2016 validation ran in dev mode, which computes every grid point, so it never exercised the final path | none: the log shows only meter counts and per-site timings; no ledger, no statistic, no figure; results/run/*.pkl (event frames) were not opened | no change to any specification; manifest v2 replaces v1 (v1 kept as FREEZE_MANIFEST_v1.md5) |

DEV-1 verification (2026-11-11 18:56 IST): `python -I src/run/main.py --year 2016 --mode dev --scm-final --part core,precool,erosion` (log logs/run2016_finalpath.log, output results/run_v0/finalpath/summary_v0.csv) reproduces the dev reference (results/run_v0/summary_v0.csv) exactly for H1-H5 estimates and Holm p (H4 0.00244, H2 0.00391, H5 0.00391, H1 0.0537, H3 0.0537) and now carries scmC keys. 15 unit tests pass. Manifest v2 (research/FREEZE_MANIFEST.md5) lists PREREG.md (unchanged hash), the 3 frozen CSVs, all src/run/*.py and this file; v1 kept as research/FREEZE_MANIFEST_v1.md5.
