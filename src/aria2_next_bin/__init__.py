from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("aria2-next-bin")
except PackageNotFoundError:  # pragma: no cover - only used from a source checkout
    __version__ = "0+unknown"
