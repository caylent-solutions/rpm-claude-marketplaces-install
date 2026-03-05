"""Shared pytest fixtures for rpm-claude-marketplaces-install."""

import pathlib

import pytest


@pytest.fixture()
def repo_root() -> pathlib.Path:
    """Return the root directory of the repository."""
    return pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture()
def makefile_path(repo_root: pathlib.Path) -> pathlib.Path:
    """Return the path to the Makefile."""
    return repo_root / "Makefile"
