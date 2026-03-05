"""Tests for install and uninstall script idempotency — safe to run multiple times.

Verifies that running the install/uninstall scripts multiple times produces
consistent results with no duplicate side effects. All tests mock
the subprocess to avoid calling the real claude CLI.

Spec Reference:
    Section 7.6 (lines 1381-1386): Install idempotency guarantees
    Section 7.7 (lines 1408-1409): Uninstall idempotency guarantees
"""

import json
import logging
import pathlib
from unittest import mock

import pytest

MODULE = "install_claude_marketplaces"
UNINSTALL_MODULE = "uninstall_claude_marketplaces"


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
def claude_bin(tmp_path):
    """Provide a dynamically constructed path to the claude binary for tests."""
    return str(tmp_path / "bin" / "claude")


@pytest.fixture()
def idempotency_env(tmp_path, monkeypatch):
    """Set up a marketplace environment for idempotency tests.

    Creates a marketplace directory with one marketplace containing two plugins.
    Configures CLAUDE_MARKETPLACES_DIR env var to point at it.
    Returns (marketplace_dir, mock_result) for use in tests.
    """
    marketplace_dir = tmp_path / "marketplaces"
    marketplace_dir.mkdir()
    market = marketplace_dir / "test-market"
    market.mkdir()
    _setup_marketplace_with_plugins(market, "test-market", ["plugin-a", "plugin-b"])
    monkeypatch.setenv("CLAUDE_MARKETPLACES_DIR", str(marketplace_dir))
    return marketplace_dir


