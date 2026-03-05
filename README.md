# rpm-claude-marketplaces-install

Install and uninstall scripts for Claude Code marketplace plugins.

## Install Script

The `install_claude_marketplaces.py` module implements the install
workflow defined in the specification (section 7.4). It discovers the
`claude` CLI binary, registers marketplace directories, and installs
plugins.

### Key Functions

- `locate_claude_binary()` — Locates the `claude` CLI on `$PATH` using
  `shutil.which("claude")`. Returns the absolute path if found, or exits
  with code 127 if not found. No fallback paths are attempted.
- `get_marketplace_dir()` — Returns the marketplace directory path. Reads
  `CLAUDE_MARKETPLACES_DIR` env var if set, otherwise defaults to
  `$HOME/.claude-marketplaces`.
- `verify_marketplace_dir(path)` — Verifies the marketplace directory exists.
  Exits with code 0 and logs a warning if the directory is missing.
- `discover_marketplace_entries(path)` — Discovers marketplace subdirectories.
  Returns a sorted list of non-hidden directory entries. Excludes broken
  symlinks (logged as warnings).
- `read_marketplace_name(path)` — Reads the marketplace name from
  `.claude-plugin/marketplace.json` inside the given directory. Raises
  `FileNotFoundError`, `KeyError`, or `json.JSONDecodeError` on failure.
- `register_marketplace(claude_bin, path)` — Registers a marketplace directory
  with the Claude CLI. Returns `True` on success, `False` on failure.
  Idempotent — re-registering an already-registered marketplace succeeds.
- `discover_plugins(marketplace_path)` — Discovers plugins within a marketplace
  directory by scanning immediate subdirectories for
  `.claude-plugin/plugin.json`. Returns a list of `(plugin_name, plugin_path)`
  tuples. Subdirectories without `plugin.json` are skipped.
- `install_plugin(claude_bin, plugin_name, marketplace_name)` — Installs a
  plugin via `claude plugin install <name>@<marketplace> --scope user`. Returns
  `True` on success, `False` on failure. Timeouts and errors are logged.
- `log_summary(marketplaces_processed, marketplaces_registered, plugins_installed)`
  — Logs a summary of the install run with counts of marketplaces processed,
  newly registered, and plugins installed.
- `main()` — Orchestrates the complete 7-step install process from spec section
  7.4. Returns exit code `0` on full success, non-zero if any operation failed.

### Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CLAUDE_MARKETPLACES_DIR` | No | `$HOME/.claude-marketplaces` | Filesystem path to the directory containing marketplace plugins. Code-level default used when env var is unset. |
| `CLAUDE_REGISTER_TIMEOUT` | No | (code-level) | Positive integer string — timeout in seconds for each marketplace registration subprocess. Code-level default used when env var is unset. Invalid values cause exit with code 1. |
| `CLAUDE_INSTALL_TIMEOUT` | No | (code-level) | Positive integer string — timeout in seconds for each plugin install subprocess. Code-level default used when env var is unset. Invalid values cause exit with code 1. |
| `CLAUDE_UNINSTALL_TIMEOUT` | No | (code-level) | Positive integer string — timeout in seconds for each uninstall/remove subprocess. Code-level default used when env var is unset. Invalid values cause exit with code 1. |

### Error Handling (Spec 7.5)

| Condition | Exit Code | Log Level | Behavior |
| --- | --- | --- | --- |
| `claude` binary not found on `$PATH` | 127 | ERROR | Abort immediately |
| Marketplace directory does not exist | 0 | WARNING | Exit gracefully (no work to do) |
| No marketplace entries found | 0 | WARNING | Return 0 (no work to do) |
| Broken symlink in marketplace directory | N/A | WARNING | Skip entry, continue processing |
| `marketplace add` subprocess fails | N/A | ERROR | Log error, continue to next marketplace |
| `plugin install` subprocess fails | N/A | ERROR | Log error, continue to next plugin |
| Mixed successes and failures | 1 | INFO | Log summary, exit 1 |
| All operations succeed | 0 | INFO | Log summary, exit 0 |

### Logging

The install script configures logging via `logging.basicConfig()` at the
start of `main()`. All output uses the Python `logging` module — `print()`
is never used. Log messages include relevant context such as file paths,
marketplace names, and plugin identifiers.

## Uninstall Script

