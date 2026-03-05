"""Tests for uninstall script — plugin uninstall and marketplace removal.

Verifies that the uninstall script correctly discovers installed plugins,
uninstalls each plugin, removes marketplace registrations, and handles
errors per spec 7.5 error table.

Spec Reference:
    Section 7.7 Step 4b-4c (lines 1400-1401): Discover plugins, uninstall each
    Section 7.5 (lines 1368-1379): Error handling rules
"""

import json
import logging
import pathlib
import subprocess
from unittest import mock

import pytest

MODULE = "uninstall_claude_marketplaces"


def _setup_marketplace_with_plugins(
    marketplace_path: pathlib.Path,
    marketplace_name: str,
    plugin_names: list[str],
) -> None:
    """Create marketplace directory with marketplace.json and plugin subdirs."""
    meta_dir = marketplace_path / ".claude-plugin"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "marketplace.json").write_text(json.dumps({"name": marketplace_name}))
    for plugin_name in plugin_names:
        plugin_dir = marketplace_path / plugin_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_meta = plugin_dir / ".claude-plugin"
        plugin_meta.mkdir(parents=True, exist_ok=True)
        (plugin_meta / "plugin.json").write_text(json.dumps({"name": plugin_name}))


@pytest.fixture()
def claude_bin():
    """Provide a configurable path to the claude binary for tests."""
    return "/usr/local/bin/claude"


