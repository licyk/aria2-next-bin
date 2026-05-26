# aria2-next-bin

`aria2-next-bin` packages prebuilt `aria2-next` executables from
`AnInsomniacy/aria2-next` GitHub Releases into platform-specific Python wheels.
It does not compile aria2-next from source.

## Build

Build the wheel for the current platform from the latest release:

```bash
python3 scripts/build_wheel.py
```

Build a specific target from the latest release:

```bash
python3 scripts/build_wheel.py --target linux-x86_64
python3 scripts/build_wheel.py --target macos-arm64
python3 scripts/build_wheel.py --target windows-x86_64
```

Build all supported targets:

```bash
python3 scripts/build_wheel.py --target all
```

Build from a specific release tag:

```bash
python3 scripts/build_wheel.py --release v2.2.6 --target linux-x86_64
```

The same settings are available through environment variables:

```bash
ARIA2_NEXT_RELEASE=v2.2.6 ARIA2_NEXT_TARGET=linux-x86_64 python3 scripts/build_wheel.py
```

## Targets

| Target | Release asset | Wheel platform tag |
| --- | --- | --- |
| `linux-x86_64` | `linux-x86_64` | `manylinux_2_28_x86_64` |
| `linux-aarch64` | `linux-aarch64` | `manylinux_2_28_aarch64` |
| `macos-x86_64` | `macos-x86_64` | `macosx_10_13_x86_64` |
| `macos-arm64` | `macos-arm64` | `macosx_11_0_arm64` |
| `windows-x86_64` | `windows-x86_64.exe` | `win_amd64` |
| `windows-arm64` | `windows-arm64.exe` | `win_arm64` |

The wheel version is derived from the GitHub release tag. For example, release
`v2.2.6` produces wheels with version `2.2.6`.

## Install And Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install dist/aria2_next_bin-*.whl
aria2-next --version
```

## Verification

Release downloads are verified with SHA-256. The builder first uses the GitHub
asset `digest` field. If that is unavailable, it downloads and parses the
release `checksums.sha256` asset.

## License

The packaged executable comes from `AnInsomniacy/aria2-next`, distributed under
GPL-2.0-or-later. The wheel includes the upstream `COPYING` file when it is
available from the selected release tag.
