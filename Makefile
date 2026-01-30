.PHONY: help format check lint test clean

help:
	@echo "Available targets:"
	@echo "  format  - Format code with ruff"
	@echo "  check   - Check code formatting and linting (no changes)"
	@echo "  lint    - Alias for check"
	@echo "  clean   - Remove Python cache files"

format:
	uv run ruff format .
	uv run ruff check --fix .

check:
	uv run ruff format --check .
	uv run ruff check .

lint: check

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
