import streamlit as st
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
GRACE_PERIOD_MINS = 10
IST = pytz.timezone('Asia/Kolkata')

# --- UI CONFIG ---
st.set_page_config(page_title="Kalolsavam Audit | Control Room", page_icon="🎭", layout="wide")

# Custom Styling
st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    [data-testid="stExpander"] { border: 1px solid #e2e8f0; border-radius: 12px; background-color: white; }
    .status-live { color: #16a34a; font-weight: bold; }
    .status-off { color: #dc2626; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- CORE FUNCTIONS ---
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

# --- APP START ---
st.title("🏛️ Kalolsavam 2026 Audit Control Room")
current_now = get_now_ist()
live_stages = fetch_live_data()

if not live_stages:
    st.error("🚨 CRITICAL ERROR: Unable to fetch data from the KITE servers.")
else:
    suspicious_list = []
    inventory_data = []
    
    # Global Counters
    total_venues = len(live_stages)
    active_now = 0
    total_participants = 0
    total_completed = 0
    
    for stage in live_stages:
        errors = []
        
        # 1. Extraction
        name = str(stage.get("name", "Unknown"))
        loc = str(stage.get("location", "Unknown"))
        raw_is_live = stage.get("isLive")
        is_live = str(raw_is_live).lower() == "true" or raw_is_live is True
        total = int(stage.get("participants", 0))
        done = int(stage.get("completed", 0))
        rem = total - done
        is_finished = str(stage.get("is_tabulation_finish", "N")).upper() == "Y"
        tent_time_str = stage.get("tent_time", "")
        item_name = stage.get("item_name", "N/A")

        # Global Stats Update
        if is_live: active_now += 1
        total_participants += total
        total_completed += done

        # 2. Logic Audit
        if rem > 0:
            if not is_live:
                errors.append(f"⏸️ LOGIC: Stage INACTIVE but {rem} participants are pending.")
            if is_finished:
                errors.append(f"📉 LOGIC: Results marked 'Finished' but {rem} people are still waiting.")

        # 3. Time Audit
        late_mins = 0
        if tent_time_str and rem > 0:
            try:
                tent_time = datetime.strptime(tent_time_str, "%Y-%m-%d %H:%M:%S")
                if current_now > tent_time:
                    diff = current_now - tent_time
                    late_mins = int(diff.total_seconds() / 60)
                    if late_mins > GRACE_PERIOD_MINS:
                        errors.append(f"⏰ CRITICAL: System is {late_mins} mins behind schedule.")
            except: pass

        if errors:
            suspicious_list.append({"name": name, "loc": loc, "errors": errors, "rem": rem})

        # 4. Prepare Table Data
        inventory_data.append({
            "Stage": name,
            "Item": item_name,
            "Status": "🔴 LIVE" if is_live else "⚪ OFF",
            "Done": done,
            "Pending": rem,
            "Schedule": tent_time_str.split(" ")[1] if " " in tent_time_str else "N/A",
            "Lag (m)": late_mins
        })

    # --- UI COMPONENT 1: TOP SUMMARY DASHBOARD ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Venues", total_venues)
    with col2:
        st.metric("Live Now", f"📡 {active_now}")
    with col3:
        prog = int((total_completed/total_participants)*100) if total_participants > 0 else 0
        st.metric("Global Progress", f"{prog}%", delta=f"{total_completed} Done")
    with col4:
        st.metric("System Time (IST)", current_now.strftime('%H:%M:%S'))

    st.divider()

    # --- UI COMPONENT 2: CRITICAL ALERTS ---
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader(f"🚩 Active Issues ({len(suspicious_list)})")
        if not suspicious_list:
            st.success("✅ Clean Audit: All venues are logically consistent.")
        else:
            for item in suspicious_list:
                with st.expander(f"🔴 {item['name']} — {item['loc']}", expanded=True):
                    c_err, c_rem = st.columns([3, 1])
                    with c_err:
                        for e in item['errors']:
                            st.markdown(f"**{e}**")
                    with c_rem:
                        st.info(f"**Pending: {item['rem']}**")

    with col_right:
        st.subheader("⚡ Quick Actions")
        if st.button("🔄 Force Refresh All Data", use_container_width=True):
            st.rerun()
        st.warning("Manual Intervention Required for red flagged stages.")

    # --- UI COMPONENT 3: COMPLETE STAGE INVENTORY ---
    st.divider()
    st.subheader("📊 All Stages Real-Time Status")
    df = pd.DataFrame(inventory_data)
    
    # Custom color coding for the table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Lag (m)": st.column_config.ProgressColumn("Lag (min)", min_value=0, max_value=60, format="%d"),
            "Pending": st.column_config.NumberColumn("Waitlist"),
            "Status": st.column_config.TextColumn("Stage Status")
        }
    )

    st.caption("Data source: Official KITE Kerala Festival Management Portal")
