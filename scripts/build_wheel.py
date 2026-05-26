#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only used on Python < 3.11
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "src"
PROJECT_FILE = ROOT / "pyproject.toml"
DEFAULT_REPOSITORY = "AnInsomniacy/aria2-next"
DEFAULT_RELEASE = "latest"
USER_AGENT = "aria2-next-bin-builder"


@dataclass(frozen=True)
class Target:
    key: str
    asset_suffix: str
    platform_tag: str
    wheel_binary: str
    executable: bool = True


TARGETS: dict[str, Target] = {
    "linux-x86_64": Target(
        key="linux-x86_64",
        asset_suffix="linux-x86_64",
        platform_tag="manylinux_2_28_x86_64",
        wheel_binary="aria2-next",
    ),
    "linux-aarch64": Target(
        key="linux-aarch64",
        asset_suffix="linux-aarch64",
        platform_tag="manylinux_2_28_aarch64",
        wheel_binary="aria2-next",
    ),
    "macos-x86_64": Target(
        key="macos-x86_64",
        asset_suffix="macos-x86_64",
        platform_tag="macosx_10_13_x86_64",
        wheel_binary="aria2-next",
    ),
    "macos-arm64": Target(
        key="macos-arm64",
        asset_suffix="macos-arm64",
        platform_tag="macosx_11_0_arm64",
        wheel_binary="aria2-next",
    ),
    "windows-x86_64": Target(
        key="windows-x86_64",
        asset_suffix="windows-x86_64.exe",
        platform_tag="win_amd64",
        wheel_binary="aria2-next.exe",
    ),
    "windows-arm64": Target(
        key="windows-arm64",
        asset_suffix="windows-arm64.exe",
        platform_tag="win_arm64",
        wheel_binary="aria2-next.exe",
    ),
}


def normalize_dist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def read_project() -> dict[str, Any]:
    with PROJECT_FILE.open("rb") as f:
        return tomllib.load(f)["project"]


def config_value(config_settings: dict[str, Any] | None, key: str) -> str | None:
    if not config_settings:
        return None
    candidates = (key, f"--{key}", f"aria2-next-{key}")
    for candidate in candidates:
        if candidate not in config_settings:
            continue
        value = config_settings[candidate]
        if isinstance(value, list):
            if not value:
                return None
            value = value[-1]
        if value is not None:
            return str(value)
    return None


def release_selector(config_settings: dict[str, Any] | None = None) -> str:
    return (
        config_value(config_settings, "release")
        or os.environ.get("ARIA2_NEXT_RELEASE")
        or DEFAULT_RELEASE
    )


def target_selector(config_settings: dict[str, Any] | None = None) -> str:
    return (
        config_value(config_settings, "target")
        or os.environ.get("ARIA2_NEXT_TARGET")
        or "current"
    )


def repository_name() -> str:
    return os.environ.get("ARIA2_NEXT_REPOSITORY", DEFAULT_REPOSITORY)


def github_api_base() -> str:
    return f"https://api.github.com/repos/{repository_name()}"


def github_raw_base() -> str:
    return f"https://raw.githubusercontent.com/{repository_name()}"


def normalize_release_version(tag_name: str) -> str:
    version_text = tag_name[1:] if tag_name.startswith(("v", "V")) else tag_name
    try:
        return str(Version(version_text))
    except InvalidVersion as exc:
        raise ValueError(f"release tag is not a valid Python package version: {tag_name}") from exc


def release_asset_version(tag_name: str) -> str:
    return tag_name[1:] if tag_name.startswith(("v", "V")) else tag_name


