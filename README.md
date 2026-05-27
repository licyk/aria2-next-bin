# aria2-next-bin

`aria2-next-bin` 项目用来把
[`AnInsomniacy/aria2-next`](https://github.com/AnInsomniacy/aria2-next) GitHub Releases
中已经构建好的 `aria2-next` 可执行文件打包成平台专用 Python wheel。本项目已经发布到
PyPI，包名为 `aria2-next`，安装命令为：

```bash
pip install aria2-next
```

本项目不会从源码编译 aria2-next。

## 构建

从最新 release 为当前平台构建 wheel：

```bash
python3 scripts/build_wheel.py
```

从最新 release 构建指定目标平台：

```bash
python3 scripts/build_wheel.py --target linux-x86_64
python3 scripts/build_wheel.py --target macos-arm64
python3 scripts/build_wheel.py --target windows-x86_64
```

构建所有支持的目标平台：

```bash
python3 scripts/build_wheel.py --target all
```

从指定 release tag 构建：

```bash
python3 scripts/build_wheel.py --release v2.2.6 --target linux-x86_64
```

也可以通过环境变量指定相同配置：

```bash
ARIA2_NEXT_RELEASE=v2.2.6 ARIA2_NEXT_TARGET=linux-x86_64 python3 scripts/build_wheel.py
```

## 支持平台

| 目标 | Release asset | Wheel 平台标签 |
| --- | --- | --- |
| `linux-x86_64` | `linux-x86_64` | `manylinux_2_28_x86_64` |
| `linux-aarch64` | `linux-aarch64` | `manylinux_2_28_aarch64` |
| `macos-x86_64` | `macos-x86_64` | `macosx_10_13_x86_64` |
| `macos-arm64` | `macos-arm64` | `macosx_11_0_arm64` |
| `windows-x86_64` | `windows-x86_64.exe` | `win_amd64` |
| `windows-arm64` | `windows-arm64.exe` | `win_arm64` |

wheel 版本号来自 GitHub release tag。例如 release `v2.2.6` 会生成版本号为
`2.2.6` 的 wheel。

## 安装和运行

从 PyPI 安装：

```bash
pip install aria2-next
```

从本地 wheel 安装：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install dist/aria2_next-*.whl
aria2-next --version
python -m aria2_next --version
```

wheel 文件名来自发行包名 `aria2-next`，安装后的 Python import 包名是 `aria2_next`。
wheel 会像 uv 一样把真实的 `aria2-next` 二进制文件安装到当前 Python 环境的脚本目录
（例如虚拟环境的 `bin/aria2-next`）。`python -m aria2_next` 会按 uv 的
`_find_uv.py` 思路定位该二进制文件并执行它。

## 校验

release 下载文件会使用 SHA-256 校验。构建脚本会优先使用 GitHub asset 的 `digest`
字段；如果该字段不可用，则下载并解析 release 中的 `checksums.sha256` 文件。

## GitHub Actions 发布

`build-wheels` workflow 会在 push、PR 和手动触发时构建所有平台 wheel，并上传
`aria2-next-bin-wheels` artifact。手动触发时可以填写 `release` 来指定要打包的
aria2-next release。

默认不会上传到 PyPI。需要发布新版本时，在 GitHub Actions 手动运行 workflow，并把
`publish` 设置为 `true`。发布使用 `twine upload dist/*.whl`，凭据从 Secrets 读取：

- 推荐设置 `PYPI_API_TOKEN`，workflow 会使用 `__token__` 作为 Twine 用户名。
- 也可以设置标准的 `TWINE_USERNAME` 和 `TWINE_PASSWORD`。
- 如果要上传到 TestPyPI 或私有仓库，可以填写 `repository_url`。

## 许可证

打包进去的可执行文件来自
[`AnInsomniacy/aria2-next`](https://github.com/AnInsomniacy/aria2-next)，按
GPL-2.0-or-later 分发。
如果所选 release tag 可以获取上游 `COPYING` 文件，构建出的 wheel 会一并包含该文件。
