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

from uninstall_claude_marketplaces import main, remove_marketplace

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


@pytest.mark.unit
class TestMarketplaceDeregistration:
    """Tests for marketplace deregistration (spec 7.7 step 4d)."""

    def test_spec_7_7_step4d_remove_marketplace_correct_command(self, claude_bin, tmp_path):
        """Verify: remove_marketplace() runs the correct subprocess command.

        Given: A mocked CLI
        When: remove_marketplace() is called with a marketplace path
        Then: Subprocess is called with 'claude plugin marketplace remove <path>'
        Spec: Section 7.7 Step 4d
        """
        market_path = tmp_path / "my-market"
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result) as mock_run:
            remove_marketplace(claude_bin, market_path)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == [claude_bin, "plugin", "marketplace", "remove", str(market_path)]

    def test_spec_7_7_step4d_remove_marketplace_failure_returns_false(self, claude_bin, tmp_path, caplog):
        """Verify: remove_marketplace() returns False on failure without raising.

        Given: A mocked CLI that returns non-zero exit code
        When: remove_marketplace() is called
        Then: Returns False AND logs ERROR (does not raise)
        Spec: Section 7.7 Step 4d, Section 7.5 error handling
        """
        mock_result = mock.Mock(returncode=1, stdout="", stderr="removal error")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = remove_marketplace(claude_bin, tmp_path / "bad-market")
        assert result is False, "Must return False on failure (not raise)"
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1, "Must log at ERROR level"

    def test_spec_7_7_step4d_remove_marketplace_failure_continues(self, claude_bin, tmp_path, caplog):
        """Verify: Failed removal logs error and caller can continue processing.

        Given: A mocked CLI that fails to remove a marketplace
        When: remove_marketplace() is called
        Then: Returns False with ERROR log including marketplace path
        Spec: Section 7.5 — marketplace remove fails → log error, continue
        """
        market_path = tmp_path / "failing-market"
        mock_result = mock.Mock(returncode=1, stdout="", stderr="not registered")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = remove_marketplace(claude_bin, market_path)
        assert result is False, "Must return False (not raise)"
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert any(str(market_path) in r.message for r in error_records), "Error log must include marketplace path"

    def test_spec_7_7_remove_already_removed_noop(self, claude_bin, tmp_path):
        """Verify: Removing an already-removed marketplace is a no-op.

        Given: A mocked CLI that returns success (already removed)
        When: remove_marketplace() is called
        Then: Returns True (CLI treats re-removal as success)
        Spec: Section 7.7 — idempotent removal
        """
        mock_result = mock.Mock(returncode=0, stdout="already removed", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = remove_marketplace(claude_bin, tmp_path / "already-gone")
        assert result is True, "Already-removed marketplace should succeed (no-op)"


@pytest.mark.unit
class TestUninstallMain:
    """Tests for uninstall main() orchestration (spec 7.7 steps 1-5)."""

    def test_spec_7_7_main_orchestrates_full_uninstall(self, tmp_path, claude_bin, caplog):
        """Verify: main() orchestrates the full uninstall process.

        Given: A marketplace directory with marketplaces and plugins
        When: main() is called
        Then: It discovers marketplaces, uninstalls plugins, removes marketplaces
        Spec: Section 7.7 — full uninstall orchestration
        """
        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()
        _setup_marketplace_with_plugins(
            marketplace_dir / "market-a",
            "market-a",
            ["plug-1"],
        )

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{MODULE}.get_marketplace_dir", return_value=marketplace_dir),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result) as mock_run,
        ):
            exit_code = main()

        assert exit_code == 0, "Must return 0 on full success"
        assert mock_run.call_count >= 2, "Must call subprocess at least twice (uninstall + remove)"

    def test_spec_7_7_main_claude_not_found_exit_127(self):
        """Verify: main() exits 127 when claude binary is not found.

        Given: locate_claude_binary() calls sys.exit(127)
        When: main() is called
        Then: SystemExit with code 127 is raised
        Spec: Section 7.7 Step 1, Section 7.5
        """
        with mock.patch(
            f"{MODULE}.locate_claude_binary",
            side_effect=SystemExit(127),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 127, "Must exit 127 when claude not found"

    def test_spec_7_7_main_marketplace_dir_missing_exit_0(self, tmp_path, claude_bin, caplog):
        """Verify: main() exits 0 when marketplace directory is missing.

        Given: Marketplace directory does not exist
        When: main() is called
        Then: Returns 0 (nothing to uninstall)
        Spec: Section 7.7 Step 2, Section 7.5
        """
        missing_dir = tmp_path / "nonexistent"
        caplog.set_level(logging.INFO)
        with (
            mock.patch(f"{MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{MODULE}.get_marketplace_dir", return_value=missing_dir),
        ):
            exit_code = main()

        assert exit_code == 0, "Must return 0 when marketplace dir missing"

    def test_spec_7_7_step5_summary_log_counts(self, tmp_path, claude_bin, caplog):
        """Verify: main() logs a summary with counts of processed items.

        Given: A marketplace with plugins that all uninstall successfully
        When: main() completes
        Then: Summary log includes marketplace and plugin counts
        Spec: Section 7.7 Step 5
        """
        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()
        _setup_marketplace_with_plugins(
            marketplace_dir / "market-a",
            "market-a",
            ["plug-1", "plug-2"],
        )

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{MODULE}.get_marketplace_dir", return_value=marketplace_dir),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result),
        ):
            main()

        info_records = [r for r in caplog.records if r.levelno >= logging.INFO]
        summary_messages = [r.message.lower() for r in info_records]
        has_summary = any("summary" in m or ("marketplace" in m and "plugin" in m) for m in summary_messages)
        assert has_summary, "Must log a summary with marketplace and plugin counts"

    def test_spec_7_7_main_mixed_failures_exit_nonzero(self, tmp_path, claude_bin, caplog):
        """Verify: main() returns non-zero when some operations fail.

        Given: A marketplace where plugin uninstall fails but removal succeeds
        When: main() completes
        Then: Returns non-zero exit code
        Spec: Section 7.7, Section 7.5
        """
        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()
        _setup_marketplace_with_plugins(
            marketplace_dir / "market-a",
            "market-a",
            ["plug-1"],
        )

        caplog.set_level(logging.INFO)

        def mock_run_side_effect(cmd, **kwargs):
            if "uninstall" in cmd:
                return mock.Mock(returncode=1, stdout="", stderr="fail")
            return mock.Mock(returncode=0, stdout="ok", stderr="")

        with (
            mock.patch(f"{MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{MODULE}.get_marketplace_dir", return_value=marketplace_dir),
            mock.patch(f"{MODULE}.subprocess.run", side_effect=mock_run_side_effect),
        ):
            exit_code = main()

        assert exit_code != 0, "Must return non-zero when any operation fails"

    def test_spec_7_7_main_no_entries_exit_0(self, tmp_path, claude_bin, caplog):
        """Verify: main() exits 0 when marketplace directory exists but has no entries.

        Given: Marketplace directory exists but contains no subdirectories
        When: main() is called
        Then: Returns 0 (nothing to uninstall)
        Spec: Section 7.7 Step 3
        """
        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()
        caplog.set_level(logging.INFO)
        with (
            mock.patch(f"{MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{MODULE}.get_marketplace_dir", return_value=marketplace_dir),
        ):
            exit_code = main()
        assert exit_code == 0, "Must return 0 when no marketplace entries found"
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("no marketplace entries" in r.message.lower() for r in warning_records)

    def test_spec_7_7_main_remove_fails_exit_nonzero(self, tmp_path, claude_bin, caplog):
        """Verify: main() returns non-zero when marketplace removal fails.

        Given: A marketplace where plugin uninstall succeeds but marketplace removal fails
        When: main() completes
        Then: Returns non-zero exit code
        Spec: Section 7.7, Section 7.5
        """
        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()
        _setup_marketplace_with_plugins(
            marketplace_dir / "market-a",
            "market-a",
            ["plug-1"],
        )

        caplog.set_level(logging.INFO)

        def mock_run_side_effect(cmd, **kwargs):
            if "remove" in cmd:
                return mock.Mock(returncode=1, stdout="", stderr="remove failed")
            return mock.Mock(returncode=0, stdout="ok", stderr="")

        with (
            mock.patch(f"{MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{MODULE}.get_marketplace_dir", return_value=marketplace_dir),
            mock.patch(f"{MODULE}.subprocess.run", side_effect=mock_run_side_effect),
        ):
            exit_code = main()

        assert exit_code != 0, "Must return non-zero when marketplace removal fails"