def current_target_key() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x64"}:
        machine = "x86_64"
    elif machine in {"arm64", "aarch64"}:
        machine = "aarch64"

    if sys.platform.startswith("linux"):
        if machine == "x86_64":
            return "linux-x86_64"
        if machine == "aarch64":
            return "linux-aarch64"
    elif sys.platform == "darwin":
        if machine == "x86_64":
            return "macos-x86_64"
        if machine == "aarch64":
            return "macos-arm64"
    elif sys.platform in {"win32", "cygwin"}:
        if machine == "x86_64":
            return "windows-x86_64"
        if machine == "aarch64":
            return "windows-arm64"

    raise SystemExit(f"unsupported current platform: sys.platform={sys.platform}, machine={platform.machine()}")


def selected_target(selector: str) -> Target:
    if selector == "current":
        selector = current_target_key()
    try:
        return TARGETS[selector]
    except KeyError as exc:
        supported = ", ".join(["current", "all", *sorted(TARGETS)])
        raise SystemExit(f"unsupported target {selector!r}; supported targets: {supported}") from exc


def request_url(url: str, *, accept: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return response.read()


def fetch_json(url: str) -> dict[str, Any]:
    data = request_url(url, accept="application/vnd.github+json")
    return json.loads(data.decode("utf-8"))


def fetch_release(selector: str) -> dict[str, Any]:
    base = github_api_base()
    if selector == "latest":
        return fetch_json(f"{base}/releases/latest")

    tag_url = f"{base}/releases/tags/{selector}"
    try:
        return fetch_json(tag_url)
    except HTTPError as exc:
        if exc.code != 404 or selector.startswith(("v", "V")):
            raise

    return fetch_json(f"{base}/releases/tags/v{selector}")


def asset_name(version: str, target: Target) -> str:
    return f"aria2-next-{version}-{target.asset_suffix}"


def checksum_asset_name(version: str) -> str:
    return f"aria2-next-{version}-checksums.sha256"


def find_asset(release: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in release.get("assets", []):
        if asset.get("name") == name:
            return asset
    tag = release.get("tag_name", "<unknown>")
    raise SystemExit(f"release {tag} does not contain required asset: {name}")


def sha256_hex(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str) -> None:
    actual = sha256_hex(path)
    if actual.lower() != expected.lower():
        raise SystemExit(f"sha256 mismatch for {path.name}: expected {expected}, got {actual}")


def parse_asset_digest(asset: dict[str, Any]) -> str | None:
    digest = asset.get("digest")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest.split(":", 1)[1]
    return None


def parse_checksums(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        checksum, filename = parts[0], parts[-1].lstrip("*")
        if re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
            checksums[filename] = checksum
    return checksums


def checksum_from_release(release: dict[str, Any], version: str, expected_asset_name: str) -> str:
    checksums_asset = find_asset(release, checksum_asset_name(version))
    content = request_url(checksums_asset["browser_download_url"]).decode("utf-8")
    checksums = parse_checksums(content)
    try:
        return checksums[expected_asset_name]
    except KeyError as exc:
        raise SystemExit(f"checksums file does not contain {expected_asset_name}") from exc


def expected_checksum(release: dict[str, Any], version: str, asset: dict[str, Any]) -> str:
    digest = parse_asset_digest(asset)
    if digest:
        return digest
    return checksum_from_release(release, version, asset["name"])


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response, temp.open("wb") as f:
            shutil.copyfileobj(response, f)
        temp.replace(destination)
    finally:
        if temp.exists():
            temp.unlink()


def ensure_release_binary(release: dict[str, Any], target: Target) -> Path:
    tag_name = release["tag_name"]
    asset_version_text = release_asset_version(tag_name)
    wanted_name = asset_name(asset_version_text, target)
    asset = find_asset(release, wanted_name)
    checksum = expected_checksum(release, asset_version_text, asset)
    cache_dir = ROOT / "build" / "downloads" / tag_name / target.key
    binary = cache_dir / wanted_name

    if binary.exists():
        verify_sha256(binary, checksum)
    else:
        print(f"downloading {wanted_name}", flush=True)
        download_file(asset["browser_download_url"], binary)
        verify_sha256(binary, checksum)

    if not target.wheel_binary.endswith(".exe"):
        binary.chmod(binary.stat().st_mode | 0o755)
    return binary


def ensure_release_license(release: dict[str, Any]) -> Path | None:
    tag_name = release["tag_name"]
    license_path = ROOT / "build" / "licenses" / tag_name / "aria2-next-COPYING"
    if license_path.exists():
        return license_path

    url = f"{github_raw_base()}/{tag_name}/COPYING"
    try:
        print("downloading upstream COPYING", flush=True)
        download_file(url, license_path)
        return license_path
    except Exception as exc:
        print(f"warning: could not download upstream COPYING: {exc}", file=sys.stderr)
        if license_path.exists():
            license_path.unlink()
        return None


def verify_binary_run(binary: Path, target: Target) -> None:
    if os.environ.get("ARIA2_NEXT_SKIP_RUN_VERIFY") == "1":
        return
    try:
        current = current_target_key()
    except SystemExit:
        return
    if target.key != current:
        return
    if target.wheel_binary.endswith(".exe") and os.name != "nt":
        return
    try:
        proc = subprocess.run(
            [str(binary), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise SystemExit(f"could not run {binary.name} --version: {exc}") from exc
    version_markers = ("aria2 version", "Aria2 Next version")
    if proc.returncode != 0 or not any(marker in proc.stdout for marker in version_markers):
        output = proc.stdout.strip()
        raise SystemExit(f"{binary.name} --version failed: {output}")


def sha256_record(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}", str(len(data))


def csv_escape(value: str) -> str:
    output = []

    class Writer:
        def write(self, text: str) -> None:
            output.append(text)

    csv.writer(Writer(), lineterminator="").writerow([value])
    return "".join(output)


def zip_write(zf: zipfile.ZipFile, source: Path, arcname: str, executable: bool = False) -> None:
    info = zipfile.ZipInfo(arcname)
    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    with source.open("rb") as f:
        zf.writestr(info, f.read())


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def metadata_text(project: dict[str, Any], version: str) -> str:
    msg = Message()
    msg["Metadata-Version"] = "2.3"
    msg["Name"] = project["name"]
    msg["Version"] = version
    msg["Summary"] = project["description"]
    msg["Requires-Python"] = project.get("requires-python", ">=3.8")
    msg["License"] = project.get("license", {}).get("text", "GPL-2.0-or-later")
    msg["Description-Content-Type"] = "text/markdown"
    for classifier in project.get("classifiers", []):
        msg["Classifier"] = classifier
    for name, url in project.get("urls", {}).items():
        msg.add_header("Project-URL", f"{name}, {url}")

    body = ""
    readme = ROOT / "README.md"
    if readme.exists():
        body = readme.read_text(encoding="utf-8")
    return msg.as_string() + "\n" + body


def wheel_text(platform_tag: str) -> str:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: aria2-next-bin custom wheel builder\n"
        "Root-Is-Purelib: false\n"
        f"Tag: py3-none-{platform_tag}\n"
    )


def metadata_files(project: dict[str, Any], version: str, platform_tag: str) -> dict[str, str]:
    return {
        "METADATA": metadata_text(project, version),
        "WHEEL": wheel_text(platform_tag),
        "entry_points.txt": "[console_scripts]\naria2-next = aria2_next.__main__:_run\n",
        "top_level.txt": "aria2_next\n",
    }


def collect_source_files() -> list[tuple[Path, str, bool]]:
    files: list[tuple[Path, str, bool]] = []
    for path in sorted(SOURCE_DIR.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if "bin" in path.relative_to(SOURCE_DIR).parts:
            continue
        rel = path.relative_to(SOURCE_DIR).as_posix()
        files.append((path, rel, False))
    return files


def write_wheel_archive(
    wheel_directory: Path,
    target: Target,
    version: str,
    binary: Path,
    license_file: Path | None = None,
) -> str:
    project = read_project()
    dist = normalize_dist_name(project["name"])
    wheel_directory.mkdir(parents=True, exist_ok=True)
    wheel_name = f"{dist}-{version}-py3-none-{target.platform_tag}.whl"
    wheel_path = wheel_directory / wheel_name
    dist_info = f"{dist}-{version}.dist-info"

    temp_meta = ROOT / "build" / "wheel-meta" / dist_info
    if temp_meta.exists():
        shutil.rmtree(temp_meta)
    temp_meta.mkdir(parents=True, exist_ok=True)
    for filename, content in metadata_files(project, version, target.platform_tag).items():
        write_text_file(temp_meta / filename, content)

    records: list[list[str]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source, arcname, executable in collect_source_files():
            zip_write(zf, source, arcname, executable)
            records.append([arcname, *sha256_record(source)])

        binary_arcname = f"aria2_next/bin/{target.wheel_binary}"
        zip_write(zf, binary, binary_arcname, target.executable)
        records.append([binary_arcname, *sha256_record(binary)])

        if license_file is not None:
            license_arcname = "aria2_next/licenses/aria2-next-COPYING"
            zip_write(zf, license_file, license_arcname)
            records.append([license_arcname, *sha256_record(license_file)])

        for meta_file in sorted(temp_meta.iterdir()):
            arcname = f"{dist_info}/{meta_file.name}"
            zip_write(zf, meta_file, arcname)
            records.append([arcname, *sha256_record(meta_file)])

        record_name = f"{dist_info}/RECORD"
        record_lines = [",".join(csv_escape(part) for part in row) for row in records]
        record_lines.append(f"{record_name},,")
        zf.writestr(record_name, "\n".join(record_lines) + "\n")

    print(f"built wheel: {wheel_path}")
    return wheel_name


def prepare_metadata(metadata_directory: Path, config_settings: dict[str, Any] | None = None) -> str:
    target = selected_target(target_selector(config_settings))
    release = fetch_release(release_selector(config_settings))
    version = normalize_release_version(release["tag_name"])
    project = read_project()
    dist = normalize_dist_name(project["name"])
    dist_info = f"{dist}-{version}.dist-info"
    out = metadata_directory / dist_info
    out.mkdir(parents=True, exist_ok=True)
    for filename, content in metadata_files(project, version, target.platform_tag).items():
        write_text_file(out / filename, content)
    return dist_info


def build_one_wheel(wheel_directory: Path, target: Target, release: dict[str, Any]) -> str:
    version = normalize_release_version(release["tag_name"])
    binary = ensure_release_binary(release, target)
    verify_binary_run(binary, target)
    license_file = ensure_release_license(release)
    return write_wheel_archive(wheel_directory, target, version, binary, license_file)


def build_wheel_from_config(wheel_directory: Path, config_settings: dict[str, Any] | None = None) -> str:
    selector = target_selector(config_settings)
    if selector == "all":
        raise SystemExit("PEP 517 build_wheel can only build one wheel; use scripts/build_wheel.py --target all")
    release = fetch_release(release_selector(config_settings))
    target = selected_target(selector)
    return build_one_wheel(wheel_directory, target, release)


def build_from_cli(args: argparse.Namespace) -> list[str]:
    release = fetch_release(args.release)
    if args.target == "all":
        targets = [TARGETS[key] for key in sorted(TARGETS)]
    else:
        targets = [selected_target(args.target)]
    return [build_one_wheel(args.dist_dir, target, release) for target in targets]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build platform wheels containing aria2-next.")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--release",
        default=os.environ.get("ARIA2_NEXT_RELEASE", DEFAULT_RELEASE),
        help="GitHub release tag to package, or 'latest'. Tags may be passed with or without a leading v.",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("ARIA2_NEXT_TARGET", "current"),
        choices=["current", "all", *sorted(TARGETS)],
        help="Platform target to package.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    build_from_cli(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
