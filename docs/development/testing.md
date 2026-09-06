# Testing

The foundation uses:

```text
pytest
pytest-cov
Ruff
mypy
pre-commit
```

The long-term test topology is:

```text
tests/
├── unit/
├── contracts/
├── adapters/
├── integration/
├── e2e/
└── smoke/
```

Repository adapters must eventually pass the same contract suites.
