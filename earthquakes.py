import requests
import time
import os
from datetime import datetime

# USGS live global feed (past hour)
URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"

seen_ids = set()

def clear():
    os.system("clear" if os.name == "posix" else "cls")

def fetch_data():
    try:
        response = requests.get(URL, timeout=10)
        return response.json()
    except Exception as e:
        print(f"[ERROR] {e}")
        return None

def format_time(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

def get_category(mag):
    """Categorize earthquake by magnitude."""
    if mag >= 7.0:
        return "MAJOR", "🔴"
    elif mag >= 5.0:
        return "STRONG", "🟠"
    elif mag >= 3.0:
        return "MODERATE", "🟡"
    elif mag >= 1.0:
        return "SMALL", "🟢"
    else:
        return "MICRO", "⚪"

def display(data):
    if not data:
        return

    quakes = data["features"]

    # Separate into small and large
    small_quakes = []
    large_quakes = []

    for quake in quakes:
        props = quake["properties"]
        mag = props["mag"]

        if mag is None:
            continue

        entry = {
            "id": quake["id"],
            "mag": mag,
            "place": props["place"],
            "time": format_time(props["time"]),
            "lat": quake["geometry"]["coordinates"][1],
            "lon": quake["geometry"]["coordinates"][0],
            "depth": quake["geometry"]["coordinates"][2],
        }

        if mag >= 3.0:
            large_quakes.append(entry)
        else:
            small_quakes.append(entry)

    # Sort both lists by magnitude descending
    large_quakes.sort(key=lambda x: x["mag"], reverse=True)
    small_quakes.sort(key=lambda x: x["mag"], reverse=True)

    print("🌍  GLOBAL EARTHQUAKE MONITOR (LIVE)")
    print(f"    Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    # ── LARGE / NOTABLE EARTHQUAKES ──────────────────────────────────
    print(f"\n🔴🟠  LARGE & NOTABLE EARTHQUAKES  (M3.0+)  [{len(large_quakes)} found]")
    print("-" * 65)

    if not large_quakes:
        print("   ✅ No large earthquakes in the past hour.")
    else:
        for q in large_quakes:
            category, icon = get_category(q["mag"])
            new_tag = "" if q["id"] in seen_ids else "  ✨ NEW"
            seen_ids.add(q["id"])

            print(f"{icon} [{category}] M{q['mag']}{new_tag}")
            print(f"   📍 Location : {q['place']}")
            print(f"   🌐 Lat/Lon  : {q['lat']}, {q['lon']}")
            print(f"   ⬇️  Depth    : {q['depth']} km")
            print(f"   ⏰ Time     : {q['time']}")
            print()

    # ── SMALL / MICRO EARTHQUAKES ────────────────────────────────────
    print("-" * 65)
    print(f"\n🟢⚪  SMALL & MICRO EARTHQUAKES  (Under M3.0)  [{len(small_quakes)} found]")
    print("-" * 65)

    if not small_quakes:
        print("   ✅ No small earthquakes in the past hour.")
    else:
        for q in small_quakes:
            category, icon = get_category(q["mag"])
            new_tag = "" if q["id"] in seen_ids else "  ✨ NEW"
            seen_ids.add(q["id"])

            print(f"{icon} [{category}] M{q['mag']}{new_tag}")
            print(f"   📍 {q['place']}")
            print(f"   ⬇️  Depth: {q['depth']} km  |  ⏰ {q['time']}")
            print()

    print("=" * 65)

def main():
    print("Starting Earthquake Monitor...")
    while True:
        clear()
        data = fetch_data()
        display(data)
        print(f"\n🔄 Refreshing in 20 seconds...  (Ctrl+C to quit)")
        time.sleep(20)

if __name__ == "__main__":
    main()