import asyncio
import json
import logging
import re
import random
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from src.database import supabase_client

log = logging.getLogger(__name__)


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_MAX_JOB_AGE_DAYS = 7   # skip jobs posted more than this many days ago
_MAX_APPLICANTS = 200   # skip jobs with more than this many applicants
UVX_PATH = "/home/cjen/anaconda3/bin/uvx"
_LINKEDIN_PROFILE = "/mnt/c/linkedin-mcp/profile"
_WINDOWS_HOST = "172.27.160.1"   # WSL gateway = Windows host
_MCP_PORT = 8765


async def _random_delay(min_s: float = 0.4, max_s: float = 1.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


def _relevance_score(job: dict, keywords: list[str]) -> int:
    """Score by keyword matches across title, location, work mode, and description."""
    title = (job.get("title") or "").lower()
    location = (job.get("location") or "").lower()
    desc = (job.get("description") or "").lower()
    work_mode = (job.get("work_mode") or "").lower()

    combined = location + " " + desc
    if not work_mode:
        for mode in ("remote", "hybrid", "onsite", "on-site", "on site"):
            if mode in combined:
                work_mode = mode
                break

    score = 0
    for kw in keywords:
        kw = kw.lower()
        if kw in title:
            score += 3
        if kw in location:
            score += 2
        if kw in desc:
            score += 3
        if kw in work_mode:
            score += 2
    return score


# ---------------------------------------------------------------------------
# LinkedIn MCP helpers
# ---------------------------------------------------------------------------

def _extract_job_ids(result: dict) -> list[str]:
    """Pull job IDs out of a linkedin-scraper-mcp search_jobs response."""
    if not result:
        return []
    ids = result.get("job_ids", [])
    if ids:
        return [str(j) for j in ids]
    # Fallback: parse /jobs/view/<id> URLs from text sections
    text = ""
    sections = result.get("sections", {})
    if isinstance(sections, dict):
        text = " ".join(str(v) for v in sections.values())
    elif isinstance(sections, str):
        text = sections
    found = re.findall(r"/jobs/view/(\d{7,13})", text)
    return list(dict.fromkeys(found))


def _parse_linkedin_job_text(raw_text: str, job_id: str, actual_url: str) -> dict | None:
    """
    Parse the raw posting text returned by linkedin-scraper-mcp get_job_details.
    Typical format:
      Line 0: Company name
      Line 1: Job title
      Line 2+: Location · type · applicants  (metadata, skip)
      Rest:   Description
    """
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    if len(lines) < 2:
        return None

    company = lines[0]
    title = lines[1]

    # Locate where actual description begins (skip metadata lines)
    desc_start = 2
    for i, line in enumerate(lines[2:], start=2):
        if any(
            sep in line
            for sep in ["·", " ago", "applicants", "people clicked",
                        "Full-time", "Part-time", "Contract", "Internship"]
        ):
            desc_start = i + 1
        else:
            break

    description = (
        "\n".join(lines[desc_start:]) if desc_start < len(lines) else "\n".join(lines[2:])
    )

    return {
        "title": title,
        "company": company,
        "location": "",        # not always available in raw text
        "url": actual_url.split("?")[0],
        "source": "linkedin",
        "posted_date": "",
        "description": description,
    }


def _parse_age_days(raw_text: str) -> int | None:
    """
    Extract posting age in days from LinkedIn job text.
    Handles: '2 days ago', '1 week ago', '3 weeks ago', 'Reposted 1 week ago', etc.
    Returns None if no age info found.
    """
    lower = raw_text.lower()
    # Hours / just now → treat as 0 days
    if re.search(r'\d+\s*hours?\s*ago|just now|today', lower):
        return 0
    m = re.search(r'(\d+)\s+(day|week|month)s?\s+ago', lower)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit == "day":   return n
        if unit == "week":  return n * 7
        if unit == "month": return n * 30
    return None


def _linkedin_job_should_skip(raw_text: str) -> bool:
    """Return True if the job should be filtered out."""
    lower = raw_text.lower()

    # Filter reposted jobs
    if "repost" in lower:
        return True

    # Filter by age — skip if older than _MAX_JOB_AGE_DAYS
    age = _parse_age_days(raw_text)
    if age is not None and age > _MAX_JOB_AGE_DAYS:
        return True

    # Filter by applicant count — catch "Over 100 applicants/people clicked apply" and explicit numbers
    if re.search(r"over\s+\d+\s+(?:applicants?|people\s+clicked)", lower):
        return True
    m = re.search(r"(\d+)\s*(?:applicants?|people\s+clicked)", lower)
    if m and int(m.group(1)) > _MAX_APPLICANTS:
        return True

    return False


# ---------------------------------------------------------------------------
# Indeed BeautifulSoup helpers
# ---------------------------------------------------------------------------

_INDEED_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
    "Accept-Encoding": "gzip, deflate, br",
}


