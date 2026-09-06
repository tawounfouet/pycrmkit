# Installation

PyCRMKit `0.1.0` is the first stable CRM Core milestone. The project remains pre-1.0, so only the documented `0.1` public surface carries the `0.1.x` compatibility promise.

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
