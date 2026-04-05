from dotenv import load_dotenv  # type: ignore

load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="Interview Agent",
    page_icon="💼",
    layout="wide",
)

with st.sidebar:
    st.title("Interview Agent")

    from src.database.supabase_client import is_mock_mode
    if is_mock_mode():
        st.caption("⚠️ Mock mode — no database connected")

    page = st.radio(
        "Navigation",
        ["Dashboard", "Jobs", "Applications", "Resume", "Cover Letters", "Market Intel", "Upwork Proposal", "Upwork Video", "Settings"],
        label_visibility="collapsed",
    )

if page == "Dashboard":
    from src.pages.dashboard import show_dashboard
    show_dashboard()
elif page == "Jobs":
    from src.pages.jobs import show_jobs
    show_jobs()
elif page == "Applications":
    from src.pages.applications import show_applications
    show_applications()
elif page == "Resume":
    from src.pages.resume import show_resume
    show_resume()
elif page == "Cover Letters":
    from src.pages.cover_letters import show_cover_letters
    show_cover_letters()
elif page == "Market Intel":
    from src.pages.market import show_market
    show_market()
elif page == "Upwork Proposal":
    from src.pages.upwork_proposal import show_upwork_proposal
    show_upwork_proposal()
elif page == "Upwork Video":
    from src.pages.upwork_video import show_upwork_video
    show_upwork_video()
elif page == "Settings":
    from src.pages.settings import show_settings
    show_settings()
