#!/bin/bash
set -e

echo "🧪 Running Lead Scoring API Tests"

# Install dependencies if needed
echo "📦 Installing dependencies..."
uv sync --dev

# Run security checks
echo "🔒 Running security checks..."
uv run bandit -r app/ -f json -o security-report.json || echo "Security warnings found"

# Run linting
echo "📝 Running code formatting and linting..."
uv run black --check app/ tests/ || echo "Code formatting issues found"
uv run ruff check app/ tests/ || echo "Linting issues found"

# Run type checking
echo "🔍 Running type checking..."
uv run mypy app/ || echo "Type checking issues found"

# Run tests with coverage
echo "🧪 Running tests with coverage..."
uv run pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

echo "✅ All tests completed!"
echo "📊 Coverage report generated in htmlcov/"