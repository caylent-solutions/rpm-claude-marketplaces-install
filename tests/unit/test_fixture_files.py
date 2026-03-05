"""Tests for test fixture files in tests/fixtures/.

Verifies that fixture files exist, are syntactically valid, and are
loadable by conftest.py fixtures for use in testing install/uninstall scripts.

Spec Reference: Plan: Per-Repo Tooling — tests/fixtures/ with initial test data.
"""

import json
import pathlib

import pytest


@pytest.mark.unit
class TestFixtureFilesExist:
    """Verify all expected fixture files are present."""

    def test_sample_marketplace_dir_exists(self, repo_root: pathlib.Path):
        """Given: tests/fixtures/ directory.
        When: We check for sample-marketplace/.
        Then: It exists as a directory.
        Spec: Plan: Test fixtures
        """
        path = repo_root / "tests" / "fixtures" / "sample-marketplace"
        assert path.is_dir(), "tests/fixtures/sample-marketplace/ must exist"

    def test_sample_marketplace_plugin_json_exists(self, repo_root: pathlib.Path):
        """Given: tests/fixtures/sample-marketplace/.
        When: We check for plugin.json.
        Then: It exists.
        Spec: Plan: Test fixtures
        """
        path = repo_root / "tests" / "fixtures" / "sample-marketplace" / "plugin.json"
        assert path.is_file(), "tests/fixtures/sample-marketplace/plugin.json must exist"

    def test_sample_marketplace_readme_exists(self, repo_root: pathlib.Path):
        """Given: tests/fixtures/sample-marketplace/.
        When: We check for README.md.
        Then: It exists.
        Spec: Plan: Test fixtures
        """
        path = repo_root / "tests" / "fixtures" / "sample-marketplace" / "README.md"
        assert path.is_file(), "tests/fixtures/sample-marketplace/README.md must exist"

    def test_fixtures_readme_exists(self, repo_root: pathlib.Path):
        """Given: tests/fixtures/ directory.
        When: We check for README.md.
        Then: It exists documenting the fixtures.
        Spec: Plan: Test fixtures
        """
        path = repo_root / "tests" / "fixtures" / "README.md"
        assert path.is_file(), "tests/fixtures/README.md must exist"


@pytest.mark.unit
class TestFixtureFilesValidSyntax:
    """Verify fixture files are syntactically valid."""

    def test_plugin_json_valid_syntax(self, repo_root: pathlib.Path):
        """Given: sample-marketplace/plugin.json exists.
        When: We parse it as JSON.
        Then: It parses without error and contains expected keys.
        Spec: Plan: Test fixtures
        """
        path = repo_root / "tests" / "fixtures" / "sample-marketplace" / "plugin.json"
        content = json.loads(path.read_text())
        assert "name" in content, "plugin.json must have a 'name' field"
        assert "version" in content, "plugin.json must have a 'version' field"

    def test_plugin_json_has_realistic_data(self, repo_root: pathlib.Path):
        """Given: sample-marketplace/plugin.json is valid JSON.
        When: We inspect the values.
        Then: They represent realistic marketplace plugin metadata.
        Spec: Plan: Test fixtures
        """
        path = repo_root / "tests" / "fixtures" / "sample-marketplace" / "plugin.json"
        content = json.loads(path.read_text())
        assert isinstance(content["name"], str), "plugin name must be a string"
        assert len(content["name"]) > 0, "plugin name must not be empty"
        assert isinstance(content["version"], str), "plugin version must be a string"
        assert len(content["version"]) > 0, "plugin version must not be empty"


@pytest.mark.unit
class TestFixtureFilesLoadableByConftest:
    """Verify fixture files are compatible with conftest.py fixtures."""

    def test_mock_marketplace_dir_matches_fixture_structure(
        self, mock_marketplace_dir: pathlib.Path, repo_root: pathlib.Path
    ):
        """Given: mock_marketplace_dir fixture creates a marketplace.
        When: We compare its structure to the on-disk sample-marketplace fixture.
        Then: Both have the same file types (plugin.json, README.md).
        Spec: Plan: Test fixtures
        """
        on_disk = repo_root / "tests" / "fixtures" / "sample-marketplace"
        on_disk_files = {p.name for p in on_disk.iterdir() if p.is_file()}
        mock_dir = list(mock_marketplace_dir.iterdir())[0]  # first marketplace subdir
        mock_files = {p.name for p in mock_dir.iterdir() if p.is_file()}
        assert on_disk_files == mock_files, (
            f"On-disk fixture files {on_disk_files} must match mock fixture files {mock_files}"
        )

    def test_fixture_plugin_json_loadable_as_dict(self, repo_root: pathlib.Path):
        """Given: sample-marketplace/plugin.json exists.
        When: Loaded via json.loads.
        Then: Returns a dict suitable for use in tests.
        Spec: Plan: Test fixtures
        """
        path = repo_root / "tests" / "fixtures" / "sample-marketplace" / "plugin.json"
        content = json.loads(path.read_text())
        assert isinstance(content, dict), "plugin.json must parse to a dict"