@pytest.mark.unit
class TestIdempotency:
    """Tests for install script idempotency guarantees (spec 7.6)."""

    def test_spec_7_6_idempotent_same_exit_code_on_repeat(self, idempotency_env, caplog):
        """Verify: Running main() twice produces the same exit code.

        Given: A valid marketplace setup with mocked CLI
        When: main() is called twice in sequence
        Then: Both calls return exit code 0
        Spec: Section 7.6 — idempotency
        """
        from install_claude_marketplaces import main

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result),
        ):
            exit_code_1 = main()
            caplog.clear()
            exit_code_2 = main()

        assert exit_code_1 == 0, "First run must succeed"
        assert exit_code_2 == 0, "Second run must also succeed"
        assert exit_code_1 == exit_code_2, "Exit codes must be identical"

    def test_spec_7_6_idempotent_no_duplicate_side_effects(self, idempotency_env, caplog):
        """Verify: Second run does not create duplicate side effects.

        Given: A valid marketplace setup with mocked CLI
        When: main() is called twice
        Then: subprocess.run is called with the same arguments both times
              (no extra calls on second run)
        Spec: Section 7.6 — idempotency
        """
        from install_claude_marketplaces import main

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result) as mock_run,
        ):
            main()
            calls_first_run = mock_run.call_count
            mock_run.reset_mock()
            caplog.clear()
            main()
            calls_second_run = mock_run.call_count

        assert calls_first_run == calls_second_run, (
            f"Same number of subprocess calls expected: first={calls_first_run}, second={calls_second_run}"
        )

    def test_spec_7_6_idempotent_registration_noop_second_run(self, idempotency_env, caplog):
        """Verify: Marketplace registration is a no-op on second run.

        Given: A marketplace already registered on first run
        When: main() is called again
        Then: Registration command is invoked again (CLI handles idempotency)
              and still succeeds
        Spec: Section 7.6 — registration is idempotent per Claude CLI design
        """
        from install_claude_marketplaces import main

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        registration_calls: list[list[str]] = []

        def capture_run(cmd, **kwargs):
            if "marketplace" in cmd and "add" in cmd:
                registration_calls.append(cmd)
            return mock_result

        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", side_effect=capture_run),
        ):
            main()
            first_reg_count = len(registration_calls)
            caplog.clear()
            main()
            total_reg_count = len(registration_calls)

        second_reg_count = total_reg_count - first_reg_count
        assert first_reg_count == second_reg_count, (
            f"Same registration calls expected: first={first_reg_count}, second={second_reg_count}"
        )
        assert first_reg_count > 0, "At least one registration must occur"

    def test_spec_7_6_idempotent_install_succeeds_second_run(self, idempotency_env, caplog):
        """Verify: Plugin install succeeds on second run.

        Given: Plugins already installed on first run
        When: main() is called again
        Then: Install commands succeed (CLI handles re-install as no-op)
        Spec: Section 7.6 — install is idempotent
        """
        from install_claude_marketplaces import main

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        install_calls: list[list[str]] = []

        def capture_run(cmd, **kwargs):
            if "install" in cmd:
                install_calls.append(cmd)
            return mock_result

        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", side_effect=capture_run),
        ):
            main()
            first_install_count = len(install_calls)
            caplog.clear()
            main()
            total_install_count = len(install_calls)

        second_install_count = total_install_count - first_install_count
        assert first_install_count == second_install_count, (
            f"Same install calls expected: first={first_install_count}, second={second_install_count}"
        )
        assert first_install_count > 0, "At least one install must occur"

    def test_spec_7_6_idempotent_summary_consistent(self, idempotency_env, caplog):
        """Verify: Summary log is consistent across runs.

        Given: A valid marketplace setup
        When: main() is called twice
        Then: Both runs produce summary logs with the same counts
        Spec: Section 7.6 — consistent summary output
        """
        from install_claude_marketplaces import main

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")

        def get_summary_messages():
            return [r.message for r in caplog.records if r.levelno == logging.INFO and "summary" in r.message.lower()]

        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result),
        ):
            main()
            summaries_1 = get_summary_messages()
            caplog.clear()
            main()
            summaries_2 = get_summary_messages()

        assert len(summaries_1) == 1, "First run must produce exactly one summary"
        assert len(summaries_2) == 1, "Second run must produce exactly one summary"
        assert summaries_1[0] == summaries_2[0], (
            f"Summary messages must be identical: '{summaries_1[0]}' vs '{summaries_2[0]}'"
        )

    def test_spec_7_6_idempotent_three_consecutive_runs(self, idempotency_env, caplog):
        """Verify: Three consecutive runs produce the same result.

        Given: A valid marketplace setup
        When: main() is called three times
        Then: All three runs return exit code 0 with same subprocess call count
        Spec: Section 7.6 — idempotency holds for N runs
        """
        from install_claude_marketplaces import main

        caplog.set_level(logging.INFO)
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        exit_codes = []
        call_counts = []

        with (
            mock.patch(f"{MODULE}.shutil.which", return_value="/usr/local/bin/claude"),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result) as mock_run,
        ):
            for _ in range(3):
                mock_run.reset_mock()
                caplog.clear()
                exit_codes.append(main())
                call_counts.append(mock_run.call_count)

        assert all(code == 0 for code in exit_codes), f"All runs must return 0: {exit_codes}"
        assert len(set(call_counts)) == 1, f"All runs must have same call count: {call_counts}"


