import streamlit as st
import json, re, requests, difflib, pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(page_title="Kalolsavam Audit | Control Room", page_icon="⚖️", layout="wide")

# --- 2. ADVANCED CSS (Auto-height & High-End Look) ---
st.markdown("""
    <style>
    /* Remove white space at top */
    .block-container { padding-top: 2rem; }
    
    /* Metric Card Styling */
    [data-testid="stMetric"] {
        background: white;
        padding: 15px 20px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f6;
    }

    /* Professional Headers */
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; color: #1e293b; }

    /* Custom Background */
    .stApp {
        background-color: #f8fafc;
    }

    /* Styling for the Expanders to look like high-end cards */
    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: white !important;
        margin-bottom: 0.5rem;
    }
    
    /* Badge styling for manual usage if needed */
    .status-badge {
        padding: 4px 12px;
        border-radius: 50px;
        font-size: 12px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD = 10 

# --- 4. DATA FETCHING (CACHED) ---
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

# --- 5. MAIN LOGIC ---
def main():
    # Header Section
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.title("🏛️ Kalolsavam 2026 Audit Control Room")
        st.caption(f"Refreshed: {datetime.now().strftime('%I:%M:%S %p')} | Logic Protocol: V2.4.1")
    with col_h2:
        if st.button('🔄 Manual Refresh', use_container_width=True):
            st.rerun()

    stages, published = fetch_all_data()
    if not stages:
        st.error("Connection Interrupted: Ensure access to the ulsavam server is active.")
        return

    # Process Metrics and Logic
    audit_results = []
    full_data_list = []
    summary = {"live": 0, "fin": 0, "total_p": 0, "done_p": 0}
    now = datetime.now()

    for s in stages:
        e, w = [], []
        is_live = s.get("isLive")
        code = str(s.get("item_code", ""))
        total, done = s.get("participants", 0), s.get("completed", 0)
        rem = total - done
        is_fin = s.get("is_tabulation_finish") == "Y"
        tent = datetime.strptime(s.get("tent_time"), "%Y-%m-%d %H:%M:%S")
        
        # Summary Counters
        if is_live: summary["live"] += 1
        if is_fin: summary["fin"] += 1
        summary["total_p"] += total
        summary["done_p"] += done

        # --- AUDIT LOGIC (All Features Preserved) ---
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

        # --- BUILD DATAFRAME ---
        full_data_list.append({
            "Stage": s['name'],
            "Location": s['location'],
            "Item": f"[{code}] {s['item_name']}",
            "📡 Live": is_live,
            "👥 Rem": rem,
            "🕒 Ends": tent,
            "⌛ Lag (m)": late_mins if late_mins > 0 else 0,
            "✅ Fin": is_fin
        })

    # --- TOP ROW: KPI CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📡 Live Venues", summary["live"])
    c2.metric("🏆 Results Tabulated", summary["fin"])
    prog = int((summary["done_p"]/summary["total_p"])*100) if summary["total_p"] > 0 else 0
    c3.metric("📊 Overall Progress", f"{prog}%", delta=f"{summary['done_p']} / {summary['total_p']}")
    c4.metric("👥 Total Pending", summary["total_p"] - summary["done_p"])

    st.write("") # Spacer

    # --- MIDDLE ROW: DISCREPANCIES & CRITICAL TIMELINE ---
    col_audit, col_time = st.columns([3, 2])

    with col_audit:
        st.subheader("🚩 Active Discrepancies")
        if not audit_results:
            st.success("Clean Audit: Data logic is 100% consistent across all venues.")
        else:
            for item in audit_results:
                with st.expander(f"{item['Status']} | {item['Stage']}"):
                    for msg in item["Errors"]: st.error(msg, icon="🚨")
                    for msg in item["Warnings"]: st.warning(msg, icon="🟡")

    with col_time:
        st.subheader("🕒 Bottleneck Analysis")
        df_time = pd.DataFrame(full_data_list).sort_values("🕒 Ends", ascending=False)
        
        # Configure Table to not scroll inline and be auto-height
        st.dataframe(
            df_time[["Stage", "🕒 Ends", "⌛ Lag (m)"]],
            hide_index=True,
            use_container_width=True,
            height=None, # This triggers auto-height in newer Streamlit versions
            column_config={
                "🕒 Ends": st.column_config.DatetimeColumn("Expected Finish", format="h:mm a"),
                "⌛ Lag (m)": st.column_config.NumberColumn("Delay", format="%d min")
            }
        )
        st.info(f"**Closing Venue:** {df_time.iloc[0]['Stage']} at {df_time.iloc[0]['🕒 Ends'].strftime('%I:%M %p')}")

    # --- BOTTOM ROW: FULL INVENTORY (AUTO-HEIGHT) ---
    st.divider()
    st.subheader("📊 Master Stage Inventory (Real-Time)")
    
    df_main = pd.DataFrame(full_data_list)
    
    # The height=None or a large height ensures the table is fully visible
    st.dataframe(
        df_main,
        use_container_width=True,
        hide_index=True,
        height=int(len(df_main) * 35.5) + 38, # Intelligent height calculation (Row height * count + header)
        column_config={
            "📡 Live": st.column_config.CheckboxColumn("Live Status"),
            "✅ Fin": st.column_config.CheckboxColumn("Tab. Fin"),
            "🕒 Ends": st.column_config.DatetimeColumn("End Time", format="h:mm a"),
            "⌛ Lag (m)": st.column_config.ProgressColumn("Lag", min_value=0, max_value=60, format="%d min"),
            "👥 Rem": st.column_config.NumberColumn("Remaining"),
            "Item": st.column_config.TextColumn("Item / Item Code", width="large")
        }
    )

if __name__ == "__main__":
    main()
