# 16: Target runtime installer

**What to build:** A repeatable installer for a supported Debian or Ubuntu x86_64 target machine. It installs the runtime system libraries, pinned `uv`, locked runtime environment, CLI, web chat, and selected local model server, then verifies the running system without installing development or test tooling.

**Blocked by:** 05, 15.

**Status:** ready-for-human

- [ ] The runtime installer succeeds on clean Debian 13 and Ubuntu 24.04 x86_64 targets and rejects unsupported systems clearly.
- [x] The installer is idempotent, fails fast, and does not require a manually prepared Python environment.
- [x] The runtime dependency group is installed from the lockfile and excludes development, test, and evaluation-only tooling.
- [x] The selected local OpenAI-compatible model server and its required runtime libraries are installed and configured.
- [x] Model weights remain outside the repository; the installer selects existing Ollama models without downloading or importing new ones.
- [x] The installer validates `nvidia-smi` and gives clear prerequisite instructions when the kernel GPU driver is missing; it does not replace the host driver automatically.
- [x] The CLI and web chat become runnable without source-development setup.
- [x] A smoke check verifies the application, local provider, evidence stores, and one supported answer on the installed target.
- [x] Secrets remain in environment variables or an equivalent secret store and are absent from installer output and committed configuration.
- [x] Re-running the installer leaves a working system without duplicating runtime configuration.

## Comments

- 2026-11-24: Implemented the target installer with a runtime-only package
  profile, pinned Ollama v0.40.18, hash-verified external chat and embedding
  GGUFs, generated local-provider configuration, an idempotent server launcher,
  source/evidence rebuild, and installed-target CLI plus web smoke. Added
  installer plan/rejection/config/idempotence tests and a clean-host acceptance
  procedure. Full Pyright, repo-wide Ruff checks, and 228 tests pass. Clean
  Debian 13 and Ubuntu 24.04 execution still requires the documented
  disposable-host acceptance because no container or second target is
  available in this workspace.
- 2026-11-25: Fixed two target-install failures found during acceptance.
  Normal runs now print the complete plan before changing the machine, and a
  preflight requires 12 GiB free on the selected runtime-home filesystem.
  Ollama and its models default to the required `/home/ollama` runtime home,
  and the large Ollama archive plus extraction workspace now live there
  instead of the often-small `/tmp` filesystem. `--runtime-home` remains an
  explicit override for test or exceptional deployments.
- 2026-11-25: The installer now provisions an absent `/home/ollama` through
  `sudo` and assigns it to the invoking user. It refuses to change ownership
  of a pre-existing `/home/ollama`; when the invoking user lacks write access,
  it uses a POSIX ACL with inherited access for new runtime directories while
  preserving the directory's existing owner and group.
- 2026-11-25: Ollama lifecycle is now owned by Linux through generated,
  enabled `ollama.service`. The service runs as `/home/ollama`'s owner and
  group, uses its model directory, binds to loopback, restarts after unit
  changes, and removes the installer's former ad hoc background-process path.
- 2026-11-25: Per operator direction, the installer no longer installs Ollama,
  writes its systemd unit, or starts/stops its service. It verifies the
  preinstalled binary, `/home/ollama`, and the externally managed
  `ollama.service`, then prints exact remediation steps and exits when those
  prerequisites are absent. Model weight acquisition and import remain in the
  installer.
- 2026-11-25: Per operator direction, the installer no longer downloads or
  imports models. It reads `ollama list`, honors `ZABM_MODEL` and
  `ZABM_EMBEDDING_MODEL` selections, otherwise prefers an embedding-named
  model for embeddings and reuses the sole installed model when needed. The
  separate model command now selects existing models and refreshes the runtime
  provider configuration.

