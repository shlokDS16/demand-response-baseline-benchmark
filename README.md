# Reproduction package: Paper B (confirmatory test of building demand-response baselines under event-day behaviour change)

This package lets a reviewer verify the frozen inputs, rerun the pipeline and rebuild the ledger and the paper.
It is slim on purpose (a few MB). Raw data and large intermediate pickles are not included; commands below fetch or regenerate them.
All commands run from the package root (the folder holding this README). Paths are relative.

## 1. What the paper is
A preregistered, computational study on the public BDG2 buildings data (14 sites, 2016 development year, 2017 confirmatory year),
with grid-region context from EIA-930. It tests five hypotheses (H1-H5, Holm family) about how baseline methods for demand-response
settlement behave when the load changes on event days (injected pre-cooling, shaped morning load), plus secondary and exploratory analyses.
Design, rules and tests are in `research/PREREG.md`; every departure is in `research/DEVIATIONS.md` (DEV-1: a crash in the final-mode SCM
path before any statistic was produced; code fixed, manifest v2 issued). Every number in the paper comes from a ledger row
(`tables/summary*.csv`, one key per number); `paper/ledger_used.csv` lists the keys the text uses.

## 2. Layout
| Path | Content |
|---|---|
| `src/run/` | frozen confirmatory pipeline (hashed by the manifest) |
| `src/secondary/` | secondary, exploratory and HPO code (imports `src/run` unchanged) |
| `src/paper/` | ledger fill, derived keys, paper build; `src/figures/` figure scripts |
| `src/design/`, `src/data/` | 2016 development and data-audit scripts (provenance only; set up once) |
| `tests/` | unit tests (73 collected) |
| `research/` | PREREG, DEVIATIONS, manifests v1 and v2 |
| `results/frozen/` | frozen folds, event dates, holidays (hashed) |
| `results/data_audit/`, `results/r2iso/`, `results/prereg2016/dst_table.csv` | small inputs read by the pipeline |
| `results/run/`, `results/run_v0/`, `results/secondary/`, `results/exploratory_v0/`, `results/hpo/*.db` | small outputs as produced (2017 final, 2016 dev, rows files, Optuna studies) |
| `tables/` | all ledgers (`summary.csv`, `summary_secondary.csv`, `summary_exploratory.csv`, `summary_derived.csv`, `summary_dev.csv`) and table sources |
| `figures/` | figure PDFs |
| `paper/` | templates (`*.tmpl.tex`), `main.tex`, `supplement.tex`, `references.bib` |
| `audits/` | audit trail: P3 and P4 research audits, independent recomputation of 2017 numbers, leakage spot check, donor-mismatch check, with their outputs |
| `logs/` | logs of the final 2017 runs |

Not included (listed so nothing is hidden): `data/raw/` (BDG2 about 352 MB, EIA-930 about 118 MB); event pickles that the pipeline
regenerates: `results/run/events_R1.pkl` (8.9 MB), `events_R2ISO.pkl` (7.3 MB), `events_R3.pkl` (43 MB), `events_erosion.pkl` (36 MB),
the same four for 2016 in `results/run_v0/` (14.5, 7.3, 47, 38 MB) and `results/prereg2016/` (13, 43, 35 MB), `results/hpo/cache` (154 MB of
float32 feature caches) and `results/hpo/eval/*.pkl` (per-site predictions). None exceeds 50 MB singly; they are left out for size.
All are rebuilt by the commands in section 4. Figure PNGs and LaTeX build files are also left out.

## 3. Environment and data
Python 3.14.3 (Windows 11), `python -m pip install --user -r requirements-lock.txt`. Every script prepends the user site-packages to
`sys.path`, so `python -I` works. CPU is enough for everything except the optional MLP part of HPO (CUDA GPU, or `--device cpu`).

