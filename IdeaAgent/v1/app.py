import streamlit as st
import requests
import time
import json
from pathlib import Path

# --- Page Configuration & Caching ---
@st.cache_data
def get_page_content():
    """Returns static page content and configuration."""
    return {
        "title": "🧩 Product Analysis Expert - API Mode",
        "config": {"page_title": "ADK Expert System", "layout": "wide"}
    }

# Set Streamlit page config using cached settings
st.set_page_config(**get_page_content()["config"])
st.title(get_page_content()["title"])

# --- Sidebar Configuration ---
with st.sidebar:
    app_name = "ad_03_product_adk"  # Identifier for the backend ADK application
    idea = st.text_area("Enter your product idea:", height=150)
    st.divider()
    start_btn = st.button("Start Analysis", type="primary")

# --- Main Logic Execution ---
if start_btn and idea:
    with st.spinner("🤖 Launching expert panel and retrieving real-time data..."):
        
        # API Configuration
        BASE_URL = "http://127.0.0.1:8000"
        user_id = "analyst_user"
        session_id = f"s_{int(time.time())}" # Unique session ID per run

        try:
            # 1. Create Session: Initialize state on the backend
            session_url = f"{BASE_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}"
            session_payload = {"state": {"input_query": idea}}
            requests.post(session_url, json=session_payload, timeout=10)
            
            # 2. Execute Run: Trigger the multi-agent orchestration
            run_url = f"{BASE_URL}/run"
            run_payload = {
                "sessionId": session_id, 
                "appName": app_name, 
                "userId": user_id,
                "newMessage": {"role": "user", "parts": [{"text": idea}]}
            }
            response = requests.post(run_url, json=run_payload, timeout=180)
            response.raise_for_status()
            events = response.json()
            
            # --- Parse Final State & Merge State Deltas ---
            final_state = {}
            
            if events and isinstance(events, list):
                for event in events:
                    # Extract state updates (deltas) from the event stream
                    state_delta = event.get("actions", {}).get("stateDelta", {})
                    
                    if state_delta:
                        # Key Logic: Ensure Mermaid code is captured and not overwritten by subsequent empty deltas
                        if "mermaid_code" in state_delta and state_delta["mermaid_code"]:
                            final_state["mermaid_code"] = state_delta["mermaid_code"]

                        # Merge all other state updates into the final state object
                        final_state.update(state_delta)
                        if "mermaid_code" in state_delta:
                            final_state["mermaid_code"] = state_delta["mermaid_code"]

            # --- UI Rendering ---
            if final_state:
                st.success("✅ Analysis Complete!")
                
                # 1. MVP Feature List Section
                st.subheader("📋 MVP Feature List")
                st.markdown(final_state.get("feature_list", "Feature list not generated."))
                
                # 2. Business Logic Diagram Section (Mermaid rendering)
                st.subheader("🎨 Business Logic Flowchart")
                m_code = final_state.get("mermaid_code", "")
                if m_code:
                    # Sanitize Mermaid code: remove markdown wrappers and non-breaking spaces
                    cleaned_m_code = m_code.replace("```mermaid", "").replace("```", "").strip()
                    cleaned_m_code = cleaned_m_code.replace('\xa0', ' ')

                    # Ensure valid Mermaid graph syntax
                    if "graph " not in cleaned_m_code:
                        cleaned_m_code = "graph TD\n" + cleaned_m_code

                    # Inject HTML/JS for high-fidelity Mermaid rendering
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
                    st.warning("Business logic flowchart not generated.")

                # 3. Raw Expert Reports (using Expanders and Tabs for UX)
                with st.expander("🔍 View Raw Expert Reports"):
                    t1, t2, t3 = st.tabs(["User Analysis", "Technical Proposal", "Market Analysis"])
                    with t1: st.markdown(final_state.get("user_analysis", "User analysis missing."))
                    with t2: st.markdown(final_state.get("tech_analysis", "Technical suggestions missing."))
                    with t3: 
                        st.markdown(final_state.get("market_analysis", "Market analysis missing."))
                        
                        # 4. Search Audit Trail: Display complete content.json history
                        with st.expander("📚 View Full Search History", expanded=True):
                            try:
                                json_path = Path(__file__).parent / "content.json"
                                if json_path.exists():
                                    with open(json_path, "r", encoding="utf-8") as f:
                                        history = json.load(f)
                                    
                                    # Display raw JSON data for auditing
                                    st.write("### Raw Search Data")
                                    st.json(history)
                                    
                                    # Display formatted key search information
                                    st.write("### Search Highlights")
                                    st.write(f"**Query:** {history.get('query', '')}")
                                    st.write(f"**Timestamp:** {history.get('timestamp', '')}")
                                    st.write("**Source Links:**")
                                    for idx, source in enumerate(history.get('sources', [])):
                                        st.markdown(f"{idx+1}. [{source.get('title', '')}]({source.get('url', '')})")
                                else:
                                    st.info("No historical search records found.")
                            except Exception as e:
                                st.error(f"Failed to load search history: {str(e)}")
            else:
                st.warning("Analysis completed, but no valid content was retrieved.")
                
        except Exception as e:
            st.error(f"❌ API Call Failed: {str(e)}")