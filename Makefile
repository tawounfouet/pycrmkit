.PHONY: test test-unit lint format typecheck coverage build smoke migration-check migration-upgrade migration-downgrade clean

test:
	pytest

test-unit:
	pytest -m "not integration and not e2e"

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src/pycrmkit

coverage:
	pytest --cov=pycrmkit --cov-report=term-missing --cov-report=xml

build:
	python -m build

smoke:
	python -c "import pycrmkit; print(pycrmkit.__version__)"

migration-check:
	alembic check

migration-upgrade:
	alembic upgrade head

migration-downgrade:
	alembic downgrade base

clean:
	rm -rf build dist site .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml
