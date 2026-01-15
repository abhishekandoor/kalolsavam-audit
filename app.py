import streamlit as st
import json
import re
import requests
import difflib
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Kalolsavam Auditor", page_icon="📊", layout="wide")

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD_MINS = 10
SIMILARITY_THRESHOLD = 0.65

pre_schedule = [
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

# --- UTILITIES ---
def get_similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

def fetch_published_item_codes():
    published_codes = set()
    try:
        response = requests.get(URL_RESULTS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 2:
                match = re.match(r"(\d+)", cols[1].text.strip())
                if match: published_codes.add(match.group(1))
        return published_codes
    except: return set()

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
        if current_time >= slot["time"]: res_item, in_slot = slot["item"], True
    return res_item, in_slot

# --- STREAMLIT UI ---
st.title("🏆 Kalolsavam Stage Auditor")
st.caption("Live monitoring of Kerala State School Kalolsavam 2026")

if st.button('🔄 Refresh Data'):
    st.rerun()

live_stages = fetch_live_data()
published_codes = fetch_published_item_codes()

if live_stages:
    current_now = datetime.now()
    suspicious_list = []
    time_overview = []
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
        
        try: 
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
            time_overview.append({"name": stage["name"], "time": tent_time, "isLive": is_live})
        except: 
            tent_time = current_now
            
        sched_item, is_in_slot = get_scheduled_item(stage["name"], current_now)

        if is_live and item_code in published_codes:
            errors.append(f"PUBLISH CONFLICT: Item [{item_code}] is LIVE, but already PUBLISHED.")
        if done > total: errors.append(f"DATA ERROR: Completed ({done}) > Total ({total}).")
        if rem <= 0 and is_live: errors.append("LOGIC: Stage LIVE but 0 pending.")
        if rem > 0:
            if not is_live: errors.append(f"LOGIC: Stage INACTIVE but {rem} pending.")
            if is_finished: errors.append(f"LOGIC: Finished Flag ON but {rem} waiting.")
        
        if is_live and tent_time < current_now:
            late_mins = int((current_now - tent_time).total_seconds() / 60)
            if late_mins > GRACE_PERIOD_MINS:
                errors.append(f"TIME CRITICAL: {late_mins}m behind tent_time.")
            elif late_mins > 0:
                errors.append(f"TIME WARNING: Lagging {late_mins}m.")

        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_now) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_now.lower():
                errors.append(f"MISMATCH: Expected '{sched_item}', Live shows '{item_now}'.")

        if errors:
            suspicious_list.append({"name": stage["name"], "loc": stage["location"], "errors": errors, "rem": rem})

    # Display Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Live Stages", summary["live"])
    m2.metric("Finished Stages", summary["fin"])
    progress = int((summary["t_c"]/summary["t_p"])*100) if summary["t_p"]>0 else 0
    m3.metric("Overall Progress", f"{progress}%")
    m4.metric("Pending", summary["t_p"] - summary["t_c"])

    # Time Analysis
    if time_overview:
        time_overview.sort(key=lambda x: x["time"], reverse=True)
        st.info(f"🕒 **Last Stage to Finish:** {time_overview[0]['name']} at {time_overview[0]['time'].strftime('%H:%M %p')}")

    # Suspicious Stages
    st.subheader(f"⚠️ Suspicious Stages ({len(suspicious_list)})")
    if not suspicious_list:
        st.success("No logical errors found.")
    else:
        for item in suspicious_list:
            with st.expander(f"🔴 {item['name']} - {item['loc']} ({item['rem']} pending)"):
                for e in item["errors"]:
                    st.error(e)
else:
    st.warning("No data found from server.")
