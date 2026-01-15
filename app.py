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
    pre.cli-output {
        background:#0b1220;
        color:#d6e6ff;
        padding:12px;
        border-radius:8px;
        overflow:auto;
        font-family:Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace;
    }
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

def get_schedule_context(stage_name, current_time):
    """
    Returns (current_item, next_item) to handle early starts.
    """
    sched = next((s for s in PRE_SCHEDULE if s["venue"] == stage_name), None)
    if not sched:
        return None, None

    items = [i.strip() for i in sched["item"].split(",")]
    times = [t.strip() for t in sched["time"].split(",")]

    slots = []
    for i in range(len(times)):
        try:
            dt = datetime.strptime(f"{current_time.strftime('%Y-%m-%d')} {times[i].replace(' ', ':')}", "%Y-%m-%d %H:%M")
            slots.append({"item": items[i], "time": dt})
        except:
            continue

    slots.sort(key=lambda x: x["time"])

    current_item = None
    next_item = None

    # Determine current slot
    for i, slot in enumerate(slots):
        if current_time >= slot["time"]:
            current_item = slot["item"]
            if i + 1 < len(slots):
                next_item = slots[i+1]["item"]
            else:
                next_item = None
        else:
            if current_item is None:
                next_item = slot["item"]
            break

    return current_item, next_item

@st.cache_data(ttl=60)
def fetch_data():
    try:
        s_res = requests.get(URL_STAGE, timeout=10)
        stages = json.loads(re.search(r"const stages = (\[.*?\]);", s_res.text, re.S).group(1))
    except Exception:
        stages = []

    try:
        r_res = requests.get(URL_RESULTS, timeout=10)
        soup = BeautifulSoup(r_res.text, 'html.parser')
        published = {re.match(r"(\d+)", r.find_all('td')[1].text.strip()).group(1): r.find_all('td')[3].text.strip()
                     for r in soup.find_all('tr') if len(r.find_all('td')) > 1}
    except Exception:
        published = {}

    return stages, published

