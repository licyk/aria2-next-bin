from __future__ import annotations

import stat
import zipfile

import pytest

from aria2_next import _find_aria2_next
from scripts import build_wheel


def test_normalize_release_version() -> None:
    assert build_wheel.normalize_release_version("v2.2.6") == "2.2.6"
    assert build_wheel.normalize_release_version("2.2.6") == "2.2.6"
    assert build_wheel.normalize_release_version("v2.2.6-beta.1") == "2.2.6b1"


def test_release_asset_version_keeps_github_suffix() -> None:
    assert build_wheel.release_asset_version("v2.2.6-beta.1") == "2.2.6-beta.1"


def test_target_mapping() -> None:
    linux = build_wheel.TARGETS["linux-x86_64"]
    assert build_wheel.asset_name("2.2.6", linux) == "aria2-next-2.2.6-linux-x86_64"
    assert linux.platform_tag == "manylinux_2_28_x86_64"

    windows = build_wheel.TARGETS["windows-arm64"]
    assert build_wheel.asset_name("2.2.6", windows) == "aria2-next-2.2.6-windows-arm64.exe"
    assert windows.platform_tag == "win_arm64"
    assert windows.wheel_binary == "aria2-next.exe"


def test_parse_checksums() -> None:
    checksums = build_wheel.parse_checksums(
        """
        c156ffa8b27ddf36f3712fd972403dc833e0e77fe66e640fa522dbd278ca0a3c  aria2-next-2.2.6-linux-aarch64
        93d981a679ab0168b195bbd64e56cb5dfdec5c7d500201e2b273bfa13ebbc5c1 *aria2-next-2.2.6-linux-x86_64
        """
    )

    assert checksums["aria2-next-2.2.6-linux-aarch64"].startswith("c156")
    assert checksums["aria2-next-2.2.6-linux-x86_64"].startswith("93d9")


def test_find_asset_reports_missing_asset() -> None:
    release = {"tag_name": "v2.2.6", "assets": [{"name": "other"}]}
    with pytest.raises(SystemExit, match="does not contain required asset"):
        build_wheel.find_asset(release, "aria2-next-2.2.6-linux-x86_64")


def test_write_wheel_archive(tmp_path) -> None:
    binary = tmp_path / "aria2-next-2.2.6-linux-x86_64"
    binary.write_bytes(b"fake-binary")
    binary.chmod(0o755)
    license_file = tmp_path / "COPYING"
    license_file.write_text("license text\n", encoding="utf-8")

    wheel_name = build_wheel.write_wheel_archive(
        tmp_path / "dist",
        build_wheel.TARGETS["linux-x86_64"],
        "2.2.6",
        binary,
        license_file,
    )

    wheel_path = tmp_path / "dist" / wheel_name
    assert wheel_name == "aria2_next_bin-2.2.6-py3-none-manylinux_2_28_x86_64.whl"
    assert wheel_path.exists()

    with zipfile.ZipFile(wheel_path) as zf:
        names = set(zf.namelist())
        assert "aria2_next/__init__.py" in names
        assert "aria2_next/__main__.py" in names
        assert "aria2_next/_find_aria2_next.py" in names
        assert "aria2_next_bin-2.2.6.data/scripts/aria2-next" in names
        assert "aria2_next/licenses/aria2-next-COPYING" in names
        assert "aria2_next_bin-2.2.6.dist-info/METADATA" in names
        assert "aria2_next_bin-2.2.6.dist-info/RECORD" in names

        metadata = zf.read("aria2_next_bin-2.2.6.dist-info/METADATA").decode()
        assert "Name: aria2-next-bin" in metadata
        assert "Version: 2.2.6" in metadata

        wheel = zf.read("aria2_next_bin-2.2.6.dist-info/WHEEL").decode()
        assert "Tag: py3-none-manylinux_2_28_x86_64" in wheel

        assert "aria2_next_bin-2.2.6.dist-info/entry_points.txt" not in names

        top_level = zf.read("aria2_next_bin-2.2.6.dist-info/top_level.txt").decode()
        assert top_level == "aria2_next\n"

        mode = zf.getinfo("aria2_next_bin-2.2.6.data/scripts/aria2-next").external_attr >> 16
        assert stat.S_ISREG(mode)
        assert stat.S_IMODE(mode) == 0o755


def test_matching_parents_handles_prefix_install_path(monkeypatch) -> None:
    monkeypatch.setattr(_find_aria2_next.os, "sep", "/")
    parent = _find_aria2_next._matching_parents(
        "/prefix/lib/python3.13/site-packages/aria2_next",
        "lib/python*/site-packages/aria2_next",
    )

    assert parent == "/prefix"


def test_matching_parents_handles_target_install_path(monkeypatch) -> None:
    monkeypatch.setattr(_find_aria2_next.os, "sep", "/")
    parent = _find_aria2_next._matching_parents("/target/aria2_next", "aria2_next")

    assert parent == "/target"


def test_find_aria2_next_bin_uses_scripts_binary(tmp_path, monkeypatch) -> None:
    site_packages = tmp_path / "site-packages"
    package_dir = site_packages / "aria2_next"
    scripts_dir = tmp_path / "bin"
    package_dir.mkdir(parents=True)
    scripts_dir.mkdir()

    scripts_binary = scripts_dir / "aria2-next"
    scripts_binary.write_bytes(b"binary")
    scripts_binary.chmod(0o644)

    monkeypatch.setattr(_find_aria2_next, "_module_path", lambda: str(package_dir))
    monkeypatch.setattr(_find_aria2_next.sysconfig, "get_config_var", lambda name: "")
    monkeypatch.setattr(_find_aria2_next.sysconfig, "get_path", lambda *args, **kwargs: str(scripts_dir))

    assert _find_aria2_next.find_aria2_next_bin() == str(scripts_binary)
    assert scripts_binary.stat().st_mode & 0o111
