import streamlit as st
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import pytz  # You may need to run: pip install pytz

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
GRACE_PERIOD_MINS = 10
IST = pytz.timezone('Asia/Kolkata')

st.set_page_config(page_title="Kalolsavam Audit", layout="wide")

# Force Streamlit to get the time in IST
def get_now_ist():
    return datetime.now(IST).replace(tzinfo=None)

@st.cache_data(ttl=10)
def fetch_live_data():
    try:
        response = requests.get(URL_STAGE, timeout=10)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", response.text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return []
    except:
        return []

st.title("🎭 Kalolsavam 2025 Audit Dashboard")

live_stages = fetch_live_data()
current_now = get_now_ist()

st.info(f"System Time (IST): {current_now.strftime('%H:%M:%S')} | Stages Checked: {len(live_stages)}")

if not live_stages:
    st.error("Could not fetch data.")
else:
    suspicious_list = []
    
    for stage in live_stages:
        errors = []
        
        # 1. DATA EXTRACTION
        name = str(stage.get("name", "Unknown"))
        loc = str(stage.get("location", "Unknown"))
        
        # kite.kerala.gov.in uses boolean or string "true"/"false"
        raw_is_live = stage.get("isLive")
        is_live = str(raw_is_live).lower() == "true" or raw_is_live is True
        
        total = int(stage.get("participants", 0))
        done = int(stage.get("completed", 0))
        rem = total - done
        is_finished = str(stage.get("is_tabulation_finish", "N")).upper() == "Y"
        tent_time_str = stage.get("tent_time", "")

        # 2. LOGIC AUDIT (Stage 16 detection)
        if rem > 0:
            if not is_live:
                errors.append(f"LOGIC: Stage INACTIVE but {rem} pending.")
            if is_finished:
                errors.append(f"LOGIC: Finished Flag ON but {rem} waiting.")

        # 3. TIME AUDIT (Stage 2 detection)
        if tent_time_str and rem > 0:
            try:
                # API format: 2025-01-xx 20:15:00
                tent_time = datetime.strptime(tent_time_str, "%Y-%m-%d %H:%M:%S")
                
                if current_now > tent_time:
                    diff = current_now - tent_time
                    late_mins = int(diff.total_seconds() / 60)
                    
                    if late_mins > GRACE_PERIOD_MINS:
                        errors.append(f"TIME CRITICAL: Stage is {late_mins} minutes behind tent_time ({tent_time.strftime('%H:%M')}).")
            except Exception as e:
                # If date format fails, we skip time check for this row
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
            with st.expander(f"🔴 {item['name']} - {item['loc']}", expanded=True):
                st.write(f"**Pending Participants:** {item['rem']}")
                for e in item['errors']:
                    st.error(f"**{e}**")
    else:
        st.success("✅ SYSTEM STATUS: No logical errors found.")

    # DEBUG SECTION
    with st.expander("Debug Stage 2 & 16 Raw Data"):
        target_stages = [s for s in live_stages if "Stage 2" in s['name'] or "Stage 16" in s['name']]
        st.write(target_stages)
