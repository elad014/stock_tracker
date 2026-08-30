from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import os
import re
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"
WIDTH = 60
STATUSES = ("passed", "failed", "errors", "skipped")
STATUS_LABELS = {
    "passed": "PASS",
    "failed": "FAIL",
    "errors": "ERROR",
    "skipped": "SKIP",
}
COMPONENT_ORDER = (
    "ADMINISTRATION",
    "AUTHENTICATION",
    "CACHE / STORAGE",
    "CHAT / LLM",
    "DOCUMENTS",
    "NEWS",
    "SERVICE COMMUNICATION",
    "STOCKS / TWELVE DATA",
    "STOCKS / WATCHLIST",
)

METHOD_LABELS = {
    "test_user_registration_valid_user_can_register": "Register a valid new user",
    "test_user_registration_duplicate_email_rejected": "Reject registration with duplicate email",
    "test_register_creates_user_after_duplicate_checks": "Register user after duplicate checks",
    "test_register_rejects_duplicate_email": "Reject duplicate registration email",
    "test_login_correct_credentials_returns_access_token": "Login with valid credentials",
    "test_login_incorrect_password_rejected": "Reject login with invalid password",
    "test_login_success_resets_email_limiter_and_returns_bearer_token": "Login returns bearer token and resets limiter",
    "test_login_failure_records_email_and_ip_attempts": "Track failed login attempts by email and IP",
    "test_login_locked_user_is_forbidden": "Reject login for locked user",
    "test_password_reset_request_sends_mail_for_known_unlocked_user": "Request password reset",
    "test_password_reset_request_does_not_reveal_unknown_email": "Hide unknown email during password reset request",
    "test_password_reset_confirm_changes_password": "Confirm password reset",
    "test_password_reset_confirm_updates_known_unlocked_user": "Confirm password reset for unlocked user",
    "test_profile_settings_update_changes_email_and_sends_notifications": "Update user profile/settings",
    "test_update_me_updates_email_and_returns_fresh_token": "Update profile and return a fresh token",
    "test_update_me_rejects_wrong_current_password": "Reject profile update with wrong password",
    "test_admin_authorization_rejects_non_admin_user": "Reject non-admin access to admin route",
    "test_admin_lists_users_through_admin_route": "List users through admin route",
    "test_admin_creates_user_with_hashed_password": "Create admin-managed user with hashed password",
    "test_admin_locks_and_unlocks_user_profile": "Lock and unlock a user account",
    "test_admin_assigns_stock_to_user": "Assign stock to a user",
    "test_admin_deletes_user_and_runs_cleanup_steps": "Delete user and run cleanup steps",
    "test_watchlist_add_stock_not_yet_stored_persists_quote_history_and_watchlist": "Add a new stock and create it in the stocks table",
    "test_ui_service_adds_stock_via_stock_manager_route_bridge": "Add stock through ui-service to stock-manager",
    "test_ui_service_prevents_duplicate_watchlist_entry": "Reject duplicate watchlist entry",
    "test_ui_service_lists_and_removes_watchlist_entry_via_bridge": "List and remove watchlist entry through service bridge",
    "test_watchlist_list_returns_user_stocks": "List user watchlist",
    "test_watchlist_remove_deletes_membership": "Remove stock from watchlist",
    "test_watchlist_remove_missing_membership_returns_404": "Reject removing stock not in watchlist",
    "test_provider_unknown_symbol_maps_to_404": "Reject unknown stock symbol",
    "test_stock_quote_all_expected_database_columns_populated": "Persist all expected stock quote fields",
    "test_stock_quote_retrieval_reads_persisted_quote": "Read persisted stock quote",
    "test_stock_history_retrieval_reads_saved_database_rows": "Read saved stock history from database",
    "test_stock_history_invalid_range_rejected": "Reject invalid stock history range",
    "test_stock_summary_update_persists_summary_columns": "Persist stock summary fields",
    "test_get_quote_maps_api_payload_to_quote_data_including_open": "Map Twelve Data quote response including open price",
    "test_upsert_quote_populates_all_quote_columns_including_open": "Upsert all quote columns including open price",
    "test_quote_normalization_converts_types_and_preserves_open": "Normalize quote types and preserve open price",
    "test_s3_clients_are_reused_for_same_cache_key": "Reuse cached S3 client for the same storage configuration",
    "test_internal_api_key_auth_accepts_shared_key": "Accept valid internal API key",
    "test_internal_api_key_auth_rejects_invalid_key": "Reject invalid internal API key",
    "test_news_route_fetches_finnhub_articles_with_provider_mock": "Fetch news articles with mocked Finnhub provider",
    "test_news_route_maps_provider_not_found_to_404": "Map news provider not-found response to 404",
    "test_stored_news_route_reads_database_rows_without_provider_call": "Read stored news without provider call",
    "test_search_and_summarize_uses_stored_articles_and_mocked_gemini": "Search and summarize stored news with mocked Gemini",
    "test_article_sync_route_maps_finnhub_response_and_persists_articles": "Map Finnhub articles and persist them",
    "test_article_summarize_route_claims_article_and_uses_mocked_gemini": "Summarize article with mocked Gemini",
    "test_doc_agent_upload_route_processes_chunks_and_persists_vectors": "Upload document, create chunks, and persist vectors",
    "test_doc_agent_ask_route_retrieves_vectors_and_uses_mocked_gemini": "Answer document question using stored chunks and mocked Gemini",
    "test_doc_agent_delete_vectors_and_purge_user_routes_clean_index_data": "Delete document vectors and purge user index data",
    "test_ui_document_upload_route_stores_pdf_and_calls_doc_agent": "Upload PDF through ui-service and call doc-agent",
    "test_chat_agent_route_runs_tool_loop_with_mocked_gemini": "Run chat request with tool loop and mocked Gemini",
    "test_chat_agent_rejects_empty_message": "Reject empty chat message",
    "test_chat_agent_clear_session_route_removes_history": "Clear chat session history",
    "test_ui_chat_route_sends_request_to_chat_agent_client": "Send chat request from ui-service to chat-agent",
}


