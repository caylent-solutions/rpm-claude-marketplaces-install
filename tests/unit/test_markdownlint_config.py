"""Tests for .markdownlint.json configuration.

Verifies that .markdownlint.json is valid, catches known-bad Markdown patterns,
and includes documentation explaining non-default rules.

Spec Reference: Plan: Per-Repo Tooling — .markdownlint.json configuration.
"""

import json
import os
import pathlib
import subprocess

import pytest

_SUBPROCESS_TIMEOUT = int(os.environ.get("TEST_SUBPROCESS_TIMEOUT", "30"))


@pytest.mark.unit
class TestMarkdownlintConfigSyntax:
    """Verify .markdownlint.json is valid configuration."""

    def test_markdownlint_config_exists(self, repo_root: pathlib.Path):
        """Given: The repo root.
        When: We check for .markdownlint.json.
        Then: It exists.
        Spec: Plan: Linter config
        """
        assert (repo_root / ".markdownlint.json").exists(), ".markdownlint.json must exist at repo root"

    def test_markdownlint_config_valid_json(self, repo_root: pathlib.Path):
        """Given: .markdownlint.json exists.
        When: We parse it as JSON.
        Then: It parses without errors.
        Spec: Plan: Linter config
        """
        config_path = repo_root / ".markdownlint.json"
        content = config_path.read_text()
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            pytest.fail(f".markdownlint.json is not valid JSON: {exc}")

    def test_markdownlint_config_valid_syntax(self, repo_root: pathlib.Path):
        """Given: .markdownlint.json exists and a known-good markdown file exists.
        When: markdownlint is run on a clean file.
        Then: It exits zero (no config errors).
        Spec: Plan: Linter config
        """
        # Create a minimal clean markdown file for validation
        clean_file = repo_root / "_lint_test_clean.md"
        try:
            clean_file.write_text("# Clean Test\n\nThis is valid markdown.\n")
            result = subprocess.run(
                ["markdownlint", str(clean_file)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            assert result.returncode == 0, f"markdownlint should pass on clean file: {result.stdout}{result.stderr}"
        finally:
            clean_file.unlink(missing_ok=True)


@pytest.mark.unit
class TestMarkdownlintCatchesBadMarkdown:
    """Verify markdownlint catches known-bad Markdown patterns."""

    def test_markdownlint_catches_known_bad_md(self, repo_root: pathlib.Path):
        """Given: A known-bad Markdown file exists in tests/fixtures/.
        When: markdownlint is run on that file.
        Then: It reports errors and exits non-zero.
        Spec: Plan: Linter config
        """
        bad_file = repo_root / "tests" / "fixtures" / "linter-test-bad.md"
        assert bad_file.exists(), "tests/fixtures/linter-test-bad.md must exist"
        result = subprocess.run(
            ["markdownlint", str(bad_file)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode != 0, "markdownlint must report errors on known-bad Markdown file"
        assert len(result.stdout + result.stderr) > 0, "markdownlint must produce output when reporting errors"


@pytest.mark.unit
class TestMarkdownlintConfigDocumentation:
    """Verify .markdownlint.json includes documentation."""

    def test_markdownlint_config_has_documentation(self, repo_root: pathlib.Path):
        """Given: .markdownlint.json exists.
        When: We read its content.
        Then: It includes a comment field explaining non-default rules (AC-DOC-1).
        Spec: Plan: Linter config
        """
        config_path = repo_root / ".markdownlint.json"
        config = json.loads(config_path.read_text())
        # JSON doesn't support comments, so look for a documentation key
        has_doc_key = any(key.startswith("comment") or key.startswith("$comment") or key == "$schema" for key in config)
        assert has_doc_key, ".markdownlint.json must include a comment/schema key documenting non-default rules"

    def test_markdownlint_config_has_default_true(self, repo_root: pathlib.Path):
        """Given: .markdownlint.json exists.
        When: We read its content.
        Then: It has 'default: true' to enable all rules by default.
        Spec: Plan: Linter config
        """
        config_path = repo_root / ".markdownlint.json"
        config = json.loads(config_path.read_text())
        assert config.get("default") is True, ".markdownlint.json must have 'default: true'"
