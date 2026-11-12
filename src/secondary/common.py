"""Shared helpers: paths, secondary ledger, per-part row files, collection into tables/summary_secondary.csv."""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from run import config as C
from run import freeze
from run import ledger as LD

SEC_LEDGER = C.ROOT / "tables" / "summary_secondary.csv"
FAMILY = "secondary"


def mode_of(year):
    return "dev" if year == 2016 else "final"


def out_dir(year):
    d = C.ROOT / "results" / "secondary" / str(year)
    d.mkdir(parents=True, exist_ok=True)
    return d


def frames_dir(year):
    """Frozen-pipeline outputs, READ ONLY here (self-written intermediates of src/run)."""
    return C.ROOT / "results" / ("run_v0" if year == 2016 else "run")


def freeze_hash(year):
    """2017: the manifest must match (abort otherwise); 2016: dev."""
    if year == 2017:
        return freeze.check_manifest()
    return "dev-unfrozen"


def load_R1(year):
    return pd.read_pickle(frames_dir(year) / "events_R1.pkl")      # self-written by run_core, trusted


class SecLedger:
    """Thin wrapper over run.ledger.Ledger: family_id fixed to 'secondary', p_holm never set."""

    def __init__(self, year, fh):
        self.year = year
        self.L = LD.Ledger(mode_of(year), year, freeze_hash=fh, source_default="src/secondary")

    def add(self, key, value, status="secondary", **kw):
        kw.pop("p_holm", None)
        kw.setdefault("hypothesis_id", "none")
        self.L.add(key, value, status=status, family_id=FAMILY, **kw)

    def has(self, key):
        return self.L.has(key)

    def save(self, year, part):
        suffix = "_v0" if year == 2016 else ""
        p = out_dir(year) / ("%s%s.rows.csv" % (part, suffix))
        self.L.to_frame().to_csv(p, index=False)
        return p


def collect():
    """Concatenate every results/secondary/*/*.rows.csv into tables/summary_secondary.csv (duplicate keys: last file wins)."""
    fr = []
    for p in sorted((C.ROOT / "results" / "secondary").glob("*/*.rows.csv")):
        d = pd.read_csv(p)
        d["_src"] = str(p.relative_to(C.ROOT)).replace("\\", "/")
        fr.append(d)
    if not fr:
        return None
    df = pd.concat(fr, ignore_index=True).drop_duplicates("key", keep="last")
    assert (df.family_id == FAMILY).all() and df.p_holm.isna().all(), "secondary rows must not carry p_holm"
    assert df.status.isin(["secondary", "exploratory", "derived", "descriptive"]).all()
    df = df.drop(columns="_src")[LD.COLUMNS]
    SEC_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SEC_LEDGER, index=False)
    return df


def peak_gb():
    try:
        import psutil
        return psutil.Process().memory_info().peak_wset / 1e9
    except Exception:
        return float("nan")


class Timer:
    def __init__(self):
        self.t0 = time.time()

    def stop(self):
        return dict(time_s=round(time.time() - self.t0, 1), peak_gb=round(peak_gb(), 3))


def log_timing(year, part, tm, note=""):
    p = out_dir(year) / "timing.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    d[part] = dict(tm, note=note)
    p.write_text(json.dumps(d, indent=1))