@pytest.mark.unit
class TestUninstallIdempotency:
    """Tests for uninstall script idempotency guarantees (spec 7.7)."""

    def test_spec_7_7_idempotent_uninstall_nothing_installed(self, tmp_path, monkeypatch, claude_bin):
        """Verify: Uninstall when nothing is installed exits 0.

        Given: Marketplace directory does not exist
        When: main() from uninstall script is called
        Then: Exits with code 0 (no-op, nothing to uninstall)
        Spec: Section 7.7 — idempotency guarantee
        """
        from uninstall_claude_marketplaces import main as uninstall_main

        missing_dir = tmp_path / "no-such-dir"
        monkeypatch.setenv("CLAUDE_MARKETPLACES_DIR", str(missing_dir))
        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{UNINSTALL_MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{UNINSTALL_MODULE}.subprocess.run", return_value=mock_result),
        ):
            exit_code = uninstall_main()
        assert exit_code == 0, "Uninstall when nothing installed must exit 0"

    def test_spec_7_7_idempotent_double_uninstall_exit_0(self, idempotency_env, claude_bin):
        """Verify: Running uninstall twice both exit 0.

        Given: A marketplace directory with installed plugins
        When: main() from uninstall script is called twice
        Then: Both calls return exit code 0
        Spec: Section 7.7 — idempotency guarantee
        """
        from uninstall_claude_marketplaces import main as uninstall_main

        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{UNINSTALL_MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{UNINSTALL_MODULE}.subprocess.run", return_value=mock_result),
        ):
            exit_code_1 = uninstall_main()
            exit_code_2 = uninstall_main()
        assert exit_code_1 == 0, "First uninstall must exit 0"
        assert exit_code_2 == 0, "Second uninstall must also exit 0"

    def test_spec_7_7_idempotent_install_uninstall_uninstall(self, idempotency_env, claude_bin):
        """Verify: Install followed by two uninstall runs all exit 0.

        Given: A marketplace with plugins
        When: install main(), then uninstall main() twice
        Then: All three runs return exit code 0
        Spec: Section 7.7 — idempotency guarantee (install + double-uninstall)
        """
        from install_claude_marketplaces import main as install_main
        from uninstall_claude_marketplaces import main as uninstall_main

        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch(f"{MODULE}.shutil.which", return_value=claude_bin),
            mock.patch(f"{MODULE}.subprocess.run", return_value=mock_result),
        ):
            install_code = install_main()
        with (
            mock.patch(f"{UNINSTALL_MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{UNINSTALL_MODULE}.subprocess.run", return_value=mock_result),
        ):
            uninstall_code_1 = uninstall_main()
            uninstall_code_2 = uninstall_main()
        assert install_code == 0, "Install must exit 0"
        assert uninstall_code_1 == 0, "First uninstall must exit 0"
        assert uninstall_code_2 == 0, "Second uninstall must exit 0"

    def test_spec_7_7_idempotent_no_errors_second_run(self, idempotency_env, claude_bin, caplog):
        """Verify: Second uninstall run produces no error logs.

        Given: A marketplace with plugins, first uninstall already run
        When: main() from uninstall script is called a second time
        Then: Second run produces no ERROR-level log messages
        Spec: Section 7.7 — idempotency guarantee (clean second run)
        """
        from uninstall_claude_marketplaces import main as uninstall_main

        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        caplog.set_level(logging.INFO)
        with (
            mock.patch(f"{UNINSTALL_MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{UNINSTALL_MODULE}.subprocess.run", return_value=mock_result),
        ):
            uninstall_main()
            caplog.clear()
            uninstall_main()
        error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_logs) == 0, f"Second run must produce no error logs: {[r.message for r in error_logs]}"

    def test_spec_7_7_idempotent_summary_consistent_second_run(self, idempotency_env, claude_bin, caplog):
        """Verify: Both uninstall runs produce identical summary logs.

        Given: A marketplace with plugins
        When: main() from uninstall script is called twice
        Then: Both runs produce the same Uninstall summary message
        Spec: Section 7.7 — idempotency guarantee (consistent output)
        """
        from uninstall_claude_marketplaces import main as uninstall_main

        mock_result = mock.Mock(returncode=0, stdout="ok", stderr="")
        caplog.set_level(logging.INFO)

        def get_summary() -> list[str]:
            return [r.message for r in caplog.records if r.levelno == logging.INFO and "Uninstall summary" in r.message]

        with (
            mock.patch(f"{UNINSTALL_MODULE}.locate_claude_binary", return_value=claude_bin),
            mock.patch(f"{UNINSTALL_MODULE}.subprocess.run", return_value=mock_result),
        ):
            uninstall_main()
            summaries_1 = get_summary()
            caplog.clear()
            uninstall_main()
            summaries_2 = get_summary()
        assert len(summaries_1) == 1, "First run must produce exactly one summary"
        assert len(summaries_2) == 1, "Second run must produce exactly one summary"
        assert summaries_1[0] == summaries_2[0], (
            f"Summary messages must be identical: '{summaries_1[0]}' vs '{summaries_2[0]}'"
        )
