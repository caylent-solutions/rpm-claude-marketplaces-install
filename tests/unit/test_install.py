"""Tests for install script — CLI discovery, marketplace registration, plugin install.

Verifies that the install script correctly locates the claude CLI binary,
discovers marketplace directories, reads marketplace metadata, registers
marketplaces with Claude Code, discovers plugins, installs them, and
orchestrates the full 7-step install process.

Spec Reference:
    Section 7.3 (lines 1279-1287): Configuration — env vars, defaults
    Section 7.4 Steps 3-7 (lines 1300-1366): Install workflow steps
    Section 7.5 (lines 1368-1379): Error handling rules
"""

import json
import logging
import pathlib
from unittest import mock

import pytest

from install_claude_marketplaces import locate_claude_binary

MODULE = "install_claude_marketplaces"


@pytest.fixture()
def claude_bin():
    """Provide a configurable path to the claude binary for tests."""
    return "/usr/local/bin/claude"


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


@pytest.mark.unit
class TestGetMarketplaceDir:
    """Tests for get_marketplace_dir() per spec section 7.3."""

    def test_spec_7_3_marketplace_dir_from_env_var(self, tmp_path):
        """Verify get_marketplace_dir() reads CLAUDE_MARKETPLACES_DIR env var.

        Given: CLAUDE_MARKETPLACES_DIR is set to a custom path
        When: get_marketplace_dir() is called
        Then: It returns the custom path as a Path object
        Spec: Section 7.3
        """
        from install_claude_marketplaces import get_marketplace_dir

        custom_path = str(tmp_path / "custom-marketplaces")
        with mock.patch.dict("os.environ", {"CLAUDE_MARKETPLACES_DIR": custom_path}):
            result = get_marketplace_dir()
            assert result == pathlib.Path(custom_path)

    def test_spec_7_3_marketplace_dir_default_home(self, monkeypatch):
        """Verify get_marketplace_dir() defaults to $HOME/.claude-marketplaces.

        Given: CLAUDE_MARKETPLACES_DIR is not set
        When: get_marketplace_dir() is called
        Then: It returns Path($HOME/.claude-marketplaces)
        Spec: Section 7.3
        """
        from install_claude_marketplaces import get_marketplace_dir

        monkeypatch.delenv("CLAUDE_MARKETPLACES_DIR", raising=False)
        result = get_marketplace_dir()
        home = pathlib.Path.home()
        assert result == home / ".claude-marketplaces"


