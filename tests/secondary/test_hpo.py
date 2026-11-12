import numpy as np
import pytest

from secondary import hpo


def _tables(year, n=400):
    d0 = np.datetime64("%d-01-01" % year, "D").astype(np.int64)
    dates = d0 + np.arange(366)
    kk = np.repeat(np.arange(0, 120), 4).astype(np.int32)          # rows on days 0..119 (Jan-Apr)
    return dict(dates=dates, year=np.int64(year)), kk


def test_inner_split_chronological():
    kd = np.repeat(np.arange(50), 3)
    tr, va = hpo.inner_split(kd)
    assert kd[tr].max() < kd[va].min() and va.sum() > 0


def test_tune_rejects_2017_dates():
    T, kk = _tables(2017)
    tr, va = hpo.inner_split(kk)
    with pytest.raises(AssertionError):
        hpo.assert_leak_free(T, kk, 130, tr, va, np.array([140, 141]), tune=True)


def test_tune_accepts_2016_dates():
    T, kk = _tables(2016)
    tr, va = hpo.inner_split(kk)
    hpo.assert_leak_free(T, kk, 130, tr, va, np.array([140, 141]), tune=True)


def test_fit_row_not_before_month_rejected():
    T, kk = _tables(2016)
    tr, va = hpo.inner_split(kk)
    with pytest.raises(AssertionError):
        hpo.assert_leak_free(T, kk, 100, tr, va, np.array([140]), tune=True)       # training rows reach day 119 > first = 100


def test_month_first():
    T, _ = _tables(2016)
    first, mo = hpo.month_first(T, 5)
    assert first == 121 and mo[first - 1] == 4          # 2016 leap year: Jan 31 + Feb 29 + Mar 31 + Apr 30 = 121


def test_method_ids_do_not_collide_with_frozen_rows():
    assert hpo.method_id("lgbM") == "lgbM_hpo" and hpo.method_id("lgbD") == "lgbD_hpo"
    assert hpo.method_id("mlpM") == "mlpM" and hpo.method_id("mlpD") == "mlpD"
