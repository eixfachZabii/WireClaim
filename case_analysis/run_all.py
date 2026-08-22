"""Run the whole case_analysis pipeline in order and produce every output.

Steps: fetch_data -> analyze -> dashboard --save -> report -> money -> diagnose.
All outputs land in case_analysis/data/ (see dashboard.md for the overview page).

Usage:
    python3 case_analysis/run_all.py            # incremental fetch
    python3 case_analysis/run_all.py --force    # re-fetch everything
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

STEPS = [
    ["fetch_data.py", *sys.argv[1:]],
    ["analyze.py"],
    ["dashboard.py", "--save"],
    ["report.py"],
    ["money.py"],
    ["diagnose.py"],
]


def main() -> None:
    for step in STEPS:
        script, *args = step
        print(f"\n=== {script} {' '.join(args)} ===")
        result = subprocess.run([sys.executable, str(HERE / script), *args], check=False)
        if result.returncode != 0:
            raise SystemExit(f"{script} failed with exit code {result.returncode}")
    print(f"\nAll outputs written to {HERE / 'data'} — see {HERE / 'dashboard.md'}")


if __name__ == "__main__":
    main()
