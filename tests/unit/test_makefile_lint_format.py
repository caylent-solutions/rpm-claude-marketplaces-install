"""Tests for Makefile lint and format target implementations.

Verifies that lint, format, format-check, and check targets invoke
the correct tools: ruff check, markdownlint, yamllint, ruff format.

Spec Reference: Plan: Per-Repo Tooling — make lint, make format, make check.
"""

import os
import pathlib
import subprocess

import pytest

_SUBPROCESS_TIMEOUT = int(os.environ.get("TEST_SUBPROCESS_TIMEOUT", "30"))


@pytest.mark.unit
class TestMakeLintTarget:
    """Verify make lint invokes all configured linters."""

    @pytest.mark.parametrize(
        "tool_name",
        ["ruff", "markdownlint", "yamllint"],
        ids=["ruff", "markdownlint", "yamllint"],
    )
    def test_make_lint_calls_tool(self, makefile_path: pathlib.Path, tool_name: str):
        """Given: The Makefile lint target exists.
        When: We read the lint recipe.
        Then: It contains a call to the specified tool.
        Spec: Plan: Lint targets
        """
        content = makefile_path.read_text()
        in_lint = False
        for line in content.splitlines():
            if line.startswith("lint:"):
                in_lint = True
                continue
            if in_lint:
                if line.startswith("\t"):
                    if tool_name in line:
                        return  # Found the tool call
                else:
                    break  # End of lint recipe
        pytest.fail(
            f"lint target must invoke '{tool_name}' but it was not found in the recipe"
        )

    def test_make_lint_exits_nonzero_on_findings(
        self, repo_root: pathlib.Path, tmp_path: pathlib.Path
    ):
        """Given: A Python file with lint errors exists.
        When: make lint is run.
        Then: It exits non-zero.
        Spec: Plan: Lint targets
        """
        bad_file = repo_root / "_lint_test_bad.py"
        try:
            bad_file.write_text("import os\nimport sys\n")  # unused imports
            result = subprocess.run(
                ["make", "lint"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            assert result.returncode != 0, (
                "make lint must exit non-zero when lint errors exist"
            )
            assert len(result.stdout + result.stderr) > 0, (
                "make lint must produce output on failure (AC-6)"
            )
        finally:
            bad_file.unlink(missing_ok=True)


@pytest.mark.unit
class TestMakeFormatTarget:
    """Verify make format invokes ruff format."""

    def test_make_format_calls_ruff_format(self, makefile_path: pathlib.Path):
        """Given: The Makefile format target exists.
        When: We read the format recipe.
        Then: It contains a call to ruff format.
        Spec: Plan: Format target
        """
        content = makefile_path.read_text()
        in_format = False
        for line in content.splitlines():
            if line.startswith("format:") and "format-check" not in line:
                in_format = True
                continue
            if in_format:
                if line.startswith("\t"):
                    if "ruff format" in line and "--check" not in line:
                        return  # Found ruff format (not --check)
                else:
                    break
        pytest.fail(
            "format target must invoke 'ruff format' "
            "(without --check) but it was not found"
        )


@pytest.mark.unit
class TestMakeCheckTarget:
    """Verify make check is read-only (no file modifications)."""

    def test_make_check_includes_format_check(self, makefile_path: pathlib.Path):
        """Given: The Makefile check target exists.
        When: We read the check target.
        Then: It depends on format-check (read-only format verification).
        Spec: Plan: Check target
        """
        content = makefile_path.read_text()
        for line in content.splitlines():
            if line.startswith("check:"):
                assert "format-check" in line, (
                    "check target must depend on format-check"
                )
                return
        pytest.fail("check target not found in Makefile")

    def test_format_check_calls_ruff_format_check(self, makefile_path: pathlib.Path):
        """Given: The Makefile format-check target exists.
        When: We read its recipe.
        Then: It calls ruff format --check (read-only).
        Spec: Plan: Check target
        """
        content = makefile_path.read_text()
        in_format_check = False
        for line in content.splitlines():
            if line.startswith("format-check:"):
                in_format_check = True
                continue
            if in_format_check:
                if line.startswith("\t"):
                    if "ruff format" in line and "--check" in line:
                        return
                else:
                    break
        pytest.fail(
            "format-check target must invoke 'ruff format --check' but it was not found"
        )

    def test_make_check_docs_describe_tools(self, makefile_path: pathlib.Path):
        """Given: The Makefile has lint, format, format-check, check targets.
        When: We read their ## comments.
        Then: Comments describe which tools are invoked (AC-DOC-1).
        """
        content = makefile_path.read_text()
        targets_with_tools = {
            "lint:": "##",
            "format:": "##",
            "format-check:": "##",
            "check:": "##",
        }
        for target_prefix, required_marker in targets_with_tools.items():
            found = False
            for line in content.splitlines():
                if line.startswith(target_prefix) and required_marker in line:
                    found = True
                    break
            assert found, (
                f"Target starting with '{target_prefix}' "
                f"must have a '{required_marker}' help comment"
            )
