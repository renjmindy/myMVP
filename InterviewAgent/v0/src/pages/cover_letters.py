import streamlit as st


def show_cover_letters():
    st.title("Letter Writer")

    from src.database import supabase_client
    from src.agents.cover_letter_agent import CoverLetterAgent

    # ── Generate new cover letter ──────────────────────────────────────
    st.subheader("Generate New Cover Letter")

    jobs = supabase_client.get_jobs()
    settings = supabase_client.get_user_settings()
    resume_text = settings.get("resume_text", "")

    if not jobs:
        st.info("No jobs found. Run a scrape from the Dashboard first.")
    elif not resume_text:
        st.warning("No resume found. Go to Settings and paste your resume first.")
    else:
        job_options = {
            f"{j.get('title', 'Untitled')} @ {j.get('company', '')}": j
            for j in jobs
        }

        col1, col2 = st.columns([3, 1])
        with col1:
            selected_label = st.selectbox("Select a job", list(job_options.keys()))
        with col2:
            tone = st.selectbox("Tone", ["professional", "enthusiastic", "confident", "creative"])

        selected_job = job_options[selected_label]

        if st.button("Generate Cover Letter", type="primary"):
            with st.spinner(f"Writing cover letter for {selected_job.get('company', '')}..."):
                agent = CoverLetterAgent()
                result = agent.generate(selected_job, resume_text, tone=tone)

            if result.get("error"):
                st.error(f"Generation failed: {result['error']}")
            else:
                st.success(
                    f"Generated! Quality: {result['quality_score']} · "
                    f"Personalization: {result['personalization_score']} · "
                    f"Words: {result['word_count']}"
                )
                st.text_area(
                    "Cover Letter",
                    result["content"],
                    height=400,
                    key="new_cl_preview",
                )
                st.rerun()

    st.divider()

    # ── Saved cover letters ────────────────────────────────────────────
    st.subheader("Saved Cover Letters")

    search_kw = st.text_input("Search by job title or company", placeholder="e.g. Engineer, Google")
    filters = {"keyword": search_kw} if search_kw.strip() else None
    letters = supabase_client.get_cover_letters(filters)

    total = len(letters)
    avg_quality = (
        round(sum(l.get("quality_score") or 0 for l in letters) / total, 1) if total else 0
    )
    avg_personal = (
        round(sum(l.get("personalization_score") or 0 for l in letters) / total, 1) if total else 0
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Saved", total)
    col2.metric("Avg Quality Score", avg_quality if total else "—")
    col3.metric("Avg Personalization Score", avg_personal if total else "—")

    if not letters:
        st.info("No cover letters saved yet. Generate one above.")
        return

    st.divider()

    _TONE_COLORS = {
        "professional": "#1565c0",
        "enthusiastic": "#e65100",
        "confident": "#2e7d32",
        "creative": "#6a1b9a",
    }

    for i in range(0, len(letters), 2):
        cols = st.columns(2)
        for col_idx, letter in enumerate(letters[i: i + 2]):
            with cols[col_idx]:
                tone = letter.get("tone") or "professional"
                tone_color = _TONE_COLORS.get(tone, "#555")
                q_score = letter.get("quality_score") or 0
                p_score = letter.get("personalization_score") or 0
                created = (letter.get("created_at") or "")[:10]

                tone_badge = (
                    f"<span style='background:{tone_color};color:white;padding:2px 8px;"
                    f"border-radius:12px;font-size:0.8em'>{tone}</span>"
                )

                with st.container(border=True):
                    st.markdown(
                        f"**{letter.get('job_title', 'Untitled')}** at **{letter.get('company_name', '')}**"
                    )
                    st.markdown(tone_badge, unsafe_allow_html=True)

                    m1, m2 = st.columns(2)
                    m1.metric("Quality", q_score)
                    m2.metric("Personalization", p_score)

                    if created:
                        st.caption(f"Generated: {created}")

                    letter_id = letter.get("id", f"letter_{i}_{col_idx}")

                    with st.expander("View Full Cover Letter"):
                        content = letter.get("content", "")
                        st.text_area(
                            "cover letter text",
                            content,
                            height=300,
                            key=f"cl_view_{letter_id}",
                            label_visibility="collapsed",
                        )
                        st.code(content, language=None)

                    if st.button(
                        "🗑️ Delete",
                        key=f"del_cl_{letter_id}",
                        use_container_width=True,
                    ):
                        supabase_client.delete_cover_letter(str(letter_id))
                        st.rerun()
