import streamlit as st
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

# --- 1. PAGE & STYLE CONFIG ---
st.set_page_config(page_title="Kalolsavam Audit | Control Room", page_icon="⚖️", layout="wide")

IST = pytz.timezone('Asia/Kolkata')

st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    /* Metric Cards */
    [data-testid="stMetric"] {
        background: white;
        padding: 15px 20px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f6;
    }
    /* Expander Styling */
    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: white !important;
    }
    /* Search Input Styling */
    .stTextInput > div > div > input {
        border-radius: 10px;
    }
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
    inventory_list = []
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

        # Logic Audit
        if rem > 0:
            if not is_live:
                errors.append(f"⏸️ LOGIC: Stage INACTIVE but {rem} participants are pending.")
            if is_finished:
                errors.append(f"📉 LOGIC: Marked 'Finished' but {rem} waiting.")

        # Time Audit
        late_mins = 0
        delay_text = "On Time"
        formatted_end_time = "N/A"
        
        if tent_time_str:
            try:
                # Format: 2025-01-15 20:15:00
                tent_time = datetime.strptime(tent_time_str, "%Y-%m-%d %H:%M:%S")
                time_tracker.append({"name": name, "item": item_name, "time": tent_time})
                
                # Format for table: Day Month, Time (e.g., 15 Jan, 08:15 PM)
                formatted_end_time = tent_time.strftime("%d %b, %I:%M %p")
                
                if rem > 0 and current_now > tent_time:
                    late_mins = int((current_now - tent_time).total_seconds() / 60)
                    if late_mins > 0:
                        delay_text = f"🚨 {late_mins} Minutes Late"
                    if late_mins > 10: 
                        errors.append(f"⏰ CRITICAL: Stage is {late_mins} mins behind schedule.")
            except: pass

        if errors:
            suspicious_list.append({
                "name": name, "loc": loc, "item": item_name,
                "errors": errors, "rem": rem
            })

        # --- PREPARE FRIENDLY INVENTORY DATA ---
        inventory_list.append({
            "Stage Name": name,
            "Venue Location": loc,
            "Active Competition": item_name,
            "Current Status": "🔴 Live Now" if is_live else ("✅ Finished" if is_finished else "⚪ Waiting"),
            "Participants Waiting": rem,
            "Total Participants": total,
            "Tentative End Time": formatted_end_time,
            "Delay Status": delay_text
        })

    # --- 4. TOP SUMMARY DASHBOARD ---
    st.title("🏛️ Master Audit Command Center")
    st.info(f"🕒 **Current System Time:** {current_now.strftime('%d %b, %I:%M:%S %p')} IST | **Data Source:** KITE Kerala Servers")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Stages Currently Live", f"{summary['live']} / {len(live_stages)}")
    m2.metric("Total Event Participants", summary['total_p'])
    prog_val = int((summary['done_p']/summary['total_p'])*100) if summary['total_p'] > 0 else 0
    m3.metric("Overall Festival Progress", f"{prog_val}%")
    m4.metric("Total Pending Performances", summary['total_p'] - summary['done_p'])

    if time_tracker:
        last_item = sorted(time_tracker, key=lambda x: x['time'], reverse=True)[0]
        # Use full date for the error banner
        end_display = last_item['time'].strftime("%d %b, %I:%M %p")
        st.error(f"🏁 **Projected Final Performance:** {last_item['name']} ({last_item['item']}) at **{end_display}**")

    st.divider()

    # --- 5. CRITICAL ALERTS & DETAILED INVENTORY ---
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.subheader(f"🚩 Critical Discrepancies ({len(suspicious_list)})")
        if not suspicious_list:
            st.success("✅ Clean Audit: All venues logically consistent.")
        else:
            for item in suspicious_list:
                with st.expander(f"🔴 {item['name']} : {item['item']} ({item['rem']} Waiting)", expanded=True):
                    for e in item['errors']:
                        st.markdown(f"**{e}**")
                    st.caption(f"Venue: {item['loc']}")

    with col_right:
        st.subheader("📊 Full Stage Inventory")
        
        # User-Friendly Search
        search_query = st.text_input("🔍 Search for a specific Stage or Art Form:", placeholder="e.g. Stage 5, Oppana, Drama...")
        
        # Filter Data based on search
        inventory_df = pd.DataFrame(inventory_list)
        if search_query:
            inventory_df = inventory_df[
                inventory_df['Stage Name'].str.contains(search_query, case=False) | 
                inventory_df['Active Competition'].str.contains(search_query, case=False) |
                inventory_df['Venue Location'].str.contains(search_query, case=False)
            ]

        # Calculate height dynamically to prevent inner scroll
        table_height = (len(inventory_df) * 35.5) + 45
        
        st.dataframe(
            inventory_df,
            use_container_width=True,
            hide_index=True,
            height=int(table_height),
            column_config={
                "Delay Status": st.column_config.TextColumn("Delay Info"),
                "Tentative End Time": st.column_config.TextColumn("Date & End Time"),
                "Current Status": st.column_config.TextColumn("State"),
                "Participants Waiting": st.column_config.NumberColumn("Waitlist")
            }
        )

    st.caption("Protocol: Verification against real-time server variables. IST-Sync Enabled.")
