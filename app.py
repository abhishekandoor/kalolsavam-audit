import streamlit as st
import json
import re
import requests
import difflib
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Kalolsavam Audit | Control Room",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL STYLING (CSS) ---
st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; }
        .stAlert { border-radius: 10px; }
        div[data-testid="stExpander"] { border: none !important; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 10px; margin-bottom: 10px; }
        .late-badge { color: #d32f2f; font-weight: bold; background: #ffebee; padding: 2px 8px; border-radius: 5px; }
        .stHeader { font-family: 'Inter', sans-serif; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD = 10 

# Hardcoded Pre-schedule for 2026 (Logic Anchor)
PRE_SCHEDULE = [
    {"venue": "Stage 1", "item": "Bharathanatyam (Boys), Thiruvathira (Girls)", "time": "09 30, 14 00"},
    {"venue": "Stage 2", "item": "Nadodi Nrutham (Girls), Oppana (Girls)", "time": "09 30, 14 00"},
    {"venue": "Stage 3", "item": "Mangalam Kali, Mangalam Kali", "time": "09 30, 13 30"},
    {"venue": "Stage 4", "item": "Mimicry, Mohiniyattam (Girls), Mimicry (Girls)", "time": "11 30, 14 00, 09 30"},
    {"venue": "Stage 5", "item": "Skit English, Vattappattu (Boys)", "time": "14 00, 09 30"},
    {"venue": "Stage 6", "item": "Dafmuttu (Boys), Lalithaganam (Boys), Lalithaganam (Girls)", "time": "14 00, 11 30, 09 30"},
    {"venue": "Stage 7", "item": "Kerala Nadanam (Girls), Poorakkali (Boys)", "time": "09 30, 14 00"},
    {"venue": "Stage 8", "item": "Ottanthullal, Ottanthullal (Girls)", "time": "09 30, 13 30"},
    {"venue": "Stage 9", "item": "Koodiyattam", "time": "09 30"},
    {"venue": "Stage 10", "item": "Kuchuppudi (Girls), Kathaprasangam", "time": "14 00, 09 30"},
    {"venue": "Stage 11", "item": "Nadakam", "time": "09 30"},
    {"venue": "Stage 12", "item": "Kathakali - Group, Kathakali", "time": "14 00, 09 30"},
    {"venue": "Stage 13", "item": "Prasangam - Sanskrit, Chambuprabhashanam, Prabhashanam", "time": "16 00, 09 30, 14 00"},
    {"venue": "Stage 14", "item": "Margamkali (Girls), Margamkali (Girls)", "time": "14 00, 09 30"},
    {"venue": "Stage 15", "item": "Chendamelam, Chenda / Thayambaka", "time": "09 30, 14 00"},
    {"venue": "Stage 16", "item": "Sangha Ganam, Kathaprasangam", "time": "14 00, 16 00"},
    {"venue": "Stage 18", "item": "Mridangam / Ganchira / Ghadam, Mridangam, Madhalam", "time": "15 00, 12 00, 09 30"},
    {"venue": "Stage 19", "item": "Prasangam - Hindi, Padyam Chollal - Hindi, Prasangam - Hindi", "time": "09 30, 16 00, 12 30"},
    {"venue": "Stage 20", "item": "Padyam Chollal - Malayalam, Prasangam - Malayalam, Padyam Chollal - Malayalam, Prasangam - Malayalam", "time": "16 00, 11 30, 14 00, 09 30"},
    {"venue": "Stage 25", "item": "Bandmelam", "time": "09 30"}
]

# --- 4. CACHED DATA FETCHING ---
@st.cache_data(ttl=60)
def get_festival_data():
    try:
        # Fetch Stages
        s_res = requests.get(URL_STAGE, timeout=10)
        stages = json.loads(re.search(r"const stages = (\[.*?\]);", s_res.text, re.S).group(1))
        
        # Fetch Published Results
        r_res = requests.get(URL_RESULTS, timeout=10)
        soup = BeautifulSoup(r_res.text, 'html.parser')
        published = {re.match(r"(\d+)", r.find_all('td')[1].text.strip()).group(1) 
                     for r in soup.find_all('tr') if len(r.find_all('td')) > 1}
        
        return stages, published
    except Exception as e:
        st.error(f"Data Connection Failed: {e}")
        return [], set()

# --- 5. LOGIC CORE ---
def audit_engine(stages, published):
    now = datetime.now()
    results = []
    summary = {"total": len(stages), "live": 0, "fin": 0, "t_p": 0, "t_c": 0}

    for s in stages:
        errs, warn = [], []
        is_live, code = s.get("isLive"), str(s.get("item_code", ""))
        total, done = s.get("participants", 0), s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish") == "Y"
        item_now = s.get("item_name", "NA")
        tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        
        # Summary metrics
        if is_live: summary["live"] += 1
        if is_fin: summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done

        # Logic Checks
        if is_live and code in published: errs.append("🚨 **PUBLISH CONFLICT:** Item published but stage still LIVE.")
        if rem <= 0 and is_live: errs.append("🧟 **ZOMBIE LIVE:** 0 participants left but stage is LIVE.")
        if rem > 0:
            if not is_live: errs.append(f"⏸️ **STALLED:** {rem} participants pending but stage is INACTIVE.")
            if is_fin: errs.append(f"📉 **TABULATION ERROR:** Marked Finished with {rem} waiting.")
        
        if is_live and tent < now:
            mins_late = int((now - tent).total_seconds() / 60)
            if mins_late > GRACE_PERIOD: errs.append(f"⏰ **OVERDUE:** Running {mins_late}m behind schedule.")
            elif mins_late > 0: warn.append(f"🟡 **LAGGING:** {mins_late}m late.")

        if errs or warn:
            results.append({"name": s['name'], "loc": s['location'], "errs": errs, "warn": warn, "rem": rem, "tent": tent})
    
    return results, summary

# --- 6. USER INTERFACE ---
st.title("⚖️ Kalolsavam Audit Dashboard")
st.markdown(f"**Last Sync:** {datetime.now().strftime('%H:%M:%S')} | **Refresh Cycle:** 60s")

stages, published = get_festival_data()

if stages:
    reports, metrics = audit_engine(stages, published)

    # Sidebar Filters
    with st.sidebar:
        st.header("⚙️ Filter View")
        show_all = st.checkbox("Show All Stages", value=False)
        severity = st.multiselect("Severity Level", ["Error", "Warning"], default=["Error"])
        st.divider()
        st.info("💡 **Tip:** Stages with pending participants that are inactive are flagged as 'Stalled'.")

    # Metrics Section
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Live Venues", f"📡 {metrics['live']}")
    c2.metric("Completed Items", f"✅ {metrics['fin']}")
    prog = int((metrics['t_c']/metrics['t_p'])*100) if metrics['t_p']>0 else 0
    c3.metric("Global Progress", f"📈 {prog}%", delta=f"{metrics['t_c']} done")
    c4.metric("Pending Total", f"👥 {metrics['t_p'] - metrics['t_c']}")

    # Critical Alerts
    st.divider()
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("🚩 Audit Discrepancies")
        if not reports:
            st.success("Clean Audit: All stages behaving logically.")
        else:
            for r in reports:
                has_error = any("🚨" in e or "**" in e for e in r['errs'])
                if has_error or "Warning" in severity:
                    color = "red" if r['errs'] else "orange"
                    with st.expander(f"{r['name']} — {r['loc']} ({r['rem']} Pending)"):
                        for e in r['errs']: st.error(e)
                        for w in r['warn']: st.warning(w)
                        st.caption(f"Estimated End: {r['tent'].strftime('%H:%M %p')}")

    with col_right:
        st.subheader("🕒 Timing Overview")
        df_time = pd.DataFrame([{"Stage": s['name'], "Ends": datetime.strptime(s['tent_time'], "%Y-%m-%d %H:%M:%S")} for s in stages])
        df_time = df_time.sort_values(by="Ends", ascending=False)
        st.dataframe(df_time, hide_index=True, use_container_width=True)
        st.write(f"**Closing Venue:** {df_time.iloc[0]['Stage']}")

else:
    st.warning("Server Offline: Unable to reach KITE ulsavam portal.")
