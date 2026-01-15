import streamlit as st
import json
import re
import requests
import difflib
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

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
GRACE_PERIOD_MINS = 10
SIMILARITY_THRESHOLD = 0.65

# Pre-schedule reference (same as your reference)
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
    """
    Exact logic from the non-Streamlit auditor:
    Returns (scheduled_item_string_or_None, in_slot_bool)
    in_slot is True if current_time >= any slot time (last matched slot).
    """
    sched = next((s for s in PRE_SCHEDULE if s["venue"] == stage_name), None)
    if not sched:
        return None, False

    items = [i.strip() for i in sched["item"].split(",")]
    times = [t.strip() for t in sched["time"].split(",")]

    slots = []
    for i in range(len(times)):
        try:
            dt = datetime.strptime(
                f"{current_time.strftime('%Y-%m-%d')} {times[i].replace(' ', ':')}",
                "%Y-%m-%d %H:%M"
            )
            slots.append({"item": items[i], "time": dt})
        except:
            continue

    slots.sort(key=lambda x: x["time"])

    res_item = None
    in_slot = False
    for slot in slots:
        if current_time >= slot["time"]:
            res_item = slot["item"]
            in_slot = True

    return res_item, in_slot

@st.cache_data(ttl=60)
def fetch_data():
    """
    Returns: (stages_list, published_codes_set)
    """
    # fetch live stages
    try:
        response = requests.get(URL_STAGE, timeout=10)
        match = re.search(r"const\s+stages\s*=\s*(\[.*?\]);", response.text, re.S)
        stages = json.loads(match.group(1)) if match else []
    except Exception:
        stages = []

    # fetch published item codes (set)
    published_codes = set()
    try:
        resp = requests.get(URL_RESULTS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.find_all('tr')
        for r in rows:
            cols = r.find_all('td')
            if len(cols) >= 2:
                m = re.match(r"(\d+)", cols[1].text.strip())
                if m:
                    published_codes.add(m.group(1))
    except Exception:
        published_codes = set()

    return stages, published_codes

# --- 5. AUDIT / REPORT (identical messages as non-Streamlit) ---
def run_audit_and_build_output(live_stages, published_codes, current_now):
    if not live_stages:
        return "", [], {"total_stages": 0, "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}

    suspicious_list = []
    time_overview = []

    summary = {"total_stages": len(live_stages), "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}

    for stage in live_stages:
        errors = []
        is_live = stage.get("isLive", False)
        item_code = str(stage.get("item_code", ""))
        total = stage.get("participants", 0)
        done = stage.get("completed", 0)
        rem = total - done
        is_finished = stage.get("is_tabulation_finish", "N") == "Y"
        item_now = stage.get("item_name", "NA")

        # Update summary
        if is_live:
            summary["live"] += 1
        else:
            summary["inactive"] += 1
        if is_finished:
            summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done

        # tent_time handling
        try:
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
            time_overview.append({"name": stage.get("name"), "time": tent_time, "isLive": is_live, "item": item_now})
        except:
            tent_time = current_now

        # get scheduled item and in-slot flag (CLI's exact behavior)
        sched_item, is_in_slot = get_scheduled_item(stage.get("name"), current_now)

        # 1. Result Conflict (published)
        if is_live and item_code in published_codes:
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

        # 3. Time Validation (grace period)
        if is_live and tent_time < current_now:
            late_delta = current_now - tent_time
            late_mins = int(late_delta.total_seconds() / 60)
            if late_mins > GRACE_PERIOD_MINS:
                errors.append(f"TIME CRITICAL: Stage is {late_mins} minutes behind tent_time ({tent_time.strftime('%H:%M')}).")
            elif late_mins > 0:
                errors.append(f"TIME WARNING: Stage starting to lag ({late_mins} mins behind).")

        # 4. Item Verification (strict: only when in-slot)
        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_now) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_now.lower():
                errors.append(f"MISMATCH: Expected '{sched_item}', Live shows '{item_now}'.")

        if errors:
            suspicious_list.append({
                "name": stage.get("name"),
                "loc": stage.get("location"),
                "errors": errors,
                "rem": rem,
                "code": item_code
            })

    # Build CLI-style text exactly like the non-Streamlit auditor
    lines = []
    lines.append("\n" + "═" * 75)
    lines.append(f"  FESTIVAL OVERVIEW | {current_now.strftime('%H:%M:%S')}")
    lines.append("─" * 75)
    lines.append(f"  Stages: {summary['total_stages']} | Live: {summary['live']} | Inactive: {summary['inactive']} | Finished: {summary['fin']}")
    progress_pct = int((summary['t_c'] / summary['t_p']) * 100) if summary['t_p'] > 0 else 0
    lines.append(f"  Progress: {summary['t_c']} / {summary['t_p']} ({progress_pct}%)")

    if time_overview:
        time_overview.sort(key=lambda x: x["time"], reverse=True)
        latest = time_overview[0]
        overdue_stages = [s for s in time_overview if s["isLive"] and s["time"] < current_now]
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

    stages, published_codes = fetch_data()
    if not stages:
        st.error("⚠️ Unable to connect to the festival server. Please try again later.")
        return

    now = datetime.now()
    full_data = []
    alerts = []

    # Build per-stage full_data and collect alerts using same rules (for UI warnings)
    for s in stages:
        is_live = s.get("isLive", False)
        code = str(s.get("item_code", ""))
        item_name = s.get("item_name", "Unknown Item")
        total = s.get("participants", 0)
        done = s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish", "N") == "Y"

        try:
            tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        except:
            tent = now

        late_mins = int((now - tent).total_seconds() / 60)
        status_text = "Live Now 🔴" if is_live else ("Finished ✅" if is_fin else "Waiting ⏸️")

        # Use exact same audit logic for UI alerts (messages identical to CLI)
        issues = []

        sched_item, is_in_slot = get_scheduled_item(s.get("name"), now)

        # 1. Result Conflict
        if is_live and code in published_codes:
            issues.append(f"PUBLISH CONFLICT: Item [{code}] is LIVE, but already PUBLISHED.")

        # 2. Status & Participant Consistency
        if done > total:
            issues.append(f"DATA ERROR: Completed ({done}) > Total ({total}).")
        if rem <= 0 and is_live:
            issues.append("LOGIC: Stage LIVE but 0 pending.")
        if rem > 0:
            if not is_live:
                issues.append(f"LOGIC: Stage INACTIVE but {rem} pending.")
            if is_fin:
                issues.append(f"LOGIC: Finished Flag ON but {rem} waiting.")

        # 3. Time Validation
        if is_live and tent < now:
            late_delta = now - tent
            late_mins = int(late_delta.total_seconds() / 60)
            if late_mins > GRACE_PERIOD_MINS:
                issues.append(f"TIME CRITICAL: Stage is {late_mins} minutes behind tent_time ({tent.strftime('%H:%M')}).")
            elif late_mins > 0:
                issues.append(f"TIME WARNING: Stage starting to lag ({late_mins} mins behind).")

        # 4. Item Verification (only when in-slot)
        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_name) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_name.lower():
                issues.append(f"MISMATCH: Expected '{sched_item}', Live shows '{item_name}'.")

        if issues:
            alerts.append({"stage": s.get("name"), "loc": s.get("location"), "issues": issues})

        full_data.append({
            "Stage": s.get("name"),
            "Item": item_name,
            "Status": status_text,
            "Remaining": rem,
            "Expected End": tent.strftime("%I:%M %p"),
            "Delay (min)": max(0, late_mins) if is_live else 0,
            "Search_Key": f"{s.get('name')} {item_name} {code}".lower()
        })

    # CLI-style audit output (identical wording)
    audit_text, suspicious_list, summary = run_audit_and_build_output(stages, published_codes, now)

    # --- METRICS ---
    if summary["t_p"] > 0:
        progress = int((summary["t_c"] / summary["t_p"]) * 100)
    else:
        progress = 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 Stages Live", summary["live"])
    m2.metric("✅ Items Done", summary["fin"])
    m3.metric("📊 Total Progress", f"{progress}%")
    m4.metric("👥 Participants Left", summary["t_p"] - summary["t_c"])

    st.divider()

    # --- AUDIT OUTPUT (CLI style) ---
    with st.expander("⚠️ Audit Output (CLI-style) — detailed stage errors and system overview", expanded=False):
        st.markdown(f'<pre class="cli-output">{audit_text}</pre>', unsafe_allow_html=True)

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
