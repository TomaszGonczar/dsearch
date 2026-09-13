#!/usr/bin/env python3
"""Enforce the v0.1 stdlib-first runtime dependency policy."""

import argparse
import ast
import re
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import cast

RUNTIME_ALLOWLIST: frozenset[str] = frozenset()
DISALLOWED_HTTP_IMPORTS = frozenset({"aiohttp", "httpx", "requests", "urllib3"})


def _dependency_name(specification: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", specification)
    if match is None:
        return specification
    return match.group(0).lower().replace("_", "-")


def _runtime_dependencies(data: object) -> list[str]:
    root = data if isinstance(data, dict) else {}
    project = root.get("project") if isinstance(root, dict) else None
    dependencies = project.get("dependencies") if isinstance(project, dict) else None
    if not isinstance(dependencies, list) or not all(
        isinstance(dependency, str) for dependency in dependencies
    ):
        return ["pyproject.toml: project.dependencies must be an array of strings"]
    return [
        f"pyproject.toml: runtime dependency {dependency!r} is not allowlisted"
        for dependency in dependencies
        if _dependency_name(dependency) not in RUNTIME_ALLOWLIST
    ]


def _disallowed_imports(source_roots: Sequence[Path]) -> list[str]:
    violations: list[str] = []
    for source_root in source_roots:
        if not source_root.exists():
            continue
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    names = [node.module]
                for name in names:
                    package = name.partition(".")[0]
                    if package in DISALLOWED_HTTP_IMPORTS:
                        violations.append(
                            f"{path}:{getattr(node, 'lineno', 0)}: "
                            f"HTTP client import {package!r} is disallowed"
                        )
    return violations


def check_dependency_policy(pyproject: Path, source_roots: Sequence[Path]) -> list[str]:
    """Return deterministic policy violations; an empty list means pass."""

    with pyproject.open("rb") as handle:
        parsed = cast(object, tomllib.load(handle))
    return sorted(_runtime_dependencies(parsed) + _disallowed_imports(source_roots))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--source-root", action="append", type=Path, dest="source_roots")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the policy check and return a lint-compatible status code."""

    args = _parser().parse_args(argv)
    pyproject = cast(Path, args.pyproject)
    configured_roots = cast(list[Path] | None, args.source_roots)
    source_roots = configured_roots or [Path("providers"), Path("core")]
    violations = check_dependency_policy(pyproject, source_roots)
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1
    print("dependency policy: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
