"""Tests of src/secondary/d29.py (decision D29): pure helpers on synthetic data, and consistency checks on the written rows file."""
import math

import numpy as np
import pandas as pd
import pytest

from run import config as C
from secondary import common as CM, d29 as D, exploratory as EX

ROWS = C.ROOT / "results" / "secondary" / "2017" / "d29.rows.csv"


def test_cp_lower_all_successes_closed_form():
    assert abs(D.cp_lower(11, 11) - 0.05 ** (1 / 11)) < 1e-12
    assert abs(D.cp_lower(11, 11) - 0.7616) < 1e-4
    assert D.cp_lower(0, 11) == 0.0


def test_cp_lower_matches_binomial_tail():
    k, n = 10, 11
    lb = D.cp_lower(k, n)
    tail = sum(math.comb(n, i) * lb ** i * (1 - lb) ** (n - i) for i in range(k, n + 1))
    assert abs(tail - 0.05) < 1e-9


def test_pred_int_coverage_and_range():
    lo, hi, cov = D.pred_int([3, 1, 2, 5, 4, 9, 8, 7, 6, 10, 0])
    assert (lo, hi) == (0.0, 10.0) and abs(cov - 10 / 12) < 1e-12


def test_episodes_gap_rule():
    d = ["2017-07-05", "2017-07-06", "2017-07-17", "2017-07-18"]
    assert D.episodes(d) == 2
    assert D.episodes(["2017-06-01", "2017-06-04"]) == 1          # gap 3 days: same episode
    assert D.episodes(["2017-06-01", "2017-06-05"]) == 2          # gap 4 days: new episode
    assert D.episodes([]) == 0 and D.episodes(["2017-06-01"] * 3) == 1


def test_holm_family_of_three_with_ties():
    adj = D.holm_adjust({"ny": 0.0009765625, "caiso": 0.00048828125, "isone": 0.00048828125})
    assert all(abs(v - 3 * 0.00048828125) < 1e-15 for v in adj.values())


def test_xwin_contrast_known_case():
    a = {"s%d" % i: -0.002 - 0.0001 * i for i in range(11)}
    b = {k: v + 0.001 for k, v in a.items()}                         # 14-18 is 0.001 lower at every site
    x = D.xwin_contrast(a, b)
    assert abs(x["est"] + 0.001) < 1e-12 and x["n_stronger_1418"] == 11 and x["n_sign_agree"] == 11
    assert abs(x["p"] - 2 ** -10) < 1e-12                           # all 11 negative: two-sided exact p = 2 * 2^-11


def test_holm_h4_tip_uses_other_p_values():
    other = {"H1": 0.00146, "H2": 0.000488, "H3": 0.01611, "H5": 0.00488}
    k, p = D.holm_h4_tip(other)
    assert k == 9 and abs(p - 0.03271484375) < 1e-12
    assert D.holm_h4_tip({"H1": 0.04, "H2": 0.04, "H3": 0.04, "H5": 0.04})[0] is None


def test_expl_ledger_relabel_keeps_keys():
    led = EX.ExplLedger(2017, "x")
    led.add("exploratory.a.b", 1.0)
    led.relabel("secondary")
    df = led.L.to_frame()
    assert list(df.key) == ["exploratory.a.b"] and (df.status == "secondary").all()
    assert {"h4_win1620", "h5_win1620", "dst_alt"} == set(EX.SECONDARY_ANALYSES)


def test_collect_accepts_derived_and_descriptive_statuses():
    src = (C.ROOT / "src" / "secondary" / "common.py").read_text()
    assert '"derived", "descriptive"' in src


@pytest.mark.skipif(not ROWS.exists(), reason="d29.rows.csv not written yet")
class TestRowsFile:
    @pytest.fixture(scope="class")
    def df(self):
        return pd.read_csv(ROWS, float_precision="round_trip").set_index("key")

    def test_shape_and_flags(self, df):
        assert (df.family_id == "secondary").all() and df.p_holm.isna().all()
        assert set(df.status) <= {"derived", "secondary", "exploratory", "descriptive"}
        assert (df.data_year == 2017).all()

    def test_lamb_has_four_event_days(self, df):
        assert float(df.loc["sample.event_days.Lamb", "value"]) == 4 and float(df.loc["sample.event_days_designated.Lamb", "value"]) == 10
        assert (df.loc["sample.event_days.Lamb", "status"]) == "descriptive"
        assert float(df.loc["sample.heat_episodes.Lamb", "value"]) == 2

    def test_cross_window_contrast_matches_site_values(self, df):
        led = pd.concat([pd.read_csv(C.ROOT / "tables" / f) for f in ("summary.csv", "summary_secondary.csv")]).drop_duplicates("key").set_index("key")
        d = np.array([float(led.loc["H5.site." + s, "value"]) - float(led.loc["exploratory.h5_win1620.site." + s, "value"])
                      for s in ("Bear", "Bull", "Cockatoo", "Eagle", "Fox", "Hog", "Lamb", "Peacock", "Rat", "Robin", "Wolf")])
        k = "exploratory.h5_window_contrast.eta_diff_1418_minus_1620"
        from run import stats as ST
        assert abs(float(df.loc[k, "value"]) - ST.hl_ci(d)[0]) < 1e-15
        assert float(df.loc["exploratory.h5_window_contrast.n_sites_stronger_1418", "value"]) == int((d < 0).sum())

    def test_levels_keys_present_both_windows(self, df):
        for w in ("w1418", "w1620"):
            assert float(df.loc["derived.H5.levels_pjmA_lower_all_K." + w, "value"]) == 4
        for m in ("pjmA", "scmR"):
            for K in (10, 20, 30, 40):
                assert "derived.H5.absdev_sitemedian_w1620.%s.K%d" % (m, K) in df.index

    def test_holm_family_values(self, df):
        for r in ("ny", "caiso", "isone"):
            assert abs(float(df.loc["H2s.p_holm_family." + r, "value"]) - 0.00146484375) < 1e-15

    def test_status_relabel_applied(self):
        for name in D.SECONDARY_FILES:
            d = pd.read_csv(C.ROOT / "results" / "secondary" / "2017" / ("%s.rows.csv" % name))
            assert (d.status == "secondary").all(), name

    def test_collected_ledger_contains_d29_keys(self, df):
        led = pd.read_csv(C.ROOT / "tables" / "summary_secondary.csv").set_index("key")
        assert set(df.index) <= set(led.index)
