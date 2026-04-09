import streamlit as st
import requests
import streamlit_mermaid as st_mermaid
import time
import logging

# Page Configuration
st.set_page_config(page_title="ADK Expert System", layout="wide")
st.title("🧩 Product Analysis Expert - API Mode")

with st.sidebar:
    app_name = "ad_02_product_adk"  # Must match the ADK folder name exactly
    idea = st.text_area("Enter your product idea:", height=150)
    selected_agents = st.multiselect(
        "Select experts for analysis:",
        options=["User Expert", "Tech Expert", "Market Expert"],
        default=["User Expert", "Tech Expert", "Market Expert"]
    )
    start_btn = st.button("Start Analysis", type="primary")

if start_btn and idea:
    with st.spinner("🤖 Injecting context and starting the expert panel..."):
        # Mapping UI names to Backend Agent IDs
        expert_mapping = {
            "User Expert": "UserExpert",
            "Tech Expert": "TechExpert", 
            "Market Expert": "MarketExpert"
        }
        # Reverse mapping for status display
        expert_display = {
            "UserExpert": "User Expert",
            "TechExpert": "Tech Expert",
            "MarketExpert": "Market Expert"
        }
        # Status messages per agent
        expert_status = {
            "UserExpert": "Analyzing user pain points...",
            "TechExpert": "Evaluating technical solutions...",
            "MarketExpert": "Researching market prospects..."
        }
        
        # Convert selected Chinese expert names to backend IDs
        backend_agents = [expert_mapping[name] for name in selected_agents]
        
        # Display individual expert progress status
        for agent in backend_agents:
            with st.status(f"{expert_display[agent]}: {expert_status[agent]}", expanded=False) as status:
                pass
        
        BASE_URL = "http://127.0.0.1:8000"
        user_id = "analyst_user"
        # Use timestamp to ensure a fresh session for every run
        session_id = f"s_{int(time.time())}"

        try:
            # 1. Create a New Session
            session_url = f"{BASE_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}"
            session_payload = {
                "state": {
                    "input_query": idea,
                    "selected_agents": backend_agents
                }
            }
            create_res = requests.post(session_url, json=session_payload, timeout=10)
            
            # 2. Execute the Run Request
            run_url = f"{BASE_URL}/run"
            run_payload = {
                "sessionId": session_id,
                "appName": app_name,
                "userId": user_id,
                "newMessage": {
                    "role": "user",
                    "parts": [{"text": idea}]
                }
            }
            response = requests.post(run_url, json=run_payload, timeout=180)
        
            # Handle Response Errors
            if response.status_code == 422:
                st.error(f"Parameter Validation Failed (422): {response.text}")
                st.stop()
            
            response.raise_for_status()
            
            # Retrieve Event Data
            events = response.json()
            
            # Log API response (internal logging)
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger(__name__)
            logger.info(f"Raw API Data: {events}")
            
            # Parse Final State: Merge 'stateDelta' from all events
            final_state = {}
            if events and isinstance(events, list):
                for event in events:
                    state_delta = event.get("actions", {}).get("stateDelta", {})
                    if state_delta:
                        # Ensure business logic code is correctly merged
                        if "mermaid_code" in state_delta:
                            final_state["mermaid_code"] = state_delta["mermaid_code"]
                        final_state.update(state_delta)
            
            # Validate output existence
            if not final_state.get("feature_list"):
                st.warning("Feature list was not generated.")
            if not final_state.get("mermaid_code"):
                st.warning("Business flowchart was not generated.")
            
            # Rendering the results
            if final_state:
                st.success("✅ Analysis Complete!")
                
                # MVP Feature List (Top Section)
                st.subheader("📋 MVP Feature List")
                st.markdown(final_state.get("feature_list", "Feature list missing"))
                
                # 🎨 Business Logic Diagram Rendering
                st.subheader("🎨 Business Logic Flowchart")
                m_code = final_state.get("mermaid_code", "")
                
                if m_code:
                    # Clean the mermaid code block
                    cleaned_m_code = m_code.replace("```mermaid", "").replace("```", "").strip()
                    cleaned_m_code = cleaned_m_code.replace('\xa0', ' ')

                    # Ensure valid Mermaid header
                    if "graph " not in cleaned_m_code:
                        cleaned_m_code = "graph TD\n" + cleaned_m_code

                    # HTML/JS injection for high-fidelity Mermaid rendering
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
                        <script>
                            mermaid.initialize({{ 
                                startOnLoad: true,
                                securityLevel: 'loose',
                                theme: 'default',
                                flowchart: {{ useMaxWidth: true, htmlLabels: true, curve: 'basis' }}
                            }});
                        </script>
                        <style>
                            .mermaid {{ background-color: white; padding: 20px; border-radius: 10px; }}
                        </style>
                    </head>
                    <body>
                        <pre class="mermaid">
                        {cleaned_m_code}
                        </pre>
                    </body>
                    </html>
                    """
                    st.components.v1.html(html_content, height=800, scrolling=True)
                else:
                    st.warning("Business logic diagram missing.")
                
                # Expert Reports (Bottom Expander)
                with st.expander("🔍 View Raw Expert Reports"):
                    t1, t2, t3 = st.tabs(["User Report", "Tech Proposal", "Market Analysis"])
                    with t1:
                        st.markdown(final_state.get("user_analysis", "Analysis missing"))
                    with t2:
                        st.markdown(final_state.get("tech_analysis", "Analysis missing"))
                    with t3:
                        st.markdown(final_state.get("market_analysis", "Analysis missing"))
            else:
                st.warning("Backend succeeded, but stateDelta is empty. Check for Agent timeouts.")
                
        except Exception as e:
            st.error(f"❌ Call Failed: {str(e)}")