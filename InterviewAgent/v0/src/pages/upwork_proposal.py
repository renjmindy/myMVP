import os
import streamlit as st


def show_upwork_proposal():
    st.title("Upwork Proposal Generator")
    st.caption("Fill in the fields below and generate a structured proposal letter.")

    from src.database import supabase_client
    settings = supabase_client.get_user_settings()
    saved_examples = settings.get("upwork_proposal_examples") or ["", "", "", "", ""]
    if len(saved_examples) < 5:
        saved_examples += [""] * (5 - len(saved_examples))

    # ── Proposal Examples ─────────────────────────────────────────────
    with st.expander("Proposal Examples (saved as reference for Gemini)", expanded=False):
        st.caption("Paste up to 5 winning proposals. Gemini will use these as style references.")
        with st.form("examples_form"):
            ex1 = st.text_area("Example 1", value=saved_examples[0], height=150, placeholder="Paste proposal example #1...")
            ex2 = st.text_area("Example 2", value=saved_examples[1], height=150, placeholder="Paste proposal example #2...")
            ex3 = st.text_area("Example 3", value=saved_examples[2], height=150, placeholder="Paste proposal example #3...")
            ex4 = st.text_area("Example 4", value=saved_examples[3], height=150, placeholder="Paste proposal example #4...")
            ex5 = st.text_area("Example 5", value=saved_examples[4], height=150, placeholder="Paste proposal example #5...")
            if st.form_submit_button("Save Examples", type="primary", use_container_width=True):
                supabase_client.save_user_settings({
                    "upwork_proposal_examples": [ex1, ex2, ex3, ex4, ex5]
                })
                st.success("Examples saved.")
                st.rerun()

    st.divider()

    # ── Generate form ─────────────────────────────────────────────────
    with st.form("proposal_form"):
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
        generate_btn = st.form_submit_button("Generate Proposal", type="primary", use_container_width=True)

    if generate_btn:
        if not job_description.strip():
            st.warning("Please enter a job description.")
            return

        # Reload latest examples at generation time
        fresh_settings = supabase_client.get_user_settings()
        examples = fresh_settings.get("upwork_proposal_examples") or []
        filled_examples = [e for e in examples if e and e.strip()]

        examples_block = ""
        if filled_examples:
            examples_block = "\n\nHere are winning proposal examples to use as style reference:\n"
            for idx, ex in enumerate(filled_examples, 1):
                examples_block += f"\n--- Example {idx} ---\n{ex.strip()}\n"

        with st.spinner("Generating proposal..."):
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                model = genai.GenerativeModel(
                    model_name="gemini-3-flash-preview",
                    system_instruction=f"""You are an expert Upwork proposal writer.
Generate a compelling proposal using EXACTLY this four-part structure:

---
## Hook — Make the Client Feel Seen
Reiterate the client's pain point and praise their direction.
- Start with "I see..." or "I understand..." to acknowledge the problem
- Add a praise line ("You're absolutely right...", "Great call on...", "It's clear that you...")

## Solution — Make the Client Feel You Can Do It
Directly explain HOW you will solve the problem, step by step.
- Mention: "Instead of a long proposal, I recorded a 2-minute video to walk you through my approach."

## Proof — Make the Client Feel You Are Credible
Include the provided case studies as social proof.
- Brief intro: "I am [name from resume], specialising in [relevant skill]..."
- List each case study concisely

## CTA — Make the Client Feel Motivated to Act
End with a low-pressure, friendly call to action.
- "Are you open to a quick 10-minute chat? Or feel free to message me..."
---

Keep the tone warm, professional, and confident. No fluff. Under 350 words total.
Please follow the examples below to generate contexts for new Upwork job applications.
{examples_block}""",
                )

                user_prompt = f"""Job Description:
{job_description}

Case Studies:
{case_studies or 'Not provided'}

My Upwork Profile:
{current_profile or 'Not provided'}

My Resume:
{current_resume or 'Not provided'}

Write the proposal now."""

                response = model.generate_content(user_prompt)
                proposal = response.text or ""
            except Exception as e:
                st.error(f"Failed to generate proposal: {e}")
                return

        st.divider()
        st.subheader("Generated Proposal")
        st.markdown(proposal)
        st.download_button(
            "Download as .txt",
            data=proposal,
            file_name="upwork_proposal.txt",
            mime="text/plain",
            use_container_width=True,
        )
