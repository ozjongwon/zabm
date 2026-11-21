from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from pydantic import BaseModel

from zabm import __version__

PINNED_PYTHON = "3.13.5"
PINNED_DEPENDENCIES = {"pydantic": "2.14.3"}


class HealthReport(BaseModel):
    status: Literal["ok"]
    application_version: str
    python_version: str
    executable: str
    dependencies: dict[str, str]


def _installed_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not-installed"


def _build_health_report() -> HealthReport:
    python_version = platform.python_version()
    dependencies = {package: _installed_version(package) for package in PINNED_DEPENDENCIES}

    if python_version != PINNED_PYTHON:
        raise RuntimeError(
            f"expected Python {PINNED_PYTHON}, found {python_version}; run ./scripts/install-dev.sh"
        )

    mismatches = [
        f"{package} {installed} (expected {expected})"
        for package, expected in PINNED_DEPENDENCIES.items()
        if (installed := dependencies[package]) != expected
    ]
    if mismatches:
        details = ", ".join(mismatches)
        raise RuntimeError(
            f"pinned runtime dependencies are not ready: {details}; run ./scripts/install-dev.sh"
        )

    return HealthReport(
        status="ok",
        application_version=__version__,
        python_version=python_version,
        executable=sys.executable,
        dependencies=dependencies,
    )


def _health_command(as_json: bool) -> int:
    try:
        report = _build_health_report()
    except RuntimeError as exc:
        print(f"zabm health: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.model_dump(), indent=2, sort_keys=True))
    else:
        print(f"zabm {report.application_version} is ready (Python {report.python_version})")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zabm",
        description="Bicycle maintenance assistant with evidence gates.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    health = commands.add_parser(
        "health",
        help="Check that the pinned development environment is ready.",
    )
    health.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable health report.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "health":
        return _health_command(args.json)
    raise AssertionError(f"unhandled command: {args.command}")
