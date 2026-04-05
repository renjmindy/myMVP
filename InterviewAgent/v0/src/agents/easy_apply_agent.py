"""
LinkedIn Easy Apply automation using Playwright.
Reuses the authenticated session created by `uvx linkedin-scraper-mcp --login`
so no separate login is required.

Two-phase flow:
  1. check_batch()  — dry-run: inspect forms, return readiness without submitting
  2. apply_batch()  — submit applications for jobs confirmed ready by the user
"""
import asyncio
import os
from typing import Optional

from src.database import supabase_client

# Session created by `uvx linkedin-scraper-mcp --login` on Windows
_LINKEDIN_PROFILE = "/mnt/c/linkedin-mcp/profile"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_EASY_APPLY_BTN = (
    "button.jobs-apply-button, "
    "button[aria-label*='Easy Apply'], "
    ".jobs-s-apply button"
)
_NEXT_BTN = "button[aria-label='Continue to next step'], button[aria-label='Review your application']"
_SUBMIT_BTN = "button[aria-label='Submit application']"
_DISMISS_BTN = "button[aria-label='Dismiss']"
_DISCARD_BTN = "button[data-control-name='discard_application_confirm_btn']"
_MAX_STEPS = 6


class EasyApplyAgent:
    def __init__(self, candidate_info: dict = None):
        self.candidate_info = candidate_info or {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fill_text_field(self, page, selector: str, value: str):
        try:
            el = await page.query_selector(selector)
            if el and value:
                await el.triple_click()
                await el.fill(value)
        except Exception:
            pass

    async def _try_fill_known_fields(self, page):
        """Fill all fields we know from candidate_info."""
        info = self.candidate_info
        if info.get("phone"):
            await self._fill_text_field(
                page,
                "input[name='phoneNumber'], input[id*='phone'], input[aria-label*='Phone']",
                info["phone"],
            )
        if info.get("email"):
            await self._fill_text_field(
                page,
                "input[name='email'], input[id*='email'], input[aria-label*='Email']",
                info["email"],
            )
        if info.get("years_of_experience"):
            await self._fill_text_field(
                page,
                "input[aria-label*='experience'], input[aria-label*='Experience'], "
                "input[id*='experience'], input[name*='experience']",
                info["years_of_experience"],
            )
        if info.get("work_authorization"):
            try:
                selects = await page.query_selector_all(
                    "select[aria-label*='authorization'], select[aria-label*='Authorization'], "
                    "select[id*='authorization'], select[name*='authorization']"
                )
                for sel in selects:
                    await sel.select_option(label=info["work_authorization"])
            except Exception:
                pass
            await self._fill_text_field(
                page,
                "input[aria-label*='authorization'], input[aria-label*='Authorization'], "
                "input[id*='authorization']",
                info["work_authorization"],
            )

    async def _get_missing_required_fields(self, page) -> list[str]:
        """Return labels of required fields that are still empty after filling."""
        missing = []
        try:
            inputs = await page.query_selector_all(
                ".jobs-easy-apply-form-section__grouping input[required], "
                ".fb-dash-form-element input[required]"
            )
            for inp in inputs:
                val = (await inp.input_value()).strip()
                if not val:
                    label = (
                        await inp.get_attribute("aria-label")
                        or await inp.get_attribute("placeholder")
                        or "Unknown field"
                    )
                    missing.append(label.strip())

            selects = await page.query_selector_all(
                ".jobs-easy-apply-form-section__grouping select[required], "
                ".fb-dash-form-element select[required]"
            )
            for sel in selects:
                val = await sel.evaluate("el => el.value")
                if not val:
                    label = (
                        await sel.get_attribute("aria-label")
                        or "Unknown dropdown"
                    )
                    missing.append(label.strip())
        except Exception:
            pass
        return missing

    async def _dismiss_modal(self, page):
        try:
            dismiss = await page.query_selector(_DISMISS_BTN)
            if dismiss:
                await dismiss.click()
                await page.wait_for_timeout(500)
                discard = await page.query_selector(_DISCARD_BTN)
                if discard:
                    await discard.click()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Phase 1: Dry-run check (no submission)
    # ------------------------------------------------------------------

    async def _check_single(self, page, job: dict) -> dict:
        """Inspect the Easy Apply form without submitting. Returns readiness."""
        job_url = job.get("url", "")
        all_missing = []

        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2500)
        except Exception as e:
            return {"status": "error", "reason": f"Navigation failed: {e}"}

        try:
            btn = await page.wait_for_selector(_EASY_APPLY_BTN, timeout=8000)
            await btn.click()
            await page.wait_for_timeout(1500)
        except Exception:
            return {"status": "skipped", "reason": "No Easy Apply button found"}

        step = 0
        while step < _MAX_STEPS:
            step += 1
            await page.wait_for_timeout(1000)

            submit_btn = await page.query_selector(_SUBMIT_BTN)
            if submit_btn:
                await self._dismiss_modal(page)
                return {"status": "ready", "steps": step, "missing_fields": []}

            await self._try_fill_known_fields(page)
            missing = await self._get_missing_required_fields(page)
            if missing:
                all_missing.extend(missing)
                await self._dismiss_modal(page)
                return {
                    "status": "needs_manual",
                    "reason": "Form requires additional information",
                    "missing_fields": list(dict.fromkeys(all_missing)),
                }

            next_btn = await page.query_selector(_NEXT_BTN)
            if next_btn:
                await next_btn.click()
            else:
                await self._dismiss_modal(page)
                return {"status": "error", "reason": "Could not find Next or Submit button"}

        await self._dismiss_modal(page)
        return {"status": "error", "reason": f"Exceeded max steps ({_MAX_STEPS})"}

    async def _run_check_async(self, jobs: list[dict]) -> list[dict]:
        from playwright.async_api import async_playwright  # type: ignore
        results = []
        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                _LINKEDIN_PROFILE,
                headless=True,
                user_agent=USER_AGENT,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else await context.new_page()
            for job in jobs:
                result = await self._check_single(page, job)
                result.update({
                    "job_id": job.get("id", ""),
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "url": job.get("url", ""),
                    "fit_score": job.get("fit_score"),
                })
                results.append(result)
                await asyncio.sleep(1)
            await context.close()
        return results

    def check_batch(self, jobs: list[dict]) -> list[dict]:
        """Dry-run: inspect forms and return readiness for each job."""
        if not jobs:
            return []
        return asyncio.run(self._run_check_async(jobs))

    # ------------------------------------------------------------------
    # Phase 2: Actual submission
    # ------------------------------------------------------------------

    async def _apply_single(self, page, job: dict) -> dict:
        job_url = job.get("url", "")
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2500)
        except Exception as e:
            return {"success": False, "status": "error", "reason": f"Navigation failed: {e}"}

        try:
            btn = await page.wait_for_selector(_EASY_APPLY_BTN, timeout=8000)
            await btn.click()
            await page.wait_for_timeout(1500)
        except Exception:
            return {"success": False, "status": "skipped", "reason": "No Easy Apply button"}

        step = 0
        while step < _MAX_STEPS:
            step += 1
            await page.wait_for_timeout(1000)

            submit_btn = await page.query_selector(_SUBMIT_BTN)
            if submit_btn:
                await self._try_fill_known_fields(page)
                await submit_btn.click()
                await page.wait_for_timeout(2000)
                try:
                    dismiss = await page.query_selector(_DISMISS_BTN)
                    if dismiss:
                        await dismiss.click()
                except Exception:
                    pass
                return {"success": True, "status": "applied", "steps": step}

            await self._try_fill_known_fields(page)
            missing = await self._get_missing_required_fields(page)
            if missing:
                await self._dismiss_modal(page)
                return {
                    "success": False,
                    "status": "manual_review",
                    "reason": f"Unexpected required fields: {', '.join(missing)}",
                    "steps": step,
                }

            next_btn = await page.query_selector(_NEXT_BTN)
            if next_btn:
                await next_btn.click()
            else:
                return {
                    "success": False,
                    "status": "error",
                    "reason": "Could not find Next or Submit button",
                    "steps": step,
                }

        return {
            "success": False,
            "status": "error",
            "reason": f"Exceeded max steps ({_MAX_STEPS})",
            "steps": step,
        }

    async def _run_async(self, jobs: list[dict]) -> list[dict]:
        from playwright.async_api import async_playwright  # type: ignore
        results = []
        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                _LINKEDIN_PROFILE,
                headless=True,
                user_agent=USER_AGENT,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else await context.new_page()
            for job in jobs:
                result = await self._apply_single(page, job)
                result["job_id"] = job.get("id", "")
                result["title"] = job.get("title", "")
                result["company"] = job.get("company", "")
                result["url"] = job.get("url", "")
                results.append(result)
                if job.get("id"):
                    if result["status"] == "applied":
                        supabase_client.update_job_status(job["id"], "applied")
                    elif result["status"] == "manual_review":
                        supabase_client.update_job_status(job["id"], "saved")
                await asyncio.sleep(2)
            await context.close()
        return results

    def apply_batch(self, jobs: list[dict]) -> list[dict]:
        """Submit applications for the given jobs."""
        if not jobs:
            return []
        return asyncio.run(self._run_async(jobs))

    def apply_single(self, job: dict) -> dict:
        return self.apply_batch([job])[0] if job else {}
