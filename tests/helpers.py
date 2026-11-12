import numpy as np
import pandas as pd

from run import data as D


def toy_site(nd=60, nb=1, win=(14, 18), fn=None):
    """All days are weekdays, all complete; building j has hourly load fn(day, j) (default 10 + day)."""
    fn = fn or (lambda k, j: 10.0 + k)
    Ys = np.zeros((nd, 24, nb))
    for k in range(nd):
        for j in range(nb):
            Ys[k, :, j] = fn(k, j)
    days = pd.date_range("2016-05-01", periods=nd, freq="D")
    return D.Site("Toy", 0, 2016, days, ["m%d" % j for j in range(nb)], ["U"] * nb, Ys, np.ones((nd, nb), bool),
                  np.ones(nd, bool), np.ones(nd, bool), np.full(nd, 25.0), np.array(["A"] * nb), win, set())
