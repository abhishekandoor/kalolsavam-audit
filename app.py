import streamlit as st
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

# --- 1. PAGE & STYLE CONFIG ---
st.set_page_config(page_title="Kalolsavam Audit | Command Center", page_icon="⚖️", layout="wide")

IST = pytz.timezone('Asia/Kolkata')

st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    /* Metric Cards */
    [data-testid="stMetric"] {
        background: white;
        padding: 15px 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f6;
    }
    /* Expander Styling */
    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: white !important;
    }
    /* Remove unnecessary padding */
    .block-container { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA FUNCTIONS ---
def get_now_ist():
    return datetime.now(IST).replace(tzinfo=None)

@st.cache_data(ttl=10)
def fetch_live_data():
    URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
    try:
        response = requests.get(URL_STAGE, timeout=10)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", response.text, re.DOTALL)
        return json.loads(match.group(1)) if match else []
    except:
        return []

# --- 3. AUDIT ENGINE ---
current_now = get_now_ist()
live_stages = fetch_live_data()

if not live_stages:
    st.error("🚨 Connection Error: Unable to reach the KITE portal.")
else:
    suspicious_list = []
    inventory_data = []
    time_tracker = []
    
    summary = {"live": 0, "total_p": 0, "done_p": 0}

    for stage in live_stages:
        errors = []
        name = str(stage.get("name", "Unknown"))
        loc = str(stage.get("location", "Unknown"))
        raw_is_live = stage.get("isLive")
        is_live = str(raw_is_live).lower() == "true" or raw_is_live is True
        total, done = int(stage.get("participants", 0)), int(stage.get("completed", 0))
        rem = total - done
        is_finished = str(stage.get("is_tabulation_finish", "N")).upper() == "Y"
        tent_time_str = stage.get("tent_time", "")
        item_name = stage.get("item_name", "N/A")

        # Accumulate Summary Stats
        if is_live: summary["live"] += 1
        summary["total_p"] += total
        summary["done_p"] += done

        # 1. Logic Audit (The Stage 16 Checks)
        if rem > 0:
            if not is_live:
                errors.append(f"⏸️ LOGIC: Stage INACTIVE but {rem} participants are pending.")
            if is_finished:
                errors.append(f"📉 LOGIC: Marked 'Finished' but {rem} waiting.")

        # 2. Time Audit (The Stage 2 Checks)
        late_mins = 0
        if tent_time_str:
            try:
                tent_time = datetime.strptime(tent_time_str, "%Y-%m-%d %H:%M:%S")
                time_tracker.append({"name": name, "item": item_name, "time": tent_time})
                
                if rem > 0 and current_now > tent_time:
                    late_mins = int((current_now - tent_time).total_seconds() / 60)
                    if late_mins > 10: # Grace period
                        errors.append(f"⏰ CRITICAL: Stage is {late_mins} mins behind schedule.")
            except: pass

        if errors:
            suspicious_list.append({"name": name, "loc": loc, "errors": errors, "rem": rem})

        inventory_data.append({
            "Stage": name,
            "Item": item_name,
            "Status": "🟢 LIVE" if is_live else "⚪ OFF",
            "Rem": rem,
            "Est. Finish": tent_time_str.split(" ")[1] if " " in tent_time_str else "N/A",
            "Lag (m)": late_mins if late_mins > 0 else "-"
        })

    # --- 4. TOP SUMMARY DASHBOARD ---
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.title("🏛️ Kalolsavam 2026 Master Audit")
    with col_t2:
        st.info(f"🕒 **Last Sync:** {current_now.strftime('%I:%M:%S %p')}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Live Venues", f"{summary['live']} / {len(live_stages)}")
    m2.metric("Total Participants", summary['total_p'])
    prog_val = int((summary['done_p']/summary['total_p'])*100) if summary['total_p'] > 0 else 0
    m3.metric("Global Progress", f"{prog_val}%")
    m4.metric("Pending Total", summary['total_p'] - summary['done_p'])

    # --- 5. NEW: LAST EXPECTED STAGE (Projected Completion) ---
    if time_tracker:
        last_item = sorted(time_tracker, key=lambda x: x['time'], reverse=True)[0]
        # Check if it spills into tomorrow
        day_str = "Today" if last_item['time'].date() == current_now.date() else "Tomorrow"
        
        st.error(f"🏁 **Projected Closing Item:** {last_item['name']} is expected to be the final venue, finishing with **{last_item['item']}** at **{last_item['time'].strftime('%I:%M %p')}** ({day_str})")

    st.divider()

    # --- 6. CRITICAL ALERTS & STAGE DETAILS ---
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader(f"🚩 Critical Discrepancies ({len(suspicious_list)})")
        if not suspicious_list:
            st.success("✅ Clean Audit: All venues logically consistent.")
        else:
            for item in suspicious_list:
                with st.expander(f"🔴 {item['name']} — {item['rem']} Pending", expanded=True):
                    for e in item['errors']:
                        st.markdown(f"**{e}**")

    with col_right:
        st.subheader("📊 Real-Time Inventory")
        df = pd.DataFrame(inventory_data)
        
        # Calculate height to remove inner scroll: (num_rows * row_height) + header_height
        table_height = (len(df) * 35) + 40 
        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=table_height,
            column_config={
                "Lag (m)": st.column_config.TextColumn("Delay", help="Minutes behind tentative finish time"),
                "Status": st.column_config.TextColumn("State"),
                "Est. Finish": st.column_config.TextColumn("Scheduled")
            }
        )

    st.caption("Protocol: Verification against dynamic KITE server variables. All times are handled in IST.")
