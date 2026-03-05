"""Install script for Claude Code marketplace plugins.

Discovers the claude CLI binary, registers marketplace directories,
and installs plugins. This module implements the install workflow
defined in spec section 7.4.

Spec Reference:
    Section 7.3: Configuration — env vars, defaults
    Section 7.4: Install script step-by-step process
    Section 7.5: Error handling rules
"""

import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


def locate_claude_binary() -> str:
    """Locate the claude CLI binary on $PATH.

    Uses shutil.which("claude") to find the binary.
    No fallback paths are attempted.

    Returns:
        Absolute path to the claude binary.

    Exits:
        Calls sys.exit(127) if claude is not found on $PATH.
        Logs an error message before exiting.
    """
    path = shutil.which("claude")
    if path is None:
        logger.error("claude binary not found on $PATH. Ensure claude is installed and available.")
        sys.exit(127)
    return os.path.abspath(path)


def get_marketplace_dir() -> pathlib.Path:
    """Return Path to marketplace directory.

    Reads CLAUDE_MARKETPLACES_DIR env var, defaults to $HOME/.claude-marketplaces.
    Does NOT verify existence (caller checks).

    Returns:
        pathlib.Path to the marketplace directory.
    """
    env_value = os.environ.get("CLAUDE_MARKETPLACES_DIR")
    if env_value:
        return pathlib.Path(env_value)
    return pathlib.Path.home() / ".claude-marketplaces"


def verify_marketplace_dir(marketplace_dir: pathlib.Path) -> None:
    """Verify the marketplace directory exists.

    If the directory does not exist, logs a warning and exits with code 0.
    This is not an error — it means no marketplaces are configured.

    Args:
        marketplace_dir: Path to the marketplace directory.

    Exits:
        Calls sys.exit(0) if the directory does not exist.
        Logs a warning before exiting.
    """
    if not marketplace_dir.is_dir():
        logger.warning(
            "Marketplace directory does not exist: %s. No marketplaces to register.",
            marketplace_dir,
        )
        sys.exit(0)


