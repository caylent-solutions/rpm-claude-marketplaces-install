"""Tests for shared pytest fixtures in conftest.py.

Verifies that mock_marketplace_dir and mock_claude_cli fixtures work correctly,
use tmp_path for isolation, and are accessible from test files.

Spec Reference: Plan: Per-Repo Tooling — tests/conftest.py with shared fixtures.
"""

import pathlib

import pytest


@pytest.mark.unit
class TestMockMarketplaceDir:
    """Verify mock_marketplace_dir fixture creates expected structure."""

    def test_mock_marketplace_dir_creates_structure(self, mock_marketplace_dir: pathlib.Path):
        """Given: conftest.py provides mock_marketplace_dir fixture.
        When: A test requests mock_marketplace_dir.
        Then: It returns a Path to a directory with marketplace structure.
        Spec: Plan: Test harness
        """
        assert mock_marketplace_dir.is_dir(), "mock_marketplace_dir must be a directory"
        # Should contain at least one subdirectory representing a marketplace
        subdirs = [p for p in mock_marketplace_dir.iterdir() if p.is_dir()]
        assert len(subdirs) > 0, "mock_marketplace_dir must contain at least one marketplace subdirectory"

    def test_mock_marketplace_dir_uses_tmp_path(self, mock_marketplace_dir: pathlib.Path, tmp_path: pathlib.Path):
        """Given: mock_marketplace_dir fixture uses tmp_path for isolation.
        When: We check the path.
        Then: It is under a temporary directory (not a hardcoded path).
        Spec: Plan: Test harness
        """
        # The fixture should create its structure under tmp_path
        # tmp_path is unique per test, so mock_marketplace_dir should be under a temp dir
        assert "/tmp" in str(mock_marketplace_dir) or "tmp" in str(mock_marketplace_dir).lower(), (
            "mock_marketplace_dir must be under a temporary directory for isolation"
        )

    def test_mock_marketplace_dir_has_plugin_structure(self, mock_marketplace_dir: pathlib.Path):
        """Given: mock_marketplace_dir creates a sample marketplace.
        When: We inspect the marketplace subdirectory.
        Then: It contains expected files (e.g., a plugin manifest or marker file).
        Spec: Plan: Test harness
        """
        subdirs = [p for p in mock_marketplace_dir.iterdir() if p.is_dir()]
        # Each marketplace subdirectory should have some content
        for subdir in subdirs:
            files = list(subdir.iterdir())
            assert len(files) > 0, f"Marketplace subdirectory {subdir.name} must contain files"


@pytest.mark.unit
class TestMockClaudeCli:
    """Verify mock_claude_cli fixture provides a callable mock."""

    def test_mock_claude_cli_is_callable(self, mock_claude_cli):
        """Given: conftest.py provides mock_claude_cli fixture.
        When: A test requests mock_claude_cli.
        Then: It is callable.
        Spec: Plan: Test harness
        """
        assert callable(mock_claude_cli), "mock_claude_cli must be callable"

    def test_mock_claude_cli_returns_result(self, mock_claude_cli):
        """Given: mock_claude_cli is callable.
        When: Called with arguments.
        Then: It returns a result object with returncode, stdout, and stderr attributes.
        Spec: Plan: Test harness
        """
        result = mock_claude_cli("--version")
        assert hasattr(result, "returncode"), "mock_claude_cli result must have returncode"
        assert hasattr(result, "stdout"), "mock_claude_cli result must have stdout"
        assert hasattr(result, "stderr"), "mock_claude_cli result must have stderr"

    def test_mock_claude_cli_default_success(self, mock_claude_cli):
        """Given: mock_claude_cli with default behavior.
        When: Called without configuring failure.
        Then: Returns returncode 0 (success).
        Spec: Plan: Test harness
        """
        result = mock_claude_cli("--version")
        assert result.returncode == 0, "mock_claude_cli should default to success (returncode 0)"