@pytest.mark.unit
class TestPluginUninstall:
    """Tests for plugin uninstall functionality (spec 7.7 step 4c)."""

    def test_spec_7_7_step4c_uninstall_plugin_success(self, claude_bin):
        """Verify: uninstall_plugin() returns True on success.

        Given: A mocked CLI that returns exit code 0
        When: uninstall_plugin() is called
        Then: Returns True
        Spec: Section 7.7 Step 4c
        """
        from uninstall_claude_marketplaces import uninstall_plugin

        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = uninstall_plugin(claude_bin, "test-plugin", "test-market")
        assert result is True, "Must return True on successful uninstall"

    def test_spec_7_7_step4c_uninstall_plugin_correct_command(self, claude_bin):
        """Verify: uninstall_plugin() runs the correct subprocess command.

        Given: A mocked CLI
        When: uninstall_plugin() is called with plugin and marketplace names
        Then: Subprocess is called with 'claude plugin uninstall <name>@<market> --scope user'
        Spec: Section 7.7 Step 4c
        """
        from uninstall_claude_marketplaces import uninstall_plugin

        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result) as mock_run:
            uninstall_plugin(claude_bin, "my-plugin", "my-market")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == [claude_bin, "plugin", "uninstall", "my-plugin@my-market", "--scope", "user"]

    def test_spec_7_7_step4c_uninstall_plugin_failure_returns_false(self, claude_bin, caplog):
        """Verify: uninstall_plugin() returns False on failure without raising.

        Given: A mocked CLI that returns non-zero exit code
        When: uninstall_plugin() is called
        Then: Returns False AND logs ERROR (does not raise)
        Spec: Section 7.7 Step 4c, Section 7.5 error handling
        """
        from uninstall_claude_marketplaces import uninstall_plugin

        mock_result = mock.Mock(returncode=1, stdout="", stderr="uninstall error")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = uninstall_plugin(claude_bin, "bad-plugin", "test-market")
        assert result is False, "Must return False on failure (not raise)"
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1, "Must log at ERROR level"

    def test_spec_7_7_step4c_uninstall_plugin_failure_continues(self, claude_bin, caplog):
        """Verify: Failed uninstall logs error and caller can continue processing.

        Given: A mocked CLI that fails for one plugin
        When: uninstall_plugin() is called
        Then: Returns False with ERROR log, allowing caller to continue
        Spec: Section 7.5 — plugin uninstall fails → log error, continue
        """
        from uninstall_claude_marketplaces import uninstall_plugin

        mock_result = mock.Mock(returncode=1, stdout="", stderr="not installed")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = uninstall_plugin(claude_bin, "missing-plugin", "test-market")
        assert result is False, "Must return False (not raise)"
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("missing-plugin" in r.message for r in error_records), "Error log must include plugin name"

    def test_spec_7_7_uninstall_already_uninstalled_noop(self, claude_bin):
        """Verify: Uninstalling an already-uninstalled plugin is a no-op.

        Given: A mocked CLI that returns success (already uninstalled)
        When: uninstall_plugin() is called
        Then: Returns True (CLI treats re-uninstall as success)
        Spec: Section 7.7 — idempotent uninstall
        """
        from uninstall_claude_marketplaces import uninstall_plugin

        mock_result = mock.Mock(returncode=0, stdout="already uninstalled", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = uninstall_plugin(claude_bin, "already-gone", "test-market")
        assert result is True, "Already-uninstalled plugin should succeed (no-op)"

    def test_spec_7_7_uninstall_order_plugins_before_marketplace(self, tmp_path, claude_bin, caplog):
        """Verify: Plugins are uninstalled before marketplace is removed.

        Given: A marketplace with two plugins
        When: The uninstall orchestrator processes the marketplace
        Then: Plugin uninstall commands precede marketplace remove command
        Spec: Section 7.7 — uninstall order
        """
        from uninstall_claude_marketplaces import uninstall_marketplace

        marketplace_dir = tmp_path / "test-market"
        marketplace_dir.mkdir()
        _setup_marketplace_with_plugins(marketplace_dir, "test-market", ["plug-a", "plug-b"])

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        call_order: list[str] = []

        def track_calls(cmd, **kwargs):
            if "uninstall" in cmd:
                call_order.append("uninstall")
            elif "remove" in cmd:
                call_order.append("remove")
            return mock_result

        with mock.patch(f"{MODULE}.subprocess.run", side_effect=track_calls):
            uninstall_marketplace(claude_bin, marketplace_dir, "test-market")

        uninstall_indices = [i for i, c in enumerate(call_order) if c == "uninstall"]
        remove_indices = [i for i, c in enumerate(call_order) if c == "remove"]
        assert len(uninstall_indices) >= 2, "Must uninstall at least 2 plugins"
        assert len(remove_indices) >= 1, "Must remove marketplace"
        assert all(ui < ri for ui in uninstall_indices for ri in remove_indices), (
            "All plugin uninstalls must precede marketplace removal"
        )

    def test_spec_7_7_step4b_discovers_plugins_reuses_shared(self, tmp_path):
        """Verify: Plugin discovery for uninstall reuses shared discover_plugins().

        Given: The uninstall module
        When: We inspect its plugin discovery mechanism
        Then: It imports discover_plugins from install_claude_marketplaces
        Spec: Section 7.7 Step 4b — shared utility
        """
        import inspect

        import uninstall_claude_marketplaces

        source = inspect.getsource(uninstall_claude_marketplaces)
        assert "from install_claude_marketplaces import" in source or (
            "import install_claude_marketplaces" in source
        ), "Uninstall module must import from install module to reuse discover_plugins"


@pytest.mark.unit
class TestUninstallCoverage:
    """Additional tests for full coverage of uninstall module."""

    def test_uninstall_timeout_invalid_value_exits(self, monkeypatch):
        """Verify: Invalid CLAUDE_UNINSTALL_TIMEOUT causes exit with code 1.

        Spec: Section 7.5 — fail-fast on invalid config
        """
        from uninstall_claude_marketplaces import _get_uninstall_timeout

        monkeypatch.setenv("CLAUDE_UNINSTALL_TIMEOUT", "not-a-number")
        with pytest.raises(SystemExit) as exc_info:
            _get_uninstall_timeout()
        assert exc_info.value.code == 1

    def test_uninstall_timeout_zero_exits(self, monkeypatch):
        """Verify: Zero CLAUDE_UNINSTALL_TIMEOUT causes exit with code 1.

        Spec: Section 7.5 — fail-fast on invalid config
        """
        from uninstall_claude_marketplaces import _get_uninstall_timeout

        monkeypatch.setenv("CLAUDE_UNINSTALL_TIMEOUT", "0")
        with pytest.raises(SystemExit) as exc_info:
            _get_uninstall_timeout()
        assert exc_info.value.code == 1

    def test_uninstall_timeout_negative_exits(self, monkeypatch):
        """Verify: Negative CLAUDE_UNINSTALL_TIMEOUT causes exit with code 1.

        Spec: Section 7.5 — fail-fast on invalid config
        """
        from uninstall_claude_marketplaces import _get_uninstall_timeout

        monkeypatch.setenv("CLAUDE_UNINSTALL_TIMEOUT", "-5")
        with pytest.raises(SystemExit) as exc_info:
            _get_uninstall_timeout()
        assert exc_info.value.code == 1

    def test_uninstall_plugin_timeout_expired(self, claude_bin):
        """Verify: Timeout during uninstall returns False.

        Spec: Section 7.5 — timeout handling
        """
        from uninstall_claude_marketplaces import uninstall_plugin

        with mock.patch(
            f"{MODULE}.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=30),
        ):
            result = uninstall_plugin(claude_bin, "slow-plugin", "test-market")
        assert result is False

    def test_remove_marketplace_success(self, claude_bin, tmp_path):
        """Verify: remove_marketplace returns True on success.

        Spec: Section 7.7 — marketplace removal
        """
        from uninstall_claude_marketplaces import remove_marketplace

        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = remove_marketplace(claude_bin, tmp_path / "market")
        assert result is True

    def test_remove_marketplace_failure(self, claude_bin, tmp_path, caplog):
        """Verify: remove_marketplace returns False on failure.

        Spec: Section 7.5 — error handling
        """
        from uninstall_claude_marketplaces import remove_marketplace

        mock_result = mock.Mock(returncode=1, stdout="", stderr="remove error")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = remove_marketplace(claude_bin, tmp_path / "market")
        assert result is False
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1

    def test_remove_marketplace_timeout(self, claude_bin, tmp_path):
        """Verify: remove_marketplace returns False on timeout.

        Spec: Section 7.5 — timeout handling
        """
        from uninstall_claude_marketplaces import remove_marketplace

        with mock.patch(
            f"{MODULE}.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=30),
        ):
            result = remove_marketplace(claude_bin, tmp_path / "market")
        assert result is False

    def test_uninstall_marketplace_with_failures(self, tmp_path, claude_bin):
        """Verify: uninstall_marketplace returns False when any operation fails.

        Spec: Section 7.7 — mixed failure handling
        """
        from uninstall_claude_marketplaces import uninstall_marketplace

        marketplace_dir = tmp_path / "test-market"
        marketplace_dir.mkdir()
        _setup_marketplace_with_plugins(marketplace_dir, "test-market", ["plug-a"])

        def mock_run_side_effect(cmd, **kwargs):
            if "uninstall" in cmd:
                return mock.Mock(returncode=1, stdout="", stderr="fail")
            return mock.Mock(returncode=0, stdout="ok", stderr="")

        with mock.patch(f"{MODULE}.subprocess.run", side_effect=mock_run_side_effect):
            result = uninstall_marketplace(claude_bin, marketplace_dir, "test-market")
        assert result is False

    def test_uninstall_marketplace_remove_failure(self, tmp_path, claude_bin):
        """Verify: uninstall_marketplace returns False when marketplace removal fails.

        Spec: Section 7.7 — marketplace removal failure
        """
        from uninstall_claude_marketplaces import uninstall_marketplace

        marketplace_dir = tmp_path / "test-market"
        marketplace_dir.mkdir()
        _setup_marketplace_with_plugins(marketplace_dir, "test-market", ["plug-a"])

        def mock_run_side_effect(cmd, **kwargs):
            if "remove" in cmd:
                return mock.Mock(returncode=1, stdout="", stderr="remove failed")
            return mock.Mock(returncode=0, stdout="ok", stderr="")

        with mock.patch(f"{MODULE}.subprocess.run", side_effect=mock_run_side_effect):
            result = uninstall_marketplace(claude_bin, marketplace_dir, "test-market")
        assert result is False
