import streamlit as st
import json, re, requests, difflib, pandas as pd
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
    /* Clean, modern font */
    html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
    
    /* Remove default padding for mobile feel */
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Search Bar Styling */
    [data-testid="stTextInput"] input { border-radius: 20px; border: 1px solid #ddd; }
    
    /* Metric Cards - Clean & Bright */
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
    
    /* Error/Warning boxes */
    .element-container .stAlert { border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD = 10 

# --- 4. DATA ENGINE (Fast & Cached) ---
@st.cache_data(ttl=60)
def fetch_data():
    try:
        s_res = requests.get(URL_STAGE, timeout=10)
        stages = json.loads(re.search(r"const stages = (\[.*?\]);", s_res.text, re.S).group(1))
        r_res = requests.get(URL_RESULTS, timeout=10)
        soup = BeautifulSoup(r_res.text, 'html.parser')
        published = {re.match(r"(\d+)", r.find_all('td')[1].text.strip()).group(1): r.find_all('td')[3].text.strip() 
                     for r in soup.find_all('tr') if len(r.find_all('td')) > 1}
        return stages, published
    except: return [], {}

# --- 5. MAIN APP ---
def main():
    # --- HEADER ---
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

    # --- PROCESS DATA ---
    now = datetime.now()
    summary = {"live": 0, "fin": 0, "total_p": 0, "done_p": 0}
    full_data = []
    alerts = []

    for s in stages:
        # Extract basic info
        is_live = s.get("isLive")
        code = str(s.get("item_code", ""))
        item_name = s.get("item_name", "Unknown Item")
        total = s.get("participants", 0)
        done = s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish") == "Y"
        tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        
        # Calculate Logic
        late_mins = int((now - tent).total_seconds() / 60)
        status_text = "Live Now 🔴" if is_live else ("Finished ✅" if is_fin else "Waiting ⏸️")
        
        # Summary
        if is_live: summary["live"] += 1
        if is_fin: summary["fin"] += 1
        summary["total_p"] += total
        summary["done_p"] += done

        # Check for Issues (Logic Engine)
        issues = []
        if is_live and code in published: issues.append("⚠️ Results published, but stage shows Live.")
        if rem <= 0 and is_live: issues.append("⚠️ Stage is Live, but no participants left.")
        if rem > 0 and not is_live: issues.append("⚠️ Stage paused, participants waiting.")
        if is_live and late_mins > GRACE_PERIOD: issues.append(f"⏰ Running {late_mins} min late.")

        if issues:
            alerts.append({"stage": s['name'], "loc": s['location'], "issues": issues})

        # Add to table
        full_data.append({
            "Stage": s['name'],
            "Item": f"{item_name}",
            "Status": status_text,
            "Remaining": rem,
            "Expected End": tent.strftime("%I:%M %p"),
            "Delay (min)": max(0, late_mins) if is_live else 0,
            "Search_Key": f"{s['name']} {item_name} {code}".lower() # Hidden column for searching
        })

    # --- TOP METRICS (Simple & Visual) ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 Stages Live", summary["live"])
    m2.metric("✅ Items Done", summary["fin"])
    progress = int((summary["done_p"]/summary["total_p"])*100) if summary["total_p"] > 0 else 0
    m3.metric("📊 Total Progress", f"{progress}%")
    m4.metric("👥 Participants Left", summary["total_p"] - summary["done_p"])

    st.divider()

    # --- ALERT SECTION (Only shows if problems exist) ---
    if alerts:
        with st.expander("⚠️ System Alerts (Click to View)", expanded=True):
            for alert in alerts:
                st.warning(f"**{alert['stage']} ({alert['loc']})**: " + " ".join(alert['issues']))

    # --- SEARCH & FILTER ---
    st.subheader("🔍 Find Your Stage")
    search_query = st.text_input("", placeholder="Search for Stage (e.g., 'Stage 5') or Item (e.g., 'Mohiniyattam')...").lower()

    # Filter Logic
    df = pd.DataFrame(full_data)
    if search_query:
        df = df[df["Search_Key"].str.contains(search_query)]

    # --- MAIN TABLE (User Friendly) ---
    # We remove the 'Search_Key' column before displaying
    display_df = df.drop(columns=["Search_Key"])

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=int(len(display_df) * 35.5) + 38,
        column_config={
            "Status": st.column_config.TextColumn("Current Status", width="small"),
            "Item": st.column_config.TextColumn("Running Item", width="large"),
            "Remaining": st.column_config.NumberColumn("Pending Ppl", help="Participants yet to perform"),
            "Delay (min)": st.column_config.ProgressColumn(
                "Delay", 
                format="%d min", 
                min_value=0, 
                max_value=60,
                help="How many minutes behind schedule"
            ),
        }
    )

    if len(df) == 0:
        st.info("No stages found matching your search.")

if __name__ == "__main__":
    main()
