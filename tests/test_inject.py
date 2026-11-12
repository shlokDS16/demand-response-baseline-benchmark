import numpy as np
import pytest

from helpers import toy_site
from run import baselines as BL
from run import inject as IJ


def test_zero_injection_identity_and_baselines():
    site = toy_site(nd=60, nb=8, fn=lambda k, j: 10.0 + k + j)
    d = 35
    Y0 = IJ.inject(site.Ys, [d], range(8), site.win, c=0.0, p=0.0, r=0.0)
    assert np.array_equal(Y0, site.Ys)
    r_a = BL.run_rule(site, site.Ys, site.Ys, {d}, [d], [0, 1, 2, 3], [4, 5, 6, 7], scm=(5, 1.0))
    r_b = BL.run_rule(site, Y0, site.Ys, {d}, [d], [0, 1, 2, 3], [4, 5, 6, 7], scm=(5, 1.0))
    assert len(r_a) == len(r_b) == 4
    n = 0
    for a, b in zip(r_a, r_b):
        for k in a:
            if isinstance(a[k], float):
                assert a[k] == b[k]
                n += 1
    assert n > 20


def test_injected_hours_exactly_declared():
    site = toy_site(nd=60, nb=4)
    days, part = [30, 31], [0, 1]
    Y = IJ.inject(site.Ys, days, part, site.win, c=0.1, p=0.05, shape="4h", r=0.1)
    IJ.assert_touched_only(site.Ys, Y, days, part, site.win, "4h")
    ch = ~np.isclose(Y, site.Ys)
    assert sorted(set(np.where(ch)[1].tolist())) == [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    assert sorted(set(np.where(ch)[2].tolist())) == part and sorted(set(np.where(ch)[0].tolist())) == days
    assert np.allclose(Y[30, 15, 0], site.Ys[30, 15, 0] * 0.9) and np.allclose(Y[30, 11, 0], site.Ys[30, 11, 0] * 1.05)
    assert np.allclose(Y[30, 18, 1], site.Ys[30, 18, 1] * 1.1)
    Y2 = Y.copy()
    Y2[0, 3, 3] += 1.0
    with pytest.raises(AssertionError):
        IJ.assert_touched_only(site.Ys, Y2, days, part, site.win, "4h")


def test_rebound_changes_no_baseline():
    site = toy_site(nd=60, nb=8, fn=lambda k, j: 10.0 + k + j)
    d = 35
    A, Bd = [0, 1, 2, 3], [4, 5, 6, 7]
    y0 = IJ.inject(site.Ys, [d], A, site.win, c=0.1)
    y1 = IJ.inject(site.Ys, [d], A, site.win, c=0.1, r=0.1)
    r0 = BL.run_rule(site, y0, site.Ys, {d}, [d], A, Bd, do_scm=False)
    r1 = BL.run_rule(site, y1, site.Ys, {d}, [d], A, Bd, do_scm=False)
    for a, b in zip(r0, r1):
        for k in ("pjm0", "caiso0", "ny0", "isone0", "dm0", "prev", "don_pjm0"):
            assert a.get(k) == b.get(k)


def test_donor_contamination_alters_only_designated_donors():
    site = toy_site(nd=60, nb=10, fn=lambda k, j: 10.0 + k + j)
    d = 35
    part, dpool = list(range(5)), list(range(5, 10))
    assert IJ.select_donors(dpool, 0.0, 3) == []
    sel = IJ.select_donors(dpool, 0.4, 3)
    assert len(sel) == 2 and set(sel) <= set(dpool)
    Y = IJ.contaminated(site.Ys, [d], part, sel, site.win, 0.1, 0.05)
    changed = set(np.where((~np.isclose(Y, site.Ys)).any(axis=(0, 1)))[0].tolist())
    assert changed == set(part) | set(sel)
    Yq0 = IJ.contaminated(site.Ys, [d], part, IJ.select_donors(dpool, 0.0, 3), site.win, 0.1, 0.05)
    assert np.array_equal(Yq0, IJ.inject(site.Ys, [d], part, site.win, c=0.1, p=0.05))
    assert set(IJ.select_donors(dpool, 1.0, 3)) == set(dpool)