def _parse_indeed_cards(soup: BeautifulSoup) -> list[dict]:
    jobs: list[dict] = []
    cards = soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c)
    if not cards:
        cards = soup.find_all("div", attrs={"data-jk": True})

    for card in cards:
        try:
            title_el = card.find("h2", class_=lambda c: c and "jobTitle" in (c or ""))
            company_el = card.find("span", attrs={"data-testid": "company-name"}) or \
                         card.find(class_=lambda c: c and "companyName" in (c or ""))
            location_el = card.find(attrs={"data-testid": "text-location"}) or \
                          card.find(class_=lambda c: c and "companyLocation" in (c or ""))
            link_el = card.find("a", attrs={"data-jk": True}) or card.find("a", href=True)
            jk = card.get("data-jk") or (link_el.get("data-jk") if link_el else None)
            date_el = card.find(attrs={"data-testid": "myJobsStateDate"}) or \
                      card.find(class_=lambda c: c and "date" in (c or ""))
            desc_el = card.find("div", class_=lambda c: c and "job-snippet" in (c or ""))

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc = location_el.get_text(strip=True) if location_el else ""
            href = f"https://www.indeed.com/viewjob?jk={jk}" if jk else ""
            posted_date = date_el.get_text(strip=True) if date_el else ""
            description = desc_el.get_text(" ", strip=True) if desc_el else ""

            if not title or not href:
                continue

            jobs.append({
                "title": title,
                "company": company,
                "location": loc,
                "url": href,
                "source": "indeed",
                "posted_date": posted_date,
                "description": description,
            })
        except Exception:
            continue
    return jobs


# ---------------------------------------------------------------------------
# JobScraper
# ---------------------------------------------------------------------------

