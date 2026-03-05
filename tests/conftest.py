"""Shared pytest fixtures for rpm-claude-marketplaces-install.

Provides common fixtures for testing install/uninstall scripts:
- repo_root / makefile_path: repository path fixtures
- mock_marketplace_dir: temporary directory with sample marketplace structure
- mock_claude_cli: callable mock simulating the claude CLI
- claude_bin: configurable path to the claude binary for tests
"""

import pathlib
import types

import pytest


@pytest.fixture()
def repo_root() -> pathlib.Path:
    """Return the root directory of the repository."""
    return pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture()
def makefile_path(repo_root: pathlib.Path) -> pathlib.Path:
    """Return the path to the Makefile."""
    return repo_root / "Makefile"


@pytest.fixture()
def mock_marketplace_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a temporary directory with sample marketplace structure.

    Returns:
        pathlib.Path: Path to the temporary marketplace root directory
            containing a sample marketplace subdirectory with plugin files.

    Example usage::

        def test_install_reads_marketplace(mock_marketplace_dir):
            plugins = list(mock_marketplace_dir.glob("*/plugin.json"))
            assert len(plugins) > 0
    """
    marketplace = tmp_path / "sample-marketplace"
    marketplace.mkdir()
    plugin_manifest = marketplace / "plugin.json"
    plugin_manifest.write_text('{"name": "sample-plugin", "version": "0.1.0"}')
    readme = marketplace / "README.md"
    readme.write_text("# Sample Plugin\n\nA sample marketplace plugin for testing.\n")
    return tmp_path


@pytest.fixture()
def mock_claude_cli():
    """Provide a callable mock that simulates the claude CLI.

    The mock returns a result object with returncode, stdout, and stderr
    attributes, defaulting to a successful (returncode=0) invocation.

    Returns:
        Callable: A function accepting CLI arguments that returns a
            SimpleNamespace with returncode, stdout, and stderr.

    Example usage::

        def test_install_calls_claude(mock_claude_cli):
            result = mock_claude_cli("--version")
            assert result.returncode == 0
    """

    def _mock_cli(*args: str) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            returncode=0,
            stdout="mock claude output",
            stderr="",
        )

    return _mock_cli


@pytest.fixture()
def claude_bin(tmp_path: pathlib.Path) -> str:
    """Provide a dynamically constructed path to the claude binary for tests.

    Returns a path under tmp_path so it is unique per test and never
    hard-codes a real filesystem location.
    """
    return str(tmp_path / "bin" / "claude")
