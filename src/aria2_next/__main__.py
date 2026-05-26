from __future__ import annotations

import os
import subprocess
import sys

from aria2_next import find_aria2_next_bin


def _run() -> None:
    aria2_next = find_aria2_next_bin()
    env = os.environ.copy()

    if sys.platform == "win32":
        try:
            completed_process = subprocess.run([aria2_next, *sys.argv[1:]], env=env, check=False)
        except KeyboardInterrupt:
            sys.exit(2)

        sys.exit(completed_process.returncode)

    os.execvpe(aria2_next, [aria2_next, *sys.argv[1:]], env=env)


if __name__ == "__main__":
    _run()
