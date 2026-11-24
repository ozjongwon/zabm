from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install-dev.sh"
RUNTIME_INSTALLER = REPO_ROOT / "scripts" / "install-runtime.sh"


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


def run_runtime_installer(
    *args: str,
    os_release: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ZABM_OS_RELEASE_FILE"] = os_release or "/etc/os-release"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(RUNTIME_INSTALLER), *args],
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
    assert "build-essential" not in result.stdout
    assert "pkg-config" not in result.stdout


def test_runtime_installer_rejects_an_unsupported_operating_system(
    tmp_path: Path,
) -> None:
    os_release = tmp_path / "unsupported-release"
    os_release.write_text(
        'ID=fedora\nVERSION_ID="42"\nPRETTY_NAME="Fedora Linux 42"\n',
        encoding="utf-8",
    )

    result = run_runtime_installer("--dry-run", os_release=str(os_release))

    assert result.returncode != 0
    assert "supports Debian 13 and Ubuntu 24.04 on x86_64" in result.stderr
    assert "Fedora Linux 42" in result.stderr


def test_runtime_installer_dry_run_reports_the_complete_target_plan(
    tmp_path: Path,
) -> None:
    os_release = tmp_path / "debian-release"
    os_release.write_text(
        'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n',
        encoding="utf-8",
    )

    result = run_runtime_installer(
        "--dry-run",
        os_release=str(os_release),
        extra_env={
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "OPENAI_API_KEY": "sk-test-do-not-print",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "Debian GNU/Linux 13" in result.stdout
    assert "runtime dependencies only" in result.stdout
    assert "ollama v0.40.18" in result.stdout
    assert "qwen2.5-1.5b-instruct-q4_k_m.gguf" in result.stdout
    assert "bge-small-en-v1.5-q8_0.gguf" in result.stdout
    assert "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e" in result.stdout
    assert "f046db1dc724cf4f6f0a0c5917e922823b73eb1d27b8f9a9c2797f7866974804" in result.stdout
    assert str(tmp_path / "data" / "zabm-runtime" / "models") in result.stdout
    assert "installed-target smoke" in result.stdout
    assert "one supported answer" in result.stdout
    assert "sk-test-do-not-print" not in result.stdout + result.stderr


def test_runtime_configuration_and_launcher_are_secret_free_and_idempotent(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    config_home = tmp_path / "config"
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(config_home),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "OPENAI_API_KEY": "sk-test-do-not-print",
        }
    )
    generate = f"source {RUNTIME_INSTALLER}; write_runtime_config; write_runtime_launcher"

    first = subprocess.run(
        ["bash", "-c", generate],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr

    config = config_home / "zabm" / "runtime.env"
    launcher = home / ".local" / "bin" / "zabm-runtime"
    config_before = config.stat()
    launcher_before = launcher.stat()
    config_contents = config.read_text(encoding="utf-8")
    launcher_contents = launcher.read_text(encoding="utf-8")

    assert config.stat().st_mode & 0o777 == 0o600
    assert launcher.stat().st_mode & 0o777 == 0o755
    assert "ZABM_PROVIDER_API_KEY=\n" in config_contents
    assert "set -a\n" in launcher_contents
    assert "sk-test-do-not-print" not in config_contents + launcher_contents

    second = subprocess.run(
        ["bash", "-c", generate],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, second.stderr
    assert config.stat().st_ino == config_before.st_ino
    assert launcher.stat().st_ino == launcher_before.st_ino
    assert config.stat().st_mtime_ns == config_before.st_mtime_ns
    assert launcher.stat().st_mtime_ns == launcher_before.st_mtime_ns
