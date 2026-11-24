from __future__ import annotations

import grp
import os
import pwd
import shlex
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
    assert "/home/ollama/models" in result.stdout
    assert "installed-target smoke" in result.stdout
    assert "systemctl (ollama.service, enabled at boot)" in result.stdout
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


def test_runtime_installer_prints_its_plan_before_a_normal_run(
    tmp_path: Path,
) -> None:
    os_release = tmp_path / "debian-release"
    os_release.write_text(
        'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n',
        encoding="utf-8",
    )
    runtime_home = tmp_path / "runtime-home"
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
check_disk_space() {{ :; }}
install_runtime_base() {{ printf 'phase: runtime base\\n'; }}
install_model_server() {{ :; }}
write_runtime_config() {{ :; }}
write_runtime_launcher() {{ :; }}
write_model_service() {{ :; }}
start_model_server() {{ :; }}
fetch_models() {{ :; }}
prepare_evidence() {{ :; }}
run_installed_smoke() {{ :; }}
main --runtime-home {shlex.quote(str(runtime_home))}
"""
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "ZABM_OS_RELEASE_FILE": str(os_release),
        }
    )

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert str(runtime_home) in result.stdout
    assert result.stdout.index("install plan:") < result.stdout.index("phase: runtime base")


def test_runtime_installer_rejects_a_runtime_home_without_enough_free_space(
    tmp_path: Path,
) -> None:
    os_release = tmp_path / "debian-release"
    os_release.write_text(
        'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n',
        encoding="utf-8",
    )
    runtime_home = tmp_path / "runtime-home"
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
df() {{
  printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\n'
  printf 'fake 100 100 100 100%% /\\n'
}}
install_runtime_base() {{ printf 'phase: runtime base\\n'; }}
main --runtime-home {shlex.quote(str(runtime_home))}
"""
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "ZABM_OS_RELEASE_FILE": str(os_release),
        }
    )

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "at least 12 GiB is required" in result.stderr
    assert "phase: runtime base" not in result.stdout


def test_runtime_installer_grants_access_without_changing_runtime_home_ownership(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "ollama"
    runtime_home.mkdir()
    runtime_home.chmod(0o500)
    owner_before = runtime_home.stat().st_uid, runtime_home.stat().st_gid
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
RUNTIME_HOME={shlex.quote(str(runtime_home))}
SERVER_DIR="{runtime_home}/server"
MODEL_DIR="{runtime_home}/models"
STATE_DIR={shlex.quote(str(runtime_home / "state"))}
setfacl() {{ :; }}
sudo() {{
  if [[ "$1" == "setfacl" ]]; then
    chmod u+w "$RUNTIME_HOME"
  fi
}}
df() {{
  printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\n'
  printf 'fake 100000000 1000 98000000 2%% /\\n'
}}
check_disk_space
"""

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "preserving its owner and group" in result.stdout
    assert "chown" not in result.stdout + result.stderr
    assert (runtime_home.stat().st_uid, runtime_home.stat().st_gid) == owner_before


def test_runtime_installer_writes_a_systemd_unit_with_runtime_home_ownership(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "ollama"
    runtime_home.mkdir()
    unit_dir = tmp_path / "systemd"
    unit_dir.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "ZABM_RUNTIME_HOME": str(runtime_home),
            "ZABM_SYSTEMD_UNIT_DIR": str(unit_dir),
        }
    )
    command = f"source {shlex.quote(str(RUNTIME_INSTALLER))}; write_model_service"

    first = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr

    service = unit_dir / "ollama.service"
    first_stat = service.stat()
    contents = service.read_text(encoding="utf-8")
    assert f"User={pwd.getpwuid(os.getuid()).pw_name}\n" in contents
    assert f"Group={grp.getgrgid(os.getgid()).gr_name}\n" in contents
    assert f'Environment="OLLAMA_MODELS={runtime_home}/models"\n' in contents
    assert 'Environment="OLLAMA_HOST=127.0.0.1:11434"\n' in contents
    assert f"ExecStart={runtime_home}/server/v0.40.18/bin/ollama serve\n" in contents
    assert "WantedBy=multi-user.target\n" in contents

    second = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, second.stderr
    assert service.stat().st_ino == first_stat.st_ino
    assert service.stat().st_mtime_ns == first_stat.st_mtime_ns


def test_runtime_installer_starts_ollama_through_systemctl(tmp_path: Path) -> None:
    runtime_home = tmp_path / "ollama"
    runtime_home.mkdir()
    state_dir = runtime_home / "state"
    service_file = tmp_path / "ollama.service"
    service_file.write_text("[Unit]\n", encoding="utf-8")
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
RUNTIME_HOME={shlex.quote(str(runtime_home))}
SERVER_DIR={shlex.quote(str(runtime_home / "server"))}
MODEL_DIR={shlex.quote(str(runtime_home / "models"))}
STATE_DIR={shlex.quote(str(state_dir))}
LEGACY_SERVER_PID_FILE={shlex.quote(str(state_dir / "ollama.pid"))}
OLLAMA_SERVICE_FILE={shlex.quote(str(service_file))}
server_version_response() {{ :; }}
wait_for_server() {{ printf 'wait: ready\\n'; }}
systemctl() {{
  printf 'systemctl:'
  printf ' %s' "$@"
  printf '\\n'
  case "$1" in
    is-active|is-enabled) return 1 ;;
  esac
}}
sudo() {{ "$@"; }}
start_model_server
"""

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "systemctl: is-enabled --quiet ollama.service" in result.stdout
    assert "systemctl: enable ollama.service" in result.stdout
    assert "systemctl: start ollama.service" in result.stdout
    assert "wait: ready" in result.stdout