The `uninstall_claude_marketplaces.py` module implements the uninstall
workflow defined in the specification (section 7.7). It discovers installed
plugins and uninstalls them, then removes marketplace registrations.

### Uninstall Functions

- `_get_uninstall_timeout()` — Reads and validates `CLAUDE_UNINSTALL_TIMEOUT`
  from the environment. Returns the timeout value as an integer. Exits with
  code 1 if the value is not a valid positive integer.
- `uninstall_plugin(claude_bin, plugin_name, marketplace_name)` — Uninstalls a
  plugin via `claude plugin uninstall <name>@<marketplace> --scope user`. Returns
  `True` on success, `False` on failure. Timeouts and errors are logged.
- `remove_marketplace(claude_bin, marketplace_path)` — Removes a marketplace
  registration via `claude plugin marketplace remove <path>`. Returns `True` on
  success, `False` on failure. On failure, logs an ERROR and returns `False`
  without raising — the caller continues processing remaining marketplaces. Removing
  an already-removed marketplace is idempotent: the CLI returns success and the
  function returns `True`.
- `uninstall_marketplace(claude_bin, marketplace_path, marketplace_name)` —
  Orchestrates per-marketplace uninstall: discovers plugins using the shared
  `discover_plugins()` function from the install module, uninstalls each plugin,
  then removes the marketplace registration. Returns `True` if all operations
  succeeded, `False` if any operation failed.
- `log_uninstall_summary(marketplaces_processed, plugins_uninstalled)` — Logs a
  summary of the uninstall run with counts of marketplaces processed and plugins
  uninstalled.
- `main()` — Orchestrates the complete uninstall process from spec section 7.7.
  Returns exit code `0` on full success or no work, `1` if any operation failed,
  `127` if the `claude` binary is not found on `$PATH`.

### Uninstall Exit Codes

| Condition | Exit Code | Behavior |
| --- | --- | --- |
| `claude` binary not found on `$PATH` | 127 | Abort immediately |
| Marketplace directory does not exist | 0 | Exit gracefully (nothing to uninstall) |
| No marketplace entries found | 0 | Exit gracefully (nothing to uninstall) |
| All operations succeed | 0 | Log summary, exit 0 |
| Any plugin uninstall or marketplace remove fails | 1 | Log errors, continue, exit 1 |

### Uninstall Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CLAUDE_UNINSTALL_TIMEOUT` | No | (code-level) | Positive integer string — timeout in seconds for each uninstall/remove subprocess. Code-level default used when env var is unset. Invalid values cause exit with code 1. |
| `LOG_LEVEL` | No | (code-level) | Logging level for the uninstall script when run as a standalone process. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Invalid values cause exit with code 1. Only applied when invoked via `python3 uninstall_claude_marketplaces.py`. |

## Developer Setup

### Prerequisites

- Python 3.11+
- Make
- [ruff](https://docs.astral.sh/ruff/) (Python linter/formatter)
- [markdownlint-cli](https://github.com/igorshubovych/markdownlint-cli) (Markdown linter)
- [yamllint](https://yamllint.readthedocs.io/) (YAML linter)

### Running Tests

```bash
# Run full validation (lint + format check + tests)
make validate

# Run all tests with coverage
make test

# Run unit tests only
make test-unit

# Run functional tests only
make test-functional
```

### Linting and Formatting

```bash
# Run all linters
make lint

# Auto-fix formatting issues
make format

# Check formatting without modifying files (CI-safe)
make check
```

### Cleaning Build Artifacts

```bash
make clean
```

### Test Structure

- `tests/unit/` — Unit tests (fast, isolated, `@pytest.mark.unit`)
- `tests/test_harness_smoke.py` — Functional smoke tests (`@pytest.mark.functional`)
- `tests/fixtures/` — Test data files (sample marketplaces, linter test files)
- `tests/conftest.py` — Shared pytest fixtures

### Available Fixtures

| Fixture | Description |
| --- | --- |
| `repo_root` | Path to the repository root directory |
| `makefile_path` | Path to the Makefile |
| `mock_marketplace_dir` | Temporary directory with sample marketplace structure |
| `mock_claude_cli` | Callable mock simulating the claude CLI |
| `claude_bin` | Configurable path to the claude binary for tests |

### Available Make Targets

Run `make help` to see all available targets.
