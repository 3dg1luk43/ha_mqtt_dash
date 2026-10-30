#!/usr/bin/env python3
"""Hash of the editor sources the bundle in custom_components/.../editor is built from.

Used by build_editor.sh (writes it into build-manifest.json), release_check.sh and
the tests (fail when the committed bundle is older than the source).
"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDITOR = ROOT / "editor"
INPUTS = ["src", "public", "index.html", "package.json", "package-lock.json", "vite.config.js"]


def source_hash() -> str:
    h = hashlib.sha256()
    for name in INPUTS:
        p = EDITOR / name
        files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else ([p] if p.is_file() else [])
        for f in files:
            h.update(f.relative_to(EDITOR).as_posix().encode())
            h.update(b"\0")
            # Normalise line endings so a checkout on another OS hashes the same
            h.update(f.read_bytes().replace(b"\r\n", b"\n"))
            h.update(b"\0")
    return h.hexdigest()


if __name__ == "__main__":
    print(source_hash())
    sys.exit(0)
