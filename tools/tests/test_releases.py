"""Every iPad package in releases/ must say inside what its filename says.

A stale Theos staging dir once produced 0.6.0-named packages whose control
still said 0.5.1, so dpkg on the iPad would have seen the old version.
"""
import io
import tarfile

import pytest

from conftest import ROOT

DEBS = sorted((ROOT / "releases").glob("*.deb"))


def _control(path):
    data = path.read_bytes()
    assert data[:8] == b"!<arch>\n", f"{path.name} is not a .deb (ar archive)"
    off = 8
    while off < len(data):
        name = data[off:off + 16].decode().strip().rstrip("/")
        size = int(data[off + 48:off + 58].decode().strip())
        body = data[off + 60:off + 60 + size]
        if name.startswith("control.tar"):
            with tarfile.open(fileobj=io.BytesIO(body)) as tar:
                member = next(m for m in tar.getmembers() if m.name.lstrip("./") == "control")
                text = tar.extractfile(member).read().decode()
            return dict(line.split(": ", 1) for line in text.splitlines() if ": " in line and not line.startswith(" "))
        off += 60 + size + (size % 2)
    raise AssertionError(f"{path.name}: no control.tar member")


@pytest.mark.parametrize("deb", DEBS, ids=[d.name for d in DEBS])
def test_package_metadata_matches_filename(deb):
    c = _control(deb)
    assert deb.name == f"{c['Package']}_{c['Version']}_{c['Architecture']}.deb"
