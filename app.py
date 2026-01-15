import streamlit as st
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# --- 1. PAGE SETTINGS ---
st.set_page_config(
    page_title="Kalolsavam Stage Analysis", 
    page_icon="🎭", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

IST = pytz.timezone('Asia/Kolkata')

# --- 2. FORCED BLACK HEADING CSS ---
st.markdown("""
    <style>
    /* Main Background */
    .stApp { background-color: #f8fafc; }

    /* FORCE ALL HEADINGS TO BLACK */
    h1, h2, h3, h4, h5, h6, .main-title {
        color: #000000 !important;
        font-weight: 800 !important;
    }
    
    /* Target Streamlit's internal header classes */
    .st-emotion-cache-10trblm, .st-emotion-cache-12w0qpk {
        color: #000000 !important;
    }

    /* SUMMARY BOX VISIBILITY */
    [data-testid="stMetric"] {
        background: #ffffff !important;
        padding: 15px 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
    }
    [data-testid="stMetricLabel"] > div, 
    [data-testid="stMetricValue"] > div {
        color: #000000 !important; /* Force black numbers/labels */
    }

    /* EXPANDER (ACCORDION) STYLING */
    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: #ffffff !important;
        margin-bottom: 10px;
    }

    /* Expander Header: Dark background with White Text for contrast */
    div[data-testid="stExpander"] summary {
        background-color: #000000 !important; 
        border-radius: 12px 12px 0 0 !important;
        padding: 5px !important;
    }

    div[data-testid="stExpander"] summary p {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Expander Arrow Color */
    div[data-testid="stExpander"] summary svg {
        fill: #ffffff !important;
    }
    
    /* Expander Inner Body Text */
    div[data-testid="stExpander"] .stMarkdown, 
    div[data-testid="stExpander"] p, 
    div[data-testid="stExpander"] li {
        color: #000000 !important;
    }

    /* Search Bar and Tables */
    .stTextInput input {
        color: #000000 !important;
        background-color: #ffffff !important;
    }

    .block-container { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA FETCHING ---
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

# --- 4. AUDIT ENGINE ---
current_now = get_now_ist()
live_stages = fetch_live_data()

if not live_stages:
    st.error("🚨 Connection Error: Unable to reach KITE servers.")
else:
    suspicious_list = []
    inventory_list = []
    time_tracker = []
    
    summary = {"live": 0, "total_p": 0, "done_p": 0}

    for stage in live_stages:
        errors = []
        name = str(stage.get("name", "Unknown Stage"))
        loc = str(stage.get("location", "Unknown Venue"))
        
        raw_is_live = stage.get("isLive")
        is_live = str(raw_is_live).lower() == "true" or raw_is_live is True
        
        total = int(stage.get("participants", 0))
        done = int(stage.get("completed", 0))
        rem = total - done
        is_finished = str(stage.get("is_tabulation_finish", "N")).upper() == "Y"
        tent_time_str = stage.get("tent_time", "")
        item_name = stage.get("item_name", "N/A")

        if is_live: summary["live"] += 1
        summary["total_p"] += total
        summary["done_p"] += done

        # Core Audits
        if rem > 0:
            if not is_live:
                errors.append(f"⏸️ Status Paused: Stage is Inactive but {rem} pending.")
            if is_finished:
                errors.append(f"📉 Flow Error: Finished Flag ON but {rem} waiting.")

        delay_status = "On Time"
        formatted_date_time = "Not Scheduled"
        
        if tent_time_str:
            try:
                tent_time = datetime.strptime(tent_time_str, "%Y-%m-%d %H:%M:%S")
                time_tracker.append({"name": name, "item": item_name, "time": tent_time})
                formatted_date_time = tent_time.strftime("%d %b, %I:%M %p")
                
                if rem > 0 and current_now > tent_time:
                    late_mins = int((current_now - tent_time).total_seconds() / 60)
                    if late_mins > 0:
                        delay_status = f"🚨 {late_mins} Minutes Late"
                    if late_mins > 10: 
                        errors.append(f"⏰ Overdue Alert: Running {late_mins} minutes behind.")
            except: pass

        if errors:
            suspicious_list.append({
                "name": name, "loc": loc, "item": item_name,
                "errors": errors, "rem": rem
            })

        inventory_list.append({
            "Stage Name": name,
            "Venue Location": loc,
            "Competition": item_name,
            "Status": "🔴 Live Now" if is_live else ("✅ Finished" if is_finished else "⚪ Inactive"),
            "Waiting": rem,
            "Total": total,
            "Scheduled Finish": formatted_date_time,
            "Timing": delay_status
        })

    # --- 5. UI DISPLAY ---
    st.markdown('<h1 class="main-title">Kerala State School Kalolsavam Stage Analysis</h1>', unsafe_allow_html=True)
    st.info(f"🕒 **System Sync:** {current_now.strftime('%d %b, %I:%M:%S %p')} IST")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Venues", f"{summary['live']} / {len(live_stages)}")
    m2.metric("Total Participants", summary['total_p'])
    prog_val = int((summary['done_p']/summary['total_p'])*100) if summary['total_p'] > 0 else 0
    m3.metric("Global Progress", f"{prog_val}%")
    m4.metric("Total Pending", summary['total_p'] - summary['done_p'])

    if time_tracker:
        last_item = sorted(time_tracker, key=lambda x: x['time'], reverse=True)[0]
        st.error(f"🏁 **Closing Analysis:** {last_item['name']} ({last_item['item']}) finishes at **{last_item['time'].strftime('%d %b, %I:%M %p')}**.")

    st.divider()

    # ALERTS SECTION
    st.subheader(f"🚩 High-Priority Discrepancies ({len(suspicious_list)})")
    
    if not suspicious_list:
        st.success("✅ Clean Audit: All stage logic synchronized.")
    else:
        for item in suspicious_list:
            with st.expander(f"🔴 {item['name']} : {item['item']} ({item['rem']} Waiting)", expanded=True):
                for e in item['errors']:
                    st.write(f"• {e}")
                st.caption(f"Location: {item['loc']}")

    st.divider()
    st.subheader("📊 Detailed Stage Inventory")
    search_query = st.text_input("🔍 Search Stage or Item:")
    
    inventory_df = pd.DataFrame(inventory_list)
    if search_query:
        inventory_df = inventory_df[
            inventory_df['Stage Name'].str.contains(search_query, case=False) | 
            inventory_df['Competition'].str.contains(search_query, case=False)
        ]

    st.dataframe(inventory_df, use_container_width=True, hide_index=True)