@dataclass
class TestRecord:
    component: str
    description: str
    status: str
    reason: str = ""


class Stats:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, int]] = defaultdict(lambda: {key: 0 for key in STATUSES})

    def add(self, key: str, status: str) -> None:
        self.data[key][status] += 1

    def merge(self, other: "Stats") -> None:
        for key, values in other.data.items():
            for status, count in values.items():
                self.data[key][status] += count


class Style:
    def __init__(self, stream) -> None:
        self.colors = self._supports_color(stream)
        self.unicode = self._supports_unicode(stream)

    @staticmethod
    def _supports_color(stream) -> bool:
        if os.getenv("NO_COLOR"):
            return False
        if os.getenv("FORCE_COLOR"):
            return True
        term = os.getenv("TERM", "")
        return bool(getattr(stream, "isatty", lambda: False)()) and term.lower() != "dumb"

    @staticmethod
    def _supports_unicode(stream) -> bool:
        encoding = getattr(stream, "encoding", None) or ""
        try:
            "✓ ✗ ⚠ ○ ─ ╭╮╰╯├┤┬┴┼│".encode(encoding or "utf-8")
        except (LookupError, UnicodeEncodeError):
            return False
        return True

    def color(self, text: str, code: str) -> str:
        if not self.colors:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, text: str) -> str:
        return self.color(text, "1")

    def green(self, text: str) -> str:
        return self.color(text, "32")

    def red(self, text: str) -> str:
        return self.color(text, "31")

    def bright_red(self, text: str) -> str:
        return self.color(text, "91")

    def yellow(self, text: str) -> str:
        return self.color(text, "33")

    def cyan(self, text: str) -> str:
        return self.color(text, "36")

    @property
    def symbols(self) -> dict[str, str]:
        if self.unicode:
            return {
                "passed": "✓",
                "failed": "✗",
                "errors": "⚠",
                "skipped": "○",
            }
        return {
            "passed": "[PASS]",
            "failed": "[FAIL]",
            "errors": "[ERROR]",
            "skipped": "[SKIP]",
        }

    @property
    def line(self) -> str:
        return "─" * WIDTH if self.unicode else "-" * WIDTH


