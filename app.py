import streamlit as st
import json
import re
import requests
import difflib
from bs4 import BeautifulSoup
from datetime import datetime

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD_MINS = 10
SIMILARITY_THRESHOLD = 0.65

# Pre-schedule reference
pre_schedule = [
    {"venue": "Stage 1", "item": "Kuchuppudi (Girls), Thiruvathirakali (Girls)", "time": "09 30, 14 00"},
    {"venue": "Stage 2", "item": "Vrundavadyam, Parichamuttu (Boys)", "time": "14 00, 09 30"},
    {"venue": "Stage 3", "item": "Malapulaya Aattam, Malapulaya Aattam", "time": "09 30, 14 00"},
    {"venue": "Stage 4", "item": "Chavittu Nadakam", "time": "09 30"},
    {"venue": "Stage 5", "item": "Bharathanatyam (Girls), Mookabhinayam", "time": "09 30, 14 00"},
    {"venue": "Stage 6", "item": "Nadanpattu, Nadanpattu", "time": "09 30, 14 00"},
    {"venue": "Stage 7", "item": "Poorakkali (Boys), Groupsong", "time": "09 30, 14 00"},
    {"venue": "Stage 8", "item": "Nangiar Koothu, Nangiar Koothu", "time": "09 30, 14 00"},
    {"venue": "Stage 9", "item": "Yakshaganam", "time": "09 30"},
    {"venue": "Stage 10", "item": "Keralanadanam, Nadodi Nrutham", "time": "09 30, 14 00"},
    {"venue": "Stage 11", "item": "Skit English, Kolkali (Boys)", "time": "09 30, 14 30"},
    {"venue": "Stage 12", "item": "Kathakali - Group, Kathakali (Girls)", "time": "14 00, 09 30"},
    {"venue": "Stage 13", "item": "Padyam Chollal - Hindi, Vandematharam, Sangha Ganam, Aksharaslokam", "time": "09 30, 14 00, 15 00, 17 30"},
    {"venue": "Stage 14", "item": "Mono Act (Boys), Vattappattu (Boys), Mono Act (Girls)", "time": "09 30, 14 00, 11 30"},
    {"venue": "Stage 15", "item": "Chenda / Thayambaka, Chendamelam", "time": "09 30, 14 00"},
    {"venue": "Stage 16", "item": "Prasangam (Arabic), Padyam Chollal (Boys), Padyam Chollal(Girls)", "time": "17 00, 15 30, 14 30"},
    {"venue": "Stage 17", "item": "Prasnothari, Caption Rachana, Nikhandu Nirmanam", "time": "11 30, 14 00, 09 30"},
    {"venue": "Stage 18", "item": "Thabala, Thabala, Madhalam", "time": "15 00, 12 00, 09 30"},
    {"venue": "Stage 19", "item": "Padyam Chollal - Arabic, Padyam Chollal - Arabic, Prasangam Arabic", "time": "15 00, 11 30, 09 30"},
    {"venue": "Stage 20", "item": "Padyam Chollal - Tamil, Prasangam - Tamil, Padyam Chollal - Tamil", "time": "09 30, 14 00, 11 00"},
    {"venue": "Stage 21", "item": "Chithra Rachana - Oil Colour, Chithra Rachana - Water Colour, Chithra Rachana - Pencil", "time": "15 00, 12 00, 09 30"},
    {"venue": "Stage 22", "item": "Katharachana - Hindi, Upanyasam - Hindi, Kavitharachana - Hindi", "time": "09 30, 15 00, 12 00"},
    {"venue": "Stage 23", "item": "Upanyasam - Urdu, Quiz (Urdu), Upanyasam - Urdu", "time": "12 00, 09 30, 15 00"},
    {"venue": "Stage 24", "item": "Kavitharachana - Tamil, Upanyasam - English, Kavitharachana - English, Kavitharachana - English", "time": "09 30, 16 30, 14 30, 12 00"},
    {"venue": "Stage 25", "item": "Bandmelam", "time": "09 30"}
]

# --- UI SETUP ---
st.set_page_config(page_title="Festival Auditor", layout="wide")
st.title("🎡 Kerala School Kalolsavam Auditor")
st.sidebar.header("Controls")
if st.sidebar.button("🔄 Refresh Audit"):
    st.rerun()

# --- UTILITIES ---
def get_similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

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
    except: return set()

@st.cache_data(ttl=30)
def fetch_live_data():
    try:
        response = requests.get(URL_STAGE, timeout=15)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", response.text, re.DOTALL)
        return json.loads(match.group(1)) if match else []
    except: return []

def get_scheduled_item(stage_name, current_time):
    sched = next((s for s in pre_schedule if s["venue"] == stage_name), None)
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
        if current_time >= slot["time"]: 
            res_item, in_slot = slot["item"], True
    return res_item, in_slot

# --- AUDIT LOGIC ---
live_stages = fetch_live_data()
published_codes = fetch_published_item_codes()

if not live_stages:
    st.error("Could not fetch data from the server. Please check the URL or your connection.")
