from flask import Flask, render_template_string
import requests
import json
import random
from datetime import datetime
from geopy.geocoders import Nominatim
import folium

app = Flask(__name__)

DB_FILE = "uap_db.json"
geolocator = Nominatim(user_agent="uap_tracker")

# -----------------------------
# LOAD / SAVE
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
# SIMULATED DATA (replace later)
# -----------------------------
def fetch_reports():
    cities = ["New York", "Los Angeles", "Berlin", "London", "Toronto"]
    shapes = ["triangle", "orb", "disk", "light"]

    reports = []
    for _ in range(random.randint(3, 6)):
        reports.append({
            "datetime": str(datetime.utcnow()),
            "city": random.choice(cities),
            "shape": random.choice(shapes),
            "description": "Fast moving glowing object"
        })
    return reports

# -----------------------------
# GEOLOCATION
# -----------------------------
def get_coords(city):
    try:
        loc = geolocator.geocode(city)
        return (loc.latitude, loc.longitude)
    except:
        return None

# -----------------------------
# FILTER (basic aircraft logic)
# -----------------------------
def is_aircraft(desc):
    desc = desc.lower()
    if "blinking" in desc or "red light" in desc:
        return True
    return False

# -----------------------------
# PROCESS DATA
# -----------------------------
def update_data():
    db = load_db()
    reports = fetch_reports()

    for r in reports:
        coords = get_coords(r["city"])
        if not coords:
            continue

        entry = {
            "datetime": r["datetime"],
            "city": r["city"],
            "lat": coords[0],
            "lon": coords[1],
            "shape": r["shape"],
            "description": r["description"],
            "filtered": is_aircraft(r["description"])
        }

        if entry not in db:
            db.append(entry)

    save_db(db)

# -----------------------------
# MAP GENERATION
# -----------------------------
def generate_map():
    db = load_db()

    m = folium.Map(location=[20, 0], zoom_start=2)

    for r in db:
        color = "red" if not r["filtered"] else "blue"

        popup = f"""
        <b>City:</b> {r['city']}<br>
        <b>Shape:</b> {r['shape']}<br>
        <b>Time:</b> {r['datetime']}<br>
        <b>Desc:</b> {r['description']}
        """

        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=6,
            popup=popup,
            color=color,
            fill=True
        ).add_to(m)

    return m._repr_html_()

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def index():
    update_data()
    map_html = generate_map()

    return render_template_string(f"""
    <html>
    <head>
        <title>UAP Intelligence System</title>
    </head>
    <body style="background:black;color:white;">
        <h1>🛰️ UAP Intelligence Map</h1>
        <p>Red = Unknown | Blue = Likely Aircraft</p>
        {map_html}
    </body>
    </html>
    """)

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)