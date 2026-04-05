import json
import os
import streamlit as st


def _extract_pdf_text(uploaded_file) -> str:
    """Extract text from PDF using pdfplumber (layout-aware)."""
    try:
        import pdfplumber  # type: ignore

        pages = []
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=True)
                if text:
                    pages.append(text)
        return "\n\n".join(pages).strip()
    except ImportError:
        st.error("pdfplumber not installed. Run: pip install pdfplumber")
        return ""
    except Exception as e:
        st.error(f"Failed to read PDF: {e}")
        return ""


def _parse_resume_with_ai(resume_text: str) -> dict:
    """Send resume text to GPT-4o-mini and return structured JSON."""
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = (
        "Parse the following resume text into structured JSON. "
        "Extract every detail accurately. Return a JSON object with these exact keys:\n"
        "- name (string)\n"
        "- email (string)\n"
        "- phone (string)\n"
        "- linkedin (string, URL or empty)\n"
        "- location (string)\n"
        "- summary (string, professional summary/objective if present)\n"
        "- skills (array of strings, all skills mentioned)\n"
        "- work_history (array of objects with: company, title, start_date, end_date, location, bullets (array of strings))\n"
        "- education (array of objects with: institution, degree, field, graduation_date, gpa)\n"
        "- certifications (array of strings)\n"
        "- projects (array of objects with: name, description, technologies (array of strings))\n"
        "- languages (array of strings)\n"
        "- sections (object mapping any other section name to its raw text content)\n\n"
        "If a field is not found, use an empty string or empty array. "
        "Do not invent information — only extract what is present.\n\n"
        f"RESUME:\n{resume_text}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a resume parser. Extract structured data from resume text accurately. Return only valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _render_parsed_resume(parsed: dict):
    """Render the AI-parsed resume in a clean structured layout."""
    # Contact info card
    name = parsed.get("name", "")
    email = parsed.get("email", "")
    phone = parsed.get("phone", "")
    linkedin = parsed.get("linkedin", "")
    location = parsed.get("location", "")

    if name:
        st.markdown(f"## {name}")

    contact_parts = [p for p in [email, phone, location] if p]
    if linkedin:
        contact_parts.append(f"[LinkedIn]({linkedin})")
    if contact_parts:
        st.markdown("  ·  ".join(contact_parts))

    st.divider()

    # Summary
    summary = parsed.get("summary", "")
    if summary:
        st.subheader("Summary")
        st.write(summary)

    # Skills as tags
    skills = parsed.get("skills", [])
    if skills:
        st.subheader("Skills")
        cols = st.columns(4)
        for i, skill in enumerate(skills):
            cols[i % 4].markdown(
                f"<span style='background:#e3f2fd;padding:3px 8px;"
                f"border-radius:4px;font-size:0.85em;display:inline-block;"
                f"margin:2px'>{skill}</span>",
                unsafe_allow_html=True,
            )

    # Work history
    work = parsed.get("work_history", [])
    if work:
        st.subheader("Work History")
        for job in work:
            dates = f"{job.get('start_date', '')} – {job.get('end_date', 'Present')}".strip(" –")
            loc = job.get("location", "")
            header = f"**{job.get('title', '')}** at **{job.get('company', '')}**"
            if dates:
                header += f"  ·  {dates}"
            if loc:
                header += f"  ·  {loc}"
            st.markdown(header)
            for bullet in job.get("bullets", []):
                st.markdown(f"- {bullet}")
            st.write("")

    # Education
    education = parsed.get("education", [])
    if education:
        st.subheader("Education")
        for edu in education:
            line = f"**{edu.get('degree', '')} in {edu.get('field', '')}** — {edu.get('institution', '')}"
            if edu.get("graduation_date"):
                line += f"  ·  {edu['graduation_date']}"
            if edu.get("gpa"):
                line += f"  ·  GPA: {edu['gpa']}"
            st.markdown(line)

    # Certifications
    certs = parsed.get("certifications", [])
    if certs:
        st.subheader("Certifications")
        for c in certs:
            st.markdown(f"- {c}")

    # Projects
    projects = parsed.get("projects", [])
    if projects:
        st.subheader("Projects")
        for p in projects:
            techs = ", ".join(p.get("technologies", []))
            st.markdown(f"**{p.get('name', '')}**" + (f" · {techs}" if techs else ""))
            if p.get("description"):
                st.caption(p["description"])

    # Languages
    languages = parsed.get("languages", [])
    if languages:
        st.subheader("Languages")
        st.write(", ".join(languages))

    # Any extra sections
    for section_name, content in (parsed.get("sections") or {}).items():
        if content:
            st.subheader(section_name)
            st.write(content)


def show_resume():
    st.title("Resume Manager")

    from src.database import supabase_client

    settings = supabase_client.get_user_settings()
    stored_resume = settings.get("resume_text", "") or ""

    tab_upload, tab_paste, tab_view, tab_optimize = st.tabs(
        ["Upload File", "Paste Text", "View & Edit", "Optimize"]
    )

    # --- Upload tab ---
    with tab_upload:
        st.markdown("Upload a PDF or plain text file.")
        uploaded = st.file_uploader("Choose file", type=["pdf", "txt"])

        if uploaded is not None:
            if uploaded.type == "application/pdf":
                with st.spinner("Extracting text from PDF..."):
                    text = _extract_pdf_text(uploaded)
            else:
                text = uploaded.read().decode("utf-8", errors="replace")

            if text:
                st.success(f"Extracted {len(text.split())} words.")
                st.text_area(
                    "Preview",
                    text[:1500] + ("..." if len(text) > 1500 else ""),
                    height=200,
                    disabled=True,
                )
                if st.button("Save This Resume", type="primary", key="save_upload"):
                    supabase_client.save_user_settings({"resume_text": text})
                    st.success("Resume saved.")
                    st.rerun()

    # --- Paste tab ---
    with tab_paste:
        st.markdown("Paste your resume as plain text.")
        pasted = st.text_area(
            "Resume text",
            value=stored_resume,
            height=400,
            placeholder="Paste your full resume here...",
        )
        word_count = len(pasted.split()) if pasted.strip() else 0
        st.caption(f"{word_count} words")

        if st.button("Save Resume", type="primary", key="save_paste"):
            if not pasted.strip():
                st.warning("Resume text is empty.")
            else:
                supabase_client.save_user_settings({"resume_text": pasted})
                st.success("Resume saved.")
                st.rerun()

    # --- View & Edit tab ---
    with tab_view:
        if not stored_resume:
            st.info("No resume saved yet. Use the Upload or Paste tab.")
            return

        col1, col2, col3 = st.columns(3)
        col1.metric("Word Count", len(stored_resume.split()))
        col2.metric("Characters", len(stored_resume))

        openai_key = os.getenv("OPENAI_API_KEY", "")
        with col3:
            parse_clicked = st.button(
                "Parse with AI",
                type="primary",
                disabled=not openai_key,
                help="Uses GPT-4o-mini to extract structured data from your resume.",
            )

        if parse_clicked:
            with st.spinner("Parsing resume with AI..."):
                try:
                    parsed = _parse_resume_with_ai(stored_resume)
                    st.session_state["parsed_resume"] = parsed
                except Exception as e:
                    st.error(f"Parsing failed: {e}")

        st.divider()

        if "parsed_resume" in st.session_state and st.session_state["parsed_resume"]:
            view_mode = st.radio(
                "View",
                ["Structured (AI)", "Raw Text"],
                horizontal=True,
                label_visibility="collapsed",
            )
            if view_mode == "Structured (AI)":
                _render_parsed_resume(st.session_state["parsed_resume"])
            else:
                st.text_area("Raw Resume", stored_resume, height=500, disabled=True)
        else:
            if openai_key:
                st.caption("Click **Parse with AI** above to extract structured data.")
            st.text_area("Raw Resume", stored_resume, height=500, disabled=True)

        st.divider()
        if st.button("Clear Saved Resume", type="secondary"):
            supabase_client.save_user_settings({"resume_text": ""})
            st.session_state.pop("parsed_resume", None)
            st.success("Resume cleared.")
            st.rerun()

    # --- Optimize tab ---
    with tab_optimize:
        if not stored_resume:
            st.info("No resume saved yet. Use the Upload or Paste tab first.")
        else:
            st.markdown("Optimize your resume for a specific job using AI.")

            jobs = supabase_client.get_jobs()
            job_options = ["(Enter job description manually)"] + [
                f"{j.get('title', 'Untitled')} — {j.get('company', '')}" for j in jobs
            ]
            selected_job_label = st.selectbox("Select a job", job_options)

            selected_job = None
            if selected_job_label != "(Enter job description manually)" and jobs:
                idx = job_options.index(selected_job_label) - 1
                selected_job = jobs[idx]

            if selected_job is None:
                manual_title = st.text_input("Job Title", placeholder="e.g. Senior Software Engineer")
                manual_company = st.text_input("Company Name", placeholder="e.g. Acme Corp")
                manual_desc = st.text_area(
                    "Job Description", height=200,
                    placeholder="Paste the job description here..."
                )
                job_for_opt = {
                    "title": manual_title,
                    "company": manual_company,
                    "description": manual_desc,
                }
            else:
                job_for_opt = selected_job
                st.markdown(
                    f"**{job_for_opt.get('title', '')}** at **{job_for_opt.get('company', '')}**"
                )

            mode_descriptions = {
                "keyword": "Match ATS keywords from the job description",
                "skills": "Reorder and emphasize skills to match requirements",
                "experience": "Rewrite bullet points to highlight relevant experience",
            }
            mode = st.radio(
                "Optimization Mode",
                options=["keyword", "skills", "experience"],
                format_func=lambda m: f"{m.title()} — {mode_descriptions[m]}",
                horizontal=True,
            )

            if st.button("Optimize Resume", type="primary", key="optimize_btn"):
                if not job_for_opt.get("description") and not job_for_opt.get("title"):
                    st.warning("Please select a job or enter a job description.")
                else:
                    with st.spinner("Optimizing resume..."):
                        from src.agents.resume_optimizer import ResumeOptimizationAgent
                        agent = ResumeOptimizationAgent()
                        opt_result = agent.optimize(stored_resume, job_for_opt, mode)
                    st.session_state["opt_result"] = opt_result
                    st.session_state["opt_job"] = job_for_opt
                    st.session_state["opt_mode"] = mode

            if "opt_result" in st.session_state:
                opt = st.session_state["opt_result"]
                opt_job = st.session_state.get("opt_job", {})

                if opt.get("error"):
                    st.error(f"Optimization failed: {opt['error']}")
                else:
                    col_m1, col_m2 = st.columns(2)
                    col_m1.metric("Match Score", f"{opt.get('match_score', 0)}/100")
                    col_m2.metric("Quality Score", f"{opt.get('quality_score', 0)}/100")

                    if opt.get("company_context"):
                        with st.expander("Company Context"):
                            st.write(opt["company_context"])

                    changes = opt.get("changes_made", [])
                    if changes:
                        st.markdown("**Changes Made:**")
                        for change in changes:
                            st.markdown(f"- {change}")

                    col_orig, col_opt = st.columns(2)
                    with col_orig:
                        st.markdown("**Original Resume**")
                        st.text_area(
                            "original", stored_resume, height=400,
                            disabled=True, label_visibility="collapsed",
                        )
                    with col_opt:
                        st.markdown("**Optimized Resume**")
                        st.text_area(
                            "optimized", opt.get("optimized_content", ""), height=400,
                            disabled=True, label_visibility="collapsed",
                        )

                    col_dl, col_save = st.columns(2)
                    with col_dl:
                        st.download_button(
                            "Download Optimized Resume (.txt)",
                            data=opt.get("optimized_content", ""),
                            file_name=f"optimized_resume_{opt_job.get('company', 'job').replace(' ', '_')}.txt",
                            mime="text/plain",
                        )
                    with col_save:
                        if st.button("Save to Library", key="save_opt_lib"):
                            saved = supabase_client.save_optimized_resume({
                                "job_title": opt_job.get("title", ""),
                                "company_name": opt_job.get("company", ""),
                                "original_content": stored_resume,
                                "optimized_content": opt.get("optimized_content", ""),
                                "optimization_mode": st.session_state.get("opt_mode", "keyword"),
                                "match_score": opt.get("match_score", 0),
                                "quality_score": opt.get("quality_score", 0),
                                "changes_made": opt.get("changes_made", []),
                            })
                            if saved:
                                st.success("Saved to library.")
                                st.rerun()
                            else:
                                st.info("Saved (mock mode).")

        st.divider()
        st.subheader("Saved Optimized Resumes")
        saved_resumes = supabase_client.get_optimized_resumes()
        if not saved_resumes:
            st.info("No optimized resumes saved yet.")
        else:
            for res in saved_resumes:
                res_id = res.get("id", "")
                created = (res.get("created_at") or "")[:10]
                with st.container(border=True):
                    col_info, col_del = st.columns([5, 1])
                    with col_info:
                        st.markdown(
                            f"**{res.get('job_title', 'Untitled')}** at **{res.get('company_name', '')}**"
                        )
                        st.caption(
                            f"Mode: {res.get('optimization_mode', '')}  ·  "
                            f"Match: {res.get('match_score', 0)}  ·  "
                            f"Quality: {res.get('quality_score', 0)}"
                            + (f"  ·  {created}" if created else "")
                        )
                    with col_del:
                        if st.button("🗑️", key=f"del_opt_{res_id}", help="Delete"):
                            supabase_client.delete_optimized_resume(str(res_id))
                            st.rerun()
                    with st.expander("View Optimized Resume"):
                        st.text_area(
                            "",
                            res.get("optimized_content", ""),
                            height=250,
                            key=f"opt_view_{res_id}",
                            disabled=True,
                            label_visibility="collapsed",
                        )
