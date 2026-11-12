"""Tests of src/secondary/exploratory.py. The reproduction tests send the frozen 2016 frames (results/run_v0, self-written by
src/run) through the SAME code path the exploratory analyses use, with the primary window 14-18, and require the frozen 2016
values in results/run_v0/summary_v0.csv exactly. EXPL_SLOW=1 adds a one-site rerun test (about 1 GB, minutes)."""
import os

import numpy as np
import pandas as pd
import pytest

from run import analysis as AN, config as C
from secondary import exploratory as EX

RUN0 = C.ROOT / "results" / "run_v0"
SUMM = pd.read_csv(RUN0 / "summary_v0.csv", float_precision="round_trip").set_index("key")


def val(k):
    return SUMM.loc[k + "_v0", "value"]


@pytest.fixture(scope="module")
def h4_frozen_path():
    R1 = pd.read_pickle(RUN0 / "events_R1.pkl")      # self-written by run_core
    return EX.h4_run(R1, C.WINDOWS["primary"])


def test_h4_reproduces_frozen_2016(h4_frozen_path):
    r = h4_frozen_path
    assert r["pooled"] == float(val("H4.pcross.pjmA_scmR.4h"))
    assert r["median_site"] == float(val("H4.median_site_pcross"))
    assert r["p"] == float(val("H4.p_sign"))
    assert r["ci_low"] == SUMM.loc["H4.median_site_pcross_v0", "ci_low"]
    assert r["ci_high"] == SUMM.loc["H4.median_site_pcross_v0", "ci_high"]
    assert r["loso_min"] == float(val("H4.loso_min")) and r["loso_max"] == float(val("H4.loso_max"))
    assert r["sens_increment_p10"] == float(val("H4.sens_increment_p10"))
    for st, v in r["site_pcross"].items():
        assert v == float(val("H4.site." + st)), st
    assert len(r["site_pcross"]) == 11


def test_h5_reproduces_frozen_2016():
    ER = pd.read_pickle(RUN0 / "events_erosion.pkl")   # self-written by run_erosion
    res = EX.h5_run(ER, C.WINDOWS["primary"])
    c = res["contrast_abs"]["pjmA"]
    assert c["est"] == float(val("H5.eta_diff"))
    assert c["p"] == float(val("H5.p_signedrank"))
    assert c["ci_low"] == SUMM.loc["H5.eta_diff_v0", "ci_low"] and c["ci_high"] == SUMM.loc["H5.eta_diff_v0", "ci_high"]
    for st, v in c["site_values"].items():
        assert v == float(val("H5.site." + st)), st
    assert res["methods"]["pjmA"]["eta_abs"] == float(val("H5.eta.pjmA"))
    assert res["methods"]["scmR"]["eta_abs"] == float(val("H5.eta.scmR"))


def test_emit_keys_are_exploratory_only(h4_frozen_path):
    led = EX.ExplLedger(2016, "dev-unfrozen")
    EX.emit_h4(led, "exploratory.h4_win1620", h4_frozen_path, (14, 18))
    df = led.L.to_frame()
    assert len(df) > 20
    assert df.key.str.startswith("exploratory.").all() and df.key.str.endswith("_v0").all()
    assert (df.status == "exploratory").all() and df.p_holm.isna().all()
    assert not df.key.str.contains(r"(?:^|\.)H[1-5]\.").any()


def _fake_early(shift):
    g = np.round(np.arange(0, 0.305, 0.005), 3)
    n = 24
    keys = pd.DataFrame({"site": ["A"] * 12 + ["B"] * 12, "b": ["b%d" % i for i in range(n)], "day": ["d"] * n, "L": np.full(n, 100.0)})
    # pjmA error grows linearly with p from 0.03 at slope `shift`, scmR error constant 0.05 -> crossing at (0.05-0.03)/shift
    P = np.array([100.0 * (1 + 0.03 + shift * p) for p in g])[:, None] * np.ones((1, n))
    S = np.full((len(g), n), 105.0)
    return keys, P, S, g


def test_early_stats_crossing_on_synthetic_curves():
    keys, P, S, g = _fake_early(0.5)
    r = EX.early_stats(keys, P, S, g)
    assert abs(r["samep_pooled"] - 0.04) < 1e-9 and abs(r["frozenstyle_pooled"] - 0.04) < 1e-9
    assert all(abs(v - 0.04) < 1e-9 for v in r["samep_site"].values())
    assert r["samep_stat"]["p"] < 0.5 and r["scmR_span_pooled"] == 0.0


