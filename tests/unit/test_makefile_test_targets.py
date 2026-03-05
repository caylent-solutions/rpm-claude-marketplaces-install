"""Tests for Makefile test, test-unit, test-functional, and validate targets.

Verifies that test targets invoke pytest with correct arguments and markers,
and that validate composes check + test.

Spec Reference: Plan: Per-Repo Tooling — make test, make test-unit,
make test-functional, make validate.
"""

import pathlib

import pytest


@pytest.mark.unit
class TestMakeTestTarget:
    """Verify make test invokes pytest with coverage."""

    def test_make_test_runs_pytest(self, makefile_path: pathlib.Path):
        """Given: The Makefile test target exists.
        When: We read the test recipe.
        Then: It contains a call to python3 -m pytest with --cov.
        Spec: Plan: Test targets
        """
        content = makefile_path.read_text()
        in_test = False
        for line in content.splitlines():
            if line.startswith("test:") and "test-unit" not in line and "test-functional" not in line:
                in_test = True
                continue
            if in_test:
                if line.startswith("\t"):
                    if "pytest" in line and "--cov" in line:
                        return  # Found pytest with coverage
                else:
                    break
        pytest.fail("test target must invoke 'pytest' with '--cov' but it was not found")

    def test_make_test_includes_coverage_report(self, makefile_path: pathlib.Path):
        """Given: The Makefile test target exists.
        When: We read the test recipe.
        Then: It includes --cov-report for coverage output.
        Spec: Plan: Test targets
        """
        content = makefile_path.read_text()
        in_test = False
        for line in content.splitlines():
            if line.startswith("test:") and "test-unit" not in line and "test-functional" not in line:
                in_test = True
                continue
            if in_test:
                if line.startswith("\t"):
                    if "--cov-report" in line:
                        return
                else:
                    break
        pytest.fail("test target must include '--cov-report' but it was not found")


@pytest.mark.unit
class TestMakeTestUnitTarget:
    """Verify make test-unit uses -m unit marker."""

    def test_make_test_unit_uses_marker(self, makefile_path: pathlib.Path):
        """Given: The Makefile test-unit target exists.
        When: We read the test-unit recipe.
        Then: It contains -m unit.
        Spec: Plan: Test targets
        """
        content = makefile_path.read_text()
        in_target = False
        for line in content.splitlines():
            if line.startswith("test-unit:"):
                in_target = True
                continue
            if in_target:
                if line.startswith("\t"):
                    if "-m unit" in line or "-m 'unit'" in line or '-m "unit"' in line:
                        return
                else:
                    break
        pytest.fail("test-unit target must invoke pytest with '-m unit' but it was not found")


@pytest.mark.unit
class TestMakeTestFunctionalTarget:
    """Verify make test-functional uses -m functional marker."""

    def test_make_test_functional_uses_marker(self, makefile_path: pathlib.Path):
        """Given: The Makefile test-functional target exists.
        When: We read the test-functional recipe.
        Then: It contains -m functional.
        Spec: Plan: Test targets
        """
        content = makefile_path.read_text()
        in_target = False
        for line in content.splitlines():
            if line.startswith("test-functional:"):
                in_target = True
                continue
            if in_target:
                if line.startswith("\t"):
                    if "-m functional" in line or "-m 'functional'" in line or '-m "functional"' in line:
                        return
                else:
                    break
        pytest.fail("test-functional target must invoke pytest with '-m functional' but it was not found")


@pytest.mark.unit
class TestMakeValidateTarget:
    """Verify make validate composes check + test."""

    def test_make_validate_runs_check_and_test(self, makefile_path: pathlib.Path):
        """Given: The Makefile validate target exists.
        When: We read the validate target.
        Then: It depends on both check and test.
        Spec: Plan: Validate target
        """
        content = makefile_path.read_text()
        for line in content.splitlines():
            if line.startswith("validate:"):
                assert "check" in line, "validate must depend on check"
                assert "test" in line, "validate must depend on test"
                return
        pytest.fail("validate target not found in Makefile")


@pytest.mark.unit
class TestPyprojectConfig:
    """Verify pyproject.toml pytest configuration."""

    def test_pytest_markers_registered(self, repo_root: pathlib.Path):
        """Given: pyproject.toml exists with pytest config.
        When: We read the markers section.
        Then: unit and functional markers are registered.
        Spec: Plan: Pytest config
        """
        pyproject = repo_root / "pyproject.toml"
        assert pyproject.exists(), "pyproject.toml must exist"
        content = pyproject.read_text()
        assert "unit" in content, "unit marker must be registered in pyproject.toml"
        assert "functional" in content, "functional marker must be registered in pyproject.toml"

    def test_pytest_testpaths_configured(self, repo_root: pathlib.Path):
        """Given: pyproject.toml exists.
        When: We read pytest configuration.
        Then: testpaths is set to tests directory.
        Spec: Plan: Pytest config
        """
        pyproject = repo_root / "pyproject.toml"
        content = pyproject.read_text()
        assert "testpaths" in content, "testpaths must be configured in pyproject.toml"
        assert '"tests"' in content or "'tests'" in content, "testpaths must include 'tests' directory"

    def test_coverage_configured(self, repo_root: pathlib.Path):
        """Given: pyproject.toml exists.
        When: We read coverage configuration.
        Then: coverage source and omit are configured.
        Spec: Plan: Pytest config
        """
        pyproject = repo_root / "pyproject.toml"
        content = pyproject.read_text()
        assert "[tool.coverage.run]" in content, "coverage.run section must exist in pyproject.toml"
        assert "omit" in content, "coverage must omit test files"

    def test_pyproject_has_marker_comments(self, repo_root: pathlib.Path):
        """Given: pyproject.toml exists with pytest config.
        When: We read the markers section.
        Then: Comments explain marker usage (AC-DOC-1).
        Spec: Plan: Pytest config
        """
        pyproject = repo_root / "pyproject.toml"
        content = pyproject.read_text()
        # Find the markers section and check for documenting comments
        in_markers = False
        has_comment = False
        for line in content.splitlines():
            if "markers" in line:
                in_markers = True
            if in_markers and line.strip().startswith("#"):
                has_comment = True
                break
            if in_markers and line.strip() == "]":
                break
        assert has_comment, "pyproject.toml markers section must include comments explaining marker usage (AC-DOC-1)"
