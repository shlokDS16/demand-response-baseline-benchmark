"""Injection grids of PREREG s4. Order (T3 4.3): DST -> filters -> injection -> lookback/training construction -> baseline.
Filters (`complete`) are computed on the raw readings BEFORE injection and are never recomputed on injected values.
Every function returns a modified COPY; the zero-injection identity is tested (tests/test_inject.py)."""
import numpy as np

from . import config as C
from . import leakage as LK


def shape_hours(s, shape):
    a, b = C.SHAPES[shape]
    return list(range(s + a, s + b))


def inject(Ytrue, days, buildings, win, c=0.0, p=0.0, shape="4h", r=0.0):
    """On the given event/dispatch `days`, for the given buildings only: window x (1-c), shaping hours x (1+p),
    rebound hours [e, e+2) x (1+r). Touches no other day, hour or building (s9.13)."""
    s, e = win
    Y = Ytrue.copy()
    days = np.asarray(sorted(days), int)
    b = np.asarray(list(buildings), int)
    if len(days) == 0 or len(b) == 0:
        return Y
    for hrs_, f in [(list(range(s, e)), 1.0 - c), (shape_hours(s, shape), 1.0 + p), ([h for h in (e, e + 1) if h < 24], 1.0 + r)]:
        if f != 1.0:
            Y[np.ix_(days, hrs_, b)] *= f
    return Y


def assert_touched_only(Ytrue, Y, days, buildings, win, shape="4h"):
    """s9.13: injections touch only the declared hours of declared buildings on declared days."""
    s, e = win
    diff = ~np.isclose(Ytrue, Y, rtol=0, atol=0) & ~(np.isnan(Ytrue) & np.isnan(Y))
    allowed = np.zeros_like(diff)
    hrs_ = sorted(set(range(s, e)) | set(shape_hours(s, shape)) | {e, e + 1})
    hrs_ = [h for h in hrs_ if h < 24]
    allowed[np.ix_(np.asarray(sorted(days), int), hrs_, np.asarray(list(buildings), int))] = True
    LK._tick("a13i")
    assert not (diff & ~allowed).any(), "injection touched undeclared cells"


def select_donors(dpool, q, site_index):
    """Share q of the donors (seed 2017 + site index) also curtail and pre-shape (q = 1: whole-site participation)."""
    dpool = list(dpool)
    n = int(round(q * len(dpool)))
    if n == 0:
        return []
    rng = np.random.default_rng(C.INJ_SEED + site_index)
    return sorted(rng.choice(dpool, n, replace=False).tolist())


def dispatch(Ytrue, disp_days, part, win, c=C.C_PRIMARY):
    """Repeated dispatch (H5): participants curtail window by c on every dispatched day; donors stay uncurtailed."""
    return inject(Ytrue, disp_days, part, win, c=c)


def contaminated(Ytrue, days, part, donors_sel, win, c, p, shape="4h", r=0.0):
    """Participants (target fold) and the selected donors both act on the event days."""
    return inject(Ytrue, days, list(part) + list(donors_sel), win, c=c, p=p, shape=shape, r=r)
