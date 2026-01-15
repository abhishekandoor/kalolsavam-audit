import streamlit as st
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
GRACE_PERIOD_MINS = 10

st.set_page_config(page_title="Kalolsavam Audit", layout="wide")

@st.cache_data(ttl=15) # Refresh every 15 seconds to catch time drifts
def fetch_live_data():
    try:
        response = requests.get(URL_STAGE, timeout=10)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", response.text, re.DOTALL)
        return json.loads(match.group(1)) if match else []
    except:
        return []

st.title("🎭 Kalolsavam 2025 Audit Dashboard")

live_stages = fetch_live_data()
current_now = datetime.now()

if not live_stages:
    st.error("Could not fetch data.")
else:
    suspicious_list = []
    
    for stage in live_stages:
        errors = []
        
        # 1. DATA EXTRACTION & CLEANING
        # Force conversion to handle cases where API returns strings like "2" instead of 2
        name = stage.get("name", "Unknown")
        loc = stage.get("location", "Unknown")
        is_live = str(stage.get("isLive", "")).lower() == "true" or stage.get("isLive") is True
        total = int(stage.get("participants", 0))
        done = int(stage.get("completed", 0))
        rem = total - done
        is_finished = stage.get("is_tabulation_finish", "N") == "Y"
        tent_time_str = stage.get("tent_time", "")

        # 2. LOGIC AUDIT (Matches your Terminal Output)
        if rem > 0:
            if not is_live:
                errors.append(f"LOGIC: Stage INACTIVE but {rem} pending.")
            if is_finished:
                errors.append(f"LOGIC: Finished Flag ON but {rem} waiting.")

        # 3. TIME AUDIT (The likely culprit for Stage 2)
        if tent_time_str:
            try:
                # We check time regardless of is_live status to catch Stage 2
                tent_time = datetime.strptime(tent_time_str, "%Y-%m-%d %H:%M:%S")
                if tent_time < current_now and rem > 0:
                    late_delta = current_now - tent_time
                    late_mins = int(late_delta.total_seconds() / 60)
                    
                    if late_mins > GRACE_PERIOD_MINS:
                        errors.append(f"TIME CRITICAL: Stage is {late_mins} minutes behind tent_time ({tent_time.strftime('%H:%M')}).")
            except Exception as e:
                pass 

        if errors:
            suspicious_list.append({
                "name": name,
                "loc": loc,
                "errors": errors,
                "rem": rem
            })

    # --- DISPLAY ---
    st.subheader(f"⚠️ Found {len(suspicious_list)} Suspicious Stages")
    
    if suspicious_list:
        for item in suspicious_list:
            # Using a warning box for better visibility
            with st.container():
                st.markdown(f"### 🔴 {item['name']} ({item['loc']})")
                st.write(f"**Pending Participants:** {item['rem']}")
                for e in item['errors']:
                    st.error(e)
                st.divider()
    else:
        st.success("✅ SYSTEM STATUS: No logical errors found.")

    # Optional: Quick view of all stages to debug
    with st.expander("View Raw Stage Data"):
        st.write(live_stages)
