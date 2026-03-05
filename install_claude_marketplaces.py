"""Install script for Claude Code marketplace plugins.

Discovers the claude CLI binary, registers marketplace directories,
and installs plugins. This module implements the install workflow
defined in spec section 7.4.

Spec Reference:
    Section 7.4: Install script step-by-step process
    Section 7.5: Error handling rules
"""

import logging
import os
import shutil
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