# --- 5. AUDIT ENGINE (same logic/messages as CLI auditor) ---
def run_audit_and_build_output(stages, published, now):
    suspicious_list = []
    time_overview = []
    summary = {"total_stages": len(stages), "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}

    for stage in stages:
        errors = []
        is_live = stage.get("isLive", False)
        item_code = str(stage.get("item_code", ""))
        total, done = stage.get("participants", 0), stage.get("completed", 0)
        rem = total - done
        is_finished = stage.get("is_tabulation_finish", "N") == "Y"
        item_now = stage.get("item_name", "NA")

        # Update Summary
        if is_live:
            summary["live"] += 1
        else:
            summary["inactive"] += 1
        if is_finished:
            summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done

        try:
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
            time_overview.append({"name": stage["name"], "time": tent_time, "isLive": is_live, "item": item_now})
        except:
            tent_time = now

        curr_sched, next_sched = get_schedule_context(stage.get("name"), now)

        # 1. Result Conflict
        if is_live and item_code in published:
            errors.append(f"PUBLISH CONFLICT: Item [{item_code}] is LIVE, but already PUBLISHED.")

        # 2. Status & Participant Consistency
        if done > total:
            errors.append(f"DATA ERROR: Completed ({done}) > Total ({total}).")
        if rem <= 0 and is_live:
            errors.append("LOGIC: Stage LIVE but 0 pending.")
        if rem > 0:
            if not is_live:
                errors.append(f"LOGIC: Stage INACTIVE but {rem} pending.")
            if is_finished:
                errors.append(f"LOGIC: Finished Flag ON but {rem} waiting.")

        # 3. Time Validation (grace period logic)
        if is_live and tent_time < now:
            late_delta = now - tent_time
            late_mins = int(late_delta.total_seconds() / 60)
            if late_mins > GRACE_PERIOD:
                errors.append(f"TIME CRITICAL: Stage is {late_mins} minutes behind tent_time ({tent_time.strftime('%H:%M')}).")
            elif late_mins > 0:
                errors.append(f"TIME WARNING: Stage starting to lag ({late_mins} mins behind).")

        # 4. Item Verification (schedule match)
        if curr_sched and curr_sched != None:
            if get_similarity(curr_sched, item_now) < SIMILARITY_THRESHOLD and curr_sched.lower() not in item_now.lower():
                errors.append(f"MISMATCH: Expected '{curr_sched}', Live shows '{item_now}'.")

        if errors:
            suspicious_list.append({
                "name": stage.get("name"),
                "loc": stage.get("location"),
                "errors": errors,
                "rem": rem,
                "code": item_code
            })

    # Build textual CLI-style output (same wording as your auditor)
    lines = []
    lines.append("\n" + "═" * 75)
    lines.append(f"  FESTIVAL OVERVIEW | {now.strftime('%H:%M:%S')}")
    lines.append("─" * 75)
    lines.append(f"  Stages: {summary['total_stages']} | Live: {summary['live']} | Inactive: {summary['inactive']} | Finished: {summary['fin']}")
    progress_pct = int((summary['t_c'] / summary['t_p']) * 100) if summary['t_p'] > 0 else 0
    lines.append(f"  Progress: {summary['t_c']} / {summary['t_p']} ({progress_pct}%)")

    if time_overview:
        time_overview.sort(key=lambda x: x["time"], reverse=True)
        latest = time_overview[0]
        overdue_stages = [s for s in time_overview if s["isLive"] and s["time"] < now]
        lines.append("─" * 75)
        lines.append(f"  🕒 LAST STAGE TO FINISH: {latest['name']} at {latest['time'].strftime('%H:%M %p')}")
        if overdue_stages:
            lines.append(f"  ⚠️  STAGES RUNNING BEHIND: {len(overdue_stages)} stage(s) have passed their tent_time.")

    lines.append("═" * 75)

    if suspicious_list:
        lines.append(f"\n  ⚠️ FOUND {len(suspicious_list)} SUSPICIOUS STAGES:")
        for item in suspicious_list:
            lines.append(f"\n  🔴 {item['name'].upper()} ({item['loc']}) | Pending: {item['rem']}")
            for e in item["errors"]:
                lines.append(f"     └─ ERROR: {e}")
    else:
        lines.append("\n  ✅ SYSTEM STATUS: No logical errors found.")

    lines.append("\n" + "═" * 75 + "\n")
    return "\n".join(lines), suspicious_list, summary

# --- 6. MAIN APP ---
def main():
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("Kalolsavam Live Status")
        st.caption(f"Last Updated: {datetime.now().strftime('%I:%M %p')}")
    with col2:
        if st.button("Refresh"):
            st.experimental_rerun()

    stages, published = fetch_data()
    if not stages:
        st.error("Unable to connect to the festival server. Please try again later.")
        return

    now = datetime.now()
    full_data = []
    alerts = []

    # Build the data and reuse the same logic for per-stage issues (to populate table & summary)
    for s in stages:
        is_live = s.get("isLive")
        code = str(s.get("item_code", ""))
        item_name = s.get("item_name", "Unknown Item")
        total = s.get("participants", 0)
        done = s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish") == "Y"

        try:
            tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        except:
            tent = now

        late_mins = int((now - tent).total_seconds() / 60)
        status_text = "Live Now" if is_live else ("Finished" if is_fin else "Waiting")

        # Replicate same issue gathering (keeps streamlit warnings consistent)
        issues = []

        curr_sched, next_sched = get_schedule_context(s['name'], now)
        if is_live and curr_sched:
            match_curr = get_similarity(curr_sched, item_name) >= SIMILARITY_THRESHOLD or (curr_sched.lower() in item_name.lower())
            match_next = False
            if next_sched:
                match_next = get_similarity(next_sched, item_name) >= SIMILARITY_THRESHOLD or (next_sched.lower() in item_name.lower())
            if not match_curr and not match_next:
                expect_msg = f"'{curr_sched}'"
                if next_sched:
                    expect_msg += f" or '{next_sched}'"
                issues.append(f"🔀 MISMATCH: Expected {expect_msg}, Live shows '{item_name}'.")

        if rem > 0 and not is_live:
            if late_mins > 0:
                issues.append(f"🔴 CRITICAL: Stage is OFF but overdue by {late_mins} mins.")
            elif done > 0:
                issues.append(f"⏸️ PAUSED: {done} finished, stopped with {rem} pending.")
            else:
                issues.append("⏳ WAITING: Item has not started yet.")

        if is_live and code in published:
            issues.append(f"🚨 DATA ERROR: Results published at {published[code]}, but stage is LIVE.")

        if rem <= 0 and is_live:
            issues.append("🧟 STUCK STATUS: All participants finished, but stage shows Live.")

        if is_live and late_mins > GRACE_PERIOD:
            issues.append(f"⏰ LAGGING: Running {late_mins} min behind schedule.")

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

    # CLI-style audit output (identical wording as your auditor)
    audit_text, suspicious_list, summary = run_audit_and_build_output(stages, published, now)

    # --- METRICS ---
    if summary["t_p"] > 0:
        progress = int((summary["t_c"] / summary["t_p"]) * 100)
    else:
        progress = 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Stages Live", summary["live"])
    m2.metric("Items Done", summary["fin"])
    m3.metric("Total Progress", f"{progress}%")
    m4.metric("Participants Left", summary["t_p"] - summary["t_c"])

    st.divider()

    # --- AUDIT OUTPUT (CLI style) ---
    with st.expander("Audit Output (CLI-style) — view detailed stage errors and system overview", expanded=False):
        st.markdown(f'<pre class="cli-output">{audit_text}</pre>', unsafe_allow_html=True)

    # --- ALERTS (same as before) ---
    if alerts:
        with st.expander("System Alerts & Delays (click to view)", expanded=True):
            for alert in alerts:
                st.warning(f"**{alert['stage']}** ({alert['loc']})\n\n" + "\n".join(alert['issues']))

    # --- TABLE ---
    st.subheader("Find Your Stage")
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
