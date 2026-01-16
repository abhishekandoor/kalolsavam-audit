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

# Ensure 'code' values match official KITE item codes for accurate auditing
PRE_SCHEDULE = [
    {"venue": "Stage 1", "item": "Kuchuppudi (Girls), Thiruvathirakali (Girls)", "code": "101, 102", "time": "09 30, 14 00"},
    {"venue": "Stage 2", "item": "Vrundavadyam, Parichamuttu (Boys)", "code": "103, 104", "time": "14 00, 09 30"},
    {"venue": "Stage 3", "item": "Malapulaya Aattam, Malapulaya Aattam", "code": "105, 106", "time": "09 30, 14 00"},
    {"venue": "Stage 4", "item": "Chavittu Nadakam", "code": "107", "time": "09 30"},
    {"venue": "Stage 5", "item": "Bharathanatyam (Girls), Mookabhinayam", "code": "108, 109", "time": "09 30, 14 00"},
    {"venue": "Stage 6", "item": "Nadanpattu, Nadanpattu", "code": "110, 111", "time": "09 30, 14 00"},
    {"venue": "Stage 7", "item": "Poorakkali (Boys), Groupsong", "code": "112, 113", "time": "09 30, 14 00"},
    {"venue": "Stage 8", "item": "Nangiar Koothu, Nangiar Koothu", "code": "114, 115", "time": "09 30, 14 00"},
    {"venue": "Stage 9", "item": "Yakshaganam", "code": "116", "time": "09 30"},
    {"venue": "Stage 10", "item": "Keralanadanam, Nadodi Nrutham", "code": "117, 118", "time": "09 30, 14 00"},
    {"venue": "Stage 11", "item": "Skit English, Kolkali (Boys)", "code": "119, 120", "time": "09 30, 14 30"},
    {"venue": "Stage 12", "item": "Kathakali - Group, Kathakali (Girls)", "code": "121, 122", "time": "14 00, 09 30"},
    {"venue": "Stage 13", "item": "Padyam Chollal - Hindi, Vandematharam, Sangha Ganam, Aksharaslokam", "code": "123, 124, 125, 126", "time": "09 30, 14 00, 15 00, 17 30"},
    {"venue": "Stage 14", "item": "Mono Act (Boys), Vattappattu (Boys), Mono Act (Girls)", "code": "127, 128, 129", "time": "09 30, 14 00, 11 30"},
    {"venue": "Stage 15", "item": "Chenda / Thayambaka, Chendamelam", "code": "130, 131", "time": "09 30, 14 00"},
    {"venue": "Stage 16", "item": "Prasangam (Arabic), Padyam Chollal (Boys), Padyam Chollal(Girls)", "code": "132, 133, 134", "time": "17 00, 15 30, 14 30"},
    {"venue": "Stage 17", "item": "Prasnothari, Caption Rachana, Nikhandu Nirmanam", "code": "135, 136, 137", "time": "11 30, 14 00, 09 30"},
    {"venue": "Stage 18", "item": "Thabala, Thabala, Madhalam", "code": "138, 139, 140", "time": "15 00, 12 00, 09 30"},
    {"venue": "Stage 19", "item": "Padyam Chollal - Arabic, Padyam Chollal - Arabic, Prasangam Arabic", "code": "141, 142, 143", "time": "15 00, 11 30, 09 30"},
    {"venue": "Stage 20", "item": "Padyam Chollal - Tamil, Prasangam - Tamil, Padyam Chollal - Tamil", "code": "144, 145, 146", "time": "09 30, 14 00, 11 00"},
    {"venue": "Stage 21", "item": "Chithra Rachana - Oil Colour, Chithra Rachana - Water Colour, Chithra Rachana - Pencil", "code": "147, 148, 149", "time": "15 00, 12 00, 09 30"},
    {"venue": "Stage 22", "item": "Katharachana - Hindi, Upanyasam - Hindi, Kavitharachana - Hindi", "code": "150, 151, 152", "time": "09 30, 15 00, 12 00"},
    {"venue": "Stage 23", "item": "Upanyasam - Urdu, Quiz (Urdu), Upanyasam - Urdu", "code": "153, 154, 155", "time": "12 00, 09 30, 15 00"},
    {"venue": "Stage 24", "item": "Kavitharachana - Tamil, Upanyasam - English, Kavitharachana - English", "code": "156, 157, 158", "time": "09 30, 16 30, 14 30"},
    {"venue": "Stage 25", "item": "Bandmelam", "code": "159", "time": "09 30"}
]

