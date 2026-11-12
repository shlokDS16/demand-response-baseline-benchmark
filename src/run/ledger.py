"""tables/summary.csv writer (PREREG s10, Revision 2 columns). One row per key; every number in the paper comes from one key.
Dev mode: every key gets the `_v0` suffix and the file goes to results/run_v0/. Secondary keys never carry p_holm."""
import numpy as np
import pandas as pd

COLUMNS = ["key", "value", "ci_low", "ci_high", "p_raw", "p_holm", "n_sites", "n_buildings", "n_events", "source_file",
           "status", "family_id", "hypothesis_id", "estimand_version", "data_year", "freeze_hash", "support_rule"]
SUPPORT_RULE = "S10"   # >= 10 building-events per site per method pair (both methods present), else the site is dropped and reported
ESTIMAND_VERSION = "PREREG-R2"


class Ledger:
    def __init__(self, mode, year, freeze_hash="dev-unfrozen", source_default=""):
        self.mode, self.year, self.fh = mode, year, freeze_hash
        self.rows = {}
        self.src = source_default

    def add(self, key, value, ci_low=None, ci_high=None, p_raw=None, p_holm=None, n_sites=None, n_buildings=None,
            n_events=None, source_file=None, status="secondary", family_id="none", hypothesis_id="none",
            support_rule="none"):
        assert status in ("confirmatory", "secondary", "exploratory"), status
        if p_holm is not None and not (isinstance(p_holm, float) and np.isnan(p_holm)):
            assert family_id == "C5", "p_holm only on the confirmatory family (key %s)" % key
        if support_rule == "none" and str(hypothesis_id).startswith("H"):
            support_rule = SUPPORT_RULE
        k = key + ("_v0" if self.mode == "dev" else "")
        assert k not in self.rows, "duplicate ledger key " + k
        if isinstance(value, (np.floating, float)):
            value = float(value)
        self.rows[k] = dict(key=k, value=value, ci_low=ci_low, ci_high=ci_high, p_raw=p_raw, p_holm=p_holm,
                            n_sites=n_sites, n_buildings=n_buildings, n_events=n_events,
                            source_file=source_file or self.src, status=status, family_id=family_id,
                            hypothesis_id=hypothesis_id, estimand_version=ESTIMAND_VERSION, data_year=self.year,
                            freeze_hash=self.fh, support_rule=support_rule)

    def has(self, key):
        return key + ("_v0" if self.mode == "dev" else "") in self.rows

    def to_frame(self):
        return pd.DataFrame(list(self.rows.values()), columns=COLUMNS)

    def write(self, path):
        df = self.to_frame()
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        return df
