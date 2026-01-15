import streamlit as st
import json, re, requests, difflib, pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- PAGE SETTINGS ---
st.set_page_config(page_title="Kalolsavam 2026 | Master Audit", page_icon="📈", layout="wide")

# --- CUSTOM CSS FOR PROFESSIONAL LOOK ---
st.markdown("""
    <style>
    .reportview-container { background: #f0f2f6; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    div[data-testid="stExpander"] { border: 1px solid #e6e9ef; border-radius: 10px; background: white; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD = 10 

# --- DATA FETCHING (CACHED) ---
@st.cache_data(ttl=60)
def fetch_all_data():
    try:
        s_res = requests.get(URL_STAGE, timeout=10)
        stages = json.loads(re.search(r"const stages = (\[.*?\]);", s_res.text, re.S).group(1))
        r_res = requests.get(URL_RESULTS, timeout=10)
        soup = BeautifulSoup(r_res.text, 'html.parser')
        published = {re.match(r"(\d+)", r.find_all('td')[1].text.strip()).group(1): r.find_all('td')[3].text.strip() 
                     for r in soup.find_all('tr') if len(r.find_all('td')) > 1}
        return stages, published
    except: return [], {}

# --- MASTER DASHBOARD ---
def main():
    st.title("🏛️ Kalolsavam 2026 Audit Control Room")
    now = datetime.now()
    st.caption(f"Real-time Logic Sync: {now.strftime('%I:%M:%S %p')} | Source: KITE Portal")

    stages, published = fetch_all_data()
    if not stages:
        st.error("Connection Lost: Unable to reach ulsavam servers.")
        return

    # Process Logic
    audit_results = []
    full_data_list = []
    summary = {"live": 0, "fin": 0, "total_p": 0, "done_p": 0}

    for s in stages:
        e, w = [], []
        is_live = s.get("isLive")
        code = str(s.get("item_code", ""))
        total, done = s.get("participants", 0), s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish") == "Y"
        tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        
        # Summary Accumulation
        if is_live: summary["live"] += 1
        if is_fin: summary["fin"] += 1
        summary["total_p"] += total
        summary["done_p"] += done

        # 1. Audit logic
        if is_live and code in published: e.append(f"PUBLISH CONFLICT: Item {code} published at {published[code]}")
        if rem <= 0 and is_live: e.append("ZOMBIE LIVE: Item finished but stage still Live")
        if rem > 0:
            if not is_live: e.append(f"STALLED: {rem} participants pending")
            if is_fin: e.append(f"TABULATION: Finished flag ON with {rem} pending")
        
        late_mins = int((now - tent).total_seconds() / 60)
        if is_live and late_mins > 0:
            if late_mins > GRACE_PERIOD: e.append(f"OVERDUE: Running {late_mins}m behind")
            else: w.append(f"LAGGING: {late_mins}m behind")

        if e or w:
            audit_results.append({"Stage": s['name'], "Errors": e, "Warnings": w, "Status": "🔴 Error" if e else "🟡 Warning"})

        # 2. Build Table Data
        full_data_list.append({
            "Stage": s['name'],
            "Location": s['location'],
            "Item": f"[{code}] {s['item_name']}",
            "Status": "📡 LIVE" if is_live else "⏸️ OFF",
            "Rem": rem,
            "Ends": tent.strftime("%H:%M"),
            "Late (m)": late_mins if late_mins > 0 else 0,
            "Finished": "✅" if is_fin else "❌"
        })

    # --- TOP ROW: KPI METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("📡 Live Venues", summary["live"])
    with c2: st.metric("✅ Tabulation Fin", summary["fin"])
    with c3: 
        prog = int((summary["done_p"]/summary["total_p"])*100)
        st.metric("📈 Progress", f"{prog}%", delta=f"{summary['done_p']} items done")
    with c4: st.metric("👥 Pending Total", summary["total_p"] - summary["done_p"])

    st.divider()

    # --- MIDDLE ROW: AUDIT & TIMELINE ---
    col_audit, col_time = st.columns([3, 2])

    with col_audit:
        st.subheader("🚩 Active Audit Failures")
        if not audit_results:
            st.success("Clean Audit: No data inconsistencies detected.")
        else:
            for item in audit_results:
                with st.expander(f"{item['Status']} | {item['Stage']}"):
                    for msg in item["Errors"]: st.error(msg)
                    for msg in item["Warnings"]: st.warning(msg)

    with col_time:
        st.subheader("🕒 Operational Schedule")
        df_time = pd.DataFrame(full_data_list).sort_values("Ends", ascending=False)
        st.dataframe(df_time[["Stage", "Ends", "Late (m)"]], hide_index=True, use_container_width=True)
        st.info(f"**Closing Venue:** {df_time.iloc[0]['Stage']} at {df_time.iloc[0]['Ends']}")

    # --- BOTTOM ROW: MASTER DATA TABLE ---
    st.divider()
    st.subheader("📊 All-Stage Detail Inventory")
    st.dataframe(pd.DataFrame(full_data_list), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
