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

# --- 2. CSS STYLING ---
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    [data-testid="stMetric"] {
        background: #ffffff;
        padding: 10px;
        border-radius: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f6;
        text-align: center;
    }
    h1 { color: #2c3e50; font-size: 2.2rem !important; }
    .element-container .stAlert { border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD = 10 
SIMILARITY_THRESHOLD = 0.65

# Pre-schedule reference
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

# --- 4. UTILITIES ---
def get_similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_scheduled_item(stage_name, current_time):
    sched = next((s for s in PRE_SCHEDULE if s["venue"] == stage_name), None)
    if not sched: return None, False
    items = [i.strip() for i in sched["item"].split(",")]
    times = [t.strip() for t in sched["time"].split(",")]
    slots = []
    for i in range(len(times)):
        try:
            dt = datetime.strptime(f"{current_time.strftime('%Y-%m-%d')} {times[i].replace(' ', ':')}", "%Y-%m-%d %H:%M")
            slots.append({"item": items[i], "time": dt})
        except: continue
    slots.sort(key=lambda x: x["time"])
    res_item, in_slot = None, False
    for slot in slots:
        if current_time >= slot["time"]: res_item, in_slot = slot["item"], True
    return res_item, in_slot

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
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🎭 Kalolsavam Live Status")
        st.caption(f"Last Updated: {datetime.now().strftime('%I:%M %p')}")
    with col2:
        if st.button("🔄 Refresh"): st.rerun()

    stages, published = fetch_data()
    if not stages:
        st.error("⚠️ Unable to connect to the festival server.")
        return

    now = datetime.now()
    summary = {"live": 0, "fin": 0, "total_p": 0, "done_p": 0}
    full_data = []
    alerts = []

    for s in stages:
        is_live = s.get("isLive")
        code = str(s.get("item_code", ""))
        item_name = s.get("item_name", "Unknown Item")
        total = s.get("participants", 0)
        done = s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish") == "Y"
        
        try: tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        except: tent = now

        late_mins = int((now - tent).total_seconds() / 60)
        status_text = "Live Now 🔴" if is_live else ("Finished ✅" if is_fin else "Waiting ⏸️")
        
        if is_live: summary["live"] += 1
        if is_fin: summary["fin"] += 1
        summary["total_p"] += total
        summary["done_p"] += done

        # --- LOGIC ENGINE ---
        issues = []
        sched_item, is_in_slot = get_scheduled_item(s['name'], now)

        # 1. Result Conflict
        if is_live and code in published:
            issues.append(f"🚨 **PUBLISH CONFLICT:** Item [{code}] is LIVE, but already PUBLISHED.")

        # 2. Data Consistency
        if done > total: 
            issues.append(f"❌ **DATA ERROR:** Completed ({done}) > Total ({total}).")
        
        if rem <= 0 and is_live: 
            issues.append("🧟 **ZOMBIE LIVE:** Stage LIVE but 0 pending.")

        # 3. Inactive & Finished Logic (Mirrors Terminal Script)
        if rem > 0:
            if not is_live:
                issues.append(f"⏸️ **LOGIC:** Stage INACTIVE but {rem} participants pending.")
            if is_fin: 
                issues.append(f"📉 **LOGIC:** Finished Flag ON but {rem} participants waiting.")

        # 4. Time Validation (Mirrors Terminal Script)
        # We now check for ANY lateness > 0 mins, not just Grace Period
        if is_live and late_mins > 0:
            if late_mins > GRACE_PERIOD:
                issues.append(f"⏰ **TIME CRITICAL:** Stage is {late_mins} minutes behind tent_time.")
            else:
                issues.append(f"🟡 **TIME WARNING:** Stage starting to lag ({late_mins} mins behind).")

        # 5. Item Mismatch
        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_name) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_name.lower():
                issues.append(f"🔀 **MISMATCH:** Expected '{sched_item}', Live shows '{item_name}'.")

        if issues:
            alerts.append({"stage": s['name'], "loc": s['location'], "issues": issues})

        full_data.append({
            "Stage": s['name'],
            "Item": f"{item_name}",
            "Status": status_text,
            "Remaining": rem,
            "Expected End": tent.strftime("%I:%M %p"),
            "Delay (min)": max(0, late_mins) if is_live else 0,
            "Search_Key": f"{s['name']} {item_name} {code}".lower()
        })

    # --- METRICS ---
    if summary["total_p"] > 0:
        progress = int((summary["done_p"] / summary["total_p"]) * 100)
    else:
        progress = 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 Stages Live", summary["live"])
    m2.metric("✅ Items Done", summary["fin"])
    m3.metric("📊 Total Progress", f"{progress}%")
    m4.metric("👥 Participants Left", summary["total_p"] - summary["done_p"])

    st.divider()

    # --- ALERTS ---
    if alerts:
        with st.expander("⚠️ System Alerts & Delays (Click to View)", expanded=True):
            for alert in alerts:
                st.warning(f"**{alert['stage']}** ({alert['loc']})\n\n" + "\n".join(alert['issues']))

    # --- TABLE ---
    st.subheader("🔍 Find Your Stage")
    search_query = st.text_input("", placeholder="Search Stage (e.g., 'Stage 5') or Item...").lower()
    
    df = pd.DataFrame(full_data)
    if not df.empty:
        if search_query:
            df = df[df["Search_Key"].str.contains(search_query, na=False)]

        st.dataframe(
            df.drop(columns=["Search_Key"]),
            use_container_width=True,
            hide_index=True,
            height=int(len(df) * 35.5) + 38,
            column_config={
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Delay (min)": st.column_config.ProgressColumn("Delay", format="%d min", min_value=0, max_value=60),
            }
        )
    else:
        st.info("No stage data available.")

if __name__ == "__main__":
    main()
