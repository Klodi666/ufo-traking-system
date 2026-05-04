"""
╔══════════════════════════════════════════════════════════════╗
║     ASTEROID OBSERVATION SYSTEM  //  NASA JPL DATA PARSER   ║
║     Target: (2010 PK9)  //  Aten-class  //  PHA             ║
╚══════════════════════════════════════════════════════════════╝

  Usage:
    python asteroid_observer.py                  # full report
    python asteroid_observer.py --target Earth   # Earth approaches only
    python asteroid_observer.py --future         # future approaches only
    python asteroid_observer.py --export         # save report to .txt
    python asteroid_observer.py --plot           # plot miss distances

  Data source: nasa.json  (NASA NEO API — single object endpoint)
"""

import json
import sys
import math
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────
#  ANSI COLORS
# ─────────────────────────────────────────────
class C:
    R = "\033[0m"
    BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[91m"; GRN = "\033[92m"; YLW = "\033[93m"
    BLU = "\033[94m"; MAG = "\033[95m"; CYN = "\033[96m"
    W   = "\033[97m"

    g = staticmethod(lambda t: f"\033[92m{t}\033[0m")
    r = staticmethod(lambda t: f"\033[91m{t}\033[0m")
    y = staticmethod(lambda t: f"\033[93m{t}\033[0m")
    c = staticmethod(lambda t: f"\033[96m{t}\033[0m")
    m = staticmethod(lambda t: f"\033[95m{t}\033[0m")
    b = staticmethod(lambda t: f"\033[1m{t}\033[0m")
    d = staticmethod(lambda t: f"\033[2m{t}\033[0m")

W = 68  # terminal width


# ─────────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────────
def hdr(title, icon="◈"):
    print(f"\n  {C.g(icon)} {C.b(title)}")
    print(C.d(f"  {'─' * (W - 4)}"))

def row(label, value, color=None):
    lbl = C.d(f"{label:<26}")
    val = color(value) if color else C.g(value)
    print(f"    {lbl}{val}")

def div():
    print(C.d(f"  {'╌' * (W - 4)}"))

def bar(ratio: float, width: int = 24, lo="#00cc44", hi="#ff3311") -> str:
    ratio = max(0.0, min(1.0, ratio))
    filled = round(ratio * width)
    r = ratio
    color = C.r if r > 0.75 else C.y if r > 0.4 else C.g
    return f"[{color('█' * filled + '░' * (width - filled))}]"

def section_break():
    print()
    print(C.d(f"  {'═' * (W - 4)}"))

def banner():
    print(f"""
{C.GRN}{C.BOLD}  ╔{'═'*(W-4)}╗
  ║{'ASTEROID OBSERVATION SYSTEM  //  NASA JPL DATA PARSER':^{W-4}}║
  ╚{'═'*(W-4)}╝{C.R}""")


# ─────────────────────────────────────────────
#  LOAD DATA
# ─────────────────────────────────────────────
def load_json(path: str = "nasa.json") -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(C.r(f"  [ERR] File not found: {path}"))
    with open(p) as f:
        return json.load(f)


# ─────────────────────────────────────────────
#  THREAT / CLASSIFICATION
# ─────────────────────────────────────────────
THREAT_COLORS = {
    "CRITICAL":  C.r,
    "HIGH":      C.r,
    "ELEVATED":  C.y,
    "MODERATE":  C.c,
    "WATCH":     C.m,
    "LOW":       C.g,
}

def threat(miss_km: float, hazard: bool, size_m: float) -> str:
    ld = miss_km / 384_400
    if hazard and miss_km < 500_000 and size_m > 100: return "CRITICAL"
    if hazard and ld < 1:                              return "HIGH"
    if hazard or (miss_km < 1_000_000 and size_m > 50): return "ELEVATED"
    if miss_km < 5_000_000:                            return "MODERATE"
    if miss_km < 20_000_000:                           return "WATCH"
    return "LOW"

def orbit_class_label(code: str) -> str:
    labels = {
        "ATE": "Aten  (a < 1.0 AU, perihelion crosses Earth)",
        "APO": "Apollo (a ≥ 1.0 AU, perihelion crosses Earth)",
        "AMO": "Amor  (1.017 < q < 1.3 AU)",
        "IEO": "Interior-Earth Object",
    }
    return labels.get(code, code)

def magnitude_to_size_km(H: float) -> tuple[float, float]:
    """Estimated diameter range from absolute magnitude H (albedo 0.05–0.25)"""
    lo = 1329 / math.sqrt(0.25) * 10 ** (-H / 5)
    hi = 1329 / math.sqrt(0.05) * 10 ** (-H / 5)
    return lo, hi

def observation_window(miss_km: float, size_m: float) -> str:
    """Rough visual magnitude estimate for an Earth flyby at given miss distance."""
    # apparent magnitude: simplified Bowell formula proxy
    r = miss_km / 1_496_000   # AU
    if r < 0.001:
        r = 0.001
    H = 21.81
    phase = 1.0
    V = H + 5 * math.log10(r * r * phase)
    if V < 10:   return f"Naked eye  (V~{V:.1f})"
    if V < 12:   return f"Binoculars (V~{V:.1f})"
    if V < 15:   return f"Small scope (V~{V:.1f})"
    if V < 18:   return f"Amateur scope (V~{V:.1f})"
    if V < 21:   return f"Large amateur (V~{V:.1f})"
    return f"Professional telescope (V~{V:.1f})"


# ─────────────────────────────────────────────
#  PARSE CLOSE APPROACHES
# ─────────────────────────────────────────────
def parse_approaches(raw: list) -> list:
    parsed = []
    for a in raw:
        try:
            parsed.append({
                "date":       a["close_approach_date"],
                "date_full":  a["close_approach_date_full"],
                "epoch_ms":   int(a["epoch_date_close_approach"]),
                "vel_kps":    float(a["relative_velocity"]["kilometers_per_second"]),
                "vel_kph":    float(a["relative_velocity"]["kilometers_per_hour"]),
                "miss_km":    float(a["miss_distance"]["kilometers"]),
                "miss_au":    float(a["miss_distance"]["astronomical"]),
                "miss_lunar": float(a["miss_distance"]["lunar"]),
                "body":       a["orbiting_body"],
            })
        except (KeyError, ValueError):
            continue
    parsed.sort(key=lambda x: x["epoch_ms"])
    return parsed


# ─────────────────────────────────────────────
#  REPORT SECTIONS
# ─────────────────────────────────────────────
def print_identity(data: dict):
    hdr("ASTEROID IDENTITY", "★")
    row("Name",               data.get("name", "?"))
    row("Designation",        data.get("designation", "?"))
    row("NASA ID",            data.get("id", "?"))
    row("JPL URL",            data.get("nasa_jpl_url", "?"), C.c)

    hazard = data.get("is_potentially_hazardous_asteroid", False)
    sentry = data.get("is_sentry_object", False)
    row("Potentially Hazardous",
        "YES ⚠" if hazard else "No",
        C.r if hazard else C.g)
    row("Sentry Object",
        "YES — on impact watchlist" if sentry else "No",
        C.r if sentry else C.g)

    H = data.get("absolute_magnitude_h", 0)
    row("Abs. Magnitude (H)", f"{H:.2f}")
    lo_h, hi_h = magnitude_to_size_km(H)
    row("Size (H-derived, km)", f"{lo_h:.3f} – {hi_h:.3f}  km")

    d = data.get("estimated_diameter", {})
    dm = d.get("meters", {})
    dmin = dm.get("estimated_diameter_min", 0)
    dmax = dm.get("estimated_diameter_max", 0)
    row("Diameter (m)",       f"~{dmin:.0f} – {dmax:.0f} m")
    row("Diameter (km)",      f"~{dmin/1000:.3f} – {dmax/1000:.3f} km")
    row("Diameter (ft)",      f"~{d.get('feet',{}).get('estimated_diameter_min',0):.0f} – {d.get('feet',{}).get('estimated_diameter_max',0):.0f} ft")


def print_orbital(data: dict):
    hdr("ORBITAL MECHANICS", "⊕")
    orb = data.get("orbital_data", {})
    oc  = orb.get("orbit_class", {})

    row("Orbit Class",     f"{oc.get('orbit_class_type','?')}  —  {orbit_class_label(oc.get('orbit_class_type','?'))}")
    row("Orbit ID",        orb.get("orbit_id", "?"))
    row("Orbit Uncertainty", orb.get("orbit_uncertainty","?"),
        C.r if orb.get("orbit_uncertainty","9") > "2" else C.g)
    row("Data Arc",        f"{orb.get('data_arc_in_days',0):,} days  ({int(orb.get('data_arc_in_days',0)/365.25)} years)")
    row("Observations",    str(orb.get("observations_used", "?")))
    row("First Obs.",      orb.get("first_observation_date", "?"))
    row("Last Obs.",       orb.get("last_observation_date", "?"))

    div()
    ecc = float(orb.get("eccentricity", 0))
    sma = float(orb.get("semi_major_axis", 0))
    inc = float(orb.get("inclination", 0))
    per = float(orb.get("orbital_period", 0))
    peri = float(orb.get("perihelion_distance", 0))
    aphe = float(orb.get("aphelion_distance", 0))
    moi  = float(orb.get("minimum_orbit_intersection", 0))
    jti  = float(orb.get("jupiter_tisserand_invariant", 0))

    row("Semi-major Axis",  f"{sma:.6f} AU")
    row("Eccentricity",     f"{ecc:.6f}  {'(highly elliptical)' if ecc>0.5 else ''}")
    row("Inclination",      f"{inc:.4f}°")
    row("Orbital Period",   f"{per:.2f} days  ({per/365.25:.3f} years)")
    row("Perihelion (q)",   f"{peri:.6f} AU  ({peri*149.6e6:,.0f} km)")
    row("Aphelion  (Q)",    f"{aphe:.6f} AU  ({aphe*149.6e6:,.0f} km)")
    row("Min. Orbit Int.",  f"{moi:.6f} AU  ({float(moi)*149600:.0f} km)", C.r if float(moi) < 0.05 else C.y)
    row("Jupiter TI",       f"{jti:.3f}  (>3 = asteroid, <3 = comet-like)")
    row("Ascending Node Ω", f"{float(orb.get('ascending_node_longitude',0)):.4f}°")
    row("Arg. of Perihelion ω", f"{float(orb.get('perihelion_argument',0)):.4f}°")
    row("Mean Motion",      f"{float(orb.get('mean_motion',0)):.6f} °/day")
    row("Equinox",          orb.get("equinox","?"))


def print_approach_stats(approaches: list, size_m: float):
    hdr("CLOSE APPROACH STATISTICS", "◎")
    total  = len(approaches)
    earth  = [a for a in approaches if a["body"] == "Earth"]
    venus  = [a for a in approaches if a["body"] == "Venus"]
    merc   = [a for a in approaches if a["body"] == "Merc"]

    row("Total Approaches Logged",   f"{total:,}")
    row("  → Earth approaches",      f"{len(earth):,}")
    row("  → Venus approaches",      f"{len(venus):,}")
    row("  → Mercury approaches",    f"{len(merc):,}")

    if earth:
        earth_miss = [a["miss_km"] for a in earth]
        earth_vel  = [a["vel_kps"] for a in earth]
        closest    = min(earth, key=lambda x: x["miss_km"])
        farthest   = max(earth, key=lambda x: x["miss_km"])
        fastest    = max(earth, key=lambda x: x["vel_kps"])
        slowest    = min(earth, key=lambda x: x["vel_kps"])
        div()
        row("EARTH APPROACH ANALYSIS", "", lambda x: x)
        row("Closest approach",
            f"{closest['miss_km']:>14,.0f} km  /  {closest['miss_lunar']:.2f} LD  on {closest['date_full']}",
            C.r if closest["miss_km"] < 1_000_000 else C.y)
        row("Farthest approach",
            f"{farthest['miss_km']:>14,.0f} km  on {farthest['date_full']}")
        row("Average miss distance",
            f"{sum(earth_miss)/len(earth_miss):>14,.0f} km")
        row("Median miss distance",
            f"{sorted(earth_miss)[len(earth_miss)//2]:>14,.0f} km")
        row("Fastest approach",
            f"{fastest['vel_kps']:.3f} km/s  on {fastest['date_full']}", C.r)
        row("Slowest approach",
            f"{slowest['vel_kps']:.3f} km/s  on {slowest['date_full']}")
        row("Avg velocity (Earth)",
            f"{sum(earth_vel)/len(earth_vel):.3f} km/s")

        within_ld   = [a for a in earth if a["miss_lunar"] < 10]
        within_1m   = [a for a in earth if a["miss_km"] < 1_000_000]
        row("Approaches < 10 LD",
            f"{len(within_ld)}",
            C.r if within_ld else C.g)
        row("Approaches < 1M km",
            f"{len(within_1m)}",
            C.r if within_1m else C.g)


def print_upcoming(approaches: list, size_m: float, target_body: str = None,
                   future_only: bool = False, limit: int = 20):
    now_ms  = int(datetime.now(timezone.utc).timestamp() * 1000)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    filtered = [a for a in approaches if a["epoch_ms"] >= now_ms]
    if target_body:
        filtered = [a for a in filtered if a["body"].lower() == target_body.lower()]

    label = f"UPCOMING APPROACHES{'  ('+target_body.upper()+' only)' if target_body else ''}"
    hdr(label, "◉")

    if not filtered:
        print(C.d("    No upcoming approaches found."))
        return

    print(C.d(f"    {'DATE':<22} {'BODY':<8} {'MISS (km)':>15} {'MISS (LD)':>9} {'VEL km/s':>9}  {'THREAT':<10} VISIBILITY"))
    print(C.d(f"    {'─'*22} {'─'*7} {'─'*15} {'─'*9} {'─'*9}  {'─'*10} {'─'*22}"))

    shown = 0
    for a in filtered:
        if shown >= limit:
            remaining = len(filtered) - shown
            print(C.d(f"    ... and {remaining} more approaches through 2200"))
            break

        body  = a["body"]
        miss  = a["miss_km"]
        lunar = a["miss_lunar"]
        vel   = a["vel_kps"]
        t     = threat(miss, True, size_m)  # PK9 is PHA so always pass hazard=True
        tcol  = THREAT_COLORS.get(t, C.g)
        obs   = observation_window(miss, size_m) if body == "Earth" else C.d("—")

        body_col = C.b(C.BLU + body + C.R) if body == "Earth" else C.d(body)

        miss_col = tcol(f"{miss:>15,.0f}")
        ld_col   = tcol(f"{lunar:>9.2f}")
        vel_col  = C.m(f"{vel:>9.3f}")
        t_col    = tcol(f"{t:<10}")

        print(f"    {C.c(a['date_full'][:22]+'  ')}{body_col:<8} {miss_col} {ld_col} {vel_col}  {t_col} {obs}")
        shown += 1


def print_closest_earth(approaches: list, size_m: float, n: int = 10):
    earth = [a for a in approaches if a["body"] == "Earth"]
    earth.sort(key=lambda x: x["miss_km"])
    hdr(f"TOP {n} CLOSEST EARTH APPROACHES (ALL TIME)", "⚠")

    print(C.d(f"    {'RANK':<5} {'DATE':<22} {'MISS (km)':>15} {'MISS (LD)':>9} {'VEL km/s':>9}  {'THREAT':<10}"))
    print(C.d(f"    {'─'*5} {'─'*22} {'─'*15} {'─'*9} {'─'*9}  {'─'*10}"))

    for i, a in enumerate(earth[:n], 1):
        miss  = a["miss_km"]
        lunar = a["miss_lunar"]
        t     = threat(miss, True, size_m)
        tcol  = THREAT_COLORS.get(t, C.g)
        rank  = C.r(f"  #{i:<3}") if i <= 3 else C.d(f"  #{i:<3}")
        vel_str = f"{a['vel_kps']:>9.3f}"
        print(f"    {rank} {C.c(a['date_full'][:22]+'  ')}{tcol(f'{miss:>15,.0f}')} {tcol(f'{lunar:>9.2f}')} {C.m(vel_str)}  {tcol(t)}")


def print_body_breakdown(approaches: list):
    hdr("APPROACH BREAKDOWN BY BODY", "◆")
    bodies = {}
    for a in approaches:
        b = a["body"]
        bodies.setdefault(b, []).append(a)

    for body, lst in sorted(bodies.items(), key=lambda x: -len(x[1])):
        miss_vals = [a["miss_km"] for a in lst]
        vel_vals  = [a["vel_kps"] for a in lst]
        avg_miss  = sum(miss_vals) / len(miss_vals)
        min_miss  = min(miss_vals)
        avg_vel   = sum(vel_vals) / len(vel_vals)

        ratio = len(lst) / len(approaches)
        print(f"\n    {C.b(C.BLU+body+C.R) if body=='Earth' else C.c(body):<20} {C.g(str(len(lst))):>4} approaches")
        print(f"      {bar(ratio, 30)} {C.d(f'{ratio*100:.1f}% of total')}")
        print(f"      Closest: {C.y(f'{min_miss:,.0f} km')}  |  Avg miss: {C.d(f'{avg_miss:,.0f} km')}  |  Avg vel: {C.m(f'{avg_vel:.2f} km/s')}")


def print_decade_histogram(approaches: list):
    """Show frequency of Earth approaches per decade."""
    earth = [a for a in approaches if a["body"] == "Earth"]
    hdr("EARTH APPROACH FREQUENCY BY DECADE", "▦")

    decades: dict[int, list] = {}
    for a in earth:
        try:
            yr = int(a["date"][:4])
            d  = (yr // 10) * 10
            decades.setdefault(d, []).append(a)
        except ValueError:
            continue

    max_count = max(len(v) for v in decades.values()) if decades else 1
    for decade in sorted(decades.keys()):
        lst   = decades[decade]
        count = len(lst)
        width = round((count / max_count) * 35)
        closest = min(lst, key=lambda x: x["miss_km"])
        flag = C.r(" ◀ CLOSE") if closest["miss_km"] < 5_000_000 else ""
        print(f"    {C.d(str(decade)+'s'):<12} {C.g('█' * width + '░' * (35-width))} {C.c(str(count).rjust(2))}{flag}")


def print_observation_guide(data: dict, approaches: list, size_m: float):
    hdr("OBSERVATION GUIDE", "🔭")
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    earth_upcoming = sorted(
        [a for a in approaches if a["body"] == "Earth" and a["epoch_ms"] >= now_ms],
        key=lambda x: x["miss_km"]
    )

    orb = data.get("orbital_data", {})
    per = float(orb.get("orbital_period", 0))
    inc = float(orb.get("inclination", 0))
    ecc = float(orb.get("eccentricity", 0))
    peri = float(orb.get("perihelion_distance", 0))

    print(f"    {C.b('Object class:')}      Aten-type NEA (crosses Earth orbit)")
    print(f"    {C.b('Orbital period:')}    {per:.1f} days ({per/365.25:.2f} years)")
    print(f"    {C.b('Inclination:')}       {inc:.2f}°  {'(low — favorable for observation)' if inc < 20 else '(elevated — harder to track)'}")
    print(f"    {C.b('Eccentricity:')}      {ecc:.3f}  (highly elliptical — fast at perihelion)")
    print(f"    {C.b('Perihelion:')}        {peri:.4f} AU  — spends time inside Venus orbit")
    print(f"    {C.b('Best approach body:')} Earth and Venus")

    div()
    print(f"    {C.b('UPCOMING EARTH WINDOWS (closest first):')}")
    for a in earth_upcoming[:5]:
        vis = observation_window(a["miss_km"], size_m)
        t   = threat(a["miss_km"], True, size_m)
        tcol = THREAT_COLORS.get(t, C.g)
        print(f"\n      {C.c(a['date_full'])}  —  threat: {tcol(t)}")
        miss_s = f"{a['miss_km']:,.0f} km"
        vel_s = f"{a['vel_kps']:.3f} km/s"
        print(f"      Miss: {C.y(miss_s)}  ({a['miss_lunar']:.2f} LD)  |  {C.m(vel_s)}")
        print(f"      Visibility: {C.g(vis)}")
        print(f"      {C.d('Tip: Track RA/Dec from JPL Horizons system closest to this date.')}")

    div()
    print(f"    {C.d('Telescope planning:')}")
    print(f"      • Use JPL Horizons: https://ssd.jpl.nasa.gov/horizons/")
    print(f"      • Object ID: {data.get('id')} (or search \"{data.get('designation')}\")")
    print(f"      • Set observer location + time window for ephemeris")
    print(f"      • Recommend 15-min cadence imaging for fast flyby")
    print(f"      • Cross-check with MPC: https://www.minorplanetcenter.net/")


def export_report(data: dict, approaches: list, size_m: float):
    fname = f"asteroid_{data.get('designation','report').replace(' ','_')}.txt"
    # Redirect stdout trick
    import io
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf

    # strip ANSI for file
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    run_report(data, approaches, size_m, export=False)
    sys.stdout = old_stdout
    clean = ansi_escape.sub('', buf.getvalue())
    with open(fname, 'w') as f:
        f.write(clean)
    print(C.g(f"  ✓ Report saved to: {fname}"))


def plot_miss_distances(approaches: list):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print(C.r("  [ERR] matplotlib not installed. Run: pip install matplotlib"))
        return

    earth = [a for a in approaches if a["body"] == "Earth"]
    dates = [datetime.fromisoformat(a["date"]) for a in earth]
    miss  = [a["miss_km"] / 1_000_000 for a in earth]   # in millions km
    vels  = [a["vel_kps"] for a in earth]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), facecolor="#050a05",
                                    gridspec_kw={"height_ratios":[3,1]})

    for ax in (ax1, ax2):
        ax.set_facecolor("#030803")
        for spine in ax.spines.values():
            spine.set_color("#1a3a1a")
        ax.tick_params(colors="#2a6a2a", labelsize=9)
        ax.yaxis.label.set_color("#4adf4a")
        ax.xaxis.label.set_color("#4adf4a")
        ax.title.set_color("#00e040")

    colors = ["#ff2200" if m < 5 else "#ffaa00" if m < 20 else "#00cc44"
              for m in miss]
    ax1.scatter(dates, miss, c=colors, s=15, zorder=3, alpha=0.85)
    ax1.axhline(y=1, color="#ff2200", linestyle="--", linewidth=0.7, alpha=0.5, label="1M km")
    ax1.axhline(y=5, color="#ffaa00", linestyle="--", linewidth=0.7, alpha=0.5, label="5M km")
    ax1.axhline(y=0.384, color="#ff0000", linestyle=":", linewidth=1.2, alpha=0.7, label="1 LD")
    ax1.set_ylabel("Miss Distance (million km)")
    ax1.set_title(f"Earth Approaches: {data_global.get('name','(2010 PK9)')} — {len(earth)} events, 1900–2200")
    ax1.legend(facecolor="#030803", edgecolor="#1a3a1a", labelcolor="#4adf4a", fontsize=8)
    ax1.grid(color="#0a1a0a", linewidth=0.5, zorder=0)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax2.scatter(dates, vels, c="#00cc88", s=10, zorder=3, alpha=0.7)
    ax2.set_ylabel("Velocity (km/s)")
    ax2.set_xlabel("Year")
    ax2.grid(color="#0a1a0a", linewidth=0.5, zorder=0)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    fname = "asteroid_plot.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight", facecolor="#050a05")
    plt.show()
    print(C.g(f"  ✓ Plot saved: {fname}"))


# ─────────────────────────────────────────────
#  FULL REPORT RUNNER
# ─────────────────────────────────────────────
data_global = {}   # used by plot function

def run_report(data: dict, approaches: list, size_m: float,
               target_body: str = None, future_only: bool = False,
               export: bool = False):
    banner()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"  {C.d('Generated:')} {C.g(now)} UTC")
    print(f"  {C.d('Source:')}    {C.c('nasa.json')}  "
          f"{C.d('|')}  {C.d('Total approaches:')} {C.g(str(len(approaches)))}")

    print_identity(data)
    section_break()
    print_orbital(data)
    section_break()
    print_approach_stats(approaches, size_m)
    section_break()
    print_closest_earth(approaches, size_m)
    section_break()
    print_body_breakdown(approaches)
    section_break()
    print_decade_histogram(approaches)
    section_break()
    print_upcoming(approaches, size_m, target_body=target_body,
                   future_only=future_only, limit=25)
    section_break()
    print_observation_guide(data, approaches, size_m)

    print(f"\n  {C.d('─'*(W-4))}")
    print(f"  {C.d('END OF REPORT')}  {C.g('●')}  "
          f"{C.d('Data: NASA JPL NEO API  |  asteroid_observer.py v2.0')}\n")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Asteroid Observation System")
    parser.add_argument("--json",    default="nasa.json",  help="Path to NASA JSON file")
    parser.add_argument("--target",  default=None,         help="Filter by orbiting body (e.g. Earth, Venus, Merc)")
    parser.add_argument("--future",  action="store_true",  help="Show future approaches only")
    parser.add_argument("--export",  action="store_true",  help="Export plain-text report to .txt file")
    parser.add_argument("--plot",    action="store_true",  help="Plot miss distances (requires matplotlib)")
    args = parser.parse_args()

    data = load_json(args.json)
    data_global = data

    approaches = parse_approaches(data.get("close_approach_data", []))
    d_m = data.get("estimated_diameter", {}).get("meters", {})
    size_m = d_m.get("estimated_diameter_max", 258.0)

    if args.export:
        export_report(data, approaches, size_m)
    elif args.plot:
        plot_miss_distances(approaches)
    else:
        run_report(
            data, approaches, size_m,
            target_body=args.target,
            future_only=args.future,
            export=False,
        )