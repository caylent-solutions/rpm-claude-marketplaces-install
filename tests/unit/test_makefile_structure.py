"""Tests for Makefile structure and target declarations.

Verifies that the Makefile follows the required structure:
- SHELL := /bin/bash
- .SHELLFLAGS := -euo pipefail -c
- All required targets declared as .PHONY
- help target prints target descriptions
- clean target removes cache artifacts

Spec Reference: Plan: Per-Repo Tooling — Makefile as task runner.
"""

import os
import pathlib
import subprocess

import pytest

_SUBPROCESS_TIMEOUT = int(os.environ.get("TEST_SUBPROCESS_TIMEOUT", "30"))


@pytest.mark.unit
class TestMakefileSyntax:
    """Verify Makefile exists and has valid GNU Make syntax."""

    def test_makefile_exists(self, makefile_path: pathlib.Path):
        """Given: The repo is set up.
        When: We check for the Makefile.
        Then: It exists at the repo root.
        """
        assert makefile_path.is_file(), f"Makefile must exist at {makefile_path}"

    def test_makefile_syntax_valid(self, repo_root: pathlib.Path):
        """Given: The Makefile exists.
        When: make --dry-run is invoked.
        Then: It exits 0 (valid GNU Make syntax).
        Spec: Plan: Makefile
        """
        result = subprocess.run(
            ["make", "--dry-run", "help"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, f"Makefile syntax is invalid: {result.stderr}"

    def test_makefile_has_bash_shell(self, makefile_path: pathlib.Path):
        """Given: The Makefile exists.
        When: We read its contents.
        Then: SHELL := /bin/bash is declared.
        Spec: Plan: Makefile
        """
        content = makefile_path.read_text()
        assert "SHELL := /bin/bash" in content, "Makefile must declare SHELL := /bin/bash"

    def test_makefile_has_shellflags(self, makefile_path: pathlib.Path):
        """Given: The Makefile exists.
        When: We read its contents.
        Then: .SHELLFLAGS := -euo pipefail -c is declared.
        Spec: Plan: Makefile
        """
        content = makefile_path.read_text()
        assert ".SHELLFLAGS := -euo pipefail -c" in content, "Makefile must declare .SHELLFLAGS := -euo pipefail -c"


REQUIRED_PHONY_TARGETS = [
    "lint",
    "format",
    "format-check",
    "check",
    "test",
    "test-unit",
    "test-functional",
    "validate",
    "clean",
    "help",
]


@pytest.mark.unit
class TestMakefilePhonyTargets:
    """Verify all required targets are declared as .PHONY."""

    def test_makefile_has_all_phony_targets(self, makefile_path: pathlib.Path):
        """Given: The Makefile exists.
        When: We parse .PHONY declarations.
        Then: All required targets are declared.
        Spec: Plan: Makefile
        """
        content = makefile_path.read_text()
        phony_targets = set()
        for line in content.splitlines():
            if line.startswith(".PHONY:"):
                targets = line.replace(".PHONY:", "").strip().split()
                phony_targets.update(targets)

        for target in REQUIRED_PHONY_TARGETS:
            assert target in phony_targets, (
                f"Target '{target}' must be declared as .PHONY. Found: {sorted(phony_targets)}"
            )


@pytest.mark.unit
class TestMakefileTargetBehavior:
    """Verify key Makefile targets behave correctly."""

    def test_make_help_prints_output(self, repo_root: pathlib.Path):
        """Given: The Makefile exists with a help target.
        When: make help is run.
        Then: It prints target descriptions (non-empty output).
        Spec: Plan: Makefile
        """
        result = subprocess.run(
            ["make", "help"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, f"make help failed: {result.stderr}"
        assert len(result.stdout.strip()) > 0, "make help must produce non-empty output describing targets"

    def test_validate_depends_on_check_and_test(self, makefile_path: pathlib.Path):
        """Given: The Makefile exists.
        When: We read the validate target.
        Then: It depends on check and test.
        Spec: Plan: Makefile
        """
        content = makefile_path.read_text()
        for line in content.splitlines():
            if line.startswith("validate:"):
                assert "check" in line, "validate target must depend on check"
                assert "test" in line, "validate target must depend on test"
                return
        pytest.fail("validate target not found in Makefile")

    def test_check_depends_on_lint_and_format_check(self, makefile_path: pathlib.Path):
        """Given: The Makefile exists.
        When: We read the check target.
        Then: It depends on lint and format-check.
        Spec: Plan: Makefile
        """
        content = makefile_path.read_text()
        for line in content.splitlines():
            if line.startswith("check:"):
                assert "lint" in line, "check target must depend on lint"
                assert "format-check" in line, "check target must depend on format-check"
                return
        pytest.fail("check target not found in Makefile")

    def test_clean_removes_artifacts(self, repo_root: pathlib.Path):
        """Given: Cache artifacts may exist.
        When: make clean is run.
        Then: __pycache__, .pytest_cache, .ruff_cache, htmlcov, .coverage
              are removed.
        Spec: Plan: Clean target
        """
        # Create artifacts to clean
        artifacts = [
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "htmlcov",
        ]
        for artifact in artifacts:
            artifact_path = repo_root / artifact
            artifact_path.mkdir(exist_ok=True)

        coverage_file = repo_root / ".coverage"
        coverage_file.write_text("placeholder")

        result = subprocess.run(
            ["make", "clean"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, f"make clean failed: {result.stderr}"

        for artifact in artifacts:
            artifact_path = repo_root / artifact
            assert not artifact_path.exists(), f"make clean should remove {artifact}"
        assert not coverage_file.exists(), "make clean should remove .coverage"

    def test_each_target_has_help_comment(self, makefile_path: pathlib.Path):
        """Given: The Makefile exists.
        When: We read target definitions.
        Then: Each target has a ## comment describing its purpose.
        Spec: AC-DOC-1
        """
        content = makefile_path.read_text()
        for target in REQUIRED_PHONY_TARGETS:
            found = False
            for line in content.splitlines():
                if line.startswith(f"{target}:") and "##" in line:
                    found = True
                    break
                if line.startswith(f"{target}:") and "##" not in line:
                    # Target exists but no help comment
                    pytest.fail(f"Target '{target}' exists but has no ## help comment")
            assert found, f"Target '{target}' must have a ## help comment"
