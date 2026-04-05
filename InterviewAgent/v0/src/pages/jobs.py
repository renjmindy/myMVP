import streamlit as st


def _score_badge(score) -> str:
    if score is None:
        return "⬜ —"
    if score >= 70:
        return f"🟢 {score}"
    if score >= 50:
        return f"🟡 {score}"
    return f"🔴 {score}"


def _rec_pill(rec: str) -> str:
    icons = {"apply": "✅", "maybe": "⚠️", "skip": "❌"}
    return f"{icons.get(rec, '❓')} {rec}" if rec else ""


_STATUS_COLORS = {
    "new":      "#1565c0",
    "saved":    "#6a1b9a",
    "applied":  "#2e7d32",
    "rejected": "#c62828",
}


def show_jobs():
    st.title("Job Listings")

    from src.database import supabase_client
    from src.agents.ai_agent import JobAnalysisAgent

    # sidebar filters
    with st.sidebar:
        st.header("Filters")
        status_opts = ["new", "saved", "applied", "rejected"]
        selected_statuses = st.multiselect("Status", status_opts, default=status_opts)
        min_score = st.slider("Min Fit Score", 0, 100, 0)
        source_opts = ["linkedin", "indeed"]
        selected_sources = st.multiselect("Source", source_opts, default=source_opts)
        keyword = st.text_input("Keyword search")

    filters: dict = {}
    if selected_statuses:
        filters["status"] = selected_statuses
    if min_score:
        filters["min_fit_score"] = min_score
    if selected_sources:
        filters["source"] = selected_sources
    if keyword:
        filters["keyword"] = keyword

    jobs = supabase_client.get_jobs(filters)

    if not jobs:
        st.info("No jobs found. Adjust filters or run a scrape from the Dashboard.")
        return

    st.caption(f"Showing {len(jobs)} job(s)")

    settings = supabase_client.get_user_settings()
    resume_text = settings.get("resume_text", "")

    # 2-column grid
    for i in range(0, len(jobs), 2):
        cols = st.columns(2)
        for col_idx, job in enumerate(jobs[i: i + 2]):
            with cols[col_idx]:
                score = job.get("fit_score")
                analysis = job.get("analysis") or {}
                rec = analysis.get("recommendation", job.get("recommendation", ""))
                current_status = job.get("status", "new") or "new"
                status_color = _STATUS_COLORS.get(current_status, "#555")

                badge = _score_badge(score)
                pill = _rec_pill(rec)

                # ── Header row: title left, status badge right ─────────
                status_badge = (
                    f"<span style='background:{status_color};color:white;"
                    f"padding:2px 10px;border-radius:12px;font-size:0.78em;"
                    f"float:right'>{current_status.upper()}</span>"
                )
                st.markdown(
                    f"<div>{status_badge}</div>"
                    f"<div style='clear:both'></div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"### [{job.get('title', 'Untitled')}]({job.get('url', '#')})"
                )
                st.markdown(
                    f"**{job.get('company', '')}** · {job.get('location', '')}"
                )
                st.markdown(f"{badge}  {pill}")

                # ── Status dropdown ────────────────────────────────────
                status_choices = ["new", "saved", "applied", "rejected"]
                new_status = st.selectbox(
                    "Status",
                    status_choices,
                    index=status_choices.index(current_status)
                    if current_status in status_choices else 0,
                    key=f"status_{job.get('id', i)}",
                )
                if new_status != current_status and job.get("id"):
                    supabase_client.update_job_status(job["id"], new_status)
                    st.rerun()

                # ── Apply button ───────────────────────────────────────
                job_url = job.get("url", "")
                if current_status == "applied":
                    st.success("✅ Already applied")
                elif job_url:
                    st.link_button(
                        "🖊 Apply on Company Website", job_url, use_container_width=True
                    )

                # ── Delete job ────────────────────────────────────────
                jid = job.get("id")
                if jid and st.button(
                    "🗑 Delete Job",
                    key=f"del_{jid}",
                    use_container_width=True,
                ):
                    supabase_client.delete_job_with_files(
                        jid, job.get("title", ""), job.get("company", "")
                    )
                    st.rerun()

                # ── Network contacts ───────────────────────────────────
                company = job.get("company", "")
                contacts = supabase_client.get_network_contacts(company)
                with st.expander(f"👥 Network at {company}"):
                    _DEGREE_COLOR = {"1st": "#1565c0", "2nd": "#2e7d32", "3rd": "#888"}

                    import re as _re
                    _company_slug = _re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
                    _company_people_url = f"https://www.linkedin.com/company/{_company_slug}/people/"

                    def _render_contacts(contact_list):
                        verified = [c for c in contact_list if c.get("linkedin_url")]
                        if not verified:
                            return False
                        for contact in verified:
                            degree = contact.get("degree", "")
                            color = _DEGREE_COLOR.get(degree, "#888")
                            degree_badge = (
                                f"<span style='background:{color};color:white;"
                                f"padding:1px 8px;border-radius:10px;font-size:0.75em'>"
                                f"{degree}</span>"
                            )
                            mutual = contact.get("mutual")
                            mutual_text = f" · via {mutual}" if mutual else ""
                            name = contact.get("name", "")
                            st.markdown(
                                f"**[{name}]({contact['linkedin_url']})** {degree_badge}  \n"
                                f"*{contact.get('title', '')}*{mutual_text}",
                                unsafe_allow_html=True,
                            )
                        return True

                    has_verified = contacts and _render_contacts(contacts)
                    if not has_verified:
                        st.caption("No verified contacts found yet.")
                    st.markdown(f"[Browse all employees on LinkedIn]({_company_people_url})")

                    btn_col, _ = st.columns([1, 2])
                    with btn_col:
                        if st.button(
                            "🔍 Find Contacts",
                            key=f"find_contacts_{job.get('id', i)}",
                            use_container_width=True,
                        ):
                            with st.spinner(f"Searching for people at {company}..."):
                                try:
                                    from src.agents.network_contacts_agent import NetworkContactsAgent
                                    agent = NetworkContactsAgent()
                                    found = agent.find_contacts(company)
                                except Exception as e:
                                    st.error(f"Agent error: {e}")
                                    found = []
                            verified_found = [c for c in found if c.get("linkedin_url")]
                            if verified_found:
                                saved = supabase_client.save_network_contacts(company, verified_found)
                                if saved:
                                    st.success(f"Found and saved {len(verified_found)} verified contact(s).")
                                    st.rerun()
                                else:
                                    st.error("Contacts found but failed to save. Check Supabase connection.")
                                    _render_contacts(verified_found)
                            else:
                                st.warning("No verified LinkedIn contacts found for this company.")

                    # ── Manual contact entry ───────────────────────────
                    _jkey = job.get('id', i)
                    with st.form(key=f"add_contact_{_jkey}"):
                        st.caption("Add a contact manually")
                        mc1, mc2 = st.columns(2)
                        m_name = mc1.text_input("Name", key=f"m_name_{_jkey}")
                        m_url = mc2.text_input("LinkedIn URL", key=f"m_url_{_jkey}")
                        mc3, mc4 = st.columns(2)
                        m_title = mc3.text_input("Title (optional)", key=f"m_title_{_jkey}")
                        m_degree = mc4.selectbox("Degree", ["1st", "2nd", "3rd"], key=f"m_deg_{_jkey}")
                        if st.form_submit_button("Add Contact", use_container_width=True):
                            if not m_name or not m_url:
                                st.warning("Name and LinkedIn URL are required.")
                            else:
                                new_contact = {
                                    "name": m_name.strip(),
                                    "title": m_title.strip(),
                                    "degree": m_degree,
                                    "mutual": None,
                                    "linkedin_url": m_url.strip(),
                                }
                                existing = supabase_client.get_network_contacts(company)
                                merged = existing + [new_contact]
                                supabase_client.save_network_contacts(company, merged)
                                st.success(f"Added {m_name}.")
                                st.rerun()

                    # ── Referral email generator ───────────────────────
                    verified_contacts = [c for c in contacts if c.get("linkedin_url")]
                    if verified_contacts:
                        st.divider()
                        st.caption("Generate referral invite email")
                        contact_names = [c["name"] for c in verified_contacts]
                        selected_name = st.selectbox(
                            "Contact",
                            contact_names,
                            key=f"ref_contact_{job.get('id', i)}",
                        )
                        if st.button(
                            "Generate Referral Email",
                            key=f"gen_ref_{job.get('id', i)}",
                            use_container_width=True,
                        ):
                            selected_contact = next(
                                c for c in verified_contacts if c["name"] == selected_name
                            )
                            settings = supabase_client.get_user_settings()
                            sender_name = settings.get("name", "")
                            resume_text = settings.get("resume_text", "")
                            with st.spinner("Drafting referral email..."):
                                try:
                                    import os
                                    from openai import OpenAI  # type: ignore
                                    _oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                                    prompt = (
                                        f"Write a concise, warm referral request email from {sender_name or 'me'} "
                                        f"to {selected_contact['name']} ({selected_contact.get('title', 'colleague')}) "
                                        f"at {company}, asking them to refer me for the role of "
                                        f"'{job.get('title', '')}'. "
                                        f"Mention we are {selected_contact.get('degree', '2nd')}-degree connections. "
                                        f"Keep it under 150 words, professional but friendly. "
                                        f"Do not invent specific shared history. "
                                        + (
                                            f"My background summary: {resume_text[:500]}"
                                            if resume_text else ""
                                        )
                                    )
                                    resp = _oai.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[{"role": "user", "content": prompt}],
                                        temperature=0.7,
                                    )
                                    referral_email = resp.choices[0].message.content or ""
                                except Exception as e:
                                    referral_email = f"(Error generating email: {e})"
                            st.session_state[f"ref_email_{job.get('id', i)}"] = referral_email

                        draft = st.session_state.get(f"ref_email_{job.get('id', i)}", "")
                        if draft:
                            st.text_area(
                                "Referral Email Draft",
                                value=draft,
                                height=220,
                                key=f"ref_draft_{job.get('id', i)}",
                            )

                # ── Job details ────────────────────────────────────────
                with st.expander("View Details"):
                    desc = job.get("description", "")
                    if desc:
                        st.markdown("**Description**")
                        st.text_area(
                            "",
                            desc[:2000] + ("..." if len(desc) > 2000 else ""),
                            height=150,
                            key=f"desc_{job.get('id', i)}",
                            disabled=True,
                        )

                    if analysis:
                        matching = analysis.get("matching_skills", [])
                        missing = analysis.get("missing_skills", [])
                        summary = analysis.get("summary", "")
                        if summary:
                            st.markdown(f"**Summary:** {summary}")
                        if matching:
                            st.markdown("**Matching Skills:** " + ", ".join(matching))
                        if missing:
                            st.markdown("**Missing Skills:** " + ", ".join(missing))

                # ── Resume tailoring ───────────────────────────────────
                with st.expander("🎯 Tailor Resume"):
                    if not resume_text:
                        st.warning("Add your resume in Settings first.")
                    else:
                        opt_mode = st.selectbox(
                            "Optimization Mode",
                            ["keyword", "skills", "experience"],
                            format_func=lambda x: {
                                "keyword": "Keyword — inject missing ATS keywords",
                                "skills": "Skills — reorder skills to match job",
                                "experience": "Experience — rewrite bullet points",
                            }[x],
                            key=f"opt_mode_{job.get('id', i)}",
                        )
                        opt_result_key = f"opt_result_{job.get('id', i)}"

                        if st.button(
                            "Tailor My Resume",
                            key=f"opt_btn_{job.get('id', i)}",
                            type="primary",
                        ):
                            with st.spinner("Tailoring resume..."):
                                from src.agents.resume_optimizer import ResumeOptimizationAgent
                                opt_agent = ResumeOptimizationAgent()
                                opt_result = opt_agent.optimize(resume_text, job, mode=opt_mode)
                            st.session_state[opt_result_key] = opt_result

                        if opt_result_key in st.session_state:
                            opt_res = st.session_state[opt_result_key]
                            m1, m2 = st.columns(2)
                            m1.metric("Match Score", opt_res.get("match_score", 0))
                            m2.metric("Quality Score", opt_res.get("quality_score", 0))
                            changes = opt_res.get("changes_made", [])
                            if changes:
                                st.markdown("**Changes made:**")
                                for c in changes:
                                    st.markdown(f"- {c}")
                            st.text_area(
                                "Tailored Resume",
                                opt_res.get("optimized_content", ""),
                                height=300,
                                key=f"opt_area_{job.get('id', i)}",
                            )
                            if st.button(
                                "🗑️ Clear",
                                key=f"clear_opt_{job.get('id', i)}",
                            ):
                                del st.session_state[opt_result_key]
                                st.rerun()

                # ── Cover letter generation ────────────────────────────
                with st.expander("✉️ Generate Cover Letter"):
                    if not resume_text:
                        st.warning("Add your resume in Settings first.")
                    else:
                        cl_key = f"cl_{job.get('id', i)}"
                        cl_result_key = f"cl_result_{job.get('id', i)}"

                        tone = st.selectbox(
                            "Tone",
                            ["professional", "enthusiastic", "confident", "creative"],
                            key=f"tone_{job.get('id', i)}",
                        )

                        with st.expander("Candidate Info (optional)"):
                            cand_name  = st.text_input("Name",  key=f"cand_name_{job.get('id', i)}")
                            cand_email = st.text_input("Email", key=f"cand_email_{job.get('id', i)}")
                            cand_phone = st.text_input("Phone", key=f"cand_phone_{job.get('id', i)}")

                        if st.button(
                            "Generate Cover Letter",
                            key=f"gen_{job.get('id', i)}",
                            type="primary",
                        ):
                            candidate_info = {
                                k: v for k, v in {
                                    "name": cand_name,
                                    "email": cand_email,
                                    "phone": cand_phone,
                                }.items() if v
                            }
                            with st.spinner("Generating cover letter..."):
                                from src.agents.cover_letter_agent import CoverLetterAgent
                                cl_agent = CoverLetterAgent()
                                cl_result = cl_agent.generate(
                                    job, resume_text, tone,
                                    candidate_info=candidate_info or None,
                                )
                            st.session_state[cl_key] = cl_result.get("content", "")
                            st.session_state[cl_result_key] = cl_result

                        if cl_result_key in st.session_state:
                            cl_res = st.session_state[cl_result_key]
                            m1, m2 = st.columns(2)
                            m1.metric("Quality Score", cl_res.get("quality_score", 0))
                            m2.metric("Personalization Score", cl_res.get("personalization_score", 0))

                        if cl_key in st.session_state:
                            st.text_area(
                                "Cover Letter",
                                st.session_state[cl_key],
                                height=250,
                                key=f"cl_area_{job.get('id', i)}",
                            )
                            if st.button("Save to Library", key=f"save_cl_{job.get('id', i)}"):
                                cl_res = st.session_state.get(cl_result_key, {})
                                saved = supabase_client.save_cover_letter({
                                    "job_title": job.get("title", ""),
                                    "company_name": job.get("company", ""),
                                    "content": st.session_state[cl_key],
                                    "tone": cl_res.get("tone", tone),
                                    "quality_score": cl_res.get("quality_score", 0),
                                    "personalization_score": cl_res.get("personalization_score", 0),
                                    "word_count": cl_res.get("word_count", 0),
                                })
                                if saved:
                                    st.success("Saved to library.")
                                else:
                                    st.info("Saved (mock mode).")

                st.divider()
