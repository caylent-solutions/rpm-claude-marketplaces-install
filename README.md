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
| `CLAUDE_MARKETPLACES_DIR` | No | `$HOME/.claude-marketplaces` | Filesystem path to the directory containing marketplace plugins |
| `CLAUDE_REGISTER_TIMEOUT` | No | `30` | Positive integer string — timeout in seconds for each marketplace registration subprocess. Invalid values cause exit with code 1. |
| `CLAUDE_INSTALL_TIMEOUT` | No | `30` | Positive integer string — timeout in seconds for each plugin install subprocess. Invalid values cause exit with code 1. |

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
