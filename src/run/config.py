"""All constants of the confirmatory pipeline, one place. Every constant names its PREREG section (Revision 2 where
the coordinator's T3 decisions apply). Nothing here is tuned on 2017."""
import os
import site
import sys
from pathlib import Path

up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "bdg2"                              # s1
AUDIT = ROOT / "results" / "data_audit" / "bdg2_meter_audit.csv"  # s1 E1 (A3 `usable`)
FROZEN = ROOT / "results" / "frozen"                              # T3 4.1: folds, event dates, holidays
FOLDS_CSV = FROZEN / "folds.csv"
EVENTS_CSV = FROZEN / "event_dates.csv"
HOLIDAYS_CSV = FROZEN / "holidays.csv"
DST_TABLE_2016 = ROOT / "results" / "prereg2016" / "dst_table.csv"  # s1 E6 (read only)
R2ISO_CSV = ROOT / "results" / "r2iso" / "r2iso_days.csv"           # s2 R2-ISO
PREREG = ROOT / "research" / "PREREG.md"
MANIFEST = ROOT / "research" / "FREEZE_MANIFEST.md5"              # T3: PREREG + results/frozen/*.csv + src/run/*.py
DEV_REF = ROOT / "results" / "prereg2016"

SITES = ["Bear", "Bobcat", "Bull", "Cockatoo", "Eagle", "Fox", "Gator", "Hog", "Lamb", "Moose", "Peacock", "Rat",
         "Robin", "Wolf"]  # s1 (sorted list; site index = position here)
YEAR_DAYS = {2016: 366, 2017: 365}
YEAR_HOURS = {2016: 8784, 2017: 8760}  # electricity_cleaned.csv holds 2016 first, then 2017 (checked by assertion)

# s1 E2/E3/E4/E8
FLAT_RUN = 4            # E2 identical consecutive readings
FLAT_METER_SHARE = 0.20  # E3
MIN_METERS_SITE = 12    # E4
MIN_TMAX_HOURS = 20     # E8
SEASON = ("05-15", "09-30")  # s2 R1
K_EVENTS = 10           # s2
R3_DRAWS = (1, 2, 3, 4, 5)  # s2 (frozen file draw ids)
MIN_SUPPORT = 10        # T3 1.2: building-events per method pair per site
# DST transitions (E6): table from 2016, applied in both years
DST_DATES = {2016: {"US": ("2016-03-13", "2016-11-06"), "UK": ("2016-03-27", "2016-10-30"), "IE": ("2016-03-27", "2016-10-30")},
             2017: {"US": ("2017-03-12", "2017-11-05"), "UK": ("2017-03-26", "2017-10-29"), "IE": ("2017-03-26", "2017-10-29")}}
DST_STD_SHIFT = (-0.5, 0.5)  # E6 STD rule
DST_CLOCK_ABS = 0.3          # E6 CLOCK rule

# s2 windows: primary 14-18, secondary 16-20 (hour-beginning s..e-1)
WINDOWS = {"primary": (14, 18), "w1620": (16, 20)}
# s3 adjustment hours relative to s (hour-beginning)
ADJ = {"pjm": (-4, -3, -2), "caiso": (-4, -3, -2), "ny": (-4, -3), "isone": (-3, -2), "dm": (-4, -3), "wm": (-4, -3), "m3": (-4, -3)}
CLIP = {"caiso": (0.8, 1.2), "ny": (0.8, 1.2), "dm": (0.8, 1.2), "wm": (0.6, 1.4), "m3": (0.8, 1.2), "towt": (0.6, 1.4)}
PJM_DROP = 0.25
# s5 fixed hyperparameters
SCM_W, SCM_LAM = 7, 3.0   # Revision 2 (s5): re-tuned on 2016 with the frozen folds
SCM_GRID_LAM = [0.01, 0.1, 0.3, 1.0, 3.0, 10.0, 100.0]
SCM_GRID_W = [2, 3, 5, 7, 10, 20, 40]
SCM_CLASSIC_PENALTY = 1000.0
LGB_FIXED = dict(objective="l1", learning_rate=0.05, num_leaves=31, min_child_samples=20, reg_lambda=1.0,
                 feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=2016, deterministic=True,
                 num_threads=20, verbose=-1)  # HPO (Optuna, 40 trials) not run: optuna absent; flagged in ledger
LGB_ROUNDS = 300
# s4 injection grids
C_PRIMARY = 0.10
C_GRID = (0.05, 0.10, 0.20)
P_BAND = (0.0, 0.02, 0.05, 0.10, 0.20, 0.30)
P_FINE = tuple(round(0.005 * i, 3) for i in range(61))
SHAPES = {"4h": (-4, 0), "2h": (-2, 0)}   # hours [s+a, s+b)
REBOUND = (0.0, 0.10)
CONTAM_Q = (0.0, 0.25, 0.5, 1.0)
CONTAM_P = 0.05
INJ_SEED = 2017
DISPATCH_K = (10, 20, 30, 40)
TAU = 0.10
HEATWAVE_MIN_RUN = 3
HEATWAVE_Q = 0.80
# s6 tests
H_FAMILY = ("H1", "H2", "H3", "H4", "H5")   # family of FIVE (T3 1.1)
TOST_DELTA = 0.0953101798043249             # log(1.10), s6 H3
PCROSS_THRESHOLD = 0.10
ALPHA = 0.05
BOOT_B = 10000
WCB_B = 9999
BOOT_SEED = 2017
WEBB = (-1.5 ** 0.5, -1.0, -0.5 ** 0.5, 0.5 ** 0.5, 1.0, 1.5 ** 0.5)
H5_PRIMARY = "abs"   # H5 eta on |rho - 1| (coordinator note after Revision 2); signed rho kept as secondary
SCM_C_W = 5            # scmC fixed W (s5)
