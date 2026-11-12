import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJ, "src", "paper"))
import derived_keys as dk  # noqa: E402


def _ledger():
    with open(os.path.join(PROJ, "tables", "summary_derived.csv"), encoding="utf-8", newline="") as f:
        return {r["key"]: r for r in csv.DictReader(f)}


def test_counts_match_site_values():
    rows = dk.read_rows([os.path.join(PROJ, "tables", "summary.csv")])
    out = {r["key"]: r for r in dk.build(PROJ, use_pickle=False)}
    m = float(rows["H3.margin"]["value"])
    assert abs(m - 0.0953101798) < 1e-9
    h3 = dk.site_values(rows, "H3")
    assert int(out["derived.H3.n_sites_outside_margin"]["value"]) == sum(abs(v) > m for v in h3.values())
    assert int(out["derived.H3.n_sites_outside_margin"]["value"]) == 5
    assert out["derived.H4.n_sites_pcross_zero"]["value"] == "2"
    assert out["derived.H4.n_sites_pcross_lt_threshold"]["value"] == "11"
    assert out["derived.H5.n_sites_scmR_faster"]["value"] == "10"
    assert out["derived.cgA.n_events_missing_eagle"]["value"] == "6"


def test_file_schema_and_admission():
    led = _ledger()
    assert "derived.dm0.n_events_differ" in led and led["derived.dm0.n_events_differ"]["value"] == "43"
    base = open(os.path.join(PROJ, "tables", "summary.csv"), encoding="utf-8").readline().strip().split(",")
    assert list(next(iter(led.values())).keys()) == base
    for r in led.values():
        assert r["data_year"] == "2017" and r["status"] == "derived"
        assert r["source_file"] == "src/paper/derived_keys.py"


def test_no_key_overlap_with_ledgers():
    led = _ledger()
    for name in ("summary.csv", "summary_secondary.csv"):
        with open(os.path.join(PROJ, "tables", name), encoding="utf-8", newline="") as f:
            ks = {r["key"] for r in csv.DictReader(f)}
        assert not (ks & set(led))


def test_round2_keys():
    led = _ledger()
    r = led["derived.H3.share_sites_inside_margin"]
    assert abs(float(r["value"]) - 6 / 11) < 1e-12
    lo, hi = dk.clopper_pearson(6, 11)
    assert abs(lo - 0.2338) < 5e-4 and abs(hi - 0.83251) < 5e-4      # Clopper-Pearson 6/11
    assert abs(float(r["ci_low"]) - lo) < 1e-12 and abs(float(r["ci_high"]) - hi) < 1e-12
    assert abs(float(led["derived.H4.ci_exact_coverage"]["value"]) - (1 - 24 / 2048)) < 1e-12
    assert abs(float(led["derived.H4.max_site_pcross"]["value"]) - 0.0665081607) < 1e-9
    assert led["derived.H5.n_K_scmR_less_accurate"]["value"] == "4"
    assert abs(float(led["derived.incr_sens.ratio_2h_4h"]["value"]) - 0.00929798 / 0.05930249) < 1e-6
    assert "derived.precool.share_daily_energy_4h" not in led     # not computable from ledgers or pickles


def test_dev_ledger_and_allowlist():
    with open(os.path.join(PROJ, "tables", "summary_dev.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 12
    allow = {ln.strip() for ln in open(os.path.join(PROJ, "paper", "ALLOW_DEV_KEYS.txt"), encoding="utf-8")
             if ln.strip() and not ln.startswith("#")}
    for r in rows:
        assert r["data_year"] == "2016" and r["freeze_hash"] == "dev-unfrozen" and r["key"].endswith("_v0")
        assert r["key"] in allow
    # fill_ledger admits a 2016 row only if its key is allowlisted; allowlisted keys may live in any ledger.
    assert {r["key"] for r in rows} <= allow
    dev_keys = set()
    for name in ("summary_dev.csv", "summary_secondary.csv", "summary_exploratory.csv", "summary_derived.csv", "summary.csv"):
        with open(os.path.join(PROJ, "tables", name), encoding="utf-8", newline="") as f:
            dev_keys |= {r["key"] for r in csv.DictReader(f) if r["data_year"] == "2016"}
    assert allow <= dev_keys, sorted(allow - dev_keys)
