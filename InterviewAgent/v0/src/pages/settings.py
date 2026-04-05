import os
import streamlit as st


def show_settings():
    st.title("Settings")

    from src.database import supabase_client

    current = supabase_client.get_user_settings()

    # ── Company filter (outside form for live mutual-disable) ─────────
    target_raw = st.text_input(
        "Target Companies Only (comma-separated, leave blank for all)",
        value=", ".join(current.get("target_companies") or []),
        placeholder="e.g. Google, Stripe, OpenAI",
        help="When set, scraping is restricted to only these companies. Disables the exclusion list.",
        key="target_raw",
        disabled=bool(st.session_state.get("excluded_raw", ", ".join(current.get("excluded_companies") or []) or "N/A").strip().lower() not in ("", "n/a")),
    )
    excluded_raw = st.text_input(
        "Companies Not Included (comma-separated, or N/A for all)",
        value=", ".join(current.get("excluded_companies") or []) or "N/A",
        placeholder="e.g. Google, Amazon, Meta",
        help="Jobs from these companies will be skipped during scraping. Disabled when Target Companies is set.",
        key="excluded_raw",
        disabled=bool(st.session_state.get("target_raw", ", ".join(current.get("target_companies") or [])).strip()),
    )

    with st.form("settings_form"):
        keywords_raw = st.text_input(
            "Search Keywords (comma-separated)",
            value=", ".join(current.get("keywords") or []),
            placeholder="e.g. software engineer, python developer",
        )

        location = st.text_input(
            "Location",
            value=current.get("location", ""),
            placeholder="e.g. New York, NY or Remote",
        )

        resume_text = st.text_area(
            "Resume Text",
            value=current.get("resume_text", ""),
            height=300,
            placeholder="Paste your full resume here...",
        )

        st.subheader("Profile")
        pc1, pc2 = st.columns(2)
        full_name = pc1.text_input(
            "Full Name",
            value=current.get("name", ""),
            placeholder="e.g. Jane Smith",
        )
        phone = pc2.text_input(
            "Phone Number",
            value=current.get("phone", ""),
            placeholder="e.g. +1 (555) 123-4567",
        )

        wa_opts = [
            "US Citizen",
            "US Permanent Resident (Green Card)",
            "H-1B Visa",
            "OPT / STEM OPT",
            "TN Visa",
            "Other Visa / Requires Sponsorship",
            "Not Authorized to Work in US",
        ]
        current_wa = current.get("work_authorization", wa_opts[0])
        work_authorization = st.selectbox(
            "Work Authorization",
            wa_opts,
            index=wa_opts.index(current_wa) if current_wa in wa_opts else 0,
        )

        yoe_opts = ["0–1", "1–3", "3–5", "5–10", "10+"]
        current_yoe = current.get("years_of_experience", yoe_opts[1])
        years_of_experience = st.selectbox(
            "Years of Experience",
            yoe_opts,
            index=yoe_opts.index(current_yoe) if current_yoe in yoe_opts else 1,
        )

        st.subheader("Notifications")
        notify_email = st.text_input(
            "Notification Email",
            value=current.get("email", ""),
            placeholder="you@example.com",
        )

        threshold = st.slider(
            "Fit Score Notification Threshold",
            min_value=0,
            max_value=100,
            value=int(current.get("notify_threshold", 70)),
            help="Only send notifications for jobs at or above this score.",
        )

        freq_opts = ["daily", "instant"]
        current_freq = current.get("notify_frequency", "daily")
        freq_index = freq_opts.index(current_freq) if current_freq in freq_opts else 0
        frequency = st.radio(
            "Notification Frequency",
            freq_opts,
            index=freq_index,
            horizontal=True,
        )

        save_btn = st.form_submit_button("Save Settings", type="primary")

    if save_btn:
        keywords_list = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        _target_val = st.session_state.get("target_raw", "")
        _excluded_val = st.session_state.get("excluded_raw", "N/A")
        target_list = [c.strip() for c in _target_val.split(",") if c.strip()]
        excluded_list = (
            []
            if _excluded_val.strip().lower() in ("", "n/a")
            else [c.strip() for c in _excluded_val.split(",") if c.strip()]
        )
        settings_dict = {
            "keywords": keywords_list,
            "location": location,
            "resume_text": resume_text,
            "name": full_name,
            "phone": phone,
            "work_authorization": work_authorization,
            "years_of_experience": years_of_experience,
            "email": notify_email,
            "notify_threshold": threshold,
            "notify_frequency": frequency,
            "target_companies": target_list,
            "excluded_companies": excluded_list,
        }
        ok = supabase_client.save_user_settings(settings_dict)
        if ok:
            st.success("Settings saved.")
        else:
            st.error("Failed to save settings. Check your Supabase configuration.")

    st.divider()
    st.subheader("Test Email")

    test_recipient = st.text_input(
        "Send test email to",
        value=current.get("email", ""),
        key="test_email_addr",
    )

    if st.button("Send Test Email"):
        smtp_email = os.getenv("SMTP_EMAIL", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")

        if not smtp_email or not smtp_password:
            st.error("SMTP credentials not configured in .env file.")
        elif not test_recipient:
            st.warning("Enter a recipient email address.")
        else:
            from src.utils.email_notifier import EmailNotifier

            notifier = EmailNotifier(
                sender_email=smtp_email,
                sender_password=smtp_password,
            )
            sample_job = {
                "title": "Test Job",
                "company": "Test Company",
                "location": "Remote",
                "url": "https://example.com",
                "fit_score": 85,
                "analysis": {
                    "recommendation": "apply",
                    "summary": "This is a test notification from Interview Agent.",
                    "matching_skills": ["Python", "Streamlit"],
                    "missing_skills": [],
                    "key_requirements": ["3+ years experience"],
                },
            }
            try:
                notifier.send_instant_alert(test_recipient, sample_job)
                st.success(f"Test email sent to {test_recipient}.")
            except Exception as e:
                st.error(f"Failed to send email: {e}")
