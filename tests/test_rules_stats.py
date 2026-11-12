import numpy as np
import pandas as pd
import pytest

from helpers import toy_site
from run import adjust as AJ
from run import baselines as BL
from run import config as C
from run import leakage as LK
from run import stats as ST


def test_pjm_and_caiso_on_hand_series():
    site = toy_site(nd=60)
    d = 35
    rows = BL.run_rule(site, site.Ys, site.Ys, {d}, [d], [0], [], do_scm=False)
    r = rows[0]
    # day k has hourly load 10 + k, window = 4 hours. PJM: 5 most recent days 34..30 (44..40), high 4 -> 44,43,42,41
    assert r["pjm0"] == pytest.approx(4 * (44 + 43 + 42 + 41) / 4)
    # CAISO 10-in-10: days 34..25 -> mean 39.5
    assert r["caiso0"] == pytest.approx(4 * 39.5)
    assert r["prev"] == pytest.approx(4 * 44)
    b = AJ.adjusted(pd.DataFrame(rows), 14, 18)
    # event-day load 45 per hour; PJM profile mean 42.5 over hours 10-12 -> SAA = 4 * (45 - 42.5)
    assert b["pjmA"][0] == pytest.approx(170 + 4 * (45 - 42.5))
    # CAISO ratio 45 / 39.5 = 1.139 inside the [0.8, 1.2] cap
    assert b["caisoA"][0] == pytest.approx(158 * 45 / 39.5)


def test_pjm_drops_low_days_and_event_exclusion():
    # a near-zero day among the 5 most recent is dropped by the 25 % rule (implemented order), then top 4 of the rest
    site = toy_site(nd=60, fn=lambda k, j: 0.1 if k == 33 else 10.0 + k)
    d = 35
    r = BL.run_rule(site, site.Ys, site.Ys, {d}, [d], [0], [], do_scm=False)[0]
    assert r["pjm0"] == pytest.approx(4 * (44 + 42 + 41 + 40) / 4)
    # an earlier event day is never in the lookback (no fallback needed)
    r2 = BL.run_rule(site, site.Ys, site.Ys, {d, 34}, [d], [0], [], do_scm=False)[0]
    assert r2["prev"] == pytest.approx(4 * 0.1)  # day 33 is now the previous eligible weekday


def test_signed_rank_enumerated():
    r = ST.signed_rank([-1, -2, -3, 4], "less")
    assert r["p"] == pytest.approx(7 / 16)          # subsets of {1,2,3,4} with sum <= 4: 7 of 16
    g = sum(1 for m in range(16) if sum(i + 1 for i in range(4) if m >> i & 1) >= 4) / 16
    assert ST.signed_rank([-1, -2, -3, 4], "greater")["p"] == pytest.approx(g)
    assert ST.signed_rank([-1, -2, -3, 4], "two")["p"] == pytest.approx(14 / 16)   # only W+ = 5 (2 subsets) is closer to M/2
    r = ST.signed_rank([0, 0, -1, 1, 2], "less")   # zeros dropped and counted
    assert r["n_zero"] == 2 and r["n"] == 3
    assert ST.signed_rank(-np.arange(1, 12), "less")["p"] == pytest.approx(1 / 2048)


def test_signed_rank_enum_matches_dp():
    x = np.array([-0.3, -0.1, 0.2, -0.5, 0.05, -0.2, -0.7, 0.4, -0.25])
    a = ST.signed_rank(x, "less", enum_max=30)["p"]
    b = ST.signed_rank(x, "less", enum_max=0)["p"]
    assert a == pytest.approx(b)
    x2 = np.array([-1.0, -1.0, 2.0, -3.0, 3.0, 0.5])   # ties -> average ranks
    assert ST.signed_rank(x2, "two", enum_max=30)["p"] == pytest.approx(ST.signed_rank(x2, "two", enum_max=0)["p"])


def test_tost_and_holm():
    x = np.linspace(-0.04, 0.04, 11)
    t = ST.tost(x, C.TOST_DELTA)
    assert t["p"] == pytest.approx(1 / 2048) and t["p_lower"] == t["p_upper"]
    wide = ST.tost(np.linspace(0.05, 0.2, 11), C.TOST_DELTA)
    assert wide["p"] > 0.5            # sites above the margin: equivalence not shown
    h = ST.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h["a"] == pytest.approx(0.03) and h["c"] == pytest.approx(0.06) and h["b"] == pytest.approx(0.06)
    h5 = ST.holm({"H4": 0.0005, "H2": 0.001, "H5": 0.016, "H1": 0.027, "H3": 0.051})
    assert h5["H4"] == pytest.approx(0.0025) and h5["H5"] == pytest.approx(0.048) and h5["H1"] == pytest.approx(0.054)


def test_hl_sign_and_order_ci():
    est, lo, hi, conf = ST.hl_ci([1, 2, 3])
    assert est == 2
    s = ST.sign_test([0.02] * 10 + [float("inf")], 0.10, "less")
    assert s["k"] == 10 and s["n"] == 11 and s["p"] == pytest.approx(12 / 2048)
    lo, hi, conf = ST.median_ci_order(list(range(11)))
    assert (lo, hi) == (1.0, 9.0) and conf == pytest.approx(1 - 2 * 12 / 2048)


def test_wcb_runs_and_is_one_sided():
    y = -np.abs(np.random.default_rng(1).normal(0.3, 0.1, 11))
    assert ST.wcb_p(y, 0.0, "less", B=999) < 0.05
    assert ST.wcb_p(-y, 0.0, "less", B=999) > 0.5


def test_leakage_assertions_fire():
    with pytest.raises(AssertionError):
        LK.a1_lookback_before(10, [3, 10])
    with pytest.raises(AssertionError):
        LK.a2_no_event_days({5}, [4, 5])
    with pytest.raises(AssertionError):
        LK.a3_hours([10, 13], 14, "I-morn")      # hour 13 > s-2
    with pytest.raises(AssertionError):
        LK.a3_hours([9, 10], 14, "I-donor")      # hour 10 >= s-4
    with pytest.raises(AssertionError):
        LK.a3_window_unused([12, 14], [14, 15, 16, 17])
    with pytest.raises(AssertionError):
        LK.a5_fit_rows_before([100, 140], 140)
    with pytest.raises(AssertionError):
        LK.a5_val_inside_train([1, 2, 3], [3, 4])
    with pytest.raises(AssertionError):
        LK.a7_folds([1, 2], [2, 3])
    LK.a1_lookback_before(10, [3, 9])


def test_first_cross_rules():
    from run import analysis as AN
    g = np.array(C.P_FINE)
    assert AN.first_cross(np.linspace(0.05, 0.08, 61), 0.10, g) == float("inf")      # censored
    assert AN.first_cross(np.full(61, 0.2), 0.10, g) == 0.0
    v = np.linspace(0.0, 0.3, 61)   # crosses 0.10 exactly at p = 0.10
    assert AN.first_cross(v, 0.10, g) == pytest.approx(0.10)
    v2 = v.copy()
    v2[10] = np.nan
    assert np.isnan(AN.first_cross(v2, 0.10, g))
