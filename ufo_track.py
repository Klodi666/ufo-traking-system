import requests
import json
import time
import random
from datetime import datetime
from collections import Counter

DB_FILE = "uap_database.json"

# -----------------------------
# CONFIG
# -----------------------------
FETCH_INTERVAL = 300  # seconds
KEYWORDS = ["triangle", "light", "fast", "hover", "orb", "disk", "unknown"]

# -----------------------------
# DATABASE FUNCTIONS
# -----------------------------
def load_db():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

# -----------------------------
# DATA COLLECTION (SIMULATED API)
# Replace with real sources later
# -----------------------------
def fetch_ufo_reports():
    # Simulated incoming reports
    sample_locations = ["USA", "Canada", "UK", "Germany", "Australia"]
    sample_shapes = ["triangle", "light", "disk", "sphere"]

    reports = []
    for _ in range(random.randint(1, 5)):
        reports.append({
            "date_time": str(datetime.utcnow()),
            "location": random.choice(sample_locations),
            "shape": random.choice(sample_shapes),
            "description": "Fast moving object with bright light"
        })
    return reports

# -----------------------------
# NORMALIZATION
# -----------------------------
def normalize(report):
    return {
        "datetime": report.get("date_time"),
        "location": report.get("location"),
        "shape": report.get("shape"),
        "description": report.get("description"),
        "keywords": extract_keywords(report.get("description", "")),
        "filtered": False,
        "source": "simulated_feed"
    }

# -----------------------------
# KEYWORD EXTRACTION
# -----------------------------
def extract_keywords(text):
    text = text.lower()
    return [kw for kw in KEYWORDS if kw in text]

# -----------------------------
# AIRCRAFT FILTER (BASIC LOGIC)
# -----------------------------
def is_likely_aircraft(report):
    desc = report["description"].lower()
    if "blinking" in desc or "red light" in desc:
        return True
    return False

# -----------------------------
# CLUSTERING (BASIC)
# -----------------------------
def cluster_reports(db):
    clusters = {}
    for r in db:
        key = f"{r['location']}_{r['shape']}"
        clusters.setdefault(key, []).append(r)
    return clusters

# -----------------------------
# DASHBOARD
# -----------------------------
def show_dashboard(db):
    print("\n====== UAP MONITOR DASHBOARD ======")
    print(f"Total Reports: {len(db)}")

    locations = Counter([r["location"] for r in db])
    shapes = Counter([r["shape"] for r in db])

    print("\nTop Locations:")
    for loc, count in locations.most_common(5):
        print(f" - {loc}: {count}")

    print("\nTop Shapes:")
    for shape, count in shapes.most_common(5):
        print(f" - {shape}: {count}")

    unknowns = [r for r in db if not r["filtered"]]
    print(f"\nPotential Unknowns: {len(unknowns)}")

# -----------------------------
# MAIN PROCESS
# -----------------------------
def process():
    db = load_db()
    new_reports = fetch_ufo_reports()

    added = 0

    for report in new_reports:
        clean = normalize(report)

        if clean not in db:
            # Filter aircraft
            if is_likely_aircraft(clean):
                clean["filtered"] = True

            db.append(clean)
            added += 1

    save_db(db)

    print(f"[+] Added {added} new reports")
    show_dashboard(db)

# -----------------------------
# LOOP
# -----------------------------
def run():
    print("[+] Starting UAP Monitor...")
    while True:
        try:
            process()
            time.sleep(FETCH_INTERVAL)
        except KeyboardInterrupt:
            print("\n[!] Stopped by user")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(10)

# -----------------------------
# ENTRY
# -----------------------------
if __name__ == "__main__":
    run()