import importlib
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "common"

if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))


_SERVICE_TOP_LEVELS = {
    "db_logics",
    "deps",
    "jobs",
    "llm_limits",
    "main",
    "models",
    "routers",
    "services",
    "ui_utils",
}


def load_backend_module(service_dir: str, module_name: str):
    """Import a backend module whose package names collide with other services."""
    backend = ROOT / service_dir / "backend"
    for loaded_name in list(sys.modules):
        top_level = loaded_name.partition(".")[0]
        if top_level in _SERVICE_TOP_LEVELS:
            del sys.modules[loaded_name]

    for path in (str(backend), str(COMMON)):
        while path in sys.path:
            sys.path.remove(path)
    sys.path.insert(0, str(COMMON))
    sys.path.insert(0, str(backend))
    return importlib.import_module(module_name)


def pytest_report_header(config):
    return [
        "stock_tracker backend unit suite",
        "external systems mocked: database, market/news/doc/chat providers, email, storage",
    ]


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    outcomes = ("passed", "failed", "error", "skipped", "xfailed", "xpassed")
    area_counts = defaultdict(Counter)
    test_reports = []

    for outcome in outcomes:
        for report in terminalreporter.stats.get(outcome, []):
            nodeid = getattr(report, "nodeid", "")
            if not nodeid.startswith("tests/"):
                continue
            parts = nodeid.split("/")
            area = parts[1] if len(parts) > 1 else "unknown"
            area_counts[area][outcome] += 1
            test_reports.append((area, nodeid, outcome))

    if not area_counts:
        return

    terminalreporter.write_line("")
    terminalreporter.write_line("Backend Unit Test Report")
    terminalreporter.write_line("========================")
    terminalreporter.write_line("")
    terminalreporter.write_line("Area Summary")
    terminalreporter.write_line("------------")
    terminalreporter.write_line(
        f"{'Area':<16} {'Pass':>5} {'Fail':>5} {'Error':>5} {'Skip':>5}"
    )
    terminalreporter.write_line(
        f"{'-' * 16:<16} {'-' * 5:>5} {'-' * 5:>5} {'-' * 5:>5} {'-' * 5:>5}"
    )
    for area in _area_order(area_counts):
        counts = area_counts[area]
        terminalreporter.write_line(
            f"{area:<16} "
            f"{counts['passed']:>5} "
            f"{counts['failed']:>5} "
            f"{counts['error']:>5} "
            f"{counts['skipped']:>5}"
        )

    total_counts = Counter()
    for counts in area_counts.values():
        total_counts.update(counts)
    terminalreporter.write_line(
        f"{'TOTAL':<16} "
        f"{total_counts['passed']:>5} "
        f"{total_counts['failed']:>5} "
        f"{total_counts['error']:>5} "
        f"{total_counts['skipped']:>5}"
    )

    terminalreporter.write_line("")
    terminalreporter.write_line("Detailed Checks")
    terminalreporter.write_line("---------------")
    reports_by_area = defaultdict(list)
    for area, nodeid, outcome in test_reports:
        reports_by_area[area].append((nodeid, outcome))

    for area in _area_order(reports_by_area):
        terminalreporter.write_line("")
        terminalreporter.write_line(area)
        for nodeid, outcome in reports_by_area[area]:
            status_text = _status_text(outcome)
            status_marker = _status_marker(outcome)
            summary = _readable_test_name(nodeid)
            params = _readable_params(nodeid)
            line = f"  {status_marker} {status_text:<5} {summary}"
            if params:
                line += f" ({params})"
            terminalreporter.write_line(line)


def _area_order(items) -> list[str]:
    preferred = ["common", "ui_service", "stock_manager", "chat_agent"]
    known = [area for area in preferred if area in items]
    extra = sorted(area for area in items if area not in preferred)
    return known + extra


def _status_text(outcome: str) -> str:
    return {
        "passed": "PASS",
        "failed": "FAIL",
        "error": "ERROR",
        "skipped": "SKIP",
        "xfailed": "XFAIL",
        "xpassed": "XPASS",
    }.get(outcome, outcome.upper())


def _status_marker(outcome: str) -> str:
    return {
        "passed": "[+]",
        "failed": "[!]",
        "error": "[!]",
        "skipped": "[-]",
        "xfailed": "[-]",
        "xpassed": "[!]",
    }.get(outcome, "[?]")


def _readable_params(nodeid: str) -> str:
    raw_name = nodeid.rsplit("::", 1)[-1]
    _function_name, separator, params = raw_name.partition("[")
    if not separator:
        return ""
    return params.rstrip("]")


def _readable_test_name(nodeid: str) -> str:
    raw_name = nodeid.rsplit("::", 1)[-1]
    function_name = raw_name.partition("[")[0]
    text = function_name.removeprefix("test_").replace("_", " ")
    return text