class JobScraper:

    # ------------------------------------------------------------------
    # LinkedIn — MCP-based (no DOM parsing)
    # ------------------------------------------------------------------
    async def scrape_linkedin(
        self, keywords: list[str], location: str, top_n: int = 10
    ) -> list[dict]:
        from mcp import ClientSession  # type: ignore
        from mcp.client.streamable_http import streamable_http_client  # type: ignore

        query = " ".join(keywords)
        # MCP server runs on Windows host; WSL reaches it via the gateway IP
        mcp_url = f"http://{_WINDOWS_HOST}:{_MCP_PORT}/mcp"

        jobs: list[dict] = []

        try:
            import httpx  # type: ignore
            # Disable read timeout — LinkedIn page scrolling can take unpredictable time
            http_client = httpx.AsyncClient(timeout=httpx.Timeout(None))
            async with streamable_http_client(mcp_url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # --- search ---
                    # --- search: collect as many unique IDs as the server returns ---
                    # linkedin-scraper-mcp doesn't support offset pagination, so one
                    # call with max_pages=40 gives us the broadest result set possible.
                    # max_pages is capped at 10 by the server; collect IDs from
                    # multiple keyword variants to broaden coverage.
                    all_job_ids: list[str] = []
                    seen_ids: set[str] = set()

                    # Single search using all keywords joined — avoids duplicate searches
                    try:
                        search_result = await session.call_tool("search_jobs", {
                            "keywords": query,
                            "location": location,
                            "date_posted": "past_week",
                            "max_pages": 5,
                        })
                        raw_search = None
                        for content in (search_result.content or []):
                            if hasattr(content, "text"):
                                try:
                                    raw_search = json.loads(content.text)
                                except Exception:
                                    pass
                                break
                        for jid in _extract_job_ids(raw_search or {}):
                            if jid not in seen_ids:
                                seen_ids.add(jid)
                                all_job_ids.append(jid)
                    except Exception as search_err:
                        log.error(f"[scraper] search_jobs failed: {search_err}", exc_info=True)

                    job_ids = all_job_ids
                    log.info(f"[scraper] search returned {len(job_ids)} job ID(s)")
                    print(f"[scraper] search returned {len(job_ids)} job ID(s)", flush=True)

                    # --- fetch details for up to 100 jobs ---
                    now = datetime.now(timezone.utc)
                    for job_id in job_ids[:100]:
                        try:
                            detail_result = await session.call_tool(
                                "get_job_details", {"job_id": job_id}
                            )
                        except Exception:
                            await _random_delay(1.0, 2.0)
                            continue

                        detail = None
                        for content in (detail_result.content or []):
                            if hasattr(content, "text"):
                                try:
                                    detail = json.loads(content.text)
                                except Exception:
                                    detail = {"raw": content.text}
                                break

                        if not detail:
                            continue

                        sections = detail.get("sections", {})
                        actual_url = detail.get(
                            "url", f"https://www.linkedin.com/jobs/view/{job_id}"
                        )
                        posted_date_str = detail.get("posted_date", "")

                        if isinstance(sections, dict):
                            raw_text = sections.get("job_posting", "") or \
                                       "\n".join(str(v) for v in sections.values())
                        else:
                            raw_text = str(sections)

                        if not raw_text.strip():
                            continue

                        # Filter reposted / over-applied
                        if _linkedin_job_should_skip(raw_text):
                            log.info(f"[scraper] job {job_id} skipped (reposted/over-applied/too-old)")
                            continue

                        # Age filter: skip jobs older than _MAX_JOB_AGE_DAYS
                        if posted_date_str:
                            try:
                                dt = datetime.fromisoformat(
                                    posted_date_str.replace("Z", "+00:00")
                                )
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                if (now - dt).days > _MAX_JOB_AGE_DAYS:
                                    continue
                            except Exception:
                                pass

                        job = _parse_linkedin_job_text(raw_text, job_id, actual_url)
                        if not job:
                            continue
                        if posted_date_str:
                            job["posted_date"] = posted_date_str

                        jobs.append(job)
                        await _random_delay(1.0, 2.0)

        except Exception as e:
            log.error(f"[scraper] LinkedIn scrape failed: {e}", exc_info=True)
            return []

        jobs.sort(key=lambda j: _relevance_score(j, keywords), reverse=True)
        return jobs[:top_n]

    # ------------------------------------------------------------------
    # Indeed — requests + BeautifulSoup (no Playwright)
    # ------------------------------------------------------------------
    async def scrape_indeed(
        self, keywords: list[str], location: str, top_n: int = 5
    ) -> list[dict]:
        query = " ".join(keywords)
        all_jobs: list[dict] = []

        session = requests.Session()
        session.headers.update(_INDEED_HEADERS)

        for page in range(2):
            start = page * 10
            params = urlencode({
                "q": query,
                "l": location,
                "sort": "date",
                "fromage": str(_MAX_JOB_AGE_DAYS),
                "start": start,
            })
            url = f"https://www.indeed.com/jobs?{params}"

            try:
                resp = session.get(url, timeout=15)
                if resp.status_code == 403:
                    break   # Indeed bot-blocked; stop gracefully
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                all_jobs.extend(_parse_indeed_cards(soup))
            except Exception:
                break

            await _random_delay(2.0, 4.0)

        all_jobs.sort(key=lambda j: _relevance_score(j, keywords), reverse=True)
        return all_jobs[:top_n]

    # ------------------------------------------------------------------
    # Combined runner
    # ------------------------------------------------------------------
    async def _run_scrape_async(
        self, keywords: list[str], location: str, sources: list[str], top_n: int
    ) -> list[dict]:
        tasks = []
        if "linkedin" in sources:
            tasks.append(self.scrape_linkedin(keywords, location, top_n))
        if "indeed" in sources:
            tasks.append(self.scrape_indeed(keywords, location, top_n))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        combined: list[dict] = []
        seen_urls: set[str] = set()
        for result in results:
            if isinstance(result, Exception):
                continue
            for job in result:  # type: ignore
                url = job.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    combined.append(job)

        combined.sort(key=lambda j: _relevance_score(j, keywords), reverse=True)
        return combined

    def run_scrape(
        self,
        keywords: list[str],
        location: str,
        sources: list[str] = None,  # type: ignore
        top_n: int = 10,
        excluded_companies: list[str] = None,  # type: ignore
        target_companies: list[str] = None,  # type: ignore
    ) -> list[dict]:
        if sources is None:
            sources = ["linkedin"]

        jobs = asyncio.run(self._run_scrape_async(keywords, location, sources, top_n))

        if target_companies:
            target_lower = [c.lower() for c in target_companies]
            jobs = [
                j for j in jobs
                if any(t in (j.get("company") or "").lower() for t in target_lower)
            ]
        elif excluded_companies:
            excluded_lower = [c.lower() for c in excluded_companies]
            jobs = [
                j for j in jobs
                if not any(ex in (j.get("company") or "").lower() for ex in excluded_lower)
            ]

        saved: list[dict] = []
        for job in jobs:
            persisted = supabase_client.upsert_job(job)
            saved.append(persisted if persisted else job)

        return saved
