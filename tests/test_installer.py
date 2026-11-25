from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install-dev.sh"
RUNTIME_INSTALLER = REPO_ROOT / "scripts" / "install-runtime.sh"
SELECT_RUNTIME_MODELS = REPO_ROOT / "scripts" / "select-runtime-models.sh"


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
        "--provider",
        "local",
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
    assert "model selection: existing models reported by 'ollama list'" in result.stdout
    assert "model downloads and imports: none" in result.stdout
    assert "chat model: selected during installation" in result.stdout
    assert "embedding model: selected during installation" in result.stdout
    assert "installed-target smoke" in result.stdout
    assert "Ollama prerequisite: preinstalled ollama v0.40.18" in result.stdout
    assert "active ollama.service" in result.stdout
    assert "one supported answer" in result.stdout
    assert "sk-test-do-not-print" not in result.stdout + result.stderr


def test_runtime_installer_defaults_to_deepseek_chat_with_local_embeddings(
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
            "DEEPSEEK_API_KEY": "deepseek-secret-do-not-print",
            "ZABM_EMBEDDING_MODEL": "mxbai-embed-large:latest",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "provider: deepseek at https://api.deepseek.com" in result.stdout
    assert "embedding provider: local Ollama at http://127.0.0.1:11434/v1" in result.stdout
    assert "chat model: deepseek-flash" in result.stdout
    assert "embedding model: mxbai-embed-large:latest" in result.stdout
    assert "deepseek-secret-do-not-print" not in result.stdout + result.stderr


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
    generate = (
        f"source {RUNTIME_INSTALLER}; "
        "PROVIDER_KIND=local; "
        "RUNTIME_PROVIDER_NAME=openai-compatible; "
        "RUNTIME_PROVIDER_URL=http://127.0.0.1:11434/v1; "
        "RUNTIME_EMBEDDING_PROVIDER_KIND=local; "
        "RUNTIME_EMBEDDING_PROVIDER_URL=http://127.0.0.1:11434/v1; "
        "RUNTIME_CHAT_MODEL_NAME=test-chat; "
        "RUNTIME_EMBEDDING_MODEL_NAME=test-embedding; "
        "write_runtime_config; write_runtime_launcher"
    )

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
    assert "ZABM_RUNTIME_PROVIDER_KIND=local\n" in config_contents
    assert "ZABM_RUNTIME_EMBEDDING_PROVIDER_KIND=local\n" in config_contents
    assert "ZABM_EMBEDDING_PROVIDER_URL=http://127.0.0.1:11434/v1\n" in config_contents
    assert "ZABM_PROVIDER=openai-compatible\n" in config_contents
    assert "ZABM_PROVIDER_API_KEY=\n" in config_contents
    assert "ZABM_MODEL=test-chat\n" in config_contents
    assert "ZABM_EMBEDDING_MODEL=test-embedding\n" in config_contents
    assert (
        f"ZABM_KOREAN_SAMPLE_SET={REPO_ROOT / 'data' / 'korean' / 'sample-set-v1.json'}\n"
        in config_contents
    )
    assert (
        f"ZABM_KOREAN_REVIEW={REPO_ROOT / 'data' / 'korean' / 'review-v1.json'}\n"
        in config_contents
    )
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
    runtime_home.mkdir()
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
prepare_runtime_directories() {{ :; }}
check_ollama_prerequisites() {{ :; }}
install_runtime_base() {{ printf 'phase: runtime base\\n'; }}
write_runtime_config() {{ :; }}
write_runtime_launcher() {{ :; }}
verify_ollama_service() {{ :; }}
select_models() {{ :; }}
prepare_evidence() {{ :; }}
run_installed_smoke() {{ :; }}
main --provider local --runtime-home {shlex.quote(str(runtime_home))}
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


def test_runtime_installer_prepares_runtime_directories_without_a_model_space_check(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "runtime-home"
    runtime_home.mkdir()
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
RUNTIME_HOME={shlex.quote(str(runtime_home))}
MODEL_DIR={shlex.quote(str(runtime_home / "models"))}
STATE_DIR={shlex.quote(str(runtime_home / "state"))}
df() {{
  printf 'df must not be called\\n' >&2
  return 99
}}
prepare_runtime_directories
"""

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (runtime_home / "models").is_dir()
    assert (runtime_home / "state").is_dir()
    assert "runtime directories are ready" in result.stdout


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
MODEL_DIR="{runtime_home}/models"
STATE_DIR={shlex.quote(str(runtime_home / "state"))}
setfacl() {{ :; }}
sudo() {{
  if [[ "$1" == "setfacl" ]]; then
    chmod u+w "$RUNTIME_HOME"
  fi
}}
prepare_runtime_directories
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


def test_runtime_installer_selects_existing_chat_and_embedding_models(
    tmp_path: Path,
) -> None:
    ollama = tmp_path / "ollama"
    call_log = tmp_path / "ollama-calls"
    ollama.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$*" >> {shlex.quote(str(call_log))}
if [ "$1" = "list" ]; then
  printf 'NAME ID SIZE MODIFIED\\n'
  printf 'qwen2.5:7b chat-id 4.7GB now\\n'
  printf 'nomic-embed-text:latest embed-id 274MB now\\n'
fi
""",
        encoding="utf-8",
    )
    ollama.chmod(0o755)
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
OLLAMA_BIN={shlex.quote(str(ollama))}
select_models
printf 'chat=%s\\n' "$RUNTIME_CHAT_MODEL_NAME"
printf 'embedding=%s\\n' "$RUNTIME_EMBEDDING_MODEL_NAME"
"""

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env={**os.environ, "OLLAMA_CALL_LOG": str(call_log)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "selected chat model: qwen2.5:7b" in result.stdout
    assert "selected embedding model: nomic-embed-text:latest" in result.stdout
    assert "chat=qwen2.5:7b" in result.stdout
    assert "embedding=nomic-embed-text:latest" in result.stdout
    assert call_log.read_text(encoding="utf-8").splitlines() == ["list"]


def test_runtime_installer_skips_embeddings_when_only_a_chat_model_exists(
    tmp_path: Path,
) -> None:
    ollama = tmp_path / "ollama"
    ollama.write_text(
        """#!/bin/sh
if [ "$1" = "list" ]; then
  printf 'NAME ID SIZE MODIFIED\\n'
  printf 'llama3.2:latest model-id 2.0GB now\\n'
fi
""",
        encoding="utf-8",
    )
    ollama.chmod(0o755)
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
OLLAMA_BIN={shlex.quote(str(ollama))}
select_models
printf 'chat=%s\\n' "$RUNTIME_CHAT_MODEL_NAME"
printf 'embedding=%s\\n' "$RUNTIME_EMBEDDING_MODEL_NAME"
"""

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "chat=llama3.2:latest" in result.stdout
    assert "embedding=not-configured" in result.stdout


def test_runtime_installer_uses_requested_installed_models(tmp_path: Path) -> None:
    ollama = tmp_path / "ollama"
    ollama.write_text(
        """#!/bin/sh
if [ "$1" = "list" ]; then
  printf 'NAME ID SIZE MODIFIED\\n'
  printf 'qwen2.5:latest chat-id 4.7GB now\\n'
  printf 'nomic-embed-text:latest embed-id 274MB now\\n'
fi
""",
        encoding="utf-8",
    )
    ollama.chmod(0o755)
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
OLLAMA_BIN={shlex.quote(str(ollama))}
select_models
printf 'chat=%s\\n' "$RUNTIME_CHAT_MODEL_NAME"
printf 'embedding=%s\\n' "$RUNTIME_EMBEDDING_MODEL_NAME"
"""
    env = os.environ.copy()
    env.update({"ZABM_MODEL": "qwen2.5", "ZABM_EMBEDDING_MODEL": "nomic-embed-text"})

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "chat=qwen2.5:latest" in result.stdout
    assert "embedding=nomic-embed-text:latest" in result.stdout


def test_runtime_installer_configures_deepseek_with_local_ollama_embeddings(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    config_home = tmp_path / "config"
    ollama = tmp_path / "ollama"
    ollama.write_text(
        """#!/bin/sh
if [ "$1" = "list" ]; then
  printf 'NAME ID SIZE MODIFIED\\n'
  printf 'mxbai-embed-large:latest embed-id 670MB now\\n'
fi
""",
        encoding="utf-8",
    )
    ollama.chmod(0o755)
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
PROVIDER_KIND=deepseek
OLLAMA_BIN={shlex.quote(str(ollama))}
check_ollama_prerequisites() {{ :; }}
verify_ollama_service() {{ :; }}
configure_remote_provider
write_runtime_config
"""
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(config_home),
            "DEEPSEEK_API_KEY": "deepseek-secret-do-not-print",
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

    config = config_home / "zabm" / "runtime.env"
    contents = config.read_text(encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert config.stat().st_mode & 0o777 == 0o600
    assert "ZABM_RUNTIME_PROVIDER_KIND=deepseek\n" in contents
    assert "ZABM_PROVIDER=deepseek\n" in contents
    assert "ZABM_PROVIDER_URL=https://api.deepseek.com\n" in contents
    assert "ZABM_RUNTIME_EMBEDDING_PROVIDER_KIND=local\n" in contents
    assert "ZABM_EMBEDDING_PROVIDER_URL=http://127.0.0.1:11434/v1\n" in contents
    assert "ZABM_MODEL=deepseek-flash\n" in contents
    assert "ZABM_EMBEDDING_MODEL=mxbai-embed-large:latest\n" in contents
    assert "DEEPSEEK_API_KEY=deepseek-secret-do-not-print\n" in contents
    assert "deepseek-secret-do-not-print" not in result.stdout + result.stderr


def test_installed_remote_runtime_does_not_require_ollama(tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "zabm"
    config_dir.mkdir(parents=True)
    (config_dir / "runtime.env").write_text(
        "ZABM_RUNTIME_PROVIDER_KIND=deepseek\nZABM_PROVIDER=deepseek\nZABM_MODEL=deepseek-flash\n",
        encoding="utf-8",
    )
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
require_installed_runtime
printf 'kind=%s provider=%s\\n' "$PROVIDER_KIND" "$RUNTIME_PROVIDER_NAME"
"""
    env = os.environ.copy()
    env.update({"XDG_CONFIG_HOME": str(tmp_path / "config")})

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "kind=deepseek provider=deepseek" in result.stdout


def test_select_runtime_models_uses_remote_provider_selection(tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "zabm"
    config_dir.mkdir(parents=True)
    (config_dir / "runtime.env").write_text(
        "ZABM_RUNTIME_PROVIDER_KIND=openai\n"
        "ZABM_PROVIDER=openai\n"
        "ZABM_RUNTIME_EMBEDDING_PROVIDER_KIND=remote\n",
        encoding="utf-8",
    )
    os_release = tmp_path / "debian-release"
    os_release.write_text(
        'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "ZABM_OS_RELEASE_FILE": str(os_release),
            "OPENAI_API_KEY": "openai-secret-do-not-print",
            "OPENAI_MODEL": "test-openai-model",
        }
    )

    result = subprocess.run(
        [str(SELECT_RUNTIME_MODELS), "--provider", "openai"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    contents = (config_dir / "runtime.env").read_text(encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "ZABM_PROVIDER=openai\n" in contents
    assert "ZABM_MODEL=test-openai-model\n" in contents
    assert "ZABM_RUNTIME_EMBEDDING_PROVIDER_KIND=remote\n" in contents
    assert "OPENAI_API_KEY=openai-secret-do-not-print\n" in contents
    assert "openai-secret-do-not-print" not in result.stdout + result.stderr


def test_select_runtime_models_dry_run_does_not_require_an_installed_config(
    tmp_path: Path,
) -> None:
    os_release = tmp_path / "debian-release"
    os_release.write_text(
        'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "ZABM_OS_RELEASE_FILE": str(os_release),
            "ZABM_EMBEDDING_MODEL": "mxbai-embed-large:latest",
        }
    )

    result = subprocess.run(
        [str(SELECT_RUNTIME_MODELS), "--dry-run"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "provider: deepseek at https://api.deepseek.com" in result.stdout
    assert "embedding provider: local Ollama" in result.stdout
    assert "dry run complete; no changes made" in result.stdout


def test_runtime_smoke_reports_route_and_failure_when_no_answer_is_found(
    tmp_path: Path,
) -> None:
    response_file = tmp_path / "response.json"
    response_file.write_text(
        """
{
  "status": "not_found",
  "failure": {"code": "not_found", "message": "No matching evidence."},
  "routing": {
    "intent": "procedure",
    "normalized_question": "Service the component."
  }
}
""",
        encoding="utf-8",
    )
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
validate_supported_response {shlex.quote(str(response_file))} CLI
"""

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "CLI: expected supported, got not_found" in result.stderr
    assert "failure=No matching evidence." in result.stderr
    assert "intent=procedure" in result.stderr
    assert "normalized_question=Service the component." in result.stderr
    assert "Traceback" not in result.stderr


def test_runtime_installer_prints_ollama_setup_instructions_when_service_is_inactive(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "ollama"
    runtime_home.mkdir()
    ollama = runtime_home / "bin" / "ollama"
    ollama.parent.mkdir()
    ollama.write_text("#!/bin/sh\nprintf 'ollama version is 0.40.18\\n'\n", encoding="utf-8")
    ollama.chmod(0o755)
    command = f"""
source {shlex.quote(str(RUNTIME_INSTALLER))}
RUNTIME_HOME={shlex.quote(str(runtime_home))}
MODEL_DIR={shlex.quote(str(runtime_home / "models"))}
systemctl() {{
  case "$1" in
    is-enabled) return 0 ;;
    is-active) return 1 ;;
  esac
}}
check_ollama_prerequisites
"""

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Ollama is not installed or managed by this script." in result.stderr
    assert "sudo systemctl enable --now ollama.service" in result.stderr
    assert "Rerun ./scripts/install-runtime.sh" in result.stderr
