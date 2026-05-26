from __future__ import annotations

import os
import sys
import sysconfig


class Aria2NextNotFound(FileNotFoundError):
    pass


def find_aria2_next_bin() -> str:
    """Return the aria2-next binary path."""

    exe = "aria2-next" + (sysconfig.get_config_var("EXE") or "")

    targets = [
        # The scripts directory for the current Python.
        sysconfig.get_path("scripts"),
        # The scripts directory for the base prefix.
        sysconfig.get_path("scripts", vars={"base": sys.base_prefix}),
        # Above the package root, e.g. from `pip install --prefix`.
        (
            # On Windows, with module path `<prefix>/Lib/site-packages/aria2_next`.
            _join(_matching_parents(_module_path(), "Lib/site-packages/aria2_next"), "Scripts")
            if sys.platform == "win32"
            # On Unix, with module path `<prefix>/lib/python3.13/site-packages/aria2_next`.
            else _join(
                _matching_parents(_module_path(), "lib/python*/site-packages/aria2_next"),
                "bin",
            )
        ),
        # Adjacent to the package root, e.g. from `pip install --target`.
        _join(_matching_parents(_module_path(), "aria2_next"), "bin"),
        # The user scheme scripts directory, e.g. `~/.local/bin`.
        sysconfig.get_path("scripts", scheme=_user_scheme()),
    ]

    seen = []
    for target in targets:
        if not target:
            continue
        if target in seen:
            continue
        seen.append(target)
        path = os.path.join(target, exe)
        if os.path.isfile(path) and not _is_python_wrapper(path):
            _ensure_executable(path)
            return path

    locations = "\n".join(f" - {target}" for target in seen)
    raise Aria2NextNotFound(
        f"Could not find the aria2-next binary in any of the following locations:\n{locations}\n"
    )


def _module_path() -> str | None:
    return os.path.dirname(__file__)


def _matching_parents(path: str | None, match: str) -> str | None:
    """
    Return the parent directory of `path` after trimming a `match` from the end.
    The match is expected to contain `/` as a path separator, while the `path`
    is expected to use the platform's path separator. Path components are
    compared case-insensitively and `*` can be used as a wildcard.
    """
    from fnmatch import fnmatch

    if not path:
        return None
    parts = path.split(os.sep)
    match_parts = match.split("/")
    if len(parts) < len(match_parts):
        return None

    if not all(
        fnmatch(part, match_part)
        for part, match_part in zip(reversed(parts), reversed(match_parts))
    ):
        return None

    return os.sep.join(parts[: -len(match_parts)])


def _join(path: str | None, *parts: str) -> str | None:
    if not path:
        return None
    return os.path.join(path, *parts)


def _is_python_wrapper(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            prefix = f.read(2048)
    except OSError:
        return False

    if not prefix.startswith(b"#!"):
        return False
    try:
        text = prefix.decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        return False
    return "aria2_next" in text


def _ensure_executable(path: str) -> None:
    if os.name == "nt" or os.access(path, os.X_OK):
        return
    try:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | 0o111)
    except OSError:
        pass


def _user_scheme() -> str:
    if sys.version_info >= (3, 10):
        user_scheme = sysconfig.get_preferred_scheme("user")
    elif os.name == "nt":
        user_scheme = "nt_user"
    elif sys.platform == "darwin" and sys._framework:
        user_scheme = "osx_framework_user"
    else:
        user_scheme = "posix_user"
    return user_scheme
