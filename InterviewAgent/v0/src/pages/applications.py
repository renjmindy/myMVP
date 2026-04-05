from datetime import date
import streamlit as st

_PIPELINE_STAGES = ["applied", "interview", "offer", "rejected"]

_STAGE_COLORS = {
    "applied": "#1f77b4",
    "interview": "#ff7f0e",
    "offer": "#2ca02c",
    "rejected": "#d62728",
}


def _score_badge(score) -> str:
    if score is None:
        return "—"
    if score >= 70:
        return f"🟢 {score}"
    if score >= 50:
        return f"🟡 {score}"
    return f"🔴 {score}"


def show_applications():
    st.title("Applications Tracker")

    from src.database import supabase_client

    view = st.radio("View", ["Pipeline", "Table"], horizontal=True, label_visibility="collapsed")

    all_jobs = supabase_client.get_jobs()
    tracked = [j for j in all_jobs if j.get("status") in _PIPELINE_STAGES]

    if not tracked:
        st.info("No tracked applications yet. Set a job's status to 'applied' or beyond from the Jobs page.")
        return

    st.caption(f"{len(tracked)} application(s) tracked")

    if view == "Pipeline":
        _render_pipeline(tracked, supabase_client)
    else:
        _render_table(tracked, supabase_client)


def _render_pipeline(jobs: list[dict], supabase_client):
    stages = {stage: [j for j in jobs if j.get("status") == stage] for stage in _PIPELINE_STAGES}
    cols = st.columns(len(_PIPELINE_STAGES))

    for col, stage in zip(cols, _PIPELINE_STAGES):
        stage_jobs = stages[stage]
        color = _STAGE_COLORS[stage]
        col.markdown(
            f"<div style='background:{color};color:white;padding:6px 10px;"
            f"border-radius:6px;font-weight:bold;text-align:center'>"
            f"{stage.title()} ({len(stage_jobs)})</div>",
            unsafe_allow_html=True,
        )
        col.write("")

        for job in stage_jobs:
            job_id = job.get("id", "")
            with col.container(border=True):
                st.markdown(f"**[{job.get('title', 'Untitled')}]({job.get('url', '#')})**")
                st.caption(f"{job.get('company', '')} · {job.get('location', '')}")
                st.markdown(_score_badge(job.get("fit_score")))

                with st.expander("Details"):
                    _render_job_details(job, job_id, supabase_client)


def _render_table(jobs: list[dict], supabase_client):
    # sort by stage order then fit_score
    stage_order = {s: i for i, s in enumerate(_PIPELINE_STAGES)}
    jobs_sorted = sorted(
        jobs,
        key=lambda j: (stage_order.get(j.get("status", ""), 99), -(j.get("fit_score") or 0)),
    )

    for job in jobs_sorted:
        job_id = job.get("id", "")
        score = job.get("fit_score")
        status = job.get("status", "applied")
        color = _STAGE_COLORS.get(status, "#999")

        header = (
            f"**{job.get('title', 'Untitled')}** &nbsp;·&nbsp; {job.get('company', '')} "
            f"&nbsp;·&nbsp; {job.get('location', '')} &nbsp;"
            f"<span style='background:{color};color:white;padding:2px 8px;"
            f"border-radius:4px;font-size:0.8em'>{status.title()}</span>"
            f"&nbsp; {_score_badge(score)}"
        )

        with st.expander(f"{job.get('title', 'Untitled')} — {job.get('company', '')}"):
            st.markdown(header, unsafe_allow_html=True)
            _render_job_details(job, job_id, supabase_client)


def _render_job_details(job: dict, job_id: str, supabase_client):
    status_choices = _PIPELINE_STAGES
    current_status = job.get("status", "applied")
    new_status = st.selectbox(
        "Stage",
        status_choices,
        index=status_choices.index(current_status) if current_status in status_choices else 0,
        key=f"app_status_{job_id}",
    )
    if new_status != current_status and job_id:
        supabase_client.update_job_status(job_id, new_status)

    # interview date
    raw_date = job.get("interview_date")
    parsed_date = None
    if raw_date:
        try:
            parsed_date = date.fromisoformat(str(raw_date))
        except ValueError:
            pass

    new_date = st.date_input(
        "Interview Date",
        value=parsed_date,
        key=f"idate_{job_id}",
    )
    date_str = new_date.isoformat() if new_date else None
    if date_str != (parsed_date.isoformat() if parsed_date else None) and job_id:
        supabase_client.save_interview_date(job_id, date_str)

    # notes
    notes = st.text_area(
        "Notes",
        value=job.get("notes") or "",
        height=100,
        key=f"notes_{job_id}",
        placeholder="Interview prep notes, contacts, next steps...",
    )
    if st.button("Save Notes", key=f"save_notes_{job_id}"):
        supabase_client.save_job_notes(job_id, notes)
        st.success("Notes saved.")

    # analysis summary if available
    analysis = job.get("analysis") or {}
    if analysis:
        summary = analysis.get("summary", "")
        matching = analysis.get("matching_skills", [])
        missing = analysis.get("missing_skills", [])
        if summary:
            st.markdown(f"**AI Summary:** {summary}")
        if matching:
            st.markdown("**Matching:** " + ", ".join(matching))
        if missing:
            st.markdown("**Gaps:** " + ", ".join(missing))