@pytest.mark.unit
class TestUninstallEntryPoint:
    """Tests for the __main__ entry point block (spec 7.7, LOG_LEVEL validation)."""

    def test_spec_7_7_main_block_invalid_log_level_exits_1(self, capsys):
        """Verify: __main__ block exits 1 on invalid LOG_LEVEL.

        Given: LOG_LEVEL env var is set to an invalid value
        When: The __main__ block executes via runpy
        Then: Writes error to stderr and exits with code 1
        Spec: Section 7.7 — entry point, Section 7.5 fail-fast
        """
        import runpy

        with mock.patch.dict("os.environ", {"LOG_LEVEL": "INVALID"}):
            with pytest.raises(SystemExit) as exc_info:
                runpy.run_module(MODULE, run_name="__main__")
        assert exc_info.value.code == 1, "Must exit 1 on invalid LOG_LEVEL"
        captured = capsys.readouterr()
        assert "Invalid LOG_LEVEL" in captured.err, "Must write error to stderr"

    def test_spec_7_7_main_block_valid_log_level_runs_main(self, claude_bin, tmp_path):
        """Verify: __main__ block with valid LOG_LEVEL calls sys.exit(main()).

        Given: LOG_LEVEL is a valid level and marketplace dir is missing
        When: The __main__ block executes
        Then: main() is called and exit code propagated (0 for missing dir)
        Spec: Section 7.7 — entry point
        """
        missing_dir = tmp_path / "no-such-dir"
        with (
            mock.patch(f"{MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{MODULE}.get_marketplace_dir", return_value=missing_dir),
            mock.patch.dict("os.environ", {"LOG_LEVEL": "DEBUG"}),
            pytest.raises(SystemExit) as exc_info,
        ):
            import runpy

            runpy.run_module(MODULE, run_name="__main__")
        assert exc_info.value.code == 0, "Must exit 0 when marketplace dir missing"