def split_words(value: str) -> str:
    value = re.sub(r"Tests$", "", value)
    value = re.sub(r"Integration$", "", value)
    value = re.sub(r"(?<!^)(?=[A-Z])", " ", value)
    value = value.replace("_", " ")
    return " ".join(value.split()).strip()


def sentence_from_method(method: str) -> str:
    phrase = method.removeprefix("test_").replace("_", " ")
    replacements = {
        " api ": " API ",
        " db ": " database ",
        " llm ": " LLM ",
        " ui ": " UI ",
        " pdf ": " PDF ",
        " s3 ": " S3 ",
        " url ": " URL ",
        " id ": " ID ",
        " ip ": " IP ",
        " json ": " JSON ",
    }
    phrase = f" {phrase} "
    for old, new in replacements.items():
        phrase = phrase.replace(old, new)
    phrase = " ".join(phrase.split())
    return phrase[:1].upper() + phrase[1:]


def human_description(test: unittest.case.TestCase) -> str:
    method = getattr(test, "_testMethodName", "")
    if method in METHOD_LABELS:
        return METHOD_LABELS[method]
    doc = test.shortDescription()
    if doc:
        return doc.strip()
    if method:
        return sentence_from_method(method)
    return str(test)


def component_for(test: unittest.case.TestCase) -> str:
    explicit = getattr(test.__class__, "COMPONENT", None)
    if explicit:
        return str(explicit)

    test_id = test.id().lower()
    module = test.__class__.__module__.lower()
    class_name = test.__class__.__name__.lower()

    if "object_storage_client" in test_id or "cache" in test_id:
        return "CACHE / STORAGE"
    if "internalauth" in class_name or "internal_auth" in module or "internal_service" in test_id:
        return "SERVICE COMMUNICATION"
    if "admin" in test_id or "job" in class_name:
        return "ADMINISTRATION"
    if any(term in test_id for term in ("auth", "login", "password", "validator", "current_user", "rate_limiter")):
        return "AUTHENTICATION"
    if any(term in class_name for term in ("document", "doc", "pdf", "embedding", "objectstorage")):
        return "DOCUMENTS"
    if any(term in test_id for term in ("chat", "llm", "prompt", "session_store")):
        return "CHAT / LLM"
    if any(term in test_id for term in ("news", "article", "finnhub")):
        return "NEWS"
    if "watchlist" in test_id:
        return "STOCKS / WATCHLIST"
    if any(term in test_id for term in ("stock", "quote", "history", "twelve")):
        return "STOCKS / TWELVE DATA"
    return "OTHER"


def short_reason(err) -> str:
    exc_type, exc_value, _tb = err
    if issubclass(exc_type, AssertionError):
        message = str(exc_value).strip() or "Assertion failed"
    else:
        message = f"{exc_type.__name__}: {exc_value}".strip()
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        lines = [exc_type.__name__]
    reason = "\n".join(lines[:4])
    if len(reason) > 600:
        reason = reason[:597].rstrip() + "..."
    return reason


class DetailedResult(unittest.TestResult):
    def __init__(self, layer: str) -> None:
        super().__init__()
        self.layer = layer
        self.component_stats = Stats()
        self.layer_stats = {key: 0 for key in STATUSES}
        self.records: list[TestRecord] = []

    def _record(self, status_key: str, test: unittest.case.TestCase, reason: str = "") -> None:
        component = component_for(test)
        self.component_stats.add(component, status_key)
        self.layer_stats[status_key] += 1
        self.records.append(
            TestRecord(
                component=component,
                description=human_description(test),
                status=status_key,
                reason=reason,
            )
        )

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self._record("passed", test)

    def addFailure(self, test: unittest.case.TestCase, err) -> None:
        super().addFailure(test, err)
        self._record("failed", test, short_reason(err))

    def addError(self, test: unittest.case.TestCase, err) -> None:
        super().addError(test, err)
        self._record("errors", test, short_reason(err))

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self._record("skipped", test, f"Reason: {reason}")


