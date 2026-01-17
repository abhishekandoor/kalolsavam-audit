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
    {"venue": "Stage 1", "item": "Group Dance (Girls), Bharathanatyam (Girls)", "code": "101, 102", "time": "14 00, 09 30"},
    {"venue": "Stage 2", "item": "Parichamuttu (Boys), Vrunda Vadyam", "code": "103, 104", "time": "09 30, 14 00"},
    {"venue": "Stage 3", "item": "Erula Nirtham, Erula Nirtham", "code": "105, 106", "time": "14 00, 09 30"},
    {"venue": "Stage 4", "item": "Chavittu Nadakam", "code": "107", "time": "09 30"},
    {"venue": "Stage 5", "item": "Paliya Nirtham, Paliya Nirtham", "code": "108, 109", "time": "14 00, 09 30"},
    {"venue": "Stage 6", "item": "Mono Act (Boys), Nadodi Nrutham (Girls), Mono Act (Girls)", "code": "110, 111", "time": "11 30, 15 00, 09 30"},
    {"venue": "Stage 7", "item": "Keralanadanam (Girls), Kolkali (Boys)", "code": "112, 113", "time": "09 30, 14 00"},
    {"venue": "Stage 8", "item": "Kathakali Sangeetham (Boys), Kathakali Sangeetham (Girls), Kathakali Sangeetham (Boys)", "code": "114, 115", "time": "12 30, 09 30, 15 30"},
    {"venue": "Stage 9", "item": "Koodiyattam", "code": "116", "time": "09 30"},
    {"venue": "Stage 10", "item": "Kuchuppudi (Boys), Vanchipattu", "code": "937", "time": "14 00, 09 30"},
    {"venue": "Stage 11", "item": "Nadakam", "code": "698, 120", "time": "09 30"},
    {"venue": "Stage 12", "item": "Kathakali , Kathakali (Girls)", "code": "121, 1007", "time": "14 00, 09 30"},
    {"venue": "Stage 13", "item": "Padakam (Girls), Padakam (Boys), Ganalapanam (Girls), Ganalapanam (Boys)", "code": "818, 124, 125, 126", "time": "12 00, 09 30, 14 00, 16 00"},
    {"venue": "Stage 14", "item": "Sasthreeya Sangeetham(Boys), Sasthreeya Sangeetham(Girls), Sasthreeya Sangeetham(Girls)", "code": "127, 128, 973", "time": "12 00, 15 00, 09 30"},
    {"venue": "Stage 15", "item": "Odakkuzhal, Nadaswaram, Odakuzhal, Triple / Jazz - Western", "code": "130, 675", "time": "12 00, 14 00, 09 30, 16 00"},
    {"venue": "Stage 16", "item": "Nadakam", "code": "", "time": "09 30"},
    {"venue": "Stage 17", "item": "Tharjama ( Arabic), Poster Nirmanam", "code": "", "time": "09 30, 11 00"},
    {"venue": "Stage 18", "item": "Violin - Oriental, Violin - Western, Violin - Paschathyam", "code": "925, 139, 140", "time": "14 00, 11 00, 09 30"},
    {"venue": "Stage 19", "item": "Prasangam - Urdu, Padyam Chollal - Urdu, Padyam Chollal - Urdu, Prasangam Urdu", "code": "141, 142, 143", "time": "15 00, 12 00, 09 30, 17 00"},
    {"venue": "Stage 20", "item": "Aksharaslokam, Kavyakeli, Aksharaslokam, Kavyakeli", "code": "144, 145, 690", "time": "14 00, 12 00, 16 00, 09 30"},
    {"venue": "Stage 21", "item": "Katharachana - Urdu, Katharachana - Urdu, Kavitharachana - Urdu, Kavitharachana - Urdu", "code": "", "time": "12 00, 09 30, 14 30, 16 30"},
    {"venue": "Stage 22", "item": "Upanyasam - Hindi, Kavitharachana - Hindi, Katharachana - Hindi", "code": "", "time": "15 00, 09 30, 12 00"},
    {"venue": "Stage 23", "item": "Upanyasam - Arabic, Katharachana - Arabic, Kavitharachana - Arabic", "code": "", "time": "15 00, 09 30, 12 00"},
    {"venue": "Stage 24", "item": "Kavitharachana - Sanskrit, Katharachana - Sanskrit", "code": "", "time": "12 00, 09 30"},
    {"venue": "Stage 25", "item": "Bandmelam", "code": "996", "time": "09 30"}
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

@st.cache_data(ttl=5)
def fetch_all_data():
    try:
        s_res = requests.get(URL_STAGE, timeout=10)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", s_res.text, re.DOTALL)
        stages = json.loads(match.group(1)) if match else []
        r_res = requests.get(URL_RESULTS, timeout=10)
        soup = BeautifulSoup(r_res.text, 'html.parser')
        published = set()
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 2:
                code_match = re.search(r"(\d+)", cols[1].text.strip())
                if code_match: published.add(code_match.group(1))
        return stages, published
    except: return [], set()

