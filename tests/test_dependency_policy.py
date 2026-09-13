"""The dependency guard itself is executable and tested."""

import subprocess
import sys
from pathlib import Path

from scripts.check_dependency_policy import check_dependency_policy

ROOT = Path(__file__).parents[1]


def test_repository_satisfies_dependency_policy() -> None:
    assert check_dependency_policy(
        ROOT / "pyproject.toml", [ROOT / "providers", ROOT / "core"]
    ) == []


def test_runtime_dependency_violation_fails_lint(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "violation"\nversion = "0"\ndependencies = ["httpx>=0.27"]\n',
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check_dependency_policy.py"),
            "--pyproject",
            str(pyproject),
            "--source-root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "runtime dependency 'httpx>=0.27' is not allowlisted" in completed.stderr


def test_nonstdlib_http_client_import_is_rejected(tmp_path: Path) -> None:
    source_root = tmp_path / "providers"
    source_root.mkdir()
    (source_root / "bad.py").write_text("import requests\n", encoding="utf-8")

    violations = check_dependency_policy(ROOT / "pyproject.toml", [source_root])

    assert len(violations) == 1
    assert "HTTP client import 'requests' is disallowed" in violations[0]


def test_missing_runtime_dependency_array_is_rejected(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "invalid"\n', encoding="utf-8")

    violations = check_dependency_policy(pyproject, [])

    assert violations == ["pyproject.toml: project.dependencies must be an array of strings"]
