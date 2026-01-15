import streamlit as st
import json
import re
import requests
import difflib
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 1. PAGE SETTINGS ---
st.set_page_config(
    page_title="Kalolsavam Live Status", 
    page_icon="🎭", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. PUBLIC-FRIENDLY CSS ---
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Search Bar Styling */
    [data-testid="stTextInput"] input { border-radius: 20px; border: 1px solid #ddd; }
    
    /* Metric Cards */
    [data-testid="stMetric"] {
        background: #ffffff;
        padding: 10px;
        border-radius: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f6;
        text-align: center;
    }
    
    /* Headers */
    h1 { color: #2c3e50; font-size: 2.2rem !important; }
    h3 { color: #34495e; font-size: 1.2rem !important; margin-top: 20px; }
    
    /* Alert Boxes */
    .element-container .stAlert { border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD = 10 

# --- 4. DATA ENGINE (Cached) ---
@st.cache_data(ttl=60)
def fetch_data():
    try:
        # Fetch Stage Data
        s_res = requests.get(URL_STAGE, timeout=10)
        stages = json.loads(re.search(r"const stages = (\[.*?\]);", s_res.text, re.S).group(1))
        
        # Fetch Published Results
        r_res = requests.get(URL_RESULTS, timeout=10)
        soup = BeautifulSoup(r_res.text, 'html.parser')
        published = {re.match(r"(\d+)", r.find_all('td')[1].text.strip()).group(1): r.find_all('td')[3].text.strip() 
                     for r in soup.find_all('tr') if len(r.find_all('td')) > 1}
        return stages, published
    except: return [], {}

# --- 5. MAIN APP LOGIC ---
def main():
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🎭 Kalolsavam Live Status")
        st.caption(f"Last Updated: {datetime.now().strftime('%I:%M %p')}")
    with col2:
        if st.button("🔄 Refresh"): st.rerun()

    stages, published = fetch_data()
    if not stages:
        st.error("⚠️ Unable to connect to the festival server. Please try again later.")
        return

    now = datetime.now()
    
    # Initialize Counters
    summary = {"live": 0, "fin": 0, "total_p": 0, "done_p": 0}
    full_data = []
    alerts = []

    # --- PROCESS LOOP ---
    for s in stages:
        # Extract Data
        is_live = s.get("isLive")
        code = str(s.get("item_code", ""))
        item_name = s.get("item_name", "Unknown Item")
        total = s.get("participants", 0)
        done = s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish") == "Y"
        
        # Safe Time Parsing
        try:
            tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        except:
            tent = now

        # Logic Calculations
        late_mins = int((now - tent).total_seconds() / 60)
        status_text = "Live Now 🔴" if is_live else ("Finished ✅" if is_fin else "Waiting ⏸️")
        
        # Update Summary Stats
        if is_live: summary["live"] += 1
        if is_fin: summary["fin"] += 1
        summary["total_p"] += total
        summary["done_p"] += done

        # --- DETAILED ISSUE ANALYSIS ---
        issues = []
        
        # 1. Inactive but Pending Logic
        if rem > 0 and not is_live:
            if late_mins > 0:
                issues.append(f"🔴 **CRITICAL:** Stage is OFF but overdue by {late_mins} mins.")
            elif done > 0:
                issues.append(f"⏸️ **PAUSED:** {done} finished, stopped with {rem} pending.")
            else:
                issues.append("⏳ **WAITING:** Item has not started yet.")

        # 2. Published Results Conflict
        if is_live and code in published:
            issues.append(f"🚨 **DATA ERROR:** Results published at {published[code]}, but stage is LIVE.")

        # 3. Zombie Live Status
        if rem <= 0 and is_live:
            issues.append("🧟 **STUCK STATUS:** All participants finished, but stage shows Live.")

        # 4. Live Lags
        if is_live and late_mins > GRACE_PERIOD:
            issues.append(f"⏰ **LAGGING:** Running {late_mins} min behind schedule.")

        if issues:
            alerts.append({"stage": s['name'], "loc": s['location'], "issues": issues})

        # Add row to Master Data Table
        full_data.append({
            "Stage": s['name'],
            "Item": f"{item_name}",
            "Status": status_text,
            "Remaining": rem,
            "Expected End": tent.strftime("%I:%M %p"),
            "Delay (min)": max(0, late_mins) if is_live else 0,
            "Search_Key": f"{s['name']} {item_name} {code}".lower()
        })

    # --- CALCULATE METRICS (Done after loop to ensure variables exist) ---
    if summary["total_p"] > 0:
        progress = int((summary["done_p"] / summary["total_p"]) * 100)
    else:
        progress = 0

    # --- DISPLAY METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 Stages Live", summary["live"])
    m2.metric("✅ Items Done", summary["fin"])
    m3.metric("📊 Total Progress", f"{progress}%")
    m4.metric("👥 Participants Left", summary["total_p"] - summary["done_p"])

    st.divider()

    # --- DISPLAY ALERTS ---
    if alerts:
        with st.expander("⚠️ System Alerts & Delays (Click to View)", expanded=True):
            for alert in alerts:
                st.warning(f"**{alert['stage']}** ({alert['loc']})\n\n" + "\n".join(alert['issues']))

    # --- DISPLAY SEARCH & TABLE ---
    st.subheader("🔍 Find Your Stage")
    search_query = st.text_input("", placeholder="Search Stage (e.g., 'Stage 5') or Item...").lower()
    
    df = pd.DataFrame(full_data)
    
    if not df.empty:
        # Apply Search Filter
        if search_query:
            # Use 'na=False' to handle any empty data safely
            df = df[df["Search_Key"].str.contains(search_query, na=False)]

        # Render Table
        st.dataframe(
            df.drop(columns=["Search_Key"]),
            use_container_width=True,
            hide_index=True,
            # Intelligent Height: (Rows * 35px) + Header Buffer
            height=int(len(df) * 35.5) + 38,
            column_config={
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Delay (min)": st.column_config.ProgressColumn(
                    "Delay", 
                    format="%d min", 
                    min_value=0, 
                    max_value=60
                ),
            }
        )
        
        if len(df) == 0:
            st.info("No stages found matching your search.")
    else:
        st.info("No stage data available currently.")

if __name__ == "__main__":
    main()
