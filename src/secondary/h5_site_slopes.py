"""D19: per-method H5 slope summaries at the site level (secondary ledger, descriptive).
Reads the frozen 2017 results state (self-written by src/run) and writes, for each H5 method, the median over the
11 sites of the per-site slope of the site-median |rho_b - 1| on K (the per-site values the frozen H5 test uses),
plus the slope of the median-over-sites curve. The frozen keys H5.eta.<m> are slopes of the building-pooled median
(descriptive) and are labelled so here."""
import csv, hashlib, os, pickle, site, sys
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
st = pickle.load(open(ROOT / "results" / "run" / "results_state.pkl", "rb"))   # self-written by src/run
er = st["erosion"]
Ks = np.array([10, 20, 30, 40], float)
fh = hashlib.md5((ROOT / "research" / "FREEZE_MANIFEST.md5").read_bytes()).hexdigest()
out = ROOT / "tables" / "summary_secondary.csv"
cols = next(csv.reader(open(out, encoding="utf-8")))
rows = []
for m, d in er["methods"].items():
    site = d.get("eta_abs_site", {})
    if not site:
        continue
    v = np.array(list(site.values()), float)
    absd = d.get("abs_dev_pooled", {})
    rows.append({"key": f"H5.eta_abs.median_of_site_slopes.{m}", "value": float(np.median(v)), "n_sites": len(v)})
    rows.append({"key": f"H5.eta_abs.building_pooled.{m}", "value": float(d["eta_abs"]), "n_sites": len(v)})
for r in rows:
    r.update(status="secondary", family_id="secondary", hypothesis_id="H5", estimand_version="D19",
             data_year=2017, freeze_hash=fh, source_file="results/run/results_state.pkl",
             support_rule="H5 common support (frozen)")
# Also keep a rows file so any later rebuild of summary_secondary.csv (which concatenates
# results/secondary/<year>/*.rows.csv) keeps these keys.
rows_file = ROOT / "results" / "secondary" / "2017" / "h5_site_slopes.rows.csv"
rows_file.parent.mkdir(parents=True, exist_ok=True)
with open(rows_file, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in cols})
existing = {r["key"] for r in csv.DictReader(open(out, encoding="utf-8"))}
with open(out, "a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    for r in rows:
        if r["key"] not in existing:
            w.writerow({c: r.get(c, "") for c in cols})
for r in rows:
    print(r["key"], round(r["value"], 6))
