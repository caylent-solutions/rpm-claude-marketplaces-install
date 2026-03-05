"""Smoke tests verifying the complete test harness works end-to-end.

Exercises all conftest.py fixtures and validates the test pipeline
functions correctly. Each fixture is tested for correct type and behavior.

Make targets that invoke pytest are verified via Makefile recipe parsing
to avoid recursive test collection. make clean is verified via subprocess
since it does not run tests.

Spec Reference: Plan: Per-Repo Tooling — test harness verification.
"""

import os
import pathlib
import subprocess

import pytest

_SUBPROCESS_TIMEOUT = int(os.environ.get("TEST_SUBPROCESS_TIMEOUT", "30"))


@pytest.mark.functional
class TestAllFixturesAvailable:
    """Verify every conftest.py fixture is exercised and returns expected types."""

    def test_repo_root_fixture_returns_path(self, repo_root: pathlib.Path):
        """Given: conftest.py provides repo_root fixture.
        When: A test requests repo_root.
        Then: It returns a Path to an existing directory containing a Makefile.
        Spec: Plan: Test harness
        """
        assert isinstance(repo_root, pathlib.Path), "repo_root must be a pathlib.Path"
        assert repo_root.is_dir(), "repo_root must be an existing directory"
        assert (repo_root / "Makefile").is_file(), "repo_root must contain a Makefile"

    def test_makefile_path_fixture_returns_path(self, makefile_path: pathlib.Path):
        """Given: conftest.py provides makefile_path fixture.
        When: A test requests makefile_path.
        Then: It returns a Path to an existing Makefile.
        Spec: Plan: Test harness
        """
        assert isinstance(makefile_path, pathlib.Path), "makefile_path must be a pathlib.Path"
        assert makefile_path.is_file(), "makefile_path must point to an existing file"
        assert makefile_path.name == "Makefile", "makefile_path must point to a file named Makefile"

    def test_mock_marketplace_dir_fixture_returns_path(self, mock_marketplace_dir: pathlib.Path):
        """Given: conftest.py provides mock_marketplace_dir fixture.
        When: A test requests mock_marketplace_dir.
        Then: It returns a Path to a temp directory with marketplace structure.
        Spec: Plan: Test harness
        """
        assert isinstance(mock_marketplace_dir, pathlib.Path), "mock_marketplace_dir must be a pathlib.Path"
        assert mock_marketplace_dir.is_dir(), "mock_marketplace_dir must be an existing directory"
        subdirs = [p for p in mock_marketplace_dir.iterdir() if p.is_dir()]
        assert len(subdirs) > 0, "mock_marketplace_dir must contain marketplace subdirectories"

    def test_mock_claude_cli_fixture_is_callable(self, mock_claude_cli):
        """Given: conftest.py provides mock_claude_cli fixture.
        When: A test requests mock_claude_cli.
        Then: It is callable and returns a result with expected attributes.
        Spec: Plan: Test harness
        """
        assert callable(mock_claude_cli), "mock_claude_cli must be callable"
        result = mock_claude_cli("--version")
        assert hasattr(result, "returncode"), "mock_claude_cli result must have returncode"
        assert hasattr(result, "stdout"), "mock_claude_cli result must have stdout"
        assert hasattr(result, "stderr"), "mock_claude_cli result must have stderr"


@pytest.mark.functional
class TestMakeTargets:
    """Verify make targets are correctly configured.

    Targets that run pytest (test, test-unit, test-functional, validate) are
    verified via Makefile recipe parsing to avoid recursive test collection.
    make clean is verified via subprocess since it does not invoke pytest.
    """

    def test_make_test_recipe_runs_pytest_with_coverage(self, makefile_path: pathlib.Path):
        """Given: Makefile has a test target.
        When: We inspect the recipe.
        Then: It runs pytest with coverage flags.
        Spec: Plan: Full pipeline
        """
        content = makefile_path.read_text()
        in_test_target = False
        for line in content.splitlines():
            if line.startswith("test:") and "test-unit" not in line and "test-functional" not in line:
                in_test_target = True
                continue
            if in_test_target:
                if line and not line[0].isspace() and not line.startswith("\t"):
                    break
                if "pytest" in line and "--cov" in line:
                    return
        pytest.fail("make test recipe must run pytest with --cov")

    def test_make_test_unit_recipe_uses_marker(self, makefile_path: pathlib.Path):
        """Given: Makefile has a test-unit target.
        When: We inspect the recipe.
        Then: It runs pytest with -m unit.
        Spec: Plan: Test harness
        """
        content = makefile_path.read_text()
        in_target = False
        for line in content.splitlines():
            if line.startswith("test-unit:"):
                in_target = True
                continue
            if in_target:
                if line and not line[0].isspace() and not line.startswith("\t"):
                    break
                if "pytest" in line and "unit" in line:
                    return
        pytest.fail("make test-unit recipe must run pytest -m unit")

    def test_make_test_functional_recipe_uses_marker(self, makefile_path: pathlib.Path):
        """Given: Makefile has a test-functional target.
        When: We inspect the recipe.
        Then: It runs pytest with -m functional.
        Spec: Plan: Test harness
        """
        content = makefile_path.read_text()
        in_target = False
        for line in content.splitlines():
            if line.startswith("test-functional:"):
                in_target = True
                continue
            if in_target:
                if line and not line[0].isspace() and not line.startswith("\t"):
                    break
                if "pytest" in line and "functional" in line:
                    return
        pytest.fail("make test-functional recipe must run pytest -m functional")

    def test_make_validate_depends_on_check_and_test(self, makefile_path: pathlib.Path):
        """Given: Makefile has a validate target.
        When: We inspect its dependencies.
        Then: It depends on check and test.
        Spec: Plan: Full pipeline
        """
        content = makefile_path.read_text()
        for line in content.splitlines():
            if line.startswith("validate:"):
                assert "check" in line, "make validate must depend on check"
                assert "test" in line, "make validate must depend on test"
                return
        pytest.fail("validate target not found in Makefile")

    def test_make_clean_removes_artifacts(self, repo_root: pathlib.Path):
        """Given: Build artifacts may exist.
        When: make clean is run.
        Then: It exits 0 and removes cache directories.
        Spec: Plan: Clean target
        """
        # Create artifacts to verify removal
        for name in ["__pycache__", "htmlcov"]:
            (repo_root / name).mkdir(exist_ok=True)
        (repo_root / ".coverage").write_text("placeholder")

        result = subprocess.run(
            ["make", "clean"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, f"make clean must exit 0: {result.stdout}{result.stderr}"
        assert not (repo_root / "htmlcov").exists(), "htmlcov should be removed after make clean"
        assert not (repo_root / ".coverage").exists(), ".coverage should be removed after make clean"
