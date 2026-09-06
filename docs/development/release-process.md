# Release Process

PyCRMKit uses Semantic Versioning meaning with PEP 440 prerelease syntax.

Examples:

```text
0.1.0a1
0.1.0b1
0.1.0rc1
0.1.0
```

Before a release:

```bash
python scripts/release_check.py
```

The release check validates linting, typing, tests, documentation, package build, artifact installation, and smoke import.

## Stable gate

For stable releases, the built wheel must install into a clean virtual environment and execute the functional `scripts/smoke_test.py` path against the installed package. The stable tag must point to the exact qualified commit.