def discover(start_dir: str) -> unittest.TestSuite:
    sys.modules.pop("test_support", None)
    loader = unittest.TestLoader()
    return loader.discover(str(TESTS / start_dir), pattern="test*.py")


def status_text(style: Style, status_key: str) -> str:
    text = (
        f"{style.symbols[status_key]} {STATUS_LABELS[status_key]}"
        if style.unicode
        else style.symbols[status_key]
    )
    if status_key == "passed":
        return style.green(text)
    if status_key == "failed":
        return style.red(text)
    if status_key == "errors":
        return style.bright_red(text)
    if status_key == "skipped":
        return style.yellow(text)
    return text


def write_title_box(stream, style: Style, title: str) -> None:
    if style.unicode:
        inner_width = WIDTH - 2
        stream.write(style.cyan("╭" + "─" * inner_width + "╮") + "\n")
        stream.write(style.cyan("│" + title.center(inner_width) + "│") + "\n")
        stream.write(style.cyan("╰" + "─" * inner_width + "╯") + "\n")
    else:
        stream.write(style.cyan("+" + "-" * (WIDTH - 2) + "+") + "\n")
        stream.write(style.cyan("|" + title.center(WIDTH - 2) + "|") + "\n")
        stream.write(style.cyan("+" + "-" * (WIDTH - 2) + "+") + "\n")


def write_section_header(stream, style: Style, title: str) -> None:
    stream.write("\n")
    stream.write(style.cyan(style.line) + "\n")
    stream.write(style.cyan(title) + "\n")
    stream.write(style.cyan(style.line) + "\n\n")


def print_component_section(stream, style: Style, title: str, records: list[TestRecord], values: dict[str, int]) -> None:
    write_section_header(stream, style, title)

    for record in records:
        stream.write(f"{status_text(style, record.status):<14}  {record.description}\n")
        if record.reason:
            reason_color = style.red if record.status == "failed" else style.bright_red if record.status == "errors" else style.yellow
            for line in record.reason.splitlines():
                stream.write(f"  {reason_color(line)}\n")

    summary = (
        f"{values['passed']} passed  •  {values['failed']} failed  •  "
        f"{values['errors']} errors  •  {values['skipped']} skipped"
        if style.unicode
        else f"{values['passed']} passed  |  {values['failed']} failed  |  {values['errors']} errors  |  {values['skipped']} skipped"
    )
    stream.write("\n" + style.bold(summary) + "\n")


def run_layer(layer_name: str, start_dir: str, aggregate: Stats, style: Style) -> DetailedResult:
    stream = sys.stdout
    stream.write(f"\nRunning {layer_name.title()} Tests...\n")
    result = DetailedResult(layer_name)
    suite = discover(start_dir)
    start = time.perf_counter()
    suite.run(result)
    elapsed = time.perf_counter() - start
    result.elapsed = elapsed  # type: ignore[attr-defined]
    aggregate.merge(result.component_stats)

    count = sum(result.layer_stats.values())
    failed = result.layer_stats["failed"] + result.layer_stats["errors"]
    if failed:
        complete = f"{style.symbols['failed']} Completed {count} tests in {elapsed:.2f}s with {failed} problems"
        stream.write(style.red(complete) + "\n")
    else:
        complete = f"{style.symbols['passed']} Completed {count} tests in {elapsed:.2f}s"
        stream.write(style.green(complete) + "\n")
    return result


def ordered_components(component_names: set[str]) -> list[str]:
    ordered = [component for component in COMPONENT_ORDER if component in component_names]
    ordered.extend(sorted(component_names.difference(COMPONENT_ORDER)))
    return ordered


def print_detailed_results(stream, style: Style, results: list[DetailedResult], aggregate: Stats) -> None:
    records_by_component: dict[str, list[TestRecord]] = defaultdict(list)
    for result in results:
        for record in result.records:
            records_by_component[record.component].append(record)

    for component in ordered_components(set(aggregate.data)):
        print_component_section(
            stream,
            style,
            component,
            records_by_component.get(component, []),
            aggregate.data[component],
        )


