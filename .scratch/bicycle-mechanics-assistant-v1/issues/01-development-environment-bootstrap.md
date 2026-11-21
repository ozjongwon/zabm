# 01: Development environment bootstrap

**What to build:** A repeatable installer for a supported Debian or Ubuntu x86_64 development machine. Running it on a clean system installs the required system libraries, a pinned `uv`, the pinned Python environment, development and evaluation dependencies, and enough project scaffolding to run a CLI health check and the initial automated test suite.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The development installer succeeds on clean Debian 13 and Ubuntu 24.04 x86_64 systems.
- [ ] The installer is idempotent, fails clearly on unsupported systems, redacts secrets, and does not require a manually prepared Python environment.
- [ ] `uv`, Python, application dependencies, test dependencies, and evaluation dependencies are reproducibly pinned, with development dependencies separated from target-runtime dependencies.
- [ ] The installer detects the NVIDIA environment but does not install or replace the kernel GPU driver; a missing `nvidia-smi` produces clear prerequisite instructions.
- [ ] A documented CLI health command and a smoke test pass from a clean development workspace after installation.
- [ ] Re-running the installer leaves a working environment without duplicating configuration or installing development tools into the target-runtime dependency group.
- [ ] The installation path contains no committed credentials or generated source data.

## Comments

- 2026-11-21: Added the Debian 13 / Ubuntu 24.04 x86_64 bootstrap, pinned uv and Python versions, hash-locked runtime/development/test dependency sets, runtime-only profile, CLI health command, and installer/CLI tests. `make verify` passes, and the development lock set was installed successfully in a clean virtual environment. Clean-machine execution remains to be exercised on throwaway Debian 13 and Ubuntu 24.04 hosts because this workspace has restricted network access and no root/sudo.
- 2026-11-21: A commit could not be created because the workspace's `.git` directory is mounted read-only.

