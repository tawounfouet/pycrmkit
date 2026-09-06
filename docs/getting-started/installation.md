# Installation

PyCRMKit is currently in pre-alpha engineering development.

For repository development:

```bash
git clone https://github.com/tawounfouet/pycrmkit.git
cd pycrmkit
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Verify:

```bash
python -c "import pycrmkit; print(pycrmkit.__version__)"
pytest
```