# --- 5. MAIN APP ---
def main():
    st.markdown('<h1 class="main-title">Kerala State School Kalolsavam Stage Analysis</h1>', unsafe_allow_html=True)
    
    current_now = datetime.now(IST).replace(tzinfo=None)
    stages, published_codes = fetch_all_data()
    
    if not stages:
        st.error("🚨 Connection Error: Unable to reach KITE servers.")
        return

    suspicious_list, inventory_list, live_completion_tracker = [], [], []
    summary = {"total": len(stages), "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}

    idx = 1
    for stage in stages:
        errors = []
        is_live = str(stage.get("isLive")).lower() == "true" or stage.get("isLive") is True
        item_code = str(stage.get("item_code", ""))
        item_now = stage.get("item_name", "NA")
        total, done = int(stage.get("participants", 0)), int(stage.get("completed", 0))
        rem = total - done
        is_finished = str(stage.get("is_tabulation_finish", "N")).upper() == "Y"
        is_published = item_code in published_codes

        if is_live: summary["live"] += 1
        else: summary["inactive"] += 1
        if is_finished: summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done

        # TODAY'S LAST PROGRAMME TRACKER: Uses live tent_time
        try:
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
            live_completion_tracker.append({
                "venue": stage["name"],
                "item": item_now,
                "code": item_code,
                "time": tent_time,
                "status": "🟢 Live" if is_live else "🔴 Inactive"
            })
        except: tent_time = current_now

        sched_item, is_in_slot, sched_time_dt = get_scheduled_item(stage["name"], current_now)

        # --- UPDATED AUDIT LOGIC (All issues handled) ---
        if is_live and is_published: 
            errors.append(f"🚨 PUBLISH CONFLICT: Item [{item_code}] is LIVE but Result already PUBLISHED.")
        
        if done > total: 
            errors.append(f"❌ DATA ERROR: Completed ({done}) > Total ({total}).")
        
        # FIX: Ensure 0 participants on a Live stage triggers an error
        if is_live and rem <= 0:
            errors.append("🧟 LOGIC: Stage is LIVE but 0 participants are pending (Zombie Stage).")
            
        if rem > 0:
            if not is_live: 
                errors.append(f"⏸️ LOGIC: Stage INACTIVE but {rem} pending.")
            if is_finished: 
                errors.append(f"📉 LOGIC: Finished Flag ON but {rem} waiting.")
        
        if is_live and tent_time < current_now:
            late_mins = int((current_now - tent_time).total_seconds() / 60)
            if late_mins > GRACE_PERIOD_MINS: 
                errors.append(f"⏰ TIME CRITICAL: Running {late_mins} mins behind.")

        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_now) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_now.lower():
                if is_live: 
                    errors.append(f"🔀 MISMATCH: Expected '{sched_item}', Live shows '{item_now}'.")

        if errors: 
            suspicious_list.append({"name": stage["name"], "loc": stage.get("location", "NA"), "errors": errors, "rem": rem})

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

    # --- TODAY'S LAST PROGRAMME ---
    st.subheader("🏁 Today's Last Programme")
    if live_completion_tracker:
        expected_last = sorted(live_completion_tracker, key=lambda x: x["time"], reverse=True)[0]
        st.error(f"""
            ### 🕒 Expected Conclusion: {expected_last['time'].strftime('%d %b, %I:%M %p')}  
            **Venue:** {expected_last['venue']} | **Current Item:** {expected_last['item']} (Code: {expected_last['code']})  
            **Status:** {expected_last['status']}
        """)
    else:
        st.warning("Live tentative completion data unavailable.")

    st.divider()

    # --- HIGH-PRIORITY DISCREPANCIES ---
    st.subheader(f"🚩 High-Priority Discrepancies ({len(suspicious_list)})")
    if suspicious_list:
        for item in suspicious_list:
            with st.expander(f"🔴 {item['name']} : {item['rem']} Pending", expanded=True):
                for e in item['errors']: st.write(f"• {e}")
                st.caption(f"Location: {item['loc']}")
    else:
        st.success("✅ Logic Clean: No discrepancies found.")

    st.divider()

    # --- MAIN INVENTORY TABLE ---
    st.subheader("📊 Detailed Stage Inventory")
    df_inv = pd.DataFrame(inventory_list)
    search = st.text_input("🔍 Search Venue or Item Name:")
    if search:
        df_inv = df_inv[df_inv['Stage Name'].str.contains(search, case=False) | df_inv['Competition'].str.contains(search, case=False)]
    st.dataframe(df_inv, use_container_width=True, hide_index=True, height=int((len(df_inv)*35.5)+45))

    # --- VENUE TIMELINE ---
    st.divider()
    st.subheader("🕵️ Detailed Venue Timeline Analysis")
    selected_stage = st.selectbox("🎯 Select Venue:", options=["None"] + [s["name"] for s in stages])
    
    if selected_stage != "None":
        stage_info = next((s for s in stages if s["name"] == selected_stage), None)
        if stage_info:
            c1, c2 = st.columns([1, 3])
            with c1:
                st.markdown(f"#### 🏟️ {selected_stage}")
                st.write(f"**Venue:** {stage_info.get('location', 'NA')}")
                st.write(f"**Status:** {'🟢 Live' if str(stage_info.get('isLive')).lower() == 'true' else '🔴 Inactive'}")
            
            with c2:
                venue_sched = next((s for s in PRE_SCHEDULE if s["venue"] == selected_stage), None)
                if venue_sched:
                    sched_items, sched_codes, sched_times = [i.strip() for i in venue_sched["item"].split(",")], [c.strip() for c in venue_sched["code"].split(",")], [t.strip() for t in venue_sched["time"].split(",")]
                    timeline_rows = [{"Scheduled Time": s_time, "Program": s_item, "Item Code": s_code} for s_item, s_code, s_time in zip(sched_items, sched_codes, sched_times)]
                    st.table(pd.DataFrame(timeline_rows))
                else:
                    st.warning("No pre-schedule codes available.")

if __name__ == "__main__":
    main()
