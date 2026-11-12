"""Leakage assertions of PREREG s9 as real checks (raise AssertionError; failures stop the run)."""
import numpy as np

COUNTS = {}


def _tick(name):
    COUNTS[name] = COUNTS.get(name, 0) + 1


def a1_lookback_before(d, days_used):
    """s9.1: max(training or lookback day) < d."""
    _tick("a1")
    if len(days_used):
        assert max(days_used) < d, "leak: lookback day >= event day"


def a2_no_event_days(evset, days_used, fallback_ok=False, day_before=False):
    """s9.2: no event day of the current rule world (or the day before, NYISO) in a later lookback / pre-period /
    training set, except the rule text's own declared fallback."""
    _tick("a2")
    if fallback_ok:
        return
    bad = [k for k in days_used if k in evset or (day_before and (k + 1) in evset)]
    assert not bad, "leak: event day in lookback %s" % bad[:3]


def a3_hours(hours_used, s, info):
    """s9.3: target event-day hours only within the information set. I-hist: none; I-morn: <= s-2; I-donor: < s-4.
    Window hours are never used."""
    _tick("a3")
    if len(hours_used) == 0:
        return
    m = max(hours_used)
    if info == "I-hist":
        raise AssertionError("I-hist method used target event-day hours")
    if info == "I-morn":
        assert m <= s - 2, "leak: I-morn hour %d > s-2" % m
    elif info == "I-donor":
        assert m < s - 4, "leak: I-donor target hour %d >= s-4" % m
    else:
        raise AssertionError("unknown info set " + str(info))


def a3_window_unused(hours_used, win):
    _tick("a3w")
    assert not (set(hours_used) & set(win)), "leak: window hour used by a baseline"


def a5_fit_rows_before(train_days, first_pred_day):
    """s9.5 / T3 F14: normalisers, encoders, early-stopping validation rows and feature selection use rows of the
    training period only (strictly before the prediction month)."""
    _tick("a5")
    assert len(train_days) == 0 or max(train_days) < first_pred_day, "leak: fit row not before prediction period"


def a5_val_inside_train(train_idx, val_idx):
    """F14: early-stopping validation rows are a subset of the training period (chronologically last part)."""
    _tick("a5v")
    assert set(val_idx) <= set(train_idx), "leak: validation rows outside the training set"


def a5_feature_selection_train_only(selection_days, first_pred_day):
    _tick("a5f")
    assert len(selection_days) == 0 or max(selection_days) < first_pred_day, "leak: feature selection used future rows"


def a6_donor_pre(days_pre, d):
    """s9.6: donor weights fitted on rows before d (pre-period); event-day rows only hours < s-4 (checked by a3)."""
    _tick("a6")
    assert len(days_pre) == 0 or max(days_pre) < d


def a7_folds(part, dpool):
    """s9.7: folds disjoint; no target in its own donor pool."""
    _tick("a7")
    assert not (set(part) & set(dpool)), "leak: fold overlap"


def a8_event_selection_no_load(source):
    _tick("a8")
    assert source in ("frozen_file", "weather_only", "r2iso_forecast", "legacy_dev", "r2loo_exploratory"), source


def a13_rebound_zero(before, after):
    """s9.13: rebound must not change any included baseline."""
    _tick("a13")
    assert np.array_equal(np.nan_to_num(before, nan=-9e99), np.nan_to_num(after, nan=-9e99)), "rebound changed a baseline"


def a14_common_support(mask_x, mask_y):
    _tick("a14")
    assert (mask_x == mask_y).all() if hasattr(mask_x, "all") else mask_x == mask_y


def a11_dst_before_windows(applied):
    _tick("a11")
    assert applied, "DST table not applied before window construction"
