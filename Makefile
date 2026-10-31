.PHONY: help install install-dev tours test test-unit lint format quality typecheck coverage docs-build docs-serve build smoke verify migration-check migration-upgrade migration-downgrade clean

help:
	@echo "PyCRMKit Developer Commands:"
	@echo "  make cli                 Run PyCRMKit CLI help"
	@echo "  make cli-doctor          Run PyCRMKit system diagnostics"
	@echo "  make tours               Run autonomous feature tours suite (<150ms)"
	@echo "  make test                Run full pytest test suite"
	@echo "  make test-unit           Run unit tests excluding integration/e2e"
	@echo "  make lint                Check code with Ruff"
	@echo "  make format              Format code with Ruff"
	@echo "  make quality             Run Ruff checks, format check, and Mypy strict"
	@echo "  make typecheck           Run Mypy typechecker"
	@echo "  make coverage            Run tests with code coverage report"
	@echo "  make docs-build          Build documentation with MkDocs"
	@echo "  make docs-serve          Serve documentation locally with MkDocs"
	@echo "  make build               Build sdist and wheel distribution packages"
	@echo "  make smoke               Verify package version and basic import"
	@echo "  make verify              Run tours, unit tests, quality checks, and build"
	@echo "  make clean               Clean build artifacts and caches"

install:
	python -m pip install -e .

install-dev:
	python -m pip install -e ".[dev]"

cli:
	PYTHONPATH=src python3 -m pycrmkit.cli --help

cli-doctor:
	PYTHONPATH=src python3 -m pycrmkit.cli doctor

tours:
	python3 examples/feature_tours/run_all_tours.py

test:
	pytest

test-unit:
	pytest -m "not integration and not e2e" tests/unit

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src/pycrmkit

quality:
	ruff check .
	ruff format --check .
	mypy src/pycrmkit

coverage:
	pytest --cov=pycrmkit --cov-report=term-missing --cov-report=xml

docs-build:
	mkdocs build --strict

docs-serve:
	mkdocs serve

build:
	python -m build

smoke:
	python -c "import pycrmkit; print(pycrmkit.__version__)"

cli:
	pck --help

dashboard:
	pck dashboard

doctor:
	pck doctor

verify: tours test-unit quality build

migration-check:
	alembic check

migration-upgrade:
	alembic upgrade head

migration-downgrade:
	alembic downgrade base

clean:
	rm -rf build dist site .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml
