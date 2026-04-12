import streamlit as st
import requests
import time
import json
from pathlib import Path

@st.cache_data
def get_page_content():
    return {
        "title": "🧩 Product Analysis Expert - Idea Factory",
        "config": {"page_title": "ADK Expert System", "layout": "wide"}
    }

st.set_page_config(**get_page_content()["config"])
st.title(get_page_content()["title"])

# --- Sidebar Configuration ---
with st.sidebar:
    app_name = "ad_04_product_adk" 
    idea = st.text_area("Input your idea:", height=150)
    st.divider()
    start_btn = st.button("Start Analysis", type="primary")


if start_btn and idea:
    with st.spinner("🤖 Launching Agent Panel and retrieving real-time data..."):
        
        BASE_URL = "http://127.0.0.1:8000"
        user_id = "analyst_pro"
        session_id = f"s_{int(time.time())}"

        try:
            # 1. Create Session
            session_url = f"{BASE_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}"
            session_payload = {"state": {"input_query": idea}}
            requests.post(session_url, json=session_payload, timeout=10)
            
            # 2. Execute Run
            run_url = f"{BASE_URL}/run"
            run_payload = {
                "sessionId": session_id, "appName": app_name, "userId": user_id,
                "newMessage": {"role": "user", "parts": [{"text": idea}]}
            }
            response = requests.post(run_url, json=run_payload, timeout=300)
            response.raise_for_status()
            events = response.json()
            
            # --- Parse Final State and Search Logs ---
            final_state = {}
            found_search_logs = False
            
            if events and isinstance(events, list):
                for event in events:
                    # Extract state delta from the current event
                    state_delta = event.get("actions", {}).get("stateDelta", {})
                    
                    if state_delta:
                        # Logic 2: If Mermaid code exists, ensure it's not overwritten by subsequent nulls
                        if "mermaid_code" in state_delta and state_delta["mermaid_code"]:
                            final_state["mermaid_code"] = state_delta["mermaid_code"]

                        # Logic 3: Merge all state updates
                        final_state.update(state_delta)
                        if "mermaid_code" in state_delta:
                            final_state["mermaid_code"] = state_delta["mermaid_code"]

            
            # --- UI Rendering ---
            if final_state:
                st.success("✅ Analysis Complete!")
                
                # 1. MVP Checklist
                st.subheader("📋 MVP Feature Checklist")
                st.markdown(final_state.get("feature_list", "Feature list not generated."))
                
                # 2. Business Logic Diagram
                st.subheader("🎨 Business Logic Diagram")
                m_code = final_state.get("mermaid_code", "")
                if m_code:
                    cleaned_m_code = m_code.replace("```mermaid", "").replace("```", "").strip()
                    cleaned_m_code = cleaned_m_code.replace('\xa0', ' ')

                    if "graph " not in cleaned_m_code:
                        cleaned_m_code = "graph TD\n" + cleaned_m_code

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
                    st.warning("Business logic diagram not generated.")

                # 4. Raw Expert Reports
                with st.expander("🔍 View Raw Expert Reports"):
                    t1, t2, t3 = st.tabs(["User Analysis", "Technical Solution", "Market Analysis"])
                    with t1: st.markdown(final_state.get("user_analysis", "User analysis not generated."))
                    with t2: st.markdown(final_state.get("tech_analysis", "Technical analysis not generated."))
                    with t3: 
                        st.markdown(final_state.get("market_analysis", "Market analysis not generated."))
                        
                        # Show full content.json content
                        with st.expander("📚 View Complete Search History", expanded=True):
                            try:
                                json_path = Path(__file__).parent / "content.json"
                                if json_path.exists():
                                    with open(json_path, "r", encoding="utf-8") as f:
                                        history = json.load(f)
                                    
                                    # Show full JSON content
                                    st.write("### Raw Search History Data")
                                    st.json(history)
                                    
                                    # Formatted key info
                                    st.write("### Key Information")
                                    st.write(f"**Query:** {history.get('query', '')}")
                                    st.write(f"**Timestamp:** {history.get('timestamp', '')}")
                                    st.write("**Source Links:**")
                                    for idx, source in enumerate(history.get('sources', [])):
                                        st.markdown(f"{idx+1}. [{source.get('title', '')}]({source.get('url', '')})")
                                else:
                                    st.info("No historical search records found.")
                            except Exception as e:
                                st.error(f"Failed to read history: {str(e)}")
            else:
                st.warning("Analysis completed but no valid content was retrieved.")
                
        except Exception as e:
            st.error(f"❌ Call Failed: {str(e)}")