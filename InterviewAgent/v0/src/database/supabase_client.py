import os
from typing import Optional
from datetime import datetime, timezone

# jobs table schema:
# id (uuid, primary key), title (text), company (text), location (text),
# url (text, unique), description (text), source (text), posted_date (text),
# scraped_at (timestamptz), status (text: new/saved/applied/rejected),
# fit_score (int), analysis (jsonb), notes (text), interview_date (date)

# settings table schema:
# id (int, primary key, default 1), keywords (text[]), location (text),
# resume_text (text), email (text), notify_threshold (int 0-100),
# notify_frequency (text: daily/instant)

_client = None
_mock_mode = False


def get_client():
    global _client, _mock_mode
    if _client is not None:
        return _client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        _mock_mode = True
        return None
    try:
        from supabase import create_client  # type: ignore
        _client = create_client(url, key)
        _mock_mode = False
    except Exception:
        _mock_mode = True
        return None
    return _client


def is_mock_mode() -> bool:
    get_client()
    return _mock_mode


def upsert_job(job_dict: dict) -> Optional[dict]:
    client = get_client()
    if not client:
        # in mock mode just return the job as-is
        return job_dict
    try:
        job_dict.setdefault("scraped_at", datetime.now(timezone.utc).isoformat())
        job_dict.setdefault("status", "new")
        result = (
            client.table("jobs")
            .upsert(job_dict, on_conflict="url")
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_jobs(filters: Optional[dict] = None) -> list[dict]:
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_JOBS
        jobs = list(MOCK_JOBS)
        if filters:
            if "status" in filters and filters["status"]:
                statuses = filters["status"]
                if isinstance(statuses, list):
                    jobs = [j for j in jobs if j.get("status") in statuses]
                else:
                    jobs = [j for j in jobs if j.get("status") == statuses]
            if "min_fit_score" in filters and filters["min_fit_score"] is not None:
                jobs = [j for j in jobs if (j.get("fit_score") or 0) >= filters["min_fit_score"]]
            if "source" in filters and filters["source"]:
                sources = filters["source"]
                if isinstance(sources, list):
                    jobs = [j for j in jobs if j.get("source") in sources]
                else:
                    jobs = [j for j in jobs if j.get("source") == sources]
            if "keyword" in filters and filters["keyword"]:
                kw = filters["keyword"].lower()
                jobs = [
                    j for j in jobs
                    if kw in (j.get("title") or "").lower()
                    or kw in (j.get("company") or "").lower()
                    or kw in (j.get("description") or "").lower()
                ]
        return jobs
    try:
        query = client.table("jobs").select("*")
        if filters:
            if "status" in filters and filters["status"]:
                statuses = filters["status"]
                if isinstance(statuses, list):
                    query = query.in_("status", statuses)
                else:
                    query = query.eq("status", statuses)
            if "min_fit_score" in filters and filters["min_fit_score"] is not None:
                query = query.gte("fit_score", filters["min_fit_score"])
            if "source" in filters and filters["source"]:
                sources = filters["source"]
                if isinstance(sources, list):
                    query = query.in_("source", sources)
                else:
                    query = query.eq("source", sources)
            if "keyword" in filters and filters["keyword"]:
                kw = filters["keyword"]
                query = query.or_(
                    f"title.ilike.%{kw}%,company.ilike.%{kw}%,description.ilike.%{kw}%"
                )
        result = query.order("scraped_at", desc=True).execute()
        return result.data if result.data else []
    except Exception:
        return []


def update_job_status(job_id: str, status: str) -> bool:
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_JOBS
        for job in MOCK_JOBS:
            if job["id"] == job_id:
                job["status"] = status
                return True
        return False
    try:
        client.table("jobs").update({"status": status}).eq("id", job_id).execute()
        return True
    except Exception:
        return False


def save_analysis(job_id: str, analysis_dict: dict) -> bool:
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_JOBS
        for job in MOCK_JOBS:
            if job["id"] == job_id:
                job["analysis"] = analysis_dict
                job["fit_score"] = analysis_dict.get("fit_score")
                return True
        return False
    try:
        payload = {
            "analysis": analysis_dict,
            "fit_score": analysis_dict.get("fit_score"),
        }
        client.table("jobs").update(payload).eq("id", job_id).execute()
        return True
    except Exception:
        return False


def save_job_notes(job_id: str, notes: str) -> bool:
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_JOBS
        for job in MOCK_JOBS:
            if job["id"] == job_id:
                job["notes"] = notes
                return True
        return False
    try:
        client.table("jobs").update({"notes": notes}).eq("id", job_id).execute()
        return True
    except Exception:
        return False


def save_interview_date(job_id: str, interview_date: Optional[str]) -> bool:
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_JOBS
        for job in MOCK_JOBS:
            if job["id"] == job_id:
                job["interview_date"] = interview_date
                return True
        return False
    try:
        client.table("jobs").update({"interview_date": interview_date}).eq("id", job_id).execute()
        return True
    except Exception:
        return False


def get_user_settings() -> dict:
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_SETTINGS
        return dict(MOCK_SETTINGS)
    try:
        result = client.table("settings").select("*").eq("id", 1).execute()
        if result.data:
            return result.data[0]
        return {}
    except Exception:
        return {}


def save_user_settings(settings_dict: dict) -> bool:
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_SETTINGS
        MOCK_SETTINGS.update(settings_dict)
        return True
    try:
        settings_dict["id"] = 1
        client.table("settings").upsert(settings_dict, on_conflict="id").execute()
        return True
    except Exception:
        return False


def delete_job_with_files(job_id: str, title: str, company: str) -> bool:
    """Delete a single job and all its associated cover letters, resumes, and network contacts."""
    client = get_client()
    if not client:
        return False
    try:
        # Delete cover letters and resumes for this job
        for table, col in [("cover_letters", "company_name"), ("optimized_resumes", "company_name")]:
            rows = (
                client.table(table)
                .select("id")
                .eq("job_title", title)
                .eq(col, company)
                .execute()
            )
            for row in (rows.data or []):
                client.table(table).delete().eq("id", row["id"]).execute()

        # Delete network contacts only if no other jobs remain for this company
        remaining = (
            client.table("jobs")
            .select("id")
            .eq("company", company)
            .neq("id", job_id)
            .execute()
        )
        if not (remaining.data or []):
            client.table("network_contacts").delete().ilike("company", company).execute()

        # Delete the job itself
        client.table("jobs").delete().eq("id", job_id).execute()
        return True
    except Exception:
        return False


def clear_all_jobs() -> bool:
    """Delete all jobs except those with status 'applied', and remove network contacts for deleted companies."""
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_JOBS, MOCK_NETWORK_CONTACTS
        kept_companies = {j.get("company") for j in MOCK_JOBS if j.get("status") == "applied"}
        MOCK_JOBS[:] = [j for j in MOCK_JOBS if j.get("status") == "applied"]
        for company in list(MOCK_NETWORK_CONTACTS.keys()):
            if company not in kept_companies:
                del MOCK_NETWORK_CONTACTS[company]
        return True
    try:
        # Identify companies that will survive (applied jobs)
        applied = client.table("jobs").select("company").eq("status", "applied").execute()
        kept_companies = {r["company"] for r in (applied.data or []) if r.get("company")}

        # Delete non-applied jobs
        client.table("jobs").delete().neq("status", "applied").execute()

        # Delete network contacts for companies no longer in any job
        all_remaining = client.table("jobs").select("company").execute()
        remaining_companies = {r["company"] for r in (all_remaining.data or []) if r.get("company")}
        contacts = client.table("network_contacts").select("id, company").execute()
        for row in (contacts.data or []):
            if row.get("company") not in remaining_companies:
                client.table("network_contacts").delete().eq("id", row["id"]).execute()

        return True
    except Exception:
        return False


def log_agent_result(
    agent_type: str,
    task_type: str,
    input_data: dict,
    output_data: dict,
    success: bool,
    error: str = None,
) -> Optional[str]:
    client = get_client()
    if not client:
        return None
    try:
        payload = {
            "agent_type": agent_type,
            "task_type": task_type,
            "input_data": input_data,
            "output_data": output_data,
            "success": success,
            "error_message": error,
        }
        result = client.table("agent_results").insert(payload).execute()
        return result.data[0]["id"] if result.data else None
    except Exception:
        return None


def save_cover_letter(cover_letter_dict: dict) -> Optional[dict]:
    client = get_client()
    if not client:
        return None
    try:
        result = client.table("cover_letters").insert(cover_letter_dict).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_cover_letters(filters: Optional[dict] = None) -> list[dict]:
    client = get_client()
    if not client:
        return []
    try:
        query = client.table("cover_letters").select("*")
        if filters and filters.get("keyword"):
            kw = filters["keyword"]
            query = query.or_(f"job_title.ilike.%{kw}%,company_name.ilike.%{kw}%")
        result = query.order("created_at", desc=True).execute()
        return result.data if result.data else []
    except Exception:
        return []


def delete_cover_letter(letter_id: str) -> bool:
    client = get_client()
    if not client:
        return False
    try:
        client.table("cover_letters").delete().eq("id", letter_id).execute()
        return True
    except Exception:
        return False


def delete_optimized_resume(resume_id: str) -> bool:
    client = get_client()
    if not client:
        return False
    try:
        client.table("optimized_resumes").delete().eq("id", resume_id).execute()
        return True
    except Exception:
        return False


def save_optimized_resume(opt_dict: dict) -> Optional[dict]:
    client = get_client()
    if not client:
        return None
    try:
        result = client.table("optimized_resumes").insert(opt_dict).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_optimized_resumes() -> list[dict]:
    client = get_client()
    if not client:
        return []
    try:
        result = (
            client.table("optimized_resumes")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data if result.data else []
    except Exception:
        return []


def get_company_research(company_name: str) -> Optional[dict]:
    client = get_client()
    if not client:
        return None
    try:
        result = (
            client.table("company_research")
            .select("*")
            .ilike("company_name", company_name)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def save_company_research(company_name: str, research_data: dict) -> bool:
    client = get_client()
    if not client:
        return False
    try:
        payload = {"company_name": company_name, "research_data": research_data}
        client.table("company_research").upsert(
            payload, on_conflict="company_name"
        ).execute()
        return True
    except Exception:
        return False


def save_job_search(
    keywords: list, location: str, sources: list, results_count: int
) -> bool:
    client = get_client()
    if not client:
        return False
    try:
        payload = {
            "keywords": keywords,
            "location": location,
            "sources": sources,
            "results_count": results_count,
        }
        client.table("job_searches").insert(payload).execute()
        return True
    except Exception:
        return False


def save_market_insight(keywords: list, location: str, insight_data: dict) -> bool:
    client = get_client()
    if not client:
        return False
    try:
        payload = {
            "keywords": keywords,
            "location": location,
            "insight_data": insight_data,
        }
        client.table("market_insights").insert(payload).execute()
        return True
    except Exception:
        return False


def save_network_contacts(company: str, contacts: list[dict]) -> bool:
    """Replace contacts for a company: delete existing rows then insert new ones."""
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_NETWORK_CONTACTS
        MOCK_NETWORK_CONTACTS[company] = contacts[:3]
        return True
    try:
        # Delete existing contacts for this company first
        client.table("network_contacts").delete().ilike("company", company).execute()
        # Insert new contacts
        rows = [
            {
                "company": company,
                "name": c.get("name", ""),
                "title": c.get("title", ""),
                "degree": c.get("degree", "3rd"),
                "mutual": c.get("mutual"),
                "linkedin_url": c.get("linkedin_url"),
            }
            for c in contacts
            if c.get("name")
        ]
        if rows:
            client.table("network_contacts").insert(rows).execute()
        return True
    except Exception as e:
        return False


def get_network_contacts(company_name: str) -> list[dict]:
    """Return up to 3 network contacts for a given company."""
    client = get_client()
    if not client:
        from src.database.mock_data import MOCK_NETWORK_CONTACTS
        return MOCK_NETWORK_CONTACTS.get(company_name, [])
    try:
        result = (
            client.table("network_contacts")
            .select("*")
            .ilike("company", company_name)
            .limit(3)
            .execute()
        )
        return result.data if result.data else []
    except Exception:
        return []


def delete_market_insight(insight_id: str) -> bool:
    client = get_client()
    if not client:
        return False
    try:
        client.table("market_insights").delete().eq("id", insight_id).execute()
        return True
    except Exception:
        return False


def get_market_insights(keywords: list = None) -> list[dict]:
    client = get_client()
    if not client:
        return []
    try:
        result = (
            client.table("market_insights")
            .select("*")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return result.data if result.data else []
    except Exception:
        return []


def save_interview_prep(prep_dict: dict) -> Optional[dict]:
    client = get_client()
    if not client:
        return None
    try:
        job_id = prep_dict.get("job_id")
        if job_id:
            result = (
                client.table("interview_prep")
                .upsert(prep_dict, on_conflict="job_id")
                .execute()
            )
        else:
            result = client.table("interview_prep").insert(prep_dict).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_interview_prep(job_id: str) -> Optional[dict]:
    client = get_client()
    if not client:
        return None
    try:
        result = (
            client.table("interview_prep")
            .select("*")
            .eq("job_id", job_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def cleanup_applied_job_files() -> dict:
    """Delete cover letters and optimized resumes for all jobs marked 'applied'."""
    client = get_client()
    if not client:
        return {"deleted_cover_letters": 0, "deleted_resumes": 0}

    deleted_cl = 0
    deleted_or = 0
    try:
        applied = client.table("jobs").select("title, company").eq("status", "applied").execute()
        applied_jobs = applied.data or []
        if not applied_jobs:
            return {"deleted_cover_letters": 0, "deleted_resumes": 0}

        for job in applied_jobs:
            title = job.get("title", "")
            company = job.get("company", "")
            if not title or not company:
                continue

            cl = (
                client.table("cover_letters")
                .select("id")
                .eq("job_title", title)
                .eq("company_name", company)
                .execute()
            )
            for row in (cl.data or []):
                client.table("cover_letters").delete().eq("id", row["id"]).execute()
                deleted_cl += 1

            or_ = (
                client.table("optimized_resumes")
                .select("id")
                .eq("job_title", title)
                .eq("company_name", company)
                .execute()
            )
            for row in (or_.data or []):
                client.table("optimized_resumes").delete().eq("id", row["id"]).execute()
                deleted_or += 1

    except Exception:
        pass

    return {"deleted_cover_letters": deleted_cl, "deleted_resumes": deleted_or}


def clear_agent_logs() -> bool:
    """Delete all rows from agent_results."""
    client = get_client()
    if not client:
        return True
    try:
        client.table("agent_results").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        return True
    except Exception:
        return False


def get_storage_usage() -> dict:
    """Return row counts for the main tables as a storage proxy."""
    client = get_client()
    if not client:
        return {}
    tables = [
        "jobs",
        "agent_results",
        "cover_letters",
        "optimized_resumes",
        "company_research",
        "network_contacts",
        "market_insights",
    ]
    counts = {}
    for table in tables:
        try:
            result = client.table(table).select("id", count="exact").limit(1).execute()
            counts[table] = result.count if result.count is not None else 0
        except Exception:
            counts[table] = 0

    # Upwork examples are stored as array columns in settings — count filled entries
    try:
        result = client.table("settings").select(
            "upwork_proposal_examples, upwork_video_examples"
        ).eq("id", 1).execute()
        row = result.data[0] if result.data else {}
        proposal_ex = row.get("upwork_proposal_examples") or []
        video_ex = row.get("upwork_video_examples") or []
        counts["upwork_proposal_examples"] = sum(1 for e in proposal_ex if e and e.strip())
        counts["upwork_video_examples"] = sum(1 for e in video_ex if e and e.strip())
    except Exception:
        counts["upwork_proposal_examples"] = 0
        counts["upwork_video_examples"] = 0

    return counts


def get_agent_stats() -> dict:
    client = get_client()
    if not client:
        return {
            "total_runs": 0,
            "successful_runs": 0,
            "cover_letters_generated": 0,
            "resumes_optimized": 0,
        }
    try:
        runs_result = client.table("agent_results").select("id, success").execute()
        runs = runs_result.data or []
        total_runs = len(runs)
        successful_runs = sum(1 for r in runs if r.get("success"))

        cl_result = client.table("cover_letters").select("id").execute()
        cover_letters_generated = len(cl_result.data) if cl_result.data else 0

        or_result = client.table("optimized_resumes").select("id").execute()
        resumes_optimized = len(or_result.data) if or_result.data else 0

        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "cover_letters_generated": cover_letters_generated,
            "resumes_optimized": resumes_optimized,
        }
    except Exception:
        return {
            "total_runs": 0,
            "successful_runs": 0,
            "cover_letters_generated": 0,
            "resumes_optimized": 0,
        }
