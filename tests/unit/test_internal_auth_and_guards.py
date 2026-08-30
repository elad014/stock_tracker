import os
import unittest

from test_support import import_project_module

llm_limiter_module = import_project_module("llm_guard.limiter", "common")
job_guard_module = import_project_module("llm_guard.job_guard", "common")
rate_limit_module = import_project_module("ui_utils.rate_limit", "common", "ui_service/backend")


class InternalAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_internal_services_require_configured_matching_api_key(self) -> None:
        modules = [
            import_project_module("deps", "common", "stock_manager/backend"),
            import_project_module("deps", "common", "news_agent/backend"),
            import_project_module("deps", "common", "chat_agent/backend"),
            import_project_module("deps", "common", "doc_agent/backend"),
        ]
        old = os.environ.get("INTERNAL_API_KEY")
        try:
            os.environ["INTERNAL_API_KEY"] = "secret"
            for module in modules:
                with self.subTest(module=module.__file__):
                    await module.verify_internal_api_key("secret")
                    with self.assertRaises(module.HTTPException) as bad:
                        await module.verify_internal_api_key("wrong")
                    self.assertEqual(bad.exception.status_code, 401)
            os.environ["INTERNAL_API_KEY"] = ""
            with self.assertRaises(modules[0].HTTPException) as missing:
                await modules[0].verify_internal_api_key("secret")
            self.assertEqual(missing.exception.status_code, 500)
        finally:
            if old is None:
                os.environ.pop("INTERNAL_API_KEY", None)
            else:
                os.environ["INTERNAL_API_KEY"] = old


class RateLimiterTests(unittest.TestCase):
    def test_auth_rate_limiter_enforces_sliding_window_and_reset(self) -> None:
        limiter = rate_limit_module.AuthRateLimiter(max_attempts=2, window_seconds=60)
        limiter.record("u")
        limiter.record("u")
        with self.assertRaises(rate_limit_module.HTTPException) as caught:
            limiter.assert_allowed("u")
        self.assertEqual(caught.exception.status_code, 429)
        limiter.reset("u")
        limiter.assert_allowed("u")

    def test_llm_rate_limiter_consume_counts_and_rejects(self) -> None:
        limiter = llm_limiter_module.LlmRateLimiter(max_attempts=1, window_seconds=60, detail="limit")
        limiter.consume("u")
        with self.assertRaises(llm_limiter_module.HTTPException) as caught:
            limiter.consume("u")
        self.assertEqual(caught.exception.status_code, 429)


class JobGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_job_guard_applies_cooldown(self) -> None:
        guard = job_guard_module.JobRunGuard(60, busy_detail="busy", cooldown_detail="cooldown", skip_log="skip")
        ran = []
        async def job():
            ran.append("run")
        await guard.run_from_http(job)
        with self.assertRaises(job_guard_module.HTTPException) as caught:
            await guard.run_from_http(job)
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(ran, ["run"])

    async def test_schedule_job_guard_skips_when_already_running(self) -> None:
        guard = job_guard_module.JobRunGuard(60, busy_detail="busy", cooldown_detail="cooldown", skip_log="skip")
        entered = []
        async def nested_job():
            entered.append("first")
            await guard.run_from_schedule(lambda: self._append_async(entered, "second"))
        await guard.run_from_schedule(nested_job)
        self.assertEqual(entered, ["first"])

    async def _append_async(self, target, value):
        target.append(value)


if __name__ == "__main__":
    unittest.main()
