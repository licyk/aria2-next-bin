from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from ._find_aria2_next import Aria2NextNotFound, find_aria2_next_bin


__all__ = ["Aria2NextNotFound", "find_aria2_next_bin"]


try:
    __version__ = version("aria2-next-bin")
except PackageNotFoundError:  # pragma: no cover - only used from a source checkout
    __version__ = "0+unknown"
