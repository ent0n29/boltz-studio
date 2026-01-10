.PHONY: install dev run test lint clean build

# Install in production mode
install:
	uv venv
	. .venv/bin/activate && uv pip install .

# Install in development mode with dev dependencies
dev:
	uv venv
	. .venv/bin/activate && uv pip install -e ".[dev]"

# Verify backend imports
build:
	. .venv/bin/activate && python -c "import boltz_studio"

# Run the application
run:
	. .venv/bin/activate && boltz-studio

# Run tests
test:
	. .venv/bin/activate && pytest tests/ -v

# Run linter
lint:
	. .venv/bin/activate && ruff check boltz_studio/ tests/

# Fix linting issues
lint-fix:
	. .venv/bin/activate && ruff check --fix boltz_studio/ tests/

# Clean build artifacts
clean:
	rm -rf .venv .pytest_cache .ruff_cache *.egg-info build dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f boltz_studio.db

# Full reset and setup
reset: clean dev

# Show help
help:
	@echo "Boltz Studio - Development Commands"
	@echo ""
	@echo "  make dev   - Set up development environment"
	@echo "  make run   - Run the application"
	@echo "  make build - Verify backend imports"
	@echo "  make test  - Run tests"
	@echo "  make lint  - Check code style"
	@echo "  make clean - Remove build artifacts"
	@echo "  make reset - Clean and reinstall"
