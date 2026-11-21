from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install-dev.sh"


def run_installer(
    *args: str,
    os_release: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ZABM_OS_RELEASE_FILE"] = os_release or "/etc/os-release"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(INSTALLER), *args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_installer_dry_run_reports_a_supported_platform_without_secrets(
    tmp_path: Path,
) -> None:
    os_release = tmp_path / "ubuntu-release"
    os_release.write_text(
        'ID=ubuntu\nVERSION_ID="24.04"\nPRETTY_NAME="Ubuntu 24.04 LTS"\n',
        encoding="utf-8",
    )

    result = run_installer(
        "--dry-run",
        os_release=str(os_release),
        extra_env={"OPENAI_API_KEY": "sk-test-do-not-print"},
    )

    assert result.returncode == 0, result.stderr
    assert "Ubuntu 24.04 LTS" in result.stdout
    assert "uv 0.8.22" in result.stdout
    assert "Python 3.13.5" in result.stdout
    assert "runtime, development, test, and evaluation" in result.stdout
    assert "sk-test-do-not-print" not in result.stdout + result.stderr


def test_installer_rejects_an_unsupported_operating_system(tmp_path: Path) -> None:
    os_release = tmp_path / "unsupported-release"
    os_release.write_text(
        'ID=fedora\nVERSION_ID="42"\nPRETTY_NAME="Fedora Linux 42"\n',
        encoding="utf-8",
    )

    result = run_installer("--dry-run", os_release=str(os_release))

    assert result.returncode != 0
    assert "supports Debian 13 and Ubuntu 24.04 on x86_64" in result.stderr
    assert "Fedora Linux 42" in result.stderr


def test_runtime_profile_excludes_development_and_test_dependencies(
    tmp_path: Path,
) -> None:
    os_release = tmp_path / "debian-release"
    os_release.write_text(
        'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n',
        encoding="utf-8",
    )

    result = run_installer(
        "--dry-run",
        "--profile",
        "runtime",
        os_release=str(os_release),
    )

    assert result.returncode == 0, result.stderr
    assert "profile: runtime" in result.stdout
    assert "runtime dependencies only" in result.stdout
    assert "development, test, and evaluation dependencies" not in result.stdout
