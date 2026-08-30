from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_support_path = Path(__file__).resolve().parents[1] / "_support.py"
_spec = spec_from_file_location("_stock_tracker_test_support", _support_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load shared test support from {_support_path}")
_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

for _name in dir(_module):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_module, _name)
