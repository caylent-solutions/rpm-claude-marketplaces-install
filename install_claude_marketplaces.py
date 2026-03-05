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


def register_all_marketplaces(claude_bin: str, entries: list[pathlib.Path]) -> None:
    """Register all marketplace entries, exiting non-zero if any fail.

    Iterates over marketplace entries, attempts registration for each,
    and tracks failures. Per spec section 7.5, individual registration
    failures are logged and skipped so all marketplaces get a chance.
    After all attempts, exits non-zero if any registration failed.

    Args:
        claude_bin: Path to claude binary.
        entries: List of marketplace directory paths to register.

    Exits:
        Calls sys.exit(1) if one or more registrations failed.
    """
    failures = []
    for entry in entries:
        success = register_marketplace(claude_bin, entry)
        if not success:
            failures.append(entry)

    if failures:
        logger.error(
            "Failed to register %d marketplace(s): %s",
            len(failures),
            ", ".join(str(f) for f in failures),
        )
        sys.exit(1)
