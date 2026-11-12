import pytest

from run import config as C
from run import freeze as FZ


def test_missing_manifest_refuses(tmp_path):
    with pytest.raises(SystemExit):
        FZ.check_manifest(manifest=tmp_path / "none.md5")


def test_manifest_match_and_mismatch(tmp_path):
    lines = ["%s  %s" % (FZ.md5_file(C.ROOT / rel), rel) for rel in FZ.required_paths()]
    m = tmp_path / "m.md5"
    m.write_text("\n".join(lines) + "\n")
    assert len(FZ.check_manifest(manifest=m)) == 32
    bad = lines.copy()
    bad[0] = "0" * 32 + bad[0][32:]
    m.write_text("\n".join(bad) + "\n")
    with pytest.raises(SystemExit):
        FZ.check_manifest(manifest=m)
    m.write_text("\n".join(lines[1:]) + "\n")      # an unlisted required file
    with pytest.raises(SystemExit):
        FZ.check_manifest(manifest=m)