Data download (into new folders; verify the checksums you record):
* BDG2 (Building Data Genome Project 2, buds-lab, CC BY-SA 4.0). Folder `data/raw/bdg2/` must hold `metadata.csv`, `weather.csv`,
  `electricity_cleaned.csv`, `electricity.csv`. Script `src/data/dl_bdg2.sh` (edit its `cd` line to the package root) fetches them from
  `https://media.githubusercontent.com/media/buds-lab/building-data-genome-project-2/master/data/` (`metadata/metadata.csv`,
  `weather/weather.csv`, `meters/cleaned/electricity_cleaned.csv`, `meters/raw/electricity.csv`), with resumable `curl -C -`.
  `electricity_cleaned.csv` holds 2016 first, then 2017 (the code asserts this).
* EIA-930 (US public data). Folder `data/raw/eia930/`: `EIA930_BALANCE_2016_Jan_Jun.csv`, `..._2016_Jul_Dec.csv`, `..._2017_Jan_Jun.csv`,
  `..._2017_Jul_Dec.csv` from `https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/<name>.csv` (send a browser-like user agent).
  Used only by `src/data/r2iso_days.py` to make `results/r2iso/r2iso_days.csv`, which is already included.

## 4. Rerun commands (order matters)
Run `python -I src/run/main.py ...` and the other scripts from the package root. The 2017 commands refuse to start unless the freeze
manifest matches (section 5). Peak memory and timings below are from `results/run/timing.json` and the logs (one workstation, 24 threads).

1. 2016 development (reference values, keys carry `_v0`; writes `results/run_v0/`):
   `python -I src/run/main.py --year 2016 --mode dev --part all`
2. 2017 confirmatory (writes `results/run/` and `tables/summary.csv`, about 1,260 rows; about 16 min in total: load 2 s, core 114 s + analysis 21 s,
   pre-cooling 217 s, erosion 89 s, secondary part 520 s; peak 1.0 GB RAM; no GPU):
   `python -I src/run/main.py --year 2017 --mode final --part all`
3. Secondary analyses (2016 first, then 2017; H6, screening tree, ablations, donor, non-event, flat-line sensitivities; about 1 GB):
   `python -I src/secondary/cli.py --year 2016 --part h6,tree,abl,donor,nonevent,flat`
   `python -I src/secondary/cli.py --year 2017 --part h6,tree,abl,donor,nonevent,flat`
   `python -I src/secondary/cli.py --year 2017 --collect`
   `python -I src/secondary/h5_site_slopes.py`   (per-site H5 slopes, D19 keys)
   `python -I src/secondary/timing_methods.py`   (per-method computational cost, referee R-D)
4. Exploratory (outside the Holm family; one command per analysis, 2016 then 2017, then collect; per-analysis 2017 time and peak RAM:
   h4_win1620 46 s / 0.36 GB, h5_win1620 118 s / 0.54 GB, dst_alt 155 s / 0.55 GB, x5 10 s / 0.24 GB, x7 121 s / 0.54 GB, neg_p 10 s / 0.24 GB,
   early_shape 1,452 s / 0.36 GB):
   `python -I src/secondary/exploratory.py --analysis <h4_win1620|h5_win1620|dst_alt|early_shape|x5|x7|neg_p> --year 2016`
   `python -I src/secondary/exploratory.py --analysis <same> --year 2017`
   `python -I src/secondary/exploratory.py --analysis early_shape --year 2017 --collect`
5. Hyperparameter tuning (Optuna, 40 TPE trials per model, tuned on 2016 only, evaluated on frozen 2017, five seeds; resumable: rerun the identical
   command). LightGBM variants (CPU, about 0.5-0.7 GB RAM per site, roughly 1-2 hours on the busy workstation):
   `python -u -I src/secondary/hpo.py --models lgbM,lgbD --trials 40 --eval-years 2017`
   MLP variants (GPU 12 GB, under 0.5 GB of GPU memory needed; about 1.1 GB RAM; hours; use `--device cpu` without a GPU):
   `python -u -I src/secondary/hpo.py --models mlpM,mlpD --trials 40 --eval-years 2017 --device cuda`
   Plan only: `python -I src/secondary/hpo.py --dry-run`. The `results/hpo/*.db` studies in this package are the completed 40-trial studies (see section 8).
