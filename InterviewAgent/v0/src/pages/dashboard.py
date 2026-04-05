import os
import streamlit as st


@st.dialog("Clear All Jobs")
def _confirm_clear_dialog(supabase_client):
    st.warning("This will delete all jobs except those marked **Applied**. This cannot be undone.")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Yes, delete all", type="primary", use_container_width=True):
            supabase_client.clear_all_jobs()
            st.session_state["clear_success"] = True
            st.rerun()
    with col_no:
        if st.button("No, keep data", use_container_width=True):
            st.rerun()


@st.dialog("Clear Agent Logs")
def _confirm_clear_logs_dialog(supabase_client):
    st.warning("This will delete **all agent run logs**. This cannot be undone.")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Yes, clear logs", type="primary", use_container_width=True):
            supabase_client.clear_agent_logs()
            st.session_state["clear_logs_success"] = True
            st.rerun()
    with col_no:
        if st.button("No, keep logs", use_container_width=True):
            st.rerun()


def show_dashboard():
    st.title("Dashboard")

    # ── LinkedIn MCP server health check ──────────────────────────────
    import requests as _requests
    try:
        _requests.get("http://172.27.160.1:8765/mcp", timeout=2)
        st.success("LinkedIn MCP server: connected", icon="🟢")
    except Exception:
        st.warning(
            "LinkedIn MCP server not reachable. "
            "Start it in Windows PowerShell: "
            "`uvx linkedin-scraper-mcp --transport streamable-http --host 0.0.0.0 --port 8765`",
            icon="🔴",
        )

    from src.database import supabase_client
    from src.agents.job_scraper import JobScraper
    from src.agents.ai_agent import JobAnalysisAgent
    from src.utils.email_notifier import EmailNotifier

    jobs = supabase_client.get_jobs()
    settings = supabase_client.get_user_settings()

    # ── Metrics ────────────────────────────────────────────────────────
    total = len(jobs)
    analyzed = [j for j in jobs if j.get("fit_score") is not None]
    avg_score = (
        round(sum(j["fit_score"] for j in analyzed) / len(analyzed), 1)
        if analyzed else None
    )
    applied = [j for j in jobs if j.get("status") == "applied"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Jobs", total)
    col2.metric("Analyzed", len(analyzed))
    col3.metric("Avg Fit Score", avg_score if avg_score is not None else "—")
    col4.metric("Applied", len(applied))

    # ── Status breakdown ───────────────────────────────────────────────
    if jobs:
        st.subheader("Jobs by Status")
        status_counts: dict[str, int] = {}
        for j in jobs:
            s = j.get("status", "new") or "new"
            status_counts[s] = status_counts.get(s, 0) + 1
        try:
            import pandas as pd  # type: ignore
            st.bar_chart(pd.Series(status_counts))
        except ImportError:
            for s, c in status_counts.items():
                st.write(f"**{s}**: {c}")

    # ── Top high-fit jobs ──────────────────────────────────────────────
    top_jobs = sorted(
        [j for j in analyzed if j.get("fit_score", 0) >= 50],
        key=lambda j: j.get("fit_score", 0),
        reverse=True,
    )[:5]

    if top_jobs:
        st.subheader("Top Recent High-Fit Jobs")
        for job in top_jobs:
            score = job.get("fit_score", 0)
            color = "green" if score >= 70 else "orange" if score >= 50 else "red"
            rec = (job.get("analysis") or {}).get("recommendation", "")
            st.markdown(
                f"**[{job.get('title', '')}]({job.get('url', '#')})** — "
                f"{job.get('company', '')} · {job.get('location', '')} · "
                f":{color}[Score: {score}]"
                + (f" · `{rec}`" if rec else "")
            )

    # ── Agent activity ─────────────────────────────────────────────────
    st.divider()
    st.subheader("Agent Activity")
    stats = supabase_client.get_agent_stats()
    proposal_examples = settings.get("upwork_proposal_examples") or []
    saved_proposal_count = sum(1 for e in proposal_examples if e and e.strip())
    video_examples = settings.get("upwork_video_examples") or []
    saved_video_count = sum(1 for e in video_examples if e and e.strip())

    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.metric("Total Agent Runs", stats.get("total_runs", 0))
    s2.metric("Successful Runs", stats.get("successful_runs", 0))
    s3.metric("Cover Letters", stats.get("cover_letters_generated", 0))
    s4.metric("Resumes Optimized", stats.get("resumes_optimized", 0))
    s5.metric("Proposal Examples", saved_proposal_count)
    s6.metric("Video Examples", saved_video_count)

    # ── Storage usage ──────────────────────────────────────────────────
    st.divider()
    with st.expander("Supabase Storage Usage (row counts)", expanded=True):
        storage = supabase_client.get_storage_usage()
        if not storage:
            st.info("Not available in mock mode.")
        else:
            # Rough byte estimates per row for each table
            _row_kb = {
                "jobs": 8,
                "agent_results": 4,
                "cover_letters": 6,
                "optimized_resumes": 6,
                "company_research": 3,
                "network_contacts": 1,
                "market_insights": 3,
                "upwork_proposal_examples": 2,
                "upwork_video_examples": 2,
            }
            FREE_TIER_KB = 50 * 1024  # 50 MB
            total_est_kb = sum(
                storage.get(t, 0) * _row_kb.get(t, 2) for t in storage
            )
            pct = min(total_est_kb / FREE_TIER_KB * 100, 100)

            st.progress(int(pct), text=f"~{total_est_kb / 1024:.1f} MB / 50 MB used (estimated)")

            import pandas as pd  # already imported above in jobs section
            rows_data = {
                "Table": list(storage.keys()),
                "Rows": [storage[t] for t in storage],
                "Est. Size (KB)": [storage[t] * _row_kb.get(t, 2) for t in storage],
            }
            st.dataframe(
                pd.DataFrame(rows_data).set_index("Table"),
                use_container_width=True,
            )
            st.caption(
                "Size estimates are approximate (based on typical row sizes). "
                "To free space, clear agent_results, old cover letters, or old resumes."
            )

    # ── Manual controls ────────────────────────────────────────────────
    st.divider()
    st.subheader("Manual Controls")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("Scrape Jobs", type="primary", use_container_width=True):
            keywords = settings.get("keywords") or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(",") if k.strip()]
            location = settings.get("location", "Remote")
            if not keywords:
                st.warning("No keywords configured. Go to Settings first.")
            else:
                excluded = settings.get("excluded_companies") or []
                target = settings.get("target_companies") or []
                with st.status("Scraping LinkedIn...", expanded=True) as scrape_status:
                    st.write(f"Keywords: **{', '.join(keywords)}** · Location: **{location}**")
                    if target:
                        st.write(f"Targeting: {', '.join(target)}")
                    elif excluded:
                        st.write(f"Excluding: {', '.join(excluded)}")
                    st.write("Connecting to LinkedIn MCP...")
                    scraper = JobScraper()
                    st.write("Fetching job listings — this may take a minute...")
                    raw_jobs = scraper.run_scrape(keywords, location, excluded_companies=excluded, target_companies=target)
                    st.write(f"Filtering & saving to Supabase...")
                    new_jobs = raw_jobs
                    scrape_status.update(
                        label=f"Done — {len(new_jobs)} job(s) saved.",
                        state="complete",
                        expanded=False,
                    )
                st.rerun()

    with c2:
        if st.button("Analyze Jobs (AI)", use_container_width=True):
            resume_text = settings.get("resume_text", "")
            if not resume_text:
                st.warning("No resume found. Go to Settings first.")
            else:
                unanalyzed = [j for j in jobs if j.get("fit_score") is None]
                if not unanalyzed:
                    st.info("All jobs are already analyzed.")
                else:
                    with st.spinner(f"Analyzing {len(unanalyzed)} jobs with GPT-4o-mini..."):
                        agent = JobAnalysisAgent()
                        agent.batch_analyze(unanalyzed, resume_text)
                    st.success(f"Analyzed {len(unanalyzed)} jobs.")
                    st.rerun()

    with c3:
        if st.session_state.pop("clear_success", False):
            st.success("All jobs cleared.")
        if st.button("Clear All Jobs", type="secondary", use_container_width=True):
            _confirm_clear_dialog(supabase_client)

    with c4:
        if st.session_state.pop("clear_logs_success", False):
            st.success("Agent logs cleared.")
        if st.button("Clear Agent Logs", type="secondary", use_container_width=True):
            _confirm_clear_logs_dialog(supabase_client)

    # ── Send Digest Now ────────────────────────────────────────────────
    st.divider()
    st.subheader("Send Digest Now")
    st.caption("Email the current job list to your Gmail without running the full pipeline.")

    digest_threshold = st.slider(
        "Include jobs with fit score ≥",
        min_value=0, max_value=100,
        value=int(settings.get("notify_threshold", 0)),
        step=5,
        key="digest_threshold",
    )

    if st.button("📧 Send Digest Email", use_container_width=True):
        recipient = settings.get("email", "")
        smtp_email = os.getenv("SMTP_EMAIL", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")

        if not recipient:
            st.error("No notification email set. Go to Settings and enter your email.")
        elif not smtp_email or not smtp_password:
            st.error(
                "Gmail credentials not configured. "
                "Add SMTP_EMAIL and SMTP_PASSWORD to your .env file."
            )
        else:
            all_jobs = supabase_client.get_jobs()
            qualifying = [j for j in all_jobs if (j.get("fit_score") or 0) >= digest_threshold]
            if not qualifying:
                st.warning(f"No jobs with fit score ≥ {digest_threshold} to send.")
            else:
                try:
                    from src.utils.email_notifier import EmailNotifier
                    notifier = EmailNotifier(
                        sender_email=smtp_email, sender_password=smtp_password
                    )
                    notifier.send_job_digest(
                        recipient, all_jobs,
                        subject_prefix="Job Digest",
                        threshold=digest_threshold,
                    )
                    st.success(f"Digest sent to {recipient} — {len(qualifying)} job(s) included.")
                except Exception as e:
                    st.error(f"Failed to send digest: {e}")
