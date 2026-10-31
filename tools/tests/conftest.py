"""Home Assistant is stubbed for this suite.

Every ``homeassistant.*`` (and ``voluptuous`` / ``aiohttp``) import resolves to
a module whose attributes are MagicMocks, so the integration's pure logic
(config building, attribute encoding, battery care, command routing) runs
without an HA install. A MagicMock accepts any service call, so these tests
cannot prove that Home Assistant would accept what we send: config flows,
entity wiring and real service schemas need a real HA (see CLAUDE.md).
"""
import importlib.abc
import importlib.util
import importlib.machinery
import pathlib
import sys
import types
from unittest.mock import MagicMock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class _Stub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, value)
        return value


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    # aiohttp is real when installed (tools/requirements-test.txt; the video
    # relay test serves HTTP), stubbed otherwise
    ROOTS = ("homeassistant", "voluptuous") + (() if importlib.util.find_spec("aiohttp") else ("aiohttp",))

    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in self.ROOTS:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        mod = _Stub(spec.name)
        mod.__path__ = []
        return mod

    def exec_module(self, module):
        pass


sys.meta_path.insert(0, _StubFinder())

import homeassistant.const as _const  # noqa: E402
import homeassistant.core as _core  # noqa: E402

_const.STATE_UNKNOWN, _const.STATE_UNAVAILABLE = "unknown", "unavailable"
_core.callback = lambda f: f
