import streamlit as st


def show_market():
    st.title("Market Intel")

    from src.database import supabase_client

    settings = supabase_client.get_user_settings()
    default_keywords = ", ".join(settings.get("keywords") or [])
    default_location = settings.get("location", "Remote")

    st.subheader("Market Analysis")

    col_kw, col_loc = st.columns(2)
    with col_kw:
        keywords_raw = st.text_input(
            "Keywords",
            value=default_keywords,
            placeholder="e.g. software engineer, python developer",
        )
    with col_loc:
        location = st.text_input("Location", value=default_location, placeholder="e.g. Remote")

    if st.button("Analyze Market", type="primary"):
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        if not keywords:
            st.warning("Enter at least one keyword.")
        else:
            with st.spinner("Researching market trends..."):
                from src.agents.job_discovery_agent import JobDiscoveryAgent
                agent = JobDiscoveryAgent()
                insight = agent.analyze_market(keywords, location)
            st.session_state["market_insight"] = insight

    if "market_insight" in st.session_state:
        insight = st.session_state["market_insight"]

        demand = insight.get("demand_level", "medium")
        demand_color = {"high": "green", "medium": "orange", "low": "red"}.get(demand, "gray")
        competition = insight.get("competition_level", "medium")

        col1, col2, col3 = st.columns(3)
        col1.metric("Demand Level", demand.title())
        col2.metric("Competition", competition.title())
        avg_salary = insight.get("avg_salary_range", "N/A")
        if isinstance(avg_salary, dict):
            # Flatten nested salary dict to a readable string
            def _extract_salary(d, depth=0):
                if depth > 2:
                    return None
                for v in d.values():
                    if isinstance(v, (int, float)):
                        return f"~${int(v):,}"
                    if isinstance(v, dict):
                        result = _extract_salary(v, depth + 1)
                        if result:
                            return result
                return None
            avg_salary = _extract_salary(avg_salary) or "See details below"
        elif not isinstance(avg_salary, str):
            avg_salary = str(avg_salary)
        col3.metric("Avg Salary", avg_salary)

        top_companies = insight.get("top_companies", [])
        if top_companies:
            st.markdown("**Top Hiring Companies:**")
            st.write(" · ".join(top_companies))

        trending_skills = insight.get("trending_skills", [])
        if trending_skills:
            st.markdown("**Trending Skills:**")
            tags_html = " ".join(
                f"<span style='background:#e3f2fd;color:#1565c0;padding:3px 10px;"
                f"border-radius:12px;margin:2px;display:inline-block'>{s}</span>"
                for s in trending_skills
            )
            st.markdown(tags_html, unsafe_allow_html=True)

        market_summary = insight.get("market_summary", "")
        if market_summary:
            with st.container(border=True):
                st.markdown("**Market Summary**")
                st.write(market_summary)

    st.divider()
    st.subheader("Recent Market Insights")

    insights_history = supabase_client.get_market_insights()
    if not insights_history:
        st.info("No market insights recorded yet.")
    else:
        for ins in insights_history:
            ins_id = ins.get("id", "")
            data = ins.get("insight_data", {})
            keywords_str = ", ".join(ins.get("keywords") or [])
            location_str = ins.get("location", "")
            demand = data.get("demand_level", "—")
            salary = data.get("avg_salary_range", "—")
            if isinstance(salary, dict):
                salary = "See detail"
            date_str = (ins.get("created_at") or "")[:10]

            col_info, col_del = st.columns([11, 1])
            with col_info:
                st.markdown(
                    f"**{keywords_str}** · {location_str} · "
                    f"Demand: `{demand}` · Salary: `{salary}` · {date_str}"
                )
            with col_del:
                if st.button("🗑", key=f"del_insight_{ins_id}", help="Delete"):
                    supabase_client.delete_market_insight(str(ins_id))
                    st.rerun()

    st.divider()
    st.subheader("Company Research")

    company_input = st.text_input(
        "Company Name", placeholder="e.g. Google, Stripe, OpenAI"
    )

    if st.button("Research Company", type="primary"):
        if not company_input.strip():
            st.warning("Enter a company name.")
        else:
            with st.spinner(f"Researching {company_input}..."):
                from src.agents.job_discovery_agent import JobDiscoveryAgent
                agent = JobDiscoveryAgent()
                research = agent.research_company(company_input.strip())
            st.session_state["company_research"] = research
            st.session_state["company_researched"] = company_input.strip()

    if "company_research" in st.session_state:
        research = st.session_state["company_research"]
        company_name = st.session_state.get("company_researched", "")

        st.markdown(f"### {company_name}")

        if research.get("overview"):
            with st.container(border=True):
                st.markdown("**Overview**")
                st.write(research["overview"])

        col_a, col_b = st.columns(2)
        with col_a:
            if research.get("culture"):
                st.markdown("**Culture**")
                st.write(research["culture"])

            if research.get("glassdoor_rating"):
                st.markdown(f"**Glassdoor Rating:** {research['glassdoor_rating']}")

        with col_b:
            tech_stack = research.get("tech_stack", [])
            if tech_stack:
                st.markdown("**Tech Stack**")
                tags_html = " ".join(
                    f"<span style='background:#f3e5f5;color:#6a1b9a;padding:3px 10px;"
                    f"border-radius:12px;margin:2px;display:inline-block'>{t}</span>"
                    for t in tech_stack
                )
                st.markdown(tags_html, unsafe_allow_html=True)

        recent_news = research.get("recent_news", [])
        if recent_news:
            st.markdown("**Recent News**")
            for news in recent_news:
                st.markdown(f"- {news}")

        if research.get("interview_tips"):
            with st.expander("Interview Tips"):
                st.write(research["interview_tips"])
