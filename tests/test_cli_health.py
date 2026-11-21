from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "zabm", *args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_health_command_reports_a_ready_development_environment() -> None:
    result = run_cli("health", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert (
        report["python_version"]
        == f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    assert report["dependencies"]["pydantic"] == "2.14.3"