def discover_marketplace_entries(marketplace_dir: pathlib.Path) -> list[pathlib.Path]:
    """Discover marketplace entries in the given directory.

    Returns sorted list of non-hidden entries that are directories or
    symlinks to directories. Hidden entries (dot-prefixed) are excluded.
    Broken symlinks are logged as warnings and excluded.

    Args:
        marketplace_dir: Path to the marketplace directory.

    Returns:
        Alphabetically sorted list of Path objects.
    """
    entries = []
    for entry in sorted(marketplace_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_symlink() and not entry.exists():
            logger.warning("Broken symlink detected and skipped: %s", entry)
            continue
        if entry.is_dir():
            entries.append(entry)
    return entries


def read_marketplace_name(marketplace_path: pathlib.Path) -> str:
    """Read marketplace name from .claude-plugin/marketplace.json.

    Args:
        marketplace_path: Path to the marketplace directory.

    Returns:
        The 'name' field from marketplace.json.

    Raises:
        FileNotFoundError: If marketplace.json does not exist.
        KeyError: If 'name' field is missing.
        json.JSONDecodeError: If file is not valid JSON.
    """
    manifest_path = marketplace_path / ".claude-plugin" / "marketplace.json"
    with manifest_path.open() as f:
        data = json.load(f)
    return data["name"]


def register_marketplace(claude_bin: str, marketplace_path: pathlib.Path) -> bool:
    """Register a marketplace with Claude Code.

    Runs: claude plugin marketplace add <absolute-path>
    Claude Code is idempotent; re-registering is a no-op.

    Fail-fast exception (spec section 7.5, lines 1368-1379):
        Registration failures use log+continue semantics per the spec's
        error handling table: "marketplace add fails → log error, continue
        to next marketplace". The caller MUST check the return value and
        exit non-zero after iterating all marketplaces if any failed.

    Environment:
        CLAUDE_REGISTER_TIMEOUT: Subprocess timeout in seconds (default: 30).

    Args:
        claude_bin: Path to claude binary.
        marketplace_path: Absolute path to marketplace directory.

    Returns:
        True if registration succeeded, False otherwise.
        Caller must track failures and exit non-zero if any returned False.
    """
    timeout_str = os.environ.get("CLAUDE_REGISTER_TIMEOUT", "30")
    try:
        timeout = int(timeout_str)
    except ValueError:
        logger.error(
            "CLAUDE_REGISTER_TIMEOUT must be a positive integer, got: %s",
            timeout_str,
        )
        sys.exit(1)

    try:
        result = subprocess.run(
            [claude_bin, "plugin", "marketplace", "add", str(marketplace_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "Timed out after %d seconds registering marketplace %s",
            timeout,
            marketplace_path,
        )
        return False

    if result.returncode != 0:
        logger.error(
            "Failed to register marketplace %s: %s",
            marketplace_path,
            result.stderr,
        )
        return False
    return True


def discover_plugins(marketplace_path: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    """Discover plugins within a marketplace directory.

    Scans immediate subdirectories for .claude-plugin/plugin.json files.
    Discovery pattern: <marketplace-dir>/*/.claude-plugin/plugin.json

    Subdirectories without .claude-plugin/plugin.json are skipped (not plugins).
    If plugin.json exists but is corrupt or missing the 'name' field,
    the error propagates to the caller (fail-fast).

    Args:
        marketplace_path: Path to the marketplace directory.

    Returns:
        List of (plugin_name, plugin_path) tuples for each discovered plugin.

    Raises:
        json.JSONDecodeError: If plugin.json exists but contains invalid JSON.
        KeyError: If plugin.json exists but lacks the 'name' field.
    """
    plugins = []
    for entry in sorted(marketplace_path.iterdir()):
        if not entry.is_dir():
            continue
        plugin_json = entry / ".claude-plugin" / "plugin.json"
        if not plugin_json.is_file():
            continue
        with plugin_json.open() as f:
            data = json.load(f)
        plugins.append((data["name"], entry))
    return plugins


def install_plugin(claude_bin: str, plugin_name: str, marketplace_name: str) -> bool:
    """Install a plugin via Claude Code CLI.

    Runs: claude plugin install <plugin_name>@<marketplace_name> --scope user

    Environment:
        CLAUDE_INSTALL_TIMEOUT: Subprocess timeout in seconds (default: 30).

    Args:
        claude_bin: Path to claude binary.
        plugin_name: Name of the plugin (from plugin.json).
        marketplace_name: Name of the marketplace (from marketplace.json).

    Returns:
        True if install succeeded, False otherwise.
    """
    timeout_str = os.environ.get("CLAUDE_INSTALL_TIMEOUT", "30")
    try:
        timeout = int(timeout_str)
    except ValueError:
        logger.error(
            "CLAUDE_INSTALL_TIMEOUT must be a positive integer, got: %s",
            timeout_str,
        )
        sys.exit(1)

    plugin_ref = f"{plugin_name}@{marketplace_name}"
    try:
        result = subprocess.run(
            [claude_bin, "plugin", "install", plugin_ref, "--scope", "user"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "Timed out after %d seconds installing plugin %s",
            timeout,
            plugin_ref,
        )
        return False

    if result.returncode != 0:
        logger.error(
            "Failed to install plugin %s: %s",
            plugin_ref,
            result.stderr,
        )
        return False
    return True


def log_summary(
    marketplaces_processed: int,
    marketplaces_registered: int,
    plugins_installed: int,
) -> None:
    """Log a summary of the install run.

    Args:
        marketplaces_processed: Total number of marketplaces processed.
        marketplaces_registered: Number of marketplaces newly registered.
        plugins_installed: Number of plugins successfully installed.
    """
    logger.info(
        "Install summary: %d marketplaces processed, %d registered, %d plugins installed",
        marketplaces_processed,
        marketplaces_registered,
        plugins_installed,
    )


def main() -> int:
    """Orchestrate the install process per spec section 7.4.

    Steps:
        1. Configure logging
        2. Locate claude binary (exit 127 if not found)
        3. Verify marketplace directory (exit 0 if missing)
        4. Discover marketplace entries
        5. Process each marketplace: read name, register, discover plugins, install
        6. Log summary with counts

    Returns:
        0 on success or no work, 1 if any operations failed.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    claude_bin = locate_claude_binary()
    marketplace_dir = get_marketplace_dir()
    verify_marketplace_dir(marketplace_dir)
    entries = discover_marketplace_entries(marketplace_dir)

    if not entries:
        logger.warning("No marketplace entries found. Nothing to do.")
        return 0

    marketplaces_processed = 0
    marketplaces_registered = 0
    plugins_installed = 0
    any_failures = False

    for entry in entries:
        marketplaces_processed += 1
        marketplace_name = read_marketplace_name(entry)

        reg_success = register_marketplace(claude_bin, entry)
        if reg_success:
            marketplaces_registered += 1
        else:
            any_failures = True

        plugins = discover_plugins(entry)
        for plugin_name, _plugin_path in plugins:
            success = install_plugin(claude_bin, plugin_name, marketplace_name)
            if success:
                plugins_installed += 1
            else:
                any_failures = True

    log_summary(marketplaces_processed, marketplaces_registered, plugins_installed)

    if any_failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
