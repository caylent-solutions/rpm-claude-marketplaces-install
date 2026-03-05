# Test Fixtures

This directory contains test data files used by the test suite.

## Fixture Files

### Linter Test Files

- `linter-test-bad.py` — Intentionally invalid Python (unused imports) for ruff validation.
- `linter-test-bad.md` — Intentionally invalid Markdown (heading skip, blank lines) for markdownlint validation.
- `linter-test-bad.yml` — Intentionally invalid YAML (indentation, duplicate keys) for yamllint validation.

### Sample Marketplace

- `sample-marketplace/` — A complete sample marketplace plugin directory structure:
  - `plugin.json` — Plugin metadata (name, version, description, author).
  - `README.md` — Plugin documentation.

This directory is used by tests that verify install/uninstall script behavior
against realistic marketplace structures. The `mock_marketplace_dir` fixture
in `conftest.py` creates a similar structure in a temporary directory for
test isolation.
