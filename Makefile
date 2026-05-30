.PHONY: run sync install browser test lint format check clean help

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ── Run ────────────────────────────────────────────────────────────────
run: ## Run the Coles price tracker
	uv run python main.py

# ── Dependencies ───────────────────────────────────────────────────────
sync: ## Sync dependencies from pyproject.toml
	uv sync

install: sync browser ## Full install (deps + browser)

browser: ## Install Patchright Chromium browser (required for scraping)
	uv run patchright install chromium

# ── Linting & Formatting ───────────────────────────────────────────────
lint: ## Lint with ruff
	uv run ruff check .

format: ## Format with ruff
	uv run ruff format .

check: lint ## Run all checks (lint only for now)
	@echo "✓ All checks passed"

# ── Testing ────────────────────────────────────────────────────────────
test: ## Run tests with pytest
	uv run pytest -v

test-cov: ## Run tests with coverage report
	uv run pytest --cov=. --cov-report=term-missing -v

# ── Cleanup ────────────────────────────────────────────────────────────
clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .coverage __pycache__ .ruff_cache
	@echo "✓ Cleaned"
