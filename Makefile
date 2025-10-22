# Makefile for Homelab Autopilot development

.PHONY: help format lint test check install clean

# Default target
help:
	@echo "Homelab Autopilot - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  format    - Format code with black and isort"
	@echo "  lint      - Run pylint on code"
	@echo "  test      - Run all tests"
	@echo "  check     - Run all checks (format + lint + test)"
	@echo "  install   - Install dependencies"
	@echo "  clean     - Remove generated files"
	@echo ""

# Format code with black and isort
format:
	@echo "🎨 Formatting code with black..."
	@black core/ lib/ plugins/ tests/
	@echo ""
	@echo "📦 Sorting imports with isort..."
	@isort core/ lib/ plugins/ tests/
	@echo "✅ Formatting complete"

# Run pylint
lint:
	@echo "🔍 Running pylint..."
	@pylint core/ lib/ plugins/ --fail-under=8.0
	@echo "✅ Pylint check passed"

# Run tests
test:
	@echo "🧪 Running tests..."
	@pytest tests/ -v --cov
	@echo "✅ Tests complete"

# Run all checks (this is what you run before committing)
check: format lint test
	@echo ""
	@echo "🎉 All checks passed! Ready to commit."

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	@pip install -r requirements-dev.txt
	@pip install -e .
	@echo "✅ Installation complete"

# Clean generated files
clean:
	@echo "🧹 Cleaning generated files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@rm -rf .pytest_cache htmlcov .coverage coverage.xml
	@rm -rf *.egg-info
	@echo "✅ Cleanup complete"
