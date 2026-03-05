SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

.PHONY: help lint format format-check check test test-unit test-functional validate clean

help: ## Show available targets and their descriptions
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint: ## Run all linters (ruff check, markdownlint, yamllint)
	ruff check .
	markdownlint '**/*.md'
	yamllint .

format: ## Auto-fix formatting issues (ruff format)
	ruff format .

format-check: ## Verify formatting without modifying files (ruff format --check, CI-safe)
	ruff format --check .

check: lint format-check ## Run all checks: lint + format verification (read-only, CI-safe)

test: ## Run full test suite with coverage (pytest + pytest-cov)
	python3 -m pytest --cov --cov-report=term-missing

test-unit: ## Run unit tests only (pytest -m unit)
	python3 -m pytest -m unit

test-functional: ## Run functional tests only (pytest -m functional)
	python3 -m pytest -m functional

validate: check test ## Full CI equivalent: check + test

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -f .coverage
	find . -type f -name '*.pyc' -delete
