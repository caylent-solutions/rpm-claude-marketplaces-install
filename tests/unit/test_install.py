"""Tests for CLI discovery — locate_claude_binary() function.

Verifies that the install script correctly locates the claude CLI binary
on $PATH using shutil.which, exits 127 when not found, and never attempts
fallback paths.

Spec Reference:
    Section 7.4 Step 3 (lines 1300-1303): Locate Claude Binary
    Section 7.5 (line 1372): Error table — Claude binary not found
    Section 7.3 (lines 1279-1287): No fallback paths
"""

import logging
from unittest import mock

import pytest

from install_claude_marketplaces import locate_claude_binary

MODULE = "install_claude_marketplaces"


@pytest.mark.unit
class TestCLIDiscovery:
    """Tests for locate_claude_binary() per spec sections 7.3, 7.4, 7.5."""

    def test_spec_7_4_step3_claude_binary_found_returns_path(self):
        """Verify locate_claude_binary() returns path when claude is on $PATH.

        Given: shutil.which("claude") returns "/usr/local/bin/claude"
        When: locate_claude_binary() is called
        Then: It returns the absolute path to claude
        Spec: Section 7.4 Step 3
        """
        mock_path = "/usr/local/bin/claude"
        with mock.patch(f"{MODULE}.shutil.which", return_value=mock_path) as mock_which:
            result = locate_claude_binary()
            mock_which.assert_called_once_with("claude")
            assert result == mock_path

    def test_spec_7_4_step3_claude_binary_not_found_exits_127(self):
        """Verify locate_claude_binary() exits 127 when claude is not on $PATH.

        Given: shutil.which("claude") returns None
        When: locate_claude_binary() is called
        Then: SystemExit is raised with code 127
        Spec: Section 7.4 Step 3
        """
        with mock.patch(f"{MODULE}.shutil.which", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                locate_claude_binary()
            assert exc_info.value.code == 127

    def test_spec_7_5_claude_not_found_logs_error_message(self, caplog):
        """Verify error message is logged when claude is not found.

        Given: shutil.which("claude") returns None
        When: locate_claude_binary() is called
        Then: An error log message containing "claude" is produced
        Spec: Section 7.5
        """
        with mock.patch(f"{MODULE}.shutil.which", return_value=None):
            with pytest.raises(SystemExit):
                locate_claude_binary()
            error_messages = [r.message.lower() for r in caplog.records if r.levelno >= logging.ERROR]
            assert any("claude" in msg for msg in error_messages), "Error log message must mention 'claude'"

    def test_spec_7_3_no_fallback_paths_only_shutil_which(self):
        """Verify only shutil.which is used — no fallback discovery mechanisms.

        Given: shutil.which("claude") returns None
        When: locate_claude_binary() is called
        Then: shutil.which is called exactly once with "claude"
              and no subprocess, os.path.exists, or glob calls are made
        Spec: Section 7.3
        """
        with (
            mock.patch(f"{MODULE}.shutil.which", return_value=None) as mock_which,
            mock.patch(
                "subprocess.run",
                side_effect=AssertionError("subprocess.run must not be called"),
            ) as mock_run,
            mock.patch(
                "os.path.exists",
                side_effect=AssertionError("os.path.exists must not be called"),
            ) as mock_exists,
        ):
            with pytest.raises(SystemExit):
                locate_claude_binary()
            mock_which.assert_called_once_with("claude")
            mock_run.assert_not_called()
            mock_exists.assert_not_called()