else:
    current_now = datetime.now()
    suspicious_list = []
    time_overview = []
    found_scheduled_items = []
    
    summary = {"total": len(live_stages), "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}

    for stage in live_stages:
        errors = []
        is_live = stage.get("isLive", False)
        item_code = str(stage.get("item_code", ""))
        total, done = stage.get("participants", 0), stage.get("completed", 0)
        rem = total - done
        is_finished = stage.get("is_tabulation_finish", "N") == "Y"
        item_now = stage.get("item_name", "NA")
        
        # Summary Tracking
        if is_live: summary["live"] += 1
        else: summary["inactive"] += 1
        if is_finished: summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done
        
        # Time Parsing
        try: 
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
            time_overview.append({"name": stage["name"], "time": tent_time, "isLive": is_live, "item": item_now})
        except: 
            tent_time = current_now
            
        # Schedule Check
        sched_item, is_in_slot = get_scheduled_item(stage["name"], current_now)
        if item_now != "NA":
            found_scheduled_items.append({"stage": stage["name"], "item": item_now})

        # 1. Result Conflict
        if is_live and item_code in published_codes:
            errors.append(f"PUBLISH CONFLICT: Item [{item_code}] is LIVE, but already PUBLISHED.")

        # 2. Status & Participant Consistency
        if done > total: errors.append(f"DATA ERROR: Completed ({done}) > Total ({total}).")
        if rem <= 0 and is_live: errors.append("LOGIC: Stage LIVE but 0 pending.")
        if rem > 0:
            if not is_live: errors.append(f"LOGIC: Stage INACTIVE but {rem} pending.")
            if is_finished: errors.append(f"LOGIC: Finished Flag ON but {rem} waiting.")
        
        # 3. Time Validation
        if is_live and tent_time < current_now:
            late_delta = current_now - tent_time
            late_mins = int(late_delta.total_seconds() / 60)
            if late_mins > GRACE_PERIOD_MINS:
                errors.append(f"TIME CRITICAL: Stage is {late_mins} mins behind tent_time.")
            elif late_mins > 0:
                errors.append(f"TIME WARNING: Stage starting to lag.")

        # 4. Item Verification
        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_now) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_now.lower():
                errors.append(f"MISMATCH: Expected '{sched_item}', Stage currently shows '{item_now}'.")

        if errors: 
            suspicious_list.append({"name": stage["name"], "loc": stage["location"], "errors": errors, "rem": rem, "code": item_code})

    # --- MISSING SCHEDULED ITEMS CHECK ---
    missing_items_report = []
    for sched in pre_schedule:
        expected_item, is_active_now = get_scheduled_item(sched["venue"], current_now)
        if is_active_now and expected_item:
            is_present = any(
                get_similarity(expected_item, f["item"]) > SIMILARITY_THRESHOLD 
                for f in found_scheduled_items if f["stage"] == sched["venue"]
            )
            if not is_present:
                missing_items_report.append({
                    "name": sched["venue"],
                    "error": f"SCHEDULE GAP: '{expected_item}' should be active, but is NOT LISTED."
                })

    # --- DISPLAY METRICS ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Stages", summary["total"])
    col2.metric("Live Now", summary["live"])
    col3.metric("Pending Participants", summary["t_p"] - summary["t_c"])
    progress_val = int((summary["t_c"]/summary["t_p"])*100) if summary["t_p"]>0 else 0
    col4.metric("Overall Progress", f"{progress_val}%")

    # --- TIME ANALYSIS PANEL ---
    with st.expander("🕒 View Time Analysis", expanded=True):
        if time_overview:
            time_overview.sort(key=lambda x: x["time"], reverse=True)
            latest = time_overview[0]
            overdue_count = len([s for s in time_overview if s["isLive"] and s["time"] < current_now])
            
            st.write(f"**Last Stage to Finish:** {latest['name']} at {latest['time'].strftime('%H:%M %p')}")
            if overdue_count > 0:
                st.warning(f"⚠️ {overdue_count} stage(s) have passed their tentative completion time.")
            else:
                st.success("✅ All live stages are within their tentative time frames.")

    # --- CRITICAL ISSUES PANEL ---
    st.subheader("🚨 Detected Issues")
    
    # 1. Schedule Gaps
    if missing_items_report:
        for item in missing_items_report:
            st.error(f"**{item['name']} | SCHEDULE MISSING**")
            st.write(f"└ {item['error']}")
            st.divider()

    # 2. Stage Errors
    if suspicious_list:
        for item in suspicious_list:
            with st.container(border=True):
                st.markdown(f"#### 🔴 {item['name']} ({item['loc']})")
                st.write(f"**Pending:** {item['rem']} | **Item Code:** {item['code']}")
                for e in item["errors"]:
                    st.write(f"⚠️ {e}")
    
    if not suspicious_list and not missing_items_report:
        st.success("System Status: Healthy. No logical errors found in the current live data.")

    # --- DATA TABLE ---
    with st.expander("📋 Raw Live Data View"):
        st.table(live_stages)

    st.caption(f"Last updated: {current_now.strftime('%Y-%m-%d %H:%M:%S')}")
