# 16: Target runtime installer

**What to build:** A repeatable installer for a supported Debian or Ubuntu x86_64 target machine. It installs the runtime system libraries, pinned `uv`, locked runtime environment, CLI, web chat, and selected local model server, then verifies the running system without installing development or test tooling.

**Blocked by:** 05, 15.

**Status:** ready-for-agent

- [ ] The runtime installer succeeds on clean Debian 13 and Ubuntu 24.04 x86_64 targets and rejects unsupported systems clearly.
- [ ] The installer is idempotent, fails fast, and does not require a manually prepared Python environment.
- [ ] The runtime dependency group is installed from the lockfile and excludes development, test, and evaluation-only tooling.
- [ ] The selected local OpenAI-compatible model server and its required runtime libraries are installed and configured.
- [ ] Model weights remain outside the repository and can be fetched through a separate documented command or optional installer flag.
- [ ] The installer validates `nvidia-smi` and gives clear prerequisite instructions when the kernel GPU driver is missing; it does not replace the host driver automatically.
- [ ] The CLI and web chat become runnable without source-development setup.
- [ ] A smoke check verifies the application, local provider, evidence stores, and one supported answer on the installed target.
- [ ] Secrets remain in environment variables or an equivalent secret store and are absent from installer output and committed configuration.
- [ ] Re-running the installer leaves a working system without duplicating runtime configuration.

