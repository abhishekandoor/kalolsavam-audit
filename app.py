import json
import re
import requests
import difflib
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
URL_STAGE = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/stage/Stage_management"
URL_RESULTS = "https://ulsavam.kite.kerala.gov.in/2025/kalolsavam/index.php/publishresult/Public_result/completedItems"
GRACE_PERIOD_MINS = 10
SIMILARITY_THRESHOLD = 0.65

# Pre-schedule reference
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
        rows = soup.find_all('tr')
        for row in rows:
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

# --- AUDITOR ---
def run_audit():
    live_stages = fetch_live_data()
    published_codes = fetch_published_item_codes()
    if not live_stages: return

    current_now = datetime.now()
    suspicious_list = []
    time_overview = []
    
    summary = {"total_stages": len(live_stages), "live": 0, "inactive": 0, "fin": 0, "t_p": 0, "t_c": 0}

    for stage in live_stages:
        errors = []
        is_live = stage.get("isLive", False)
        item_code = str(stage.get("item_code", ""))
        total, done = stage.get("participants", 0), stage.get("completed", 0)
        rem = total - done
        is_finished = stage.get("is_tabulation_finish", "N") == "Y"
        item_now = stage.get("item_name", "NA")
        
        # Update Summary
        if is_live: summary["live"] += 1
        else: summary["inactive"] += 1
        if is_finished: summary["fin"] += 1
        summary["t_p"] += total
        summary["t_c"] += done
        
        # Time Parsing
        try: 
            tent_time = datetime.strptime(stage.get("tent_time", ""), "%Y-%m-%d %H:%M:%S")
        except: 
            tent_time = current_now
        
        # Calculate Late Minutes
        late_mins = 0
        if tent_time < current_now:
            late_mins = int((current_now - tent_time).total_seconds() / 60)

        # Add to Time Overview
        time_overview.append({"name": stage["name"], "time": tent_time, "isLive": is_live, "late_mins": late_mins})
            
        sched_item, is_in_slot = get_scheduled_item(stage["name"], current_now)

        # --- LOGIC CHECKS ---

        # 1. Result Conflict
        if is_live and item_code in published_codes:
            errors.append(f"PUBLISH CONFLICT: Item [{item_code}] is LIVE, but already PUBLISHED.")

        # 2. Status & Participant Consistency
        if done > total: errors.append(f"DATA ERROR: Completed ({done}) > Total ({total}).")
        if rem <= 0 and is_live: errors.append("LOGIC: Stage LIVE but 0 pending.")
        
        # 3. Inactive but Pending Logic (FIXED to capture Stage 16 issues)
        if rem > 0 and not is_live:
            if late_mins > 0:
                errors.append(f"CRITICAL: Stage INACTIVE but Overdue by {late_mins} mins.")
            else:
                errors.append(f"LOGIC: Stage INACTIVE but {rem} participants pending.")
        
        if rem > 0 and is_finished: 
            errors.append(f"LOGIC: Finished Flag ON but {rem} waiting.")
        
        # 4. Live Time Validation
        if is_live and late_mins > 0:
            if late_mins > GRACE_PERIOD_MINS:
                errors.append(f"TIME CRITICAL: Running {late_mins} mins behind schedule.")
            else:
                errors.append(f"TIME WARNING: Lagging {late_mins} mins.")

        # 5. Item Verification
        if is_in_slot and sched_item:
            if get_similarity(sched_item, item_now) < SIMILARITY_THRESHOLD and sched_item.lower() not in item_now.lower():
                errors.append(f"MISMATCH: Expected '{sched_item}', Live shows '{item_now}'.")

        if errors: 
            suspicious_list.append({"name": stage["name"], "loc": stage["location"], "errors": errors, "rem": rem})

    # --- PRINT OUTPUT ---
    print("\n" + "═"*75)
    print(f"  FESTIVAL OVERVIEW | {current_now.strftime('%H:%M:%S')}")
    print("─"*75)
    print(f"  Stages: {summary['total_stages']} | Live: {summary['live']} | Inactive: {summary['inactive']} | Finished: {summary['fin']}")
    print(f"  Progress: {summary['t_c']} / {summary['t_p']} ({int((summary['t_c']/summary['t_p'])*100) if summary['t_p']>0 else 0}%)")
    
    # TENTATIVE TIME ANALYSIS (SYNCED LOGIC)
    if time_overview:
        time_overview.sort(key=lambda x: x["time"], reverse=True)
        latest = time_overview[0]
        # Count stages that are > 0 mins late (Syncs with error logic)
        overdue_stages = [s for s in time_overview if s["isLive"] and s["late_mins"] > 0]
        
        print("─"*75)
        print(f"  🕒 LAST STAGE TO FINISH: {latest['name']} at {latest['time'].strftime('%H:%M %p')}")
        if overdue_stages:
            print(f"  ⚠️  STAGES RUNNING BEHIND: {len(overdue_stages)} stage(s) exceed tent_time.")
    
    print("═"*75)

    if suspicious_list:
        print(f"\n  ⚠️ FOUND {len(suspicious_list)} SUSPICIOUS STAGES:")
        for item in suspicious_list:
            print(f"\n  🔴 {item['name'].upper()} ({item['loc']}) | Pending: {item['rem']}")
            for e in item["errors"]: print(f"     └─ ERROR: {e}")
    else:
        print("\n  ✅ SYSTEM STATUS: No logical errors found.")
    print("\n" + "═"*75 + "\n")

if __name__ == "__main__":
    run_audit()
