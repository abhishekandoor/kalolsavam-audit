import streamlit as st
import json
import re
import requests
import difflib
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD_MINS = 10
SIMILARITY_THRESHOLD = 0.65

# Pre-schedule reference (same as your original data)
PRE_SCHEDULE = [
    {"venue": "Stage 1", "item": "Bharathanatyam (Boys), Thiruvathira (Girls)", "time": "09 30, 14 00"},
    {"venue": "Stage 2", "item": "Nadodi Nrutham (Girls), Oppana (Girls)", "time": "09 30, 14 00"},
    # ... (Rest of your pre_schedule list)
    {"venue": "Stage 25", "item": "Bandmelam", "time": "09 30"}
]

# --- APP SETUP ---
st.set_page_config(page_title="Kalolsavam Audit Dashboard", layout="wide")

# --- DATA FETCHING ---
@st.cache_data(ttl=60)  # Refresh data every 60 seconds
def fetch_live_data():
    try:
        response = requests.get(URL_STAGE, timeout=15)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", response.text, re.DOTALL)
        return json.loads(match.group(1)) if match else []
    except Exception as e:
        st.error(f"Failed to fetch live data: {e}")
        return []

@st.cache_data(ttl=120)
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

# --- LOGIC HELPERS ---
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

# --- MAIN UI ---
def main():
    st.title("🎭 Kalolsavam 2025 Audit Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    live_stages = fetch_live_data()
    published_codes = fetch_published_item_codes()

    if not live_stages:
        st.warning("No stage data available.")
        return

    # --- PROCESSING ---
    current_now = datetime.now()
    suspicious_list = []
    summary = {"total": len(live_stages), "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}
    
    for stage in live_stages:
        errors = []
        is_live = stage.get("isLive", False)
        item_code = str(stage.get("item_code", ""))
        total, done = stage.get("participants", 0), stage.get("completed", 0)
        rem = total - done
        is_finished = stage.get("is_tabulation_finish", "N") == "Y"
        item_now = stage.get("item_name", "NA")
        
        if is_live: summary["live"] += 1
        else: summary["inactive"] += 1
        if is_finished: summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done
        
        try: tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
        except: tent_time = current_now
            
        sched_item, is_in_slot = get_scheduled_item(stage["name"], current_now)

        # Logical Audits
        if is_live and item_code in published_codes:
            errors.append(f"PUBLISH CONFLICT: Item [{item_code}] is LIVE but already PUBLISHED.")
        if done > total: 
            errors.append(f"DATA ERROR: Completed ({done}) > Total ({total}).")
        if rem <= 0 and is_live: 
            errors.append("LOGIC: Stage is LIVE but has 0 pending participants.")
        if is_live and tent_time < current_now:
            late_mins = int((current_now - tent_time).total_seconds() / 60)
            if late_mins > GRACE_PERIOD_MINS:
                errors.append(f"TIME CRITICAL: Running {late_mins} mins behind.")
        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_now) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_now.lower():
                errors.append(f"MISMATCH: Expected '{sched_item}', Live shows '{item_now}'.")

        if errors:
            suspicious_list.append({
                "Stage": stage["name"],
                "Location": stage["location"],
                "Item": item_now,
                "Pending": rem,
                "Errors": errors
            })

    # --- TOP METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Stages", summary["total"])
    m2.metric("Active Stages", summary["live"], f"{summary['inactive']} inactive", delta_color="normal")
    m3.metric("Tabulation Finished", summary["fin"])
    prog_perc = int((summary['t_c']/summary['t_p'])*100) if summary['t_p']>0 else 0
    m4.metric("Global Progress", f"{prog_perc}%", f"{summary['t_c']}/{summary['t_p']} Items")

    st.divider()

    # --- ALERTS SECTION ---
    st.subheader("⚠️ Suspicious Stages & Logical Conflicts")
    if suspicious_list:
        for item in suspicious_list:
            with st.expander(f"🔴 {item['Stage']} - {item['Location']} ({len(item['Errors'])} issues)"):
                col_a, col_b = st.columns([1, 2])
                col_a.write(f"**Current Item:** {item['Item']}")
                col_a.write(f"**Pending:** {item['Pending']}")
                for e in item["Errors"]:
                    col_b.error(e)
    else:
        st.success("All systems operational. No logical conflicts detected.")

    # --- FULL DATA TABLE ---
    st.divider()
    st.subheader("📋 Detailed Stage Status")
    df = pd.DataFrame(live_stages)
    if not df.empty:
        # Clean up dataframe for display
        display_df = df[['name', 'location', 'item_name', 'participants', 'completed', 'isLive', 'tent_time']]
        st.dataframe(display_df, use_container_width=True)

    if st.button("Manual Refresh"):
        st.rerun()

if __name__ == "__main__":
    main()
