import os
import streamlit as st


def show_upwork_video():
    st.title("Upwork Video Script Generator")
    st.caption("Generate a 2-minute pitch video script tailored to an Upwork job.")

    from src.database import supabase_client
    settings = supabase_client.get_user_settings()
    saved_examples = settings.get("upwork_video_examples") or ["", "", ""]
    if len(saved_examples) < 3:
        saved_examples += [""] * (3 - len(saved_examples))

    # ── Video Script Examples ─────────────────────────────────────────
    with st.expander("Video Script Examples (saved as reference for Gemini)", expanded=False):
        st.caption("Paste up to 3 winning video scripts. Gemini will use these as style references.")
        with st.form("video_examples_form"):
            ex1 = st.text_area("Example 1", value=saved_examples[0], height=150, placeholder="Paste video script example #1...")
            ex2 = st.text_area("Example 2", value=saved_examples[1], height=150, placeholder="Paste video script example #2...")
            ex3 = st.text_area("Example 3", value=saved_examples[2], height=150, placeholder="Paste video script example #3...")
            if st.form_submit_button("Save Examples", type="primary", use_container_width=True):
                supabase_client.save_user_settings({
                    "upwork_video_examples": [ex1, ex2, ex3]
                })
                st.success("Examples saved.")
                st.rerun()

    st.divider()

    # ── Generate form ─────────────────────────────────────────────────
    with st.form("video_form"):
        job_description = st.text_area(
            "Job Description",
            height=180,
            placeholder="Paste the Upwork job posting here...",
        )
        case_studies = st.text_area(
            "Case Studies",
            height=150,
            placeholder=(
                "Case Study #1: ...\n"
                "Case Study #2: ...\n"
                "Case Study #3: ..."
            ),
        )
        current_profile = st.text_area(
            "Current Upwork Profile",
            height=120,
            placeholder="Paste your Upwork profile summary / headline here...",
        )
        current_resume = st.text_area(
            "Current Resume",
            height=180,
            placeholder="Paste your resume or key highlights here...",
        )
        generate_btn = st.form_submit_button("Generate Video Script", type="primary", use_container_width=True)

    if generate_btn:
        if not job_description.strip():
            st.warning("Please enter a job description.")
            return

        # Reload latest examples at generation time
        fresh_settings = supabase_client.get_user_settings()
        examples = fresh_settings.get("upwork_video_examples") or []
        filled_examples = [e for e in examples if e and e.strip()]

        examples_block = ""
        if filled_examples:
            examples_block = "\n\nHere are winning video script examples to use as style reference:\n"
            for idx, ex in enumerate(filled_examples, 1):
                examples_block += f"\n--- Example {idx} ---\n{ex.strip()}\n"

        with st.spinner("Writing your video script..."):
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                model = genai.GenerativeModel(
                    model_name="gemini-3-flash-preview",
                    system_instruction=f"""You are "Pitch Assistant", writing 2-min video scripts that win Upwork jobs.

Tone & Style rules:
- Friendly, casual, natural — like a voice message to a friend
- Simple English — short sentences, everyday words
- No hype, no fluff, never exaggerate
- Do NOT make up case studies — only use the ones provided
- Start with a clear, direct reference to the project. Don't over-introduce yourself
- Mention case studies quickly, like you talk about this stuff all the time
- Spend most of the time showing exactly what you'd do — with tools, examples, or a live flow
- End with a confident, low-pressure CTA assuming the win

Output format — return a Markdown block with EXACTLY these four timestamped sections:

## 0–5 sec: Hook + Greeting
[Start by greeting and referencing their specific project in the first sentence]

## 5–15 sec: Prospect-First Insight
[Point out a specific insight or challenge in their project that shows you truly read it]

## 15–40 sec: About Me + Social Proof
[1-line intro of yourself, then drop 2–3 case studies casually — don't dwell]

## 40–120 sec: Mini Solution + Close
[Walk through exactly what you'd do for THIS project — specific tools, steps, approach]
[End with a CTA that assumes the win: invite to a call, keep it real and low pressure]

Please follow the examples below to generate contexts for new Upwork job applications.
{examples_block}""",
                )

                user_prompt = f"""Job Description:
{job_description}

Case Studies:
{case_studies or 'Not provided — use profile/resume highlights only'}

My Upwork Profile:
{current_profile or 'Not provided'}

My Resume:
{current_resume or 'Not provided'}

Write the 2-minute video script now."""

                response = model.generate_content(user_prompt)
                script = response.text or ""
            except Exception as e:
                st.error(f"Failed to generate script: {e}")
                return

        st.divider()
        st.subheader("2-Minute Video Script")
        st.markdown(script)
        st.download_button(
            "Download as .txt",
            data=script,
            file_name="upwork_video_script.txt",
            mime="text/plain",
            use_container_width=True,
        )
