import streamlit as st
import json, re, requests, difflib, pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(
    page_title="Kalolsavam Audit Control Room",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

IST = pytz.timezone('Asia/Kolkata')

# --- 2. HIGH-CONTRAST UI CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    h1, h2, h3, h4, h5, h6, .main-title {
        color: #000000 !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetric"] {
        background: #ffffff !important;
        padding: 15px 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
    }
    [data-testid="stMetricLabel"] > div, 
    [data-testid="stMetricValue"] > div {
        color: #000000 !important;
    }
    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: #ffffff !important;
        margin-bottom: 10px;
    }
    div[data-testid="stExpander"] summary {
        background-color: #000000 !important; 
        border-radius: 12px 12px 0 0 !important;
        padding: 5px !important;
    }
    div[data-testid="stExpander"] summary p {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    div[data-testid="stExpander"] summary svg {
        fill: #ffffff !important;
    }
    div[data-testid="stExpander"] .stMarkdown, 
    div[data-testid="stExpander"] p, 
    div[data-testid="stExpander"] li {
        color: #000000 !important;
    }
    .stTextInput input {
        color: #000000 !important;
        background-color: #ffffff !important;
    }
    .block-container { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONFIGURATION & DATA ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD_MINS = 10
SIMILARITY_THRESHOLD = 0.65

# Pre-schedule reference
PRE_SCHEDULE = [
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
    {"venue": "Stage 24", "item": "Kavitharachana - Tamil, Upanyasam - English, Kavitharachana - English", "time": "09 30, 16 30, 14 30"},
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

@st.cache_data(ttl=10)
def fetch_all_data():
    try:
        s_res = requests.get(URL_STAGE, timeout=15)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", s_res.text, re.DOTALL)
        stages = json.loads(match.group(1)) if match else []
        r_res = requests.get(URL_RESULTS, timeout=15)
        soup = BeautifulSoup(r_res.text, 'html.parser')
        published = {re.match(r"(\d+)", r.find_all('td')[1].text.strip()).group(1)
                     for r in soup.find_all('tr') if len(r.find_all('td')) >= 2 and re.match(r"(\d+)", r.find_all('td')[1].text.strip())}
        return stages, published
    except: return [], set()

# --- 5. MAIN APP ---
def main():
    st.markdown('<h1 class="main-title">Kerala State School Kalolsavam Stage Analysis</h1>', unsafe_allow_html=True)
    
    current_now = datetime.now(IST).replace(tzinfo=None)
    stages, published_codes = fetch_all_data()
    
    if not stages:
        st.error("🚨 Connection Error: Unable to sync with official KITE servers.")
        return

    suspicious_list, inventory_list, time_tracker = [], [], []
    # found_scheduled_items = [] # COMMENTED: Used for Schedule Gap Analysis
    summary = {"total": len(stages), "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}

    for stage in stages:
        errors = []
        is_live = str(stage.get("isLive")).lower() == "true" or stage.get("isLive") is True
        item_code, item_now = str(stage.get("item_code", "")), stage.get("item_name", "NA")
        total, done = int(stage.get("participants", 0)), int(stage.get("completed", 0))
        rem, is_finished = total - done, str(stage.get("is_tabulation_finish", "N")).upper() == "Y"
        
        if is_live: summary["live"] += 1
        else: summary["inactive"] += 1
        if is_finished: summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done

        try:
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
            time_tracker.append({"name": stage["name"], "time": tent_time, "isLive": is_live, "item": item_now})
        except: tent_time = current_now

        sched_item, is_in_slot = get_scheduled_item(stage["name"], current_now)
        # if item_now != "NA": found_scheduled_items.append({"stage": stage["name"], "item": item_now}) # COMMENTED

        # --- AUDIT LOGIC ---
        if is_live and item_code in published_codes: errors.append(f"🚨 PUBLISH CONFLICT: Item [{item_code}] is LIVE, but already PUBLISHED.")
        if done > total: errors.append(f"❌ DATA ERROR: Completed ({done}) > Total ({total}).")
        if rem <= 0 and is_live: errors.append("🧟 LOGIC: Stage LIVE but 0 pending.")
        if rem > 0:
            if not is_live: errors.append(f"⏸️ LOGIC: Stage INACTIVE but {rem} pending.")
            if is_finished: errors.append(f"📉 LOGIC: Finished Flag ON but {rem} waiting.")
        
        if is_live and tent_time < current_now:
            late_mins = int((current_now - tent_time).total_seconds() / 60)
            if late_mins > GRACE_PERIOD_MINS: errors.append(f"⏰ TIME CRITICAL: Running {late_mins} mins behind schedule.")
            elif late_mins > 0: errors.append(f"🟡 TIME WARNING: Stage starting to lag.")

        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_now) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_now.lower():
                errors.append(f"🔀 MISMATCH: Expected '{sched_item}', Live shows '{item_now}'.")

        if errors: suspicious_list.append({"name": stage["name"], "loc": stage.get("location", "NA"), "errors": errors, "rem": rem})

        inventory_list.append({
            "Stage Name": stage["name"],
            "Venue Location": stage.get("location", "NA"),
            "Competition": item_now,
            "Stage Status": "🟢 Live Now" if is_live else "🔴 Inactive",
            "Pending Participants": rem,
            "Total Participants": total,
            "Scheduled Finish": tent_time.strftime("%d %b, %I:%M %p")
        })

    # --- COMMENTED: SCHEDULE GAP ANALYSIS ---
    # missing_items_report = []
    # for sched in PRE_SCHEDULE:
    #     expected_item, is_active_now = get_scheduled_item(sched["venue"], current_now)
    #     if is_active_now and expected_item:
    #         is_present = any(get_similarity(expected_item, f["item"]) > SIMILARITY_THRESHOLD for f in found_scheduled_items if f["stage"] == sched["venue"])
    #         if not is_present: missing_items_report.append({"name": sched["venue"], "error": f"❌ GAP: '{expected_item}' should be active, but is MISSING from server list."})

    # --- UI DISPLAY ---
    st.info(f"🕒 **System Sync:** {current_now.strftime('%d %b, %I:%M:%S %p')} IST")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Venues", f"{summary['live']} / {summary['total']}")
    m2.metric("Total Load", summary['t_p'])
    prog = int((summary['t_c']/summary['t_p'])*100) if summary['t_p'] > 0 else 0
    m3.metric("Global Progress", f"{prog}%")
    m4.metric("Pending Performances", summary['t_p'] - summary['t_c'])

    if time_tracker:
        last_item = sorted(time_tracker, key=lambda x: x['time'], reverse=True)[0]
        st.error(f"🏁 **Closing Analysis:** {last_item['name']} projected to finish at **{last_item['time'].strftime('%I:%M %p')}**")

    st.divider()

    col_l, col_r = st.columns([1, 2])
    with col_l:
        st.subheader(f"🚩 High-Priority Discrepancies ({len(suspicious_list)})")
        # for item in missing_items_report: # COMMENTED: UI part for Schedule Gaps
        #     with st.expander(f"⚠️ {item['name']} | SCHEDULE GAP", expanded=True): st.error(item['error'])
        if not suspicious_list: st.success("✅ Clean Audit: All stage logic synchronized.")
        for item in suspicious_list:
            with st.expander(f"🔴 {item['name']} ({item['rem']} Pending)", expanded=True):
                for e in item['errors']: st.write(f"• {e}")
                st.caption(f"Location: {item['loc']}")

    with col_r:
        st.subheader("📊 Detailed Stage Inventory")
        df = pd.DataFrame(inventory_list)
        search_query = st.text_input("🔍 Search Stage or Item Name:", placeholder="e.g. Stage 5, Mohiniyattam...")
        if search_query:
            df = df[df['Stage Name'].str.contains(search_query, case=False) | df['Competition'].str.contains(search_query, case=False)]
        
        full_table_height = (len(df) * 35.5) + 45
        st.dataframe(df, use_container_width=True, hide_index=True, height=int(full_table_height))

if __name__ == "__main__":
    main()
