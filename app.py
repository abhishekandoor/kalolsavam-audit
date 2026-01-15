import streamlit as st
import json
import re
import requests
import difflib
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD_MINS = 10
SIMILARITY_THRESHOLD = 0.65

st.set_page_config(page_title="Kalolsavam Audit", layout="wide")

# --- DATA FETCHING ---
@st.cache_data(ttl=30) # Reduced TTL for higher accuracy
def fetch_live_data():
    try:
        response = requests.get(URL_STAGE, timeout=15)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", response.text, re.DOTALL)
        return json.loads(match.group(1)) if match else []
    except:
        return []

@st.cache_data(ttl=60)
def fetch_published_item_codes():
    published_codes = set()
    try:
        response = requests.get(URL_RESULTS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                match = re.match(r"(\d+)", cols[1].text.strip())
                if match: published_codes.add(match.group(1))
        return published_codes
    except:
        return set()

def get_similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

# --- MAIN UI ---
st.title("🎭 Kalolsavam 2025 Audit Dashboard")

live_stages = fetch_live_data()
published_codes = fetch_published_item_codes()
current_now = datetime.now()

if not live_stages:
    st.error("Could not fetch data from the server.")
else:
    suspicious_list = []
    
    # Global Summary Counters
    total_p, total_c, live_count, fin_count = 0, 0, 0, 0

    for stage in live_stages:
        errors = []
        # Ensure correct data types (Kite API often returns strings for numbers)
        is_live = stage.get("isLive", False)
        total = int(stage.get("participants", 0))
        done = int(stage.get("completed", 0))
        rem = total - done
        is_finished = stage.get("is_tabulation_finish", "N") == "Y"
        item_code = str(stage.get("item_code", ""))
        item_now = stage.get("item_name", "NA")
        
        # Summary Updates
        total_p += total
        total_c += done
        if is_live: live_count += 1
        if is_finished: fin_count += 1

        # --- AUDIT LOGIC (Matched to your terminal script) ---
        
        # 1. Result Conflict
        if is_live and item_code in published_codes:
            errors.append(f"PUBLISH CONFLICT: Item [{item_code}] is LIVE, but already PUBLISHED.")

        # 2. Status & Participant Consistency
        if done > total: 
            errors.append(f"DATA ERROR: Completed ({done}) > Total ({total}).")
        
        if rem <= 0 and is_live: 
            errors.append("LOGIC: Stage LIVE but 0 pending.")
            
        if rem > 0:
            if not is_live: 
                errors.append(f"LOGIC: Stage INACTIVE but {rem} pending.")
            if is_finished: 
                errors.append(f"LOGIC: Finished Flag ON but {rem} waiting.")

        # 3. Time Validation
        try:
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
            if is_live and tent_time < current_now:
                late_mins = int((current_now - tent_time).total_seconds() / 60)
                if late_mins > GRACE_PERIOD_MINS:
                    errors.append(f"TIME CRITICAL: Stage is {late_mins} minutes behind tent_time ({tent_time.strftime('%H:%M')}).")
                elif late_mins > 0:
                    errors.append(f"TIME WARNING: Stage starting to lag ({late_mins} mins behind).")
        except:
            pass

        if errors:
            suspicious_list.append({
                "name": stage["name"],
                "loc": stage["location"],
                "errors": errors,
                "rem": rem
            })

    # --- DISPLAY METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Live Stages", live_count)
    c2.metric("Finished Flag", fin_count)
    c3.metric("Pending Items", total_p - total_c)
    prog = int((total_c/total_p)*100) if total_p > 0 else 0
    c4.metric("Progress", f"{prog}%")

    # --- DISPLAY ERRORS ---
    st.subheader(f"⚠️ Found {len(suspicious_list)} Suspicious Stages")
    
    if suspicious_list:
        for item in suspicious_list:
            # Create a red box for each suspicious stage
            with st.container():
                st.markdown(f"### 🔴 {item['name']} ({item['loc']})")
                st.write(f"**Pending Participants:** {item['rem']}")
                for e in item['errors']:
                    st.error(f"└─ {e}")
                st.divider()
    else:
        st.success("✅ SYSTEM STATUS: No logical errors found.")
