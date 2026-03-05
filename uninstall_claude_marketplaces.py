"""Uninstall script for Claude Code marketplace plugins.

Discovers installed plugins and uninstalls them, then removes marketplace
registrations. This module implements the uninstall workflow defined in
spec section 7.7.

Spec Reference:
    Section 7.7: Uninstall script step-by-step process
    Section 7.5: Error handling rules
"""

import logging
import os
import pathlib
import subprocess
import sys

from install_claude_marketplaces import discover_plugins

logger = logging.getLogger(__name__)


def _get_uninstall_timeout() -> int:
    """Read and validate CLAUDE_UNINSTALL_TIMEOUT from environment.

    Returns:
        Timeout value in seconds.

    Exits:
        Calls sys.exit(1) if the value is not a valid positive integer.
    """
    timeout_str = os.environ.get("CLAUDE_UNINSTALL_TIMEOUT", "30")
    try:
        value = int(timeout_str)
    except ValueError:
        logger.error(
            "CLAUDE_UNINSTALL_TIMEOUT must be a positive integer, got: %s",
            timeout_str,
        )
        sys.exit(1)
    if value <= 0:
        logger.error(
            "CLAUDE_UNINSTALL_TIMEOUT must be a positive integer, got: %s",
            timeout_str,
        )
        sys.exit(1)
    return value


def uninstall_plugin(claude_bin: str, plugin_name: str, marketplace_name: str) -> bool:
    """Uninstall a plugin via Claude Code CLI.

    Runs: claude plugin uninstall <plugin_name>@<marketplace_name> --scope user

    Environment:
        CLAUDE_UNINSTALL_TIMEOUT: Subprocess timeout in seconds (default: 30).

    Args:
        claude_bin: Path to claude binary.
        plugin_name: Name of the plugin (from plugin.json).
        marketplace_name: Name of the marketplace (from marketplace.json).

    Returns:
        True if uninstall succeeded, False otherwise.
    """
    timeout = _get_uninstall_timeout()
    plugin_ref = f"{plugin_name}@{marketplace_name}"
    try:
        result = subprocess.run(
            [claude_bin, "plugin", "uninstall", plugin_ref, "--scope", "user"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "Timed out after %d seconds uninstalling plugin %s",
            timeout,
            plugin_ref,
        )
        return False

    if result.returncode != 0:
        logger.error(
            "Failed to uninstall plugin %s: %s",
            plugin_ref,
            result.stderr,
        )
        return False
    return True


def remove_marketplace(claude_bin: str, marketplace_path: pathlib.Path) -> bool:
    """Remove a marketplace registration from Claude Code.

    Runs: claude plugin marketplace remove <absolute-path>

    Environment:
        CLAUDE_UNINSTALL_TIMEOUT: Subprocess timeout in seconds (default: 30).

    Args:
        claude_bin: Path to claude binary.
        marketplace_path: Absolute path to marketplace directory.

    Returns:
        True if removal succeeded, False otherwise.
    """
    timeout = _get_uninstall_timeout()
    try:
        result = subprocess.run(
            [claude_bin, "plugin", "marketplace", "remove", str(marketplace_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "Timed out after %d seconds removing marketplace %s",
            timeout,
            marketplace_path,
        )
        return False

    if result.returncode != 0:
        logger.error(
            "Failed to remove marketplace %s: %s",
            marketplace_path,
            result.stderr,
        )
        return False
    return True


def uninstall_marketplace(claude_bin: str, marketplace_path: pathlib.Path, marketplace_name: str) -> bool:
    """Uninstall all plugins in a marketplace, then remove the marketplace.

    Steps:
        1. Discover plugins using shared discover_plugins()
        2. Uninstall each plugin (log errors, continue)
        3. Remove marketplace registration

    Args:
        claude_bin: Path to claude binary.
        marketplace_path: Path to the marketplace directory.
        marketplace_name: Name of the marketplace.

    Returns:
        True if all operations succeeded, False if any failed.
    """
    any_failures = False

    plugins = discover_plugins(marketplace_path)
    for plugin_name, _plugin_path in plugins:
        success = uninstall_plugin(claude_bin, plugin_name, marketplace_name)
        if not success:
            any_failures = True

    remove_success = remove_marketplace(claude_bin, marketplace_path)
    if not remove_success:
        any_failures = True

    return not any_failures
