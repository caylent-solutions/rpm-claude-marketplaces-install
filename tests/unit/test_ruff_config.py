"""Tests for ruff.toml configuration.

Verifies that ruff.toml is valid, catches known-bad Python patterns,
and includes documentation comments for non-default rule selections.

Spec Reference: Plan: Per-Repo Tooling — ruff.toml configuration.
"""

import os
import pathlib
import subprocess

import pytest

_SUBPROCESS_TIMEOUT = int(os.environ.get("TEST_SUBPROCESS_TIMEOUT", "30"))


@pytest.mark.unit
class TestRuffConfigSyntax:
    """Verify ruff.toml is valid ruff configuration."""

    def test_ruff_config_exists(self, repo_root: pathlib.Path):
        """Given: The repo root.
        When: We check for ruff.toml.
        Then: It exists.
        Spec: Plan: Linter config
        """
        assert (repo_root / "ruff.toml").exists(), "ruff.toml must exist at repo root"

    def test_ruff_config_valid_syntax(self, repo_root: pathlib.Path):
        """Given: ruff.toml exists at repo root.
        When: ruff check is run from the repo root (auto-discovers ruff.toml).
        Then: It does not report configuration errors.
        Spec: Plan: Linter config
        """
        result = subprocess.run(
            ["ruff", "check", "--preview", str(repo_root / "ruff.toml")],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        # ruff.toml is not Python, so check exits 0 (nothing to lint)
        # A config error would exit non-zero with "Invalid config" message
        assert "invalid" not in result.stderr.lower(), f"ruff.toml has invalid configuration: {result.stderr}"

    def test_ruff_check_runs_clean_on_repo(self, repo_root: pathlib.Path):
        """Given: ruff.toml exists and the repo has clean code.
        When: ruff check . is run.
        Then: It exits zero (no violations in committed code).
        Spec: Plan: Linter config
        """
        result = subprocess.run(
            ["ruff", "check", "."],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, f"ruff check should pass on clean repo: {result.stdout}"

    def test_ruff_format_check_runs_clean(self, repo_root: pathlib.Path):
        """Given: ruff.toml exists and code is formatted.
        When: ruff format --check . is run.
        Then: It exits zero (all files formatted).
        Spec: Plan: Linter config
        """
        result = subprocess.run(
            ["ruff", "format", "--check", "."],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, f"ruff format --check should pass: {result.stdout}"


@pytest.mark.unit
class TestRuffCatchesBadPython:
    """Verify ruff catches known-bad Python patterns."""

    def test_ruff_catches_known_bad_python(self, repo_root: pathlib.Path):
        """Given: A known-bad Python file exists in tests/fixtures/.
        When: ruff check is run on that file.
        Then: It reports errors and exits non-zero.
        Spec: Plan: Linter config
        """
        bad_file = repo_root / "tests" / "fixtures" / "linter-test-bad.py"
        assert bad_file.exists(), "tests/fixtures/linter-test-bad.py must exist"
        result = subprocess.run(
            ["ruff", "check", str(bad_file)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode != 0, "ruff check must report errors on known-bad Python file"
        assert len(result.stdout + result.stderr) > 0, "ruff must produce output when reporting errors"


@pytest.mark.unit
class TestRuffConfigDocumentation:
    """Verify ruff.toml includes documentation comments."""

    def test_ruff_toml_has_comments(self, repo_root: pathlib.Path):
        """Given: ruff.toml exists.
        When: We read its content.
        Then: It includes comments explaining non-default rule selections (AC-DOC-1).
        Spec: Plan: Linter config
        """
        content = (repo_root / "ruff.toml").read_text()
        comment_lines = [line for line in content.splitlines() if line.strip().startswith("#")]
        assert len(comment_lines) >= 2, "ruff.toml must include comments explaining non-default rule selections"

    def test_ruff_toml_has_target_version(self, repo_root: pathlib.Path):
        """Given: ruff.toml exists.
        When: We read its content.
        Then: It specifies a target Python version.
        Spec: Plan: Linter config
        """
        content = (repo_root / "ruff.toml").read_text()
        assert "target-version" in content, "ruff.toml must specify target-version"

    def test_ruff_toml_has_line_length(self, repo_root: pathlib.Path):
        """Given: ruff.toml exists.
        When: We read its content.
        Then: It specifies a line length.
        Spec: Plan: Linter config
        """
        content = (repo_root / "ruff.toml").read_text()
        assert "line-length" in content, "ruff.toml must specify line-length"

    def test_ruff_toml_has_rule_selections(self, repo_root: pathlib.Path):
        """Given: ruff.toml exists.
        When: We read its content.
        Then: It has lint rule selections.
        Spec: Plan: Linter config
        """
        content = (repo_root / "ruff.toml").read_text()
        assert "select" in content, "ruff.toml must have lint rule selections"
