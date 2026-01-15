import streamlit as st
import json, re, requests, difflib, pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 1. PRO-LEVEL PAGE SETTINGS ---
st.set_page_config(
    page_title="Kalolsavam 2026 | Master Audit Dashboard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CUSTOM THEME & CSS ---
st.markdown("""
    <style>
        .main { background-color: #f0f2f6; }
        [data-testid="stMetricValue"] { font-size: 28px !important; color: #1f77b4; }
        .stMetric { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eef0f5; }
        div[data-testid="stExpander"] { background: white; border-radius: 12px; border: 1px solid #e0e6ed; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        .status-pill { padding: 4px 10px; border-radius: 20px; font-weight: bold; font-size: 12px; }
        .live { background: #e8f5e9; color: #2e7d32; }
        .off { background: #ffebee; color: #c62828; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONFIGURATION & SOURCE URLS ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD = 10 
SIMILARITY_THRESHOLD = 0.65

# --- 4. DYNAMIC DATA CORE (CACHED) ---
@st.cache_data(ttl=60) # Refreshes every 60 seconds
def load_live_context():
    try:
        # Fetch Stage Data
        s_res = requests.get(URL_STAGE, timeout=10)
        stages = json.loads(re.search(r"const stages = (\[.*?\]);", s_res.text, re.S).group(1))
        
        # Fetch Result Data
        r_res = requests.get(URL_RESULTS, timeout=10)
        soup = BeautifulSoup(r_res.text, 'html.parser')
        published = {re.match(r"(\d+)", r.find_all('td')[1].text.strip()).group(1): r.find_all('td')[3].text.strip() 
                     for r in soup.find_all('tr') if len(r.find_all('td')) > 1}
        return stages, published
    except Exception as e:
        st.error(f"⚠️ Connection to Server Lost: {e}")
        return [], {}

# --- 5. AUDIT & ANALYTICS ENGINE ---
def run_audit_engine(stages, published):
    now = datetime.now()
    audit_log, inventory = [], []
    stats = {"live": 0, "fin": 0, "total_p": 0, "done_p": 0, "overdue": 0}

    for s in stages:
        errs, warn = [], []
        is_live, code = s.get("isLive"), str(s.get("item_code", ""))
        total, done = s.get("participants", 0), s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish") == "Y"
        item_name = s.get("item_name", "NA")
        tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        
        # Metrics Calculation
        if is_live: stats["live"] += 1
        if is_fin: stats["fin"] += 1
        stats["total_p"] += total
        stats["done_p"] += done

        # --- THE 7 CORE LOGIC CONDITIONS ---
        # 1. Result Conflict
        if is_live and code in published:
            errs.append(f"🚨 **CONFLICT:** Results published ({published[code]}) but stage still LIVE.")
        # 2. Status Consistency
        if rem <= 0 and is_live: errs.append("🧟 **ZOMBIE LIVE:** 0 participants left but stage is LIVE.")
        if rem > 0:
            if not is_live: errs.append(f"⏸️ **STALLED:** {rem} pending but stage is INACTIVE.")
            if is_fin: errs.append(f"📉 **DATA ERROR:** Finished Flag ON with {rem} pending.")
        # 3. Time Validation
        late_mins = int((now - tent).total_seconds() / 60)
        if is_live and late_mins > 0:
            stats["overdue"] += 1
            if late_mins > GRACE_PERIOD: errs.append(f"⏰ **CRITICAL LATE:** {late_mins}m behind tent_time.")
            else: warn.append(f"🟡 **LAGGING:** {late_mins}m behind.")
        # 4. Integrity Check
        if done > total: errs.append(f"❌ **DATA INTEGRITY:** Completed ({done}) > Total ({total})")

        if errs or warn:
            audit_log.append({"Stage": s['name'], "Errors": errs, "Warnings": warn, "Priority": "🔴 High" if errs else "🟡 Medium"})

        inventory.append({
            "Stage": s['name'], "Location": s['location'], "Running Item": f"[{code}] {item_name}",
            "Status": "LIVE" if is_live else "OFF", "Rem": rem, "Ends": tent.strftime("%H:%M"),
            "Lag (m)": late_mins if late_mins > 0 else 0, "Fin": "✅" if is_fin else "❌"
        })
    
    return audit_log, inventory, stats

# --- 6. USER INTERFACE DESIGN ---
def main():
    st.header("🏛️ Kalolsavam 2026 Audit Control Room")
    st.caption(f"Refreshed: {datetime.now().strftime('%I:%M:%S %p')} IST")

    stages, published = load_live_context()
    if not stages: return

    logs, table, stats = run_audit_engine(stages, published)

    # --- TOP ROW: KPI CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📡 Live Venues", f"{stats['live']} / {len(stages)}")
    c2.metric("✅ Completed Items", stats['fin'])
    prog = int((stats['done_p']/stats['total_p'])*100) if stats['total_p'] > 0 else 0
    c3.metric("📈 Progress", f"{prog}%", delta=f"{stats['done_p']} items done")
    c4.metric("⚠️ Time Delays", stats['overdue'], delta_color="inverse")

    # --- MIDDLE ROW: CONSOLIDATED ANALYTICS ---
    st.divider()
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("🚩 Active Audit Discrepancies")
        if not logs:
            st.success("Perfect Audit: All systems logically consistent.")
        else:
            for log in logs:
                with st.expander(f"{log['Priority']} | {log['Stage']}"):
                    for e in log['Errors']: st.error(e)
                    for w in log['Warnings']: st.warning(w)

    with col_right:
        st.subheader("🕒 Timing & Bottlenecks")
        df_table = pd.DataFrame(table)
        df_sorted = df_table.sort_values("Ends", ascending=False)
        st.dataframe(df_sorted[["Stage", "Ends", "Lag (m)"]], hide_index=True, use_container_width=True)
        st.info(f"**Final Venue Expected:** {df_sorted.iloc[0]['Stage']} at {df_sorted.iloc[0]['Ends']}")

    # --- BOTTOM ROW: MASTER INVENTORY ---
    st.divider()
    st.subheader("📊 Master Stage Inventory (Real-Time)")
    # Style the master table
    st.dataframe(
        df_table, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn("Status", help="Live status from server"),
            "Lag (m)": st.column_config.ProgressColumn("Lag (m)", min_value=0, max_value=120, format="%d min")
        }
    )

if __name__ == "__main__":
    main()
