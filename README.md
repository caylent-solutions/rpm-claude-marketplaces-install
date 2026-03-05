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

### Available Make Targets

Run `make help` to see all available targets.