def final_summary_table(style: Style, unit: DetailedResult, integration: DetailedResult) -> list[str]:
    rows = [
        ("Unit", unit.layer_stats),
        ("Integration", integration.layer_stats),
    ]
    totals = {key: unit.layer_stats[key] + integration.layer_stats[key] for key in STATUSES}

    suite_w = 23
    num_w = 8
    if style.unicode:
        top = "╭" + "─" * suite_w + "┬" + "─" * num_w + "┬" + "─" * num_w + "┬" + "─" * num_w + "┬" + "─" * 7 + "╮"
        mid = "├" + "─" * suite_w + "┼" + "─" * num_w + "┼" + "─" * num_w + "┼" + "─" * num_w + "┼" + "─" * 7 + "┤"
        bottom = "╰" + "─" * suite_w + "┴" + "─" * num_w + "┴" + "─" * num_w + "┴" + "─" * num_w + "┴" + "─" * 7 + "╯"
        line = "│ {suite:<21} │ {passed:>6} │ {failed:>6} │ {errors:>6} │ {skipped:>5} │"
    else:
        top = "+" + "-" * suite_w + "+" + "-" * num_w + "+" + "-" * num_w + "+" + "-" * num_w + "+" + "-" * 7 + "+"
        mid = "+" + "-" * suite_w + "+" + "-" * num_w + "+" + "-" * num_w + "+" + "-" * num_w + "+" + "-" * 7 + "+"
        bottom = top
        line = "| {suite:<21} | {passed:>6} | {failed:>6} | {errors:>6} | {skipped:>5} |"

    output = [top]
    output.append(line.format(suite="Test Suite", passed="Passed", failed="Failed", errors="Errors", skipped="Skip"))
    output.append(mid)
    for suite_name, stats in rows:
        output.append(
            line.format(
                suite=suite_name,
                passed=stats["passed"],
                failed=stats["failed"],
                errors=stats["errors"],
                skipped=stats["skipped"],
            )
        )
    output.append(mid)
    output.append(
        line.format(
            suite="TOTAL",
            passed=totals["passed"],
            failed=totals["failed"],
            errors=totals["errors"],
            skipped=totals["skipped"],
        )
    )
    output.append(bottom)
    return output


def print_final_summary(stream, style: Style, unit: DetailedResult, integration: DetailedResult, total_elapsed: float) -> int:
    unit_failed = unit.layer_stats["failed"] + unit.layer_stats["errors"]
    integration_failed = integration.layer_stats["failed"] + integration.layer_stats["errors"]
    total_failed = unit.layer_stats["failed"] + integration.layer_stats["failed"]
    total_errors = unit.layer_stats["errors"] + integration.layer_stats["errors"]

    stream.write("\n")
    write_title_box(stream, style, "FINAL SUMMARY")
    for row in final_summary_table(style, unit, integration):
        stream.write(style.bold(row) + "\n")

    if total_failed or total_errors:
        status = f"{style.symbols['failed']} TEST SUITE FAILED"
        stream.write("\n" + style.bright_red(style.bold(status)) + "\n")
        stream.write(style.bright_red(f"Failures: {total_failed}  Errors: {total_errors}") + "\n")
    else:
        status = f"{style.symbols['passed']} ALL TESTS PASSED"
        stream.write("\n" + style.green(style.bold(status)) + "\n")

    stream.write(f"\nTotal execution time: {total_elapsed:.2f}s\n")
    return 0 if unit_failed == 0 and integration_failed == 0 else 1


def main() -> int:
    sys.path.insert(0, str(TESTS))
    stream = sys.stdout
    style = Style(stream)
    start = time.perf_counter()

    write_title_box(stream, style, "STOCK TRACKER TEST SUITE")
    aggregate = Stats()
    unit = run_layer("unit", "unit", aggregate, style)
    integration = run_layer("integration", "integration", aggregate, style)

    print_detailed_results(stream, style, [unit, integration], aggregate)

    total_elapsed = time.perf_counter() - start
    return print_final_summary(stream, style, unit, integration, total_elapsed)


if __name__ == "__main__":
    raise SystemExit(main())

