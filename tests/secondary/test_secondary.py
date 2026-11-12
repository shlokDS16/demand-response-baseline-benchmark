import numpy as np
import pandas as pd

from secondary import h6, tree


def test_per_zero_when_exact():
    assert h6.per(np.array([5.0, 5.0]), np.array([4.0, 6.0])) == 0.0
    assert abs(h6.per(11.0, 10.0) - 0.1 / 0.10) < 1e-12      # error 1 on load 10, c = 0.10 -> PER 1


def test_disjoint_blocks_partition():
    rng = np.random.default_rng(7)
    blocks = h6.disjoint_blocks(47, 20, rng)
    assert len(blocks) == 2 and all(len(b) == 20 for b in blocks)
    flat = np.concatenate(blocks)
    assert len(set(flat.tolist())) == 40                       # disjoint
    assert flat.max() < 47 and flat.min() >= 0


def test_disjoint_blocks_seeded_reproducible():
    a = h6.disjoint_blocks(60, 20, np.random.default_rng([7, 1, 2, 0]))
    b = h6.disjoint_blocks(60, 20, np.random.default_rng([7, 1, 2, 0]))
    assert all((x == y).all() for x, y in zip(a, b))


def test_matched_random_within_tolerance():
    rng = np.random.default_rng(7)
    ref = rng.uniform(1, 10, 200)
    target = 100.0
    for _ in range(20):
        ix = h6.matched_random(ref, target, rng)
        assert ix is not None
        assert 90.0 <= ref[ix].sum() <= 110.0
        assert len(set(ix.tolist())) == len(ix)                # no building twice


def test_matched_random_impossible_returns_none():
    rng = np.random.default_rng(1)
    assert h6.matched_random(np.ones(5), 1000.0, rng) is None


def _toy(n=300, seed=0):
    rng = np.random.default_rng(seed)
    f = pd.DataFrame({"slope_rel": rng.normal(0, 0.1, n), "cv": rng.uniform(0, 1, n), "log_size": rng.normal(8, 1, n),
                      "corr_site": rng.uniform(0, 1, n)})
    y = np.where(f.slope_rel < -0.05, "scmR", np.where(f.corr_site > 0.5, "cgA", "pjmA"))
    return f, pd.Series(y)


def test_tree_depth_and_leaf_size():
    f, y = _toy()
    t = tree.fit_tree(f, y)
    assert t.get_depth() <= 2
    leaves = t.apply(f.values)
    counts = pd.Series(leaves).value_counts()
    assert counts.min() >= 20                                   # minimum leaf of 20 buildings
    assert (t.predict(f.values) == y.values).mean() > 0.95      # recovers the planted rule


def test_tree_ties_go_to_pjmA():
    rel = pd.DataFrame({"pjmA": [0.1, 0.2], "cgA": [0.1, 0.1], "scmR": [0.1, 0.3]})
    assert tree.label_from_relmae(rel).tolist() == ["pjmA", "cgA"]
