"""Tests for .yamllint.yml configuration.

Verifies that .yamllint.yml is valid, catches known-bad YAML patterns,
and includes documentation comments for non-default rule choices.

Spec Reference: Plan: Per-Repo Tooling — .yamllint.yml configuration.
"""

import os
import pathlib
import subprocess

import pytest

_SUBPROCESS_TIMEOUT = int(os.environ.get("TEST_SUBPROCESS_TIMEOUT", "30"))


@pytest.mark.unit
class TestYamllintConfigSyntax:
    """Verify .yamllint.yml is valid yamllint configuration."""

    def test_yamllint_config_exists(self, repo_root: pathlib.Path):
        """Given: The repo root.
        When: We check for .yamllint.yml.
        Then: It exists.
        Spec: Plan: Linter config
        """
        assert (repo_root / ".yamllint.yml").exists(), ".yamllint.yml must exist at repo root"

    def test_yamllint_config_valid_syntax(self, repo_root: pathlib.Path):
        """Given: .yamllint.yml exists at repo root.
        When: yamllint is run on the config file itself (which is valid YAML).
        Then: It exits zero.
        Spec: Plan: Linter config
        """
        result = subprocess.run(
            ["yamllint", str(repo_root / ".yamllint.yml")],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, f"yamllint config should be valid YAML: {result.stdout}{result.stderr}"

    def test_yamllint_runs_clean_on_repo(self, repo_root: pathlib.Path):
        """Given: .yamllint.yml exists and repo YAML files are clean.
        When: yamllint . is run.
        Then: It exits zero.
        Spec: Plan: Linter config
        """
        result = subprocess.run(
            ["yamllint", "."],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, f"yamllint should pass on clean repo: {result.stdout}{result.stderr}"


@pytest.mark.unit
class TestYamllintCatchesBadYaml:
    """Verify yamllint catches known-bad YAML patterns."""

    def test_yamllint_catches_known_bad_yaml(self, repo_root: pathlib.Path):
        """Given: A known-bad YAML file exists in tests/fixtures/.
        When: yamllint is run on that file.
        Then: It reports errors and exits non-zero.
        Spec: Plan: Linter config
        """
        bad_file = repo_root / "tests" / "fixtures" / "linter-test-bad.yml"
        assert bad_file.exists(), "tests/fixtures/linter-test-bad.yml must exist"
        result = subprocess.run(
            ["yamllint", str(bad_file)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode != 0, "yamllint must report errors on known-bad YAML file"
        assert len(result.stdout + result.stderr) > 0, "yamllint must produce output when reporting errors"


@pytest.mark.unit
class TestYamllintConfigDocumentation:
    """Verify .yamllint.yml includes documentation comments."""

    def test_yamllint_config_has_comments(self, repo_root: pathlib.Path):
        """Given: .yamllint.yml exists.
        When: We read its content.
        Then: It includes comments explaining non-default rule choices (AC-DOC-1).
        Spec: Plan: Linter config
        """
        content = (repo_root / ".yamllint.yml").read_text()
        comment_lines = [line for line in content.splitlines() if line.strip().startswith("#")]
        assert len(comment_lines) >= 2, ".yamllint.yml must include comments explaining non-default rule choices"

    def test_yamllint_config_extends_default(self, repo_root: pathlib.Path):
        """Given: .yamllint.yml exists.
        When: We read its content.
        Then: It extends the default ruleset.
        Spec: Plan: Linter config
        """
        content = (repo_root / ".yamllint.yml").read_text()
        assert "extends: default" in content, ".yamllint.yml must extend the default ruleset"