def test_early_stats_scmR_moving_separates_the_two_definitions():
    keys, P, S, g = _fake_early(0.5)
    S = S * (1 + 0.5 * g[:, None] * 0.5)        # scmR error also grows: same-p crossing moves right of the frozen style
    r = EX.early_stats(keys, P, S, g)
    assert r["samep_pooled"] > r["frozenstyle_pooled"] or np.isinf(r["samep_pooled"])
    assert r["scmR_span_pooled"] > 0


def test_early_shapes_do_not_wrap_and_stay_four_hours():
    for k, (a, b) in EX.EARLY.items():
        assert b - a == 4
    a, b = EX.EARLY["b"]
    assert b <= -4                              # variant b ends before the first PJM adjustment hour s-4
    assert EX.EARLY["a"][1] == -3               # variant a: last shaped hour is s-4 (one adjustment hour)


def test_sliced_runs_refuse_2017():
    with pytest.raises(SystemExit):
        EX.main(["--analysis", "h4_win1620", "--year", "2017", "--sites", "Fox"])


@pytest.mark.skipif(os.environ.get("EXPL_SLOW") != "1", reason="one-site rerun, set EXPL_SLOW=1")
def test_rerun_path_with_frozen_shape_matches_analytic():
    """Rerun path (inject target load, rerun run_rule, read observed morning) with the frozen 4h shape must reproduce the analytic
    pjmA at p and leave scmR unchanged (it ignores hours >= s-4), on one real site."""
    from run import adjust, data as D
    Y = D.build_year(2016)
    site, _ = D.make_site(Y, "Fox")
    s, e = site.win
    grid = [0.0, 0.05, 0.10]
    keys, P, S = EX.early_site(site, "4h", grid)
    from run import events as EV, baselines as BL
    r1 = EV.r1_days(site)
    rows = []
    for f, part, dpool in (("A", site.part_idx("A"), site.part_idx("B")), ("B", site.part_idx("B"), site.part_idx("A"))):
        rows += BL.run_rule(site, site.Ys, site.Ys, set(r1.tolist()), r1, part, dpool, scm=EX.SCM, do_scm=True)
    R = pd.DataFrame(rows)
    for i, p in enumerate(grid):
        b = adjust.adjusted(R, s, e, p, "4h")
        np.testing.assert_allclose(P[i], b["pjmA"], rtol=1e-9, atol=1e-9)
        np.testing.assert_allclose(S[i], b["scmR"], rtol=0, atol=0)


def test_signed_h4_plus_reproduces_frozen_and_mirror_is_consistent(h4_frozen_path):
    R1 = pd.read_pickle(RUN0 / "events_R1.pkl")      # self-written by run_core
    r = EX.signed_h4(R1, C.WINDOWS["primary"], +1)
    assert r["pooled"] == h4_frozen_path["pooled"] and r["median_site"] == h4_frozen_path["median_site"]
    assert r["p"] == h4_frozen_path["p"]
    assert r["site_pcross"] == h4_frozen_path["site_pcross"]
    n = EX.signed_h4(R1, C.WINDOWS["primary"], -1)
    # scmR invariant, m = 0 identical to the positive side
    assert n["curve_pooled"]["pjmA"][0] == r["curve_pooled"]["pjmA"][0]
    assert np.allclose(n["curve_pooled"]["scmR"], n["curve_pooled"]["scmR"][0])
    # a decrease lowers the pjmA baseline: pooled bias at m=0.2 below the m=0 bias
    assert n["bias_pooled"]["pjmA"][40] < n["bias_pooled"]["pjmA"][0]
    assert r["bias_pooled"]["pjmA"][40] > r["bias_pooled"]["pjmA"][0]


def test_x5_kwh_is_pcross_times_load(h4_frozen_path):
    R1 = pd.read_pickle(RUN0 / "events_R1.pkl")      # self-written by run_core
    x = EX.x5_kwh(R1, C.WINDOWS["primary"], h4_frozen_path)
    for st, v in x["kwh"].items():
        assert abs(v - h4_frozen_path["site_pcross"][st] * x["site_load"][st]) < 1e-9
    assert x["min_kwh"] <= x["median_kwh"] <= x["max_kwh"]