6. Ledger and paper (no network, no data needed beyond the ledgers):
   `python -I src/paper/derived_keys.py`, `python -I src/paper/exploratory_keys.py`,
   `python -I src/paper/fill_ledger.py --strict` (fills `*.tmpl.tex` from the ledger; fails on a literal number that is not a ledger key),
   `python -I src/paper/build_paper.py` (fill, place floats, then pdflatex, bibtex, pdflatex x2 for `main` and `supplement`; needs a TeX Live with
   `elsarticle`; `--no-tex` stops before LaTeX). Figures: `python -I src/figures/fig_NN_<name>.py` (they read `results/run/`).

## 5. Verify the freeze
The dated record of the freeze is `research/FREEZE_MANIFEST.md5` (v2, issued after DEV-1, before any 2017 statistic was computed; v1 is kept in
`research/FREEZE_MANIFEST_v1.md5` and differs only in `src/run/baselines.py` and `src/run/main.py`, the two files changed by DEV-1).
`PREREG.md` is part of the hashed set, so its text cannot have changed since.

    md5sum -c research/FREEZE_MANIFEST.md5          # expect 20 lines "OK" (PREREG, DEVIATIONS, 3 frozen CSVs, 15 files in src/run)
    python -I -c "import sys; sys.path.insert(0,'src'); from run import freeze; print(freeze.check_manifest())"   # prints 8bc576292eb91fd5c00e416a7452a230

Expected hashes (v2): PREREG.md `02a36872d674647eb8fcbf8632c5663e`, DEVIATIONS.md `f3ee45fcb13f4480d29ce69dace18d73`, event_dates.csv
`3eeafcda69eb694249034cc90ff8b01f`, folds.csv `c62a9ff5add45ec9832038623cf4b938`, holidays.csv `63158d70be29352eda18802aee7caedc`; the 15
`src/run` hashes are in the manifest. Note: the status line of `PREREG.md` ("Revision 2 complete ...") was written before the freeze and does
not itself say "frozen"; the dated manifest is the verifiable freeze record, and the manifest hash is stored as `freeze_hash` in every 2017 ledger row.

## 6. Leakage assertions and tests
    python -I -c "import sys,site; sys.path.append(site.getusersitepackages()); import pytest; sys.exit(pytest.main(['tests','-q']))"
(or `python -m pytest tests -q`). Expected: 72 passed, 1 skipped (a slow one-site rerun, enabled by `EXPL_SLOW=1`) on a full working tree.
In this slim package six tests (in `tests/secondary/test_exploratory.py` and `tests/test_exploratory_keys.py`) need the regenerated 2016 and 2017
event pickles and fail or error with `FileNotFoundError` until step 1 and 2 of section 4 have run; the other 66 pass at once.
They check: the freeze lock (a changed byte in a hashed file aborts 2017); injection arithmetic; the baseline rules and statistics (Holm,
randomisation and bootstrap routines against exact enumeration); that exploratory code reproduces frozen 2016 H4 and H5 values exactly and writes
only `exploratory.*` keys; ledger fill (a literal number in prose that is not a ledger key fails); derived keys. The pipeline also carries runtime
assertions from PREREG section 9 (training data strictly before the event day, no test-site information in folds, event dates frozen before the
electricity file is opened, no 2017 data in tuning). Independent checks are in `audits/` (`recompute_2017.py`, `leakage_spot.py`,
`donor_mismatch.py`, with their `*_output.txt`).

## 7. Notes
* `tables/summary.csv` keeps a `source_file` column with the absolute path of the machine that produced it; it is a ledger and is left byte-identical.
* Text files under `src/design`, `src/data`, `audits`, `logs` had local absolute paths replaced by `<ROOT>` or by relative expressions; no file hashed
  by the manifest was touched.
* Licence: MIT for the code (`LICENSE`); CC BY-SA 4.0 for the derived data tables (`LICENSE-DATA.md`), as required by BDG2's share-alike licence.

## 8. Status of this snapshot
Built on 2026-11-12 after all pre-registered tuning runs finished. The LightGBM variants (lgbM, lgbD) and the MLP variants (mlpM, mlpD)
each ran 40 TPE trials on 2016 and were evaluated on the frozen 2017 data with five seeds (the MLP search ran on CPU, about 2.4 hours in total).
`tables/summary_secondary.csv` and `results/hpo/*.db` hold the final rows and studies. All four variants are evaluated in the paper.
