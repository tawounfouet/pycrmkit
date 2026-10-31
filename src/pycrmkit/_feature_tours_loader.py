"""Load trusted, installed PyCRMKit tour resources without a repository checkout.

Only the six allowlisted package assets can be executed. Filesystem-supplied
paths and arbitrary user scripts are not accepted as tour names.
"""

from __future__ import annotations

import sys
from importlib import resources, util
from importlib.machinery import SourceFileLoader
from types import ModuleType

TOUR_FILES: tuple[str, ...] = (
    "01_core_crm.py",
    "02_sales_pipelines.py",
    "03_events_and_webhooks.py",
    "04_data_operations.py",
    "05_segmentation_queries.py",
    "06_campaigns_v1_2.py",
)


def load_tour(filename: str) -> ModuleType:
    """Import one trusted Python source resource included in the installed package."""
    if filename not in TOUR_FILES:
        raise ValueError("Unknown or unsupported PyCRMKit feature tour")

    resource = resources.files("pycrmkit").joinpath("_feature_tours", f"{filename}.txt")
    if not resource.is_file():
        raise FileNotFoundError(f"Required packaged feature tour missing: {filename}")

    module_name = "pycrmkit._feature_tour_" + filename.removesuffix(".py")
    with resources.as_file(resource) as path:
        loader = SourceFileLoader(module_name, str(path))
        spec = util.spec_from_loader(module_name, loader)
        if spec is None:
            raise ImportError(f"Could not build feature tour import spec: {filename}")
        module = util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            loader.exec_module(module)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise
    return module


def run_tour(filename: str) -> object:
    """Run the entrypoint exported by a bundled tour."""
    module = load_tour(filename)
    execute = getattr(module, "run_tour", None)
    if not callable(execute):
        raise AttributeError(f"Packaged feature tour has no run_tour entrypoint: {filename}")
    result: object = execute()
    return result