@pytest.mark.unit
class TestMarketplaceDirVerification:
    """Tests for marketplace directory existence check per spec 7.4 Step 4."""

    def test_spec_7_4_step4_marketplace_dir_missing_exit_0(self, tmp_path, caplog):
        """Verify exit 0 and warning when marketplace dir does not exist.

        Given: Marketplace directory does not exist
        When: The check is performed
        Then: SystemExit(0) is raised and a warning is logged
        Spec: Section 7.4 Step 4, Section 7.5
        """
        from install_claude_marketplaces import verify_marketplace_dir

        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(SystemExit) as exc_info:
            verify_marketplace_dir(nonexistent)
        assert exc_info.value.code == 0
        warning_messages = [r.message.lower() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("marketplace" in msg for msg in warning_messages), "Warning must mention marketplace directory"

    def test_spec_7_4_step4_marketplace_dir_exists_returns_normally(self, tmp_path):
        """Verify no exit when marketplace directory exists.

        Given: Marketplace directory exists
        When: verify_marketplace_dir() is called
        Then: Function returns normally (no SystemExit)
        Spec: Section 7.4 Step 4
        """
        from install_claude_marketplaces import verify_marketplace_dir

        verify_marketplace_dir(tmp_path)


@pytest.mark.unit
class TestDiscoverMarketplaceEntries:
    """Tests for discover_marketplace_entries() per spec 7.4 Step 5."""

    def test_spec_7_4_step5_discover_entries_sorted_alphabetically(self, tmp_path):
        """Verify entries are returned in sorted alphabetical order.

        Given: Marketplace dir contains dirs: zeta, alpha, beta
        When: discover_marketplace_entries() is called
        Then: Returns [alpha, beta, zeta]
        Spec: Section 7.4 Step 5
        """
        from install_claude_marketplaces import discover_marketplace_entries

        for name in ["zeta", "alpha", "beta"]:
            (tmp_path / name).mkdir()
        result = discover_marketplace_entries(tmp_path)
        names = [p.name for p in result]
        assert names == ["alpha", "beta", "zeta"]

    def test_spec_7_4_step5_discover_excludes_hidden_entries(self, tmp_path):
        """Verify hidden (dot-prefixed) entries are excluded.

        Given: Marketplace dir contains dirs: visible, .hidden
        When: discover_marketplace_entries() is called
        Then: Only 'visible' is returned
        Spec: Section 7.4 Step 5
        """
        from install_claude_marketplaces import discover_marketplace_entries

        (tmp_path / "visible").mkdir()
        (tmp_path / ".hidden").mkdir()
        result = discover_marketplace_entries(tmp_path)
        names = [p.name for p in result]
        assert "visible" in names
        assert ".hidden" not in names

    def test_spec_7_4_step5_discover_includes_symlinks_to_dirs(self, tmp_path):
        """Verify symlinks to directories are included.

        Given: Marketplace dir contains a symlink pointing to a directory
        When: discover_marketplace_entries() is called
        Then: The symlink is included in results
        Spec: Section 7.4 Step 5
        """
        from install_claude_marketplaces import discover_marketplace_entries

        real_dir = tmp_path / "real-marketplace"
        real_dir.mkdir()
        symlink = tmp_path / "linked-marketplace"
        symlink.symlink_to(real_dir)
        result = discover_marketplace_entries(tmp_path)
        names = [p.name for p in result]
        assert "linked-marketplace" in names

    def test_spec_7_4_step5_discover_excludes_regular_files(self, tmp_path):
        """Verify regular files are excluded from discovered entries.

        Given: Marketplace dir contains a regular file and a directory
        When: discover_marketplace_entries() is called
        Then: Only the directory is returned, not the file
        Spec: Section 7.4 Step 5
        """
        from install_claude_marketplaces import discover_marketplace_entries

        (tmp_path / "valid-dir").mkdir()
        (tmp_path / "regular-file.txt").write_text("not a directory")
        result = discover_marketplace_entries(tmp_path)
        names = [p.name for p in result]
        assert "valid-dir" in names
        assert "regular-file.txt" not in names

    def test_spec_7_4_step5_empty_dir_returns_empty_list(self, tmp_path):
        """Verify empty directory returns empty list.

        Given: Marketplace dir exists but is empty
        When: discover_marketplace_entries() is called
        Then: Returns an empty list (caller handles exit 0 + warning)
        Spec: Section 7.4 Step 5
        """
        from install_claude_marketplaces import discover_marketplace_entries

        result = discover_marketplace_entries(tmp_path)
        assert result == [], "Empty dir should return empty list"


@pytest.mark.unit
class TestBrokenSymlinks:
    """Tests for broken symlink handling per spec 7.4 Step 6a."""

    def test_spec_7_4_step6a_broken_symlink_logged_and_skipped(self, tmp_path, caplog):
        """Verify broken symlinks are excluded and logged.

        Given: Marketplace dir contains a broken symlink and a valid dir
        When: discover_marketplace_entries() is called
        Then: The broken symlink is not in the returned list,
              a log message about the broken symlink is produced,
              and valid entries are still returned
        Spec: Section 7.4 Step 6a
        """
        from install_claude_marketplaces import discover_marketplace_entries

        valid_dir = tmp_path / "valid-marketplace"
        valid_dir.mkdir()
        broken = tmp_path / "broken-link"
        broken.symlink_to(tmp_path / "nonexistent-target")
        result = discover_marketplace_entries(tmp_path)
        names = [p.name for p in result]
        assert "broken-link" not in names
        assert "valid-marketplace" in names
        log_messages = [r.message.lower() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("broken" in msg or "symlink" in msg for msg in log_messages), (
            "A warning/error log should mention the broken symlink"
        )


@pytest.mark.unit
class TestReadMarketplaceName:
    """Tests for read_marketplace_name() per spec 7.4 Step 6b."""

    def test_spec_7_4_step6b_read_marketplace_name_valid(self, tmp_path):
        """Verify reading name from valid marketplace.json.

        Given: Marketplace dir has .claude-plugin/marketplace.json with name
        When: read_marketplace_name() is called
        Then: Returns the name field value
        Spec: Section 7.4 Step 6b
        """
        from install_claude_marketplaces import read_marketplace_name

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "marketplace.json"
        manifest.write_text(json.dumps({"name": "test-marketplace"}))
        result = read_marketplace_name(tmp_path)
        assert result == "test-marketplace"

    @pytest.mark.parametrize(
        ("scenario", "setup_fn", "expected_error"),
        [
            pytest.param(
                "missing_file",
                lambda tmp_path: None,
                FileNotFoundError,
                id="marketplace_json_missing",
            ),
            pytest.param(
                "no_name_field",
                lambda tmp_path: _write_marketplace_json(tmp_path, '{"version": "1.0"}'),
                KeyError,
                id="marketplace_json_no_name_field",
            ),
            pytest.param(
                "invalid_json",
                lambda tmp_path: _write_marketplace_json(tmp_path, "not valid json {{{"),
                json.JSONDecodeError,
                id="marketplace_json_invalid_json",
            ),
        ],
    )
    def test_spec_7_4_step6b_marketplace_json_errors(self, tmp_path, scenario, setup_fn, expected_error):
        """Verify read_marketplace_name() raises appropriate errors for invalid inputs.

        Given: marketplace.json is missing, has no 'name' field, or has invalid JSON
        When: read_marketplace_name() is called
        Then: The appropriate error is raised
        Spec: Section 7.4 Step 6b
        """
        from install_claude_marketplaces import read_marketplace_name

        setup_fn(tmp_path)
        with pytest.raises(expected_error):
            read_marketplace_name(tmp_path)


def _write_marketplace_json(tmp_path: pathlib.Path, content: str) -> None:
    """Write content to .claude-plugin/marketplace.json under tmp_path."""
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir(exist_ok=True)
    manifest = plugin_dir / "marketplace.json"
    manifest.write_text(content)


@pytest.mark.unit
class TestRegisterMarketplace:
    """Tests for register_marketplace() per spec 7.4 Step 6c."""

    def test_spec_7_4_step6c_register_marketplace_success(self, tmp_path, claude_bin):
        """Verify successful marketplace registration.

        Given: claude binary path and marketplace path
        When: register_marketplace() is called and subprocess succeeds
        Then: Returns True and runs correct command
        Spec: Section 7.4 Step 6c
        """
        from install_claude_marketplaces import register_marketplace

        marketplace_path = tmp_path / "my-marketplace"
        marketplace_path.mkdir()
        mock_result = mock.Mock(returncode=0, stdout="registered", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result) as mock_run:
            result = register_marketplace(claude_bin, marketplace_path)
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == claude_bin
            assert "marketplace" in call_args
            assert "add" in call_args
            assert str(marketplace_path) in call_args

    def test_spec_7_4_step6c_register_marketplace_failure_continue(self, tmp_path, claude_bin):
        """Verify failed registration returns False (does not raise).

        Given: claude binary path and marketplace path
        When: register_marketplace() is called and subprocess fails (non-zero)
        Then: Returns False
        Spec: Section 7.4 Step 6c, Section 7.5
        """
        from install_claude_marketplaces import register_marketplace

        marketplace_path = tmp_path / "bad-marketplace"
        marketplace_path.mkdir()
        mock_result = mock.Mock(returncode=1, stdout="", stderr="error occurred")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = register_marketplace(claude_bin, marketplace_path)
            assert result is False

    def test_spec_7_6_register_already_registered_idempotent(self, tmp_path, claude_bin):
        """Verify idempotent registration returns True.

        Given: A marketplace that is already registered
        When: register_marketplace() is called
        Then: Returns True (Claude Code handles idempotency with zero exit)
        Spec: Section 7.6
        """
        from install_claude_marketplaces import register_marketplace

        marketplace_path = tmp_path / "existing-marketplace"
        marketplace_path.mkdir()
        mock_result = mock.Mock(returncode=0, stdout="already materialized", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = register_marketplace(claude_bin, marketplace_path)
            assert result is True

    def test_spec_7_4_step6c_register_marketplace_timeout(self, tmp_path, claude_bin):
        """Verify timeout returns False and logs error.

        Given: subprocess.run raises TimeoutExpired
        When: register_marketplace() is called
        Then: Returns False (log+continue per spec 7.5)
        Spec: Section 7.4 Step 6c, Section 7.5
        """
        import subprocess as sp

        from install_claude_marketplaces import register_marketplace

        marketplace_path = tmp_path / "slow-marketplace"
        marketplace_path.mkdir()
        with mock.patch(
            f"{MODULE}.subprocess.run",
            side_effect=sp.TimeoutExpired(cmd="claude", timeout=30),
        ):
            result = register_marketplace(claude_bin, marketplace_path)
            assert result is False

    def test_spec_7_3_invalid_timeout_env_exits(self, tmp_path, claude_bin):
        """Verify invalid CLAUDE_REGISTER_TIMEOUT exits with code 1.

        Given: CLAUDE_REGISTER_TIMEOUT is set to a non-integer value
        When: register_marketplace() is called
        Then: sys.exit(1) is raised with an error log
        Spec: Section 7.3 (configuration validation)
        """
        from install_claude_marketplaces import register_marketplace

        marketplace_path = tmp_path / "some-marketplace"
        marketplace_path.mkdir()
        with mock.patch.dict("os.environ", {"CLAUDE_REGISTER_TIMEOUT": "abc"}):
            with pytest.raises(SystemExit) as exc_info:
                register_marketplace(claude_bin, marketplace_path)
            assert exc_info.value.code == 1


def _write_plugin_json(plugin_path: pathlib.Path, name: str) -> None:
    """Write a .claude-plugin/plugin.json with the given name under plugin_path."""
    plugin_dir = plugin_path / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = plugin_dir / "plugin.json"
    manifest.write_text(json.dumps({"name": name}))


def _setup_marketplace_with_plugins(
    marketplace_path: pathlib.Path,
    marketplace_name: str,
    plugin_names: list[str],
) -> None:
    """Create a marketplace directory with marketplace.json and plugin subdirectories."""
    _write_marketplace_json(marketplace_path, json.dumps({"name": marketplace_name}))
    for plugin_name in plugin_names:
        plugin_subdir = marketplace_path / plugin_name
        plugin_subdir.mkdir()
        _write_plugin_json(plugin_subdir, plugin_name)


@pytest.mark.unit
class TestDiscoverPlugins:
    """Tests for discover_plugins() per spec 7.4 Step 6d."""

    def test_spec_7_4_step6d_discover_plugins_finds_plugin_json(self, tmp_path):
        """Verify discover_plugins() finds plugins with .claude-plugin/plugin.json.

        Given: A marketplace dir with subdirs containing .claude-plugin/plugin.json
        When: discover_plugins() is called
        Then: It returns tuples with plugin name and path for each discovered plugin
        Spec: Section 7.4 Step 6d
        """
        from install_claude_marketplaces import discover_plugins

        plugin_a = tmp_path / "plugin-a"
        plugin_a.mkdir()
        _write_plugin_json(plugin_a, "alpha-plugin")

        plugin_b = tmp_path / "plugin-b"
        plugin_b.mkdir()
        _write_plugin_json(plugin_b, "beta-plugin")

        result = discover_plugins(tmp_path)
        assert len(result) == 2
        names = [name for name, _ in result]
        assert "alpha-plugin" in names
        assert "beta-plugin" in names

    def test_spec_7_4_step6d_discover_plugins_reads_name_field(self, tmp_path):
        """Verify discover_plugins() reads the name field from plugin.json.

        Given: A plugin subdirectory with .claude-plugin/plugin.json containing name
        When: discover_plugins() is called
        Then: The returned name matches the name field in plugin.json
        Spec: Section 7.4 Step 6d
        """
        from install_claude_marketplaces import discover_plugins

        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        _write_plugin_json(plugin_dir, "custom-name")

        result = discover_plugins(tmp_path)
        assert len(result) == 1
        assert result[0][0] == "custom-name"
        assert result[0][1] == plugin_dir

    def test_spec_7_4_step6d_discover_plugins_no_plugins_returns_empty(self, tmp_path):
        """Verify discover_plugins() returns empty list when no plugins exist.

        Given: A marketplace dir with subdirs but none containing plugin.json
        When: discover_plugins() is called
        Then: Returns an empty list
        Spec: Section 7.4 Step 6d
        """
        from install_claude_marketplaces import discover_plugins

        (tmp_path / "no-plugin-dir").mkdir()
        result = discover_plugins(tmp_path)
        assert result == []

    def test_spec_7_4_step6d_discover_plugins_missing_plugin_json_skipped(self, tmp_path, caplog):
        """Verify subdirs without .claude-plugin/plugin.json are skipped.

        Given: Marketplace with one valid plugin and one dir without plugin.json
        When: discover_plugins() is called
        Then: Only the valid plugin is returned
        Spec: Section 7.4 Step 6d
        """
        from install_claude_marketplaces import discover_plugins

        valid = tmp_path / "valid-plugin"
        valid.mkdir()
        _write_plugin_json(valid, "valid")

        invalid = tmp_path / "no-manifest"
        invalid.mkdir()

        result = discover_plugins(tmp_path)
        assert len(result) == 1
        assert result[0][0] == "valid"


@pytest.mark.unit
class TestInstallPlugin:
    """Tests for install_plugin() per spec 7.4 Step 6e."""

    def test_spec_7_4_step6e_install_plugin_success(self, claude_bin):
        """Verify successful plugin installation returns True.

        Given: claude binary, plugin name, marketplace name
        When: install_plugin() is called and subprocess succeeds
        Then: Returns True
        Spec: Section 7.4 Step 6e
        """
        from install_claude_marketplaces import install_plugin

        mock_result = mock.Mock(returncode=0, stdout="installed", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = install_plugin(claude_bin, "my-plugin", "my-market")
            assert result is True

    def test_spec_7_4_step6e_install_plugin_failure_returns_false(self, claude_bin, caplog):
        """Verify failed plugin install returns False without raising.

        Given: claude binary, plugin name, marketplace name
        When: install_plugin() is called and subprocess fails
        Then: Returns False and logs an error
        Spec: Section 7.4 Step 6e, Section 7.5
        """
        from install_claude_marketplaces import install_plugin

        mock_result = mock.Mock(returncode=1, stdout="", stderr="install failed")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result):
            result = install_plugin(claude_bin, "bad-plugin", "my-market")
            assert result is False
        error_messages = [r.message.lower() for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("bad-plugin" in msg for msg in error_messages)

    def test_spec_7_4_step6e_install_plugin_correct_command(self, claude_bin):
        """Verify install_plugin() runs the correct subprocess command.

        Given: claude binary "claude", plugin "my-plugin", marketplace "my-market"
        When: install_plugin() is called
        Then: subprocess.run is called with
              [claude_bin, "plugin", "install", "my-plugin@my-market", "--scope", "user"]
        Spec: Section 7.4 Step 6e
        """
        from install_claude_marketplaces import install_plugin

        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result) as mock_run:
            install_plugin(claude_bin, "my-plugin", "my-market")
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args == [
                claude_bin,
                "plugin",
                "install",
                "my-plugin@my-market",
                "--scope",
                "user",
            ]

    def test_spec_7_4_step6e_install_plugin_timeout(self, claude_bin):
        """Verify timeout during plugin install returns False.

        Given: subprocess.run raises TimeoutExpired
        When: install_plugin() is called
        Then: Returns False (log+continue per spec 7.5)
        Spec: Section 7.4 Step 6e, Section 7.5
        """
        import subprocess as sp

        from install_claude_marketplaces import install_plugin

        with mock.patch(
            f"{MODULE}.subprocess.run",
            side_effect=sp.TimeoutExpired(cmd="claude", timeout=30),
        ):
            result = install_plugin(claude_bin, "slow-plugin", "my-market")
            assert result is False


@pytest.mark.unit
class TestSummaryLog:
    """Tests for summary logging per spec 7.4 Step 7."""

    def test_spec_7_4_step7_summary_log_counts(self, caplog):
        """Verify summary log contains marketplace and plugin counts.

        Given: 2 marketplaces processed, 3 plugins installed
        When: log_summary() is called
        Then: Log contains counts for marketplaces processed and plugins installed
        Spec: Section 7.4 Step 7
        """
        from install_claude_marketplaces import log_summary

        with caplog.at_level(logging.INFO):
            log_summary(
                marketplaces_processed=2,
                marketplaces_registered=1,
                plugins_installed=3,
            )
        log_output = " ".join(r.message for r in caplog.records)
        assert "2" in log_output
        assert "3" in log_output


@pytest.mark.unit
class TestMainOrchestration:
    """Tests for main() orchestration per spec 7.4 complete workflow."""

    def test_spec_7_4_main_orchestrates_all_steps(self, tmp_path, monkeypatch):
        """Verify main() orchestrates the full 7-step install process.

        Given: claude on PATH, marketplace dir with one marketplace containing one plugin
        When: main() is called
        Then: It executes all steps and returns 0
        Spec: Section 7.4
        """
        from install_claude_marketplaces import main

        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()
        market = marketplace_dir / "test-market"
        market.mkdir()
        _setup_marketplace_with_plugins(market, "test-market", ["test-plugin"])

        monkeypatch.setenv("CLAUDE_MARKETPLACES_DIR", str(marketplace_dir))
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result),
        ):
            exit_code = main()
            assert exit_code == 0

    def test_spec_7_5_all_success_exit_zero(self, tmp_path, monkeypatch):
        """Verify exit code 0 when all marketplaces and plugins succeed.

        Given: Two marketplaces each with one plugin, all succeed
        When: main() is called
        Then: Returns 0
        Spec: Section 7.5
        """
        from install_claude_marketplaces import main

        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()
        for name in ["market-a", "market-b"]:
            market = marketplace_dir / name
            market.mkdir()
            _setup_marketplace_with_plugins(market, name, [f"{name}-plugin"])

        monkeypatch.setenv("CLAUDE_MARKETPLACES_DIR", str(marketplace_dir))
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result),
        ):
            exit_code = main()
            assert exit_code == 0

    def test_spec_7_5_all_failures_exit_nonzero(self, tmp_path, monkeypatch):
        """Verify non-zero exit when any plugin install fails.

        Given: One marketplace with a plugin whose install fails
        When: main() is called
        Then: Returns non-zero exit code
        Spec: Section 7.5
        """
        from install_claude_marketplaces import main

        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()
        market = marketplace_dir / "fail-market"
        market.mkdir()
        _setup_marketplace_with_plugins(market, "fail-market", ["fail-plugin"])

        monkeypatch.setenv("CLAUDE_MARKETPLACES_DIR", str(marketplace_dir))

        def mock_run_side_effect(cmd, **kwargs):
            if "marketplace" in cmd and "add" in cmd:
                return mock.Mock(returncode=0, stdout="ok", stderr="")
            return mock.Mock(returncode=1, stdout="", stderr="install failed")

        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", side_effect=mock_run_side_effect),
        ):
            exit_code = main()
            assert exit_code != 0

    def test_spec_7_4_multiple_marketplaces_multiple_plugins(self, tmp_path, monkeypatch):
        """Verify multiple marketplaces with multiple plugins are all processed.

        Given: 2 marketplaces, first with 2 plugins, second with 1 plugin
        When: main() is called
        Then: All 3 plugins are installed and exit code is 0
        Spec: Section 7.4
        """
        from install_claude_marketplaces import main

        marketplace_dir = tmp_path / "marketplaces"
        marketplace_dir.mkdir()

        market_a = marketplace_dir / "market-a"
        market_a.mkdir()
        _setup_marketplace_with_plugins(market_a, "market-a", ["plugin-one", "plugin-two"])

        market_b = marketplace_dir / "market-b"
        market_b.mkdir()
        _setup_marketplace_with_plugins(market_b, "market-b", ["plugin-three"])

        monkeypatch.setenv("CLAUDE_MARKETPLACES_DIR", str(marketplace_dir))
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result) as mock_run,
        ):
            exit_code = main()
            assert exit_code == 0
            # 2 marketplace registrations + 3 plugin installs = 5 subprocess calls
            assert mock_run.call_count == 5