# --- 4. UTILITIES ---
def get_similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_scheduled_item(stage_name, current_time):
    sched = next((s for s in PRE_SCHEDULE if s["venue"] == stage_name), None)
    if not sched: return None, False, None
    items = [i.strip() for i in sched["item"].split(",")]
    times = [t.strip() for t in sched["time"].split(",")]
    slots = []
    for i in range(len(times)):
        try:
            dt = datetime.strptime(f"{current_time.strftime('%Y-%m-%d')} {times[i].replace(' ', ':')}", "%Y-%m-%d %H:%M")
            slots.append({"item": items[i], "time": dt})
        except: continue
    slots.sort(key=lambda x: x["time"])
    res_item, in_slot, sched_time = None, False, None
    for slot in slots:
        if current_time >= slot["time"]: 
            res_item, in_slot, sched_time = slot["item"], True, slot["time"]
    return res_item, in_slot, sched_time

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
    summary = {"total": len(stages), "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}

    idx = 1
    for stage in stages:
        errors = []
        is_live = str(stage.get("isLive")).lower() == "true" or stage.get("isLive") is True
        item_code = str(stage.get("item_code", ""))
        item_now = stage.get("item_name", "NA")
        total, done = int(stage.get("participants", 0)), int(stage.get("completed", 0))
        rem, is_finished = total - done, str(stage.get("is_tabulation_finish", "N")).upper() == "Y"
        
        is_published = item_code in published_codes

        if is_live: summary["live"] += 1
        else: summary["inactive"] += 1
        if is_finished: summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done

        try:
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
            time_tracker.append({"name": stage["name"], "time": tent_time, "isLive": is_live, "item": item_now})
        except: tent_time = current_now

        sched_item, is_in_slot, sched_time_dt = get_scheduled_item(stage["name"], current_now)

        # Audit logic
        if is_live and is_published: errors.append(f"🚨 PUBLISH CONFLICT: Item [{item_code}] is LIVE, but already PUBLISHED.")
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
                if is_live:
                    errors.append(f"🔀 MISMATCH: Expected '{sched_item}', Live shows '{item_now}'.")
                else:
                    delay_from_sched = int((current_now - sched_time_dt).total_seconds() / 60)
                    errors.append(f"⏳ STARTUP DELAY: Expected '{sched_item}' ({delay_from_sched} mins overdue).")

        if errors: suspicious_list.append({"name": stage["name"], "loc": stage.get("location", "NA"), "errors": errors, "rem": rem})

        inventory_list.append({
            "#": idx,
            "Stage Name": stage["name"],
            "Item Code": item_code,
            "Competition": item_now,
            "Status": "🟢 Live Now" if is_live else "🔴 Inactive",
            "Result": "✅ Published" if is_published else "⏳ Pending",
            "Pending": rem,
            "Total": total,
            "Finish": tent_time.strftime("%d %b, %I:%M %p")
        })
        idx += 1

    # --- UI SUMMARY ---
    st.info(f"🕒 **System Sync:** {current_now.strftime('%d %b, %I:%M:%S %p')} IST")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Venues", f"{summary['live']} / {summary['total']}")
    m2.metric("Total Participants", summary['t_p'])
    prog = int((summary['t_c']/summary['t_p'])*100) if summary['t_p'] > 0 else 0
    m3.metric("Global Progress", f"{prog}%")
    m4.metric("Pending Performances", summary['t_p'] - summary['t_c'])

    st.divider()

    # --- HIGH-PRIORITY DISCREPANCIES ---
    st.subheader(f"🚩 High-Priority Discrepancies ({len(suspicious_list)})")
    if not suspicious_list:
        st.success("✅ Clean Audit: All stage logic currently synchronized.")
    else:
        for item in suspicious_list:
            with st.expander(f"🔴 {item['name']} : {item['rem']} Pending Participants", expanded=True):
                c_err, c_loc = st.columns([3, 1])
                with c_err:
                    for e in item['errors']: st.write(f"• {e}")
                with c_loc: st.caption(f"**Location:** {item['loc']}")

    st.divider()

    # --- INVENTORY TABLE ---
    st.subheader("📊 Detailed Stage Inventory")
    df = pd.DataFrame(inventory_list)
    search_query = st.text_input("🔍 Filter by Stage Name or Item Name:")
    if search_query:
        df = df[df['Stage Name'].str.contains(search_query, case=False) | df['Competition'].str.contains(search_query, case=False)]
    
    st.dataframe(df, use_container_width=True, hide_index=True, height=int((len(df)*35.5)+45))

    # --- SYNCHRONIZED CODE-BASED AUDIT TIMELINE ---
    st.divider()
    st.subheader("🕵️ Detailed Venue Timeline & Code-Based Result Audit")
    selected_stage = st.selectbox("🎯 Select a Venue for Deep Audit:", options=["None"] + [s["name"] for s in stages])
    
    if selected_stage != "None":
        stage_info = next((s for s in stages if s["name"] == selected_stage), None)
        if stage_info:
            c1, c2 = st.columns([1, 3])
            with c1:
                st.markdown(f"#### 🏟️ {selected_stage}")
                st.write(f"**Venue:** {stage_info.get('location', 'NA')}")
                st.write(f"**Status:** {'🟢 Live Now' if str(stage_info.get('isLive')).lower() == 'true' else '🔴 Inactive'}")
            
            with c2:
                venue_sched = next((s for s in PRE_SCHEDULE if s["venue"] == selected_stage), None)
                if venue_sched:
                    sched_items = [i.strip() for i in venue_sched["item"].split(",")]
                    sched_codes = [c.strip() for c in venue_sched["code"].split(",")]
                    sched_times = [t.strip() for t in venue_sched["time"].split(",")]
                    
                    timeline_rows = []
                    for s_item, s_code, s_time in zip(sched_items, sched_codes, sched_times):
                        # FIX: Audit strictly against published_codes using the item code
                        is_code_published = s_code in published_codes
                        
                        live_item_code = str(stage_info.get('item_code', ''))
                        if live_item_code == s_code:
                            res_status = "🔴 Currently Live"
                        elif is_code_published:
                            res_status = "✅ Result Published"
                        else:
                            res_status = "⏳ Pending/In Progress"
                        
                        timeline_rows.append({
                            "Scheduled Time": s_time,
                            "Program": s_item,
                            "Item Code": s_code,
                            "Audit Status": res_status
                        })
                    st.table(pd.DataFrame(timeline_rows))
                else:
                    st.warning("No pre-schedule data (Item Codes) available for this venue.")

if __name__ == "__main__":
    main()
