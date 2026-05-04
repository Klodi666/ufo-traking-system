import sys
import os
import time
import random
import threading
import logging
import json
import hashlib
import argparse
from datetime import datetime
from collections import Counter
from itertools import cycle

# Advanced Persistence Layer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ─────────────────────────────────────────────────────────────
#  TERMINAL COLOR PALETTE  (256-color + bold)
# ─────────────────────────────────────────────────────────────
RST  = "\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"

# Foreground
G    = "\033[1;32m"   # matrix green
LG   = "\033[0;32m"   # dim green
R    = "\033[1;31m"   # alert red
LR   = "\033[0;31m"   # dim red
B    = "\033[1;34m"   # blue
C    = "\033[1;36m"   # cyan
LC   = "\033[0;36m"   # dim cyan
Y    = "\033[1;33m"   # yellow
M    = "\033[1;35m"   # magenta
W    = "\033[1;37m"   # white
GR   = "\033[0;37m"   # grey

# ─────────────────────────────────────────────────────────────
#  GLOBAL CONFIG
# ─────────────────────────────────────────────────────────────
DB_URL        = "sqlite:///uap_intelligence_full.db"
EXPORT_FILE   = "intel_export.json"
LOG_FILE      = "uap_intel.log"
VERSION       = "4.2.1-CLASSIFIED"
BUILD_HASH    = hashlib.md5(VERSION.encode()).hexdigest().upper()
SCAN_INTERVAL = (1.5, 5.0)   # seconds between intercepts
HUD_INTERVAL  = 18           # seconds between HUD redraws

# ─────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────
LOG_FORMAT = f"{LG}[%(asctime)s]{RST} %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ]
)
logger = logging.getLogger("PHANTOM-GRID")

# ─────────────────────────────────────────────────────────────
#  DATABASE SCHEMA
# ─────────────────────────────────────────────────────────────
Base = declarative_base()

class IntelligenceEntry(Base):
    __tablename__ = "intel_reports"
    id               = Column(Integer, primary_key=True)
    timestamp        = Column(DateTime, default=datetime.utcnow)
    uid              = Column(String)        # unique intercept hash
    country          = Column(String)
    city             = Column(String)
    geolocation      = Column(String)
    signature_type   = Column(String)
    classification   = Column(String)       # UNCLASSIFIED / CONFIDENTIAL / TOP SECRET
    velocity_index   = Column(Float)
    altitude_km      = Column(Float)
    threat_level     = Column(Integer)
    threat_tier      = Column(String)       # GREEN / YELLOW / RED / BLACK
    is_anomaly       = Column(Boolean, default=False)
    decrypted_payload= Column(Text)
    signal_hash      = Column(String)       # SHA-256 fingerprint

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# ─────────────────────────────────────────────────────────────
#  HELPER UTILITIES
# ─────────────────────────────────────────────────────────────
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def glitch_text(text: str, intensity: int = 2) -> str:
    """Randomly corrupt a few characters for a glitch effect."""
    glitch_chars = "█▓▒░▄▀■□●○◆◇"
    chars = list(text)
    for _ in range(intensity):
        if chars:
            idx = random.randint(0, len(chars) - 1)
            chars[idx] = random.choice(glitch_chars)
    return "".join(chars)

def typewrite(text: str, delay: float = 0.03, color: str = G):
    """Print text one character at a time like a terminal."""
    for ch in text:
        sys.stdout.write(color + ch + RST)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def decrypt_animation(label: str, length: int = 32, steps: int = 8):
    """Animate a fake decryption bar."""
    chars = "0123456789ABCDEF"
    sys.stdout.write(f"  {LC}[DECRYPTING {label}]{RST}  ")
    for i in range(steps):
        fake = "".join(random.choices(chars, k=length))
        display = (G if i == steps - 1 else Y) + fake + RST
        sys.stdout.write(f"\r  {LC}[DECRYPTING {label}]{RST}  {display}")
        sys.stdout.flush()
        time.sleep(0.06)
    print()

def signal_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16].upper()

def tier_color(tier: str) -> str:
    return {
        "GREEN":  G,
        "YELLOW": Y,
        "RED":    R,
        "BLACK":  M,
    }.get(tier, W)

def get_tier(threat: int) -> str:
    if threat < 30:  return "GREEN"
    if threat < 55:  return "YELLOW"
    if threat < 80:  return "RED"
    return "BLACK"

def get_classification(threat: int) -> str:
    if threat < 30:  return "UNCLASSIFIED"
    if threat < 55:  return "CONFIDENTIAL"
    if threat < 80:  return "SECRET"
    return "TOP SECRET // SCI"

# ─────────────────────────────────────────────────────────────
#  SPLASH SCREEN
# ─────────────────────────────────────────────────────────────
BANNER = f"""
{M}
 ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗
 ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║
 ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
 ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
 ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
 ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝
{RST}{C}         G R I D   ·   U A P   I N T E L L I G E N C E   S U I T E{RST}
{GR}         version {VERSION}  ·  build {BUILD_HASH[:8]}{RST}
"""

# ─────────────────────────────────────────────────────────────
#  INTELLIGENCE ENGINE
# ─────────────────────────────────────────────────────────────
class PhantomGridSuite:
    def __init__(self, verbose: bool = False, export: bool = False):
        self.session  = Session()
        self.active   = True
        self.verbose  = verbose
        self.export   = export
        self.lock     = threading.Lock()
        self.intercept_count = 0
        self.anomaly_count   = 0

        # ── Geospatial Recon Nodes ──────────────────────────────
        self.geo_nodes = [
            {"country": "USA",       "city": "Nevada / Area 51",    "coords": "37.2343 N, 115.8067 W"},
            {"country": "USA",       "city": "Skinwalker Ranch",     "coords": "40.2571 N, 109.8928 W"},
            {"country": "Russia",    "city": "Kapustin Yar",         "coords": "48.5780 N, 45.7800 E"},
            {"country": "Russia",    "city": "Tunguska Basin",       "coords": "60.9170 N, 101.9530 E"},
            {"country": "Australia", "city": "Wycliffe Well",        "coords": "20.7761 S, 134.2415 E"},
            {"country": "UK",        "city": "Rendlesham Forest",    "coords": "52.0930 N, 1.4350 E"},
            {"country": "UK",        "city": "Bonnybridge",          "coords": "56.0020 N, 3.8860 W"},
            {"country": "Chile",     "city": "San Clemente",         "coords": "35.5333 S, 71.4833 W"},
            {"country": "Japan",     "city": "Mount Fuji",           "coords": "35.3606 N, 138.7274 E"},
            {"country": "Brazil",    "city": "Varginha",             "coords": "21.5511 S, 45.4303 W"},
            {"country": "Mexico",    "city": "Gulf of Mexico",       "coords": "25.0000 N, 90.0000 W"},
            {"country": "Norway",    "city": "Hessdalen Valley",     "coords": "62.8167 N, 11.1833 E"},
            {"country": "Iran",      "city": "Tehran Air Corridor",  "coords": "35.6892 N, 51.3890 E"},
            {"country": "China",     "city": "Gobi Desert Sector-7", "coords": "42.5000 N, 102.0000 E"},
            {"country": "INTL",      "city": "Pacific Fleet Zone",   "coords": "28.0000 N, 142.0000 E"},
            {"country": "INTL",      "city": "Atlantic Deep-Water",  "coords": "35.0000 N, 45.0000 W"},
        ]

        # ── Signal Signatures ────────────────────────────────────
        self.signatures = [
            "TRIANGULAR",     "KINETIC-ORB",     "TIC-TAC",
            "TRANSMEDIUM",    "HIVE-MIND-NODE",  "DELTA-WING",
            "LUMINOUS-RING",  "CUBE-IN-SPHERE",  "TETRAHEDRON",
            "PLASMA-CLOUD",   "MORPHIC-SWARM",   "BLACK-CHEVRON",
        ]

        # ── Decrypted Payloads ───────────────────────────────────
        self.payloads = [
            "Non-ballistic trajectory confirmed. Object defies Newtonian physics.",
            "Signal pattern suggests non-human sentient origin.",
            "Electronic warfare countermeasures detected. GPS blackout radius: 40 km.",
            "Signature bypasses standard IFF transponder protocols.",
            "Atmospheric ionization localized around object. EM pulse imminent.",
            "Craft entered transmedium phase — air-to-subsurface in 0.3 seconds.",
            "Gravity wave distortion detected. Spacetime metric anomaly flagged.",
            "Radio emission encoded — partial decode: repeating prime sequence.",
            "Object split into six sub-craft; regrouped without velocity loss.",
            "Heat signature: ZERO. Object is thermally invisible to FLIR.",
            "Radar cross-section oscillates between 0 and ∞. Stealth mode active.",
            "Military comms blackout correlated with object proximity.",
            "Witness EEG disruption logged. Neurological effect suspected.",
            "Object reversed vector at Mach 32 without deceleration event.",
        ]

        # ── Operator Messages (printed during slow intervals) ────
        self.operator_msgs = [
            "Standing by for confirmation from SECTOR-7 relay...",
            "Cross-referencing against NORAD ephemeris database...",
            "Signal triangulated — awaiting satellite imagery pass...",
            "Uplink to NSA PRISM node: STABLE",
            "Running pattern match against 1952–2024 historical database...",
            "No human-made propulsion system matches current velocity profile.",
            "Consulting allied AARO database... ACCESS GRANTED.",
            "Passive SIGINT sweep in progress across 2.4 GHz — 300 GHz band...",
        ]

    # ── Threat Heuristics ─────────────────────────────────────
    def _calculate_threat(self, v_idx: float, sig: str, altitude: float) -> int:
        base = random.randint(5, 20)
        if v_idx > 15.0:                              base += 35
        elif v_idx > 8.0:                             base += 15
        if sig in ("TIC-TAC", "HIVE-MIND-NODE",
                   "CUBE-IN-SPHERE", "MORPHIC-SWARM"): base += 30
        if altitude < 0.5:                            base += 20   # near-ground
        if altitude > 80.0:                           base += 10   # near-space
        return min(base + random.randint(0, 10), 100)

    # ── Continuous Intercept Stream ───────────────────────────
    def intercept_stream(self):
        while self.active:
            node      = random.choice(self.geo_nodes)
            sig       = random.choice(self.signatures)
            v_idx     = round(random.uniform(0.05, 48.0), 2)
            altitude  = round(random.uniform(0.0, 120.0), 2)
            threat    = self._calculate_threat(v_idx, sig, altitude)
            tier      = get_tier(threat)
            classif   = get_classification(threat)
            uid_raw   = f"{node['city']}{sig}{v_idx}{time.time()}"
            uid       = hashlib.md5(uid_raw.encode()).hexdigest()[:10].upper()
            s_hash    = signal_hash(uid_raw)
            payload   = random.choice(self.payloads)

            entry = IntelligenceEntry(
                uid=uid,
                country=node["country"],
                city=node["city"],
                geolocation=node["coords"],
                signature_type=sig,
                classification=classif,
                velocity_index=v_idx,
                altitude_km=altitude,
                threat_level=threat,
                threat_tier=tier,
                is_anomaly=(threat > 70),
                decrypted_payload=payload,
                signal_hash=s_hash,
            )

            with self.lock:
                self.session.add(entry)
                self.session.commit()
                self.intercept_count += 1
                if entry.is_anomaly:
                    self.anomaly_count += 1

            tc = tier_color(tier)
            logger.info(
                f"{LC}UID:{uid}{RST}  {C}[{node['country']:>4}]{RST}"
                f"  {Y}{sig:<18}{RST}"
                f"  THR:{tc}{threat:>3}%{RST}"
                f"  V:{W}{v_idx:>5} Mach{RST}"
                f"  ALT:{GR}{altitude:>6} km{RST}"
                f"  [{tc}{tier}{RST}]"
            )

            if self.verbose:
                logger.info(f"  {DIM}↳ {payload}{RST}")

            # Occasional operator message
            if random.random() < 0.12:
                logger.info(f"  {DIM}{random.choice(self.operator_msgs)}{RST}")

            # Auto-export on anomaly
            if entry.is_anomaly and self.export:
                self._export_to_json()

            time.sleep(random.uniform(*SCAN_INTERVAL))

    # ── HUD: Periodic Intelligence Briefing ──────────────────
    def render_hud(self):
        spinner = cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        while self.active:
            for _ in range(HUD_INTERVAL * 4):
                if not self.active: return
                sys.stdout.write(f"\r  {G}{next(spinner)}{RST} {GR}Scanning global airspace...{RST}")
                sys.stdout.flush()
                time.sleep(0.25)

            with self.lock:
                data = self.session.query(IntelligenceEntry).all()
            if not data:
                continue

            anomalies  = [r for r in data if r.is_anomaly]
            locations  = Counter(r.country for r in data)
            sigs       = Counter(r.signature_type for r in data)
            avg_threat = sum(r.threat_level for r in data) / len(data)
            top_sig    = sigs.most_common(1)[0]
            top_loc    = locations.most_common(1)[0]
            last       = data[-1]
            last_anom  = anomalies[-1] if anomalies else None

            W80 = "═" * 62
            print(f"\n{B}╔{W80}╗{RST}")
            print(f"{B}║{RST}{M}{'  ▓▓ PHANTOM-GRID  ·  GLOBAL UAP INTELLIGENCE CONSOLE  ▓▓':^62}{RST}{B}║{RST}")
            print(f"{B}║{RST}{GR}{'  version ' + VERSION:^62}{RST}{B}║{RST}")
            print(f"{B}╠{W80}╣{RST}")
            # System stats
            print(f"{B}║{RST}  {GR}SYSTEM_TIME   {RST}{W}{datetime.now().strftime('%Y-%m-%d  %H:%M:%S UTC'):<46}{RST}{B}║{RST}")
            print(f"{B}║{RST}  {GR}SESSION_UPLINK{RST}  {G}● SECURE  AES-256  TLS-1.3{RST}{'':>30}{B}║{RST}")
            print(f"{B}║{RST}  {GR}DB_RECORDS    {RST}  {C}{len(data):<55}{RST}{B}║{RST}")
            print(f"{B}╠{W80}╣{RST}")
            # Intelligence summary
            print(f"{B}║{RST}  {Y}ACTIVE_SIGNALS  {RST}{W}{self.intercept_count:<47}{RST}{B}║{RST}")
            print(f"{B}║{RST}  {R}ANOMALY_ALERTS  {RST}{R}{self.anomaly_count:<47}{RST}{B}║{RST}")
            print(f"{B}║{RST}  {GR}AVG_THREAT_LVL {RST}{Y}{avg_threat:.1f}%{RST}{'':>51}{B}║{RST}")
            print(f"{B}║{RST}  {GR}PRIMARY_HOTSPOT {RST}{Y}{top_loc[0]} ({top_loc[1]} hits){'':>39}{RST}{B}║{RST}")
            print(f"{B}║{RST}  {GR}TOP_SIGNATURE   {RST}{C}{top_sig[0]} ({top_sig[1]} detected){'':>35}{RST}{B}║{RST}")
            print(f"{B}╠{W80}╣{RST}")
            # Tier breakdown
            tiers = Counter(r.threat_tier for r in data)
            for t in ("GREEN", "YELLOW", "RED", "BLACK"):
                bar_len = int((tiers.get(t, 0) / len(data)) * 30)
                bar = tier_color(t) + "█" * bar_len + GR + "░" * (30 - bar_len) + RST
                print(f"{B}║{RST}  {tier_color(t)}{t:<7}{RST}  {bar}  {GR}{tiers.get(t,0):>4} events{RST}{'':>6}{B}║{RST}")
            print(f"{B}╠{W80}╣{RST}")
            # Latest intercept
            print(f"{B}║{RST}  {GR}LAST_SIGNAL     {RST}{LC}{last.uid}{RST}  {W}{last.city}{RST}{'':>20}{B}║{RST}")
            # Latest anomaly
            if last_anom:
                print(f"{B}║{RST}  {R}LATEST_ALARM    {RST}{R}{last_anom.city}  [{last_anom.signature_type}]{RST}{'':>15}{B}║{RST}")
                short_pay = last_anom.decrypted_payload[:50] + "..."
                print(f"{B}║{RST}  {GR}INTEL_FRAGMENT  {RST}{M}\"{short_pay}\"{RST}{'':>0}{B}║{RST}")
            print(f"{B}╚{W80}╝{RST}\n")

    # ── Threat Alarm: fires on BLACK-tier events ──────────────
    def alarm_monitor(self):
        seen_uids = set()
        while self.active:
            time.sleep(3)
            with self.lock:
                entries = self.session.query(IntelligenceEntry).filter_by(threat_tier="BLACK").all()
            for e in entries:
                if e.uid not in seen_uids:
                    seen_uids.add(e.uid)
                    print(f"\n{M}{'▌':>4} !!  BLACK-TIER ANOMALY DETECTED  !!{'':>4}▐{RST}")
                    print(f"{M}{'':>4}  UID: {e.uid}   LOC: {e.city}{RST}")
                    print(f"{M}{'':>4}  SIG: {e.signature_type}   V-IDX: {e.velocity_index} Mach{RST}")
                    print(f"{M}{'':>4}  ↳  {e.decrypted_payload}{RST}\n")

    # ── JSON Export ──────────────────────────────────────────
    def _export_to_json(self):
        with self.lock:
            data = self.session.query(IntelligenceEntry).all()
        records = [
            {
                "uid":          r.uid,
                "timestamp":    r.timestamp.isoformat() if r.timestamp else None,
                "country":      r.country,
                "city":         r.city,
                "coords":       r.geolocation,
                "signature":    r.signature_type,
                "classification": r.classification,
                "velocity_mach": r.velocity_index,
                "altitude_km":  r.altitude_km,
                "threat_level": r.threat_level,
                "threat_tier":  r.threat_tier,
                "is_anomaly":   r.is_anomaly,
                "payload":      r.decrypted_payload,
                "signal_hash":  r.signal_hash,
            }
            for r in data
        ]
        with open(EXPORT_FILE, "w") as f:
            json.dump(records, f, indent=2)
        logger.info(f"{G}[EXPORT] {len(records)} records written → {EXPORT_FILE}{RST}")

    # ── Scheduled Export Thread ──────────────────────────────
    def export_scheduler(self, interval: int = 60):
        while self.active:
            time.sleep(interval)
            self._export_to_json()

    # ── Top-10 Report ────────────────────────────────────────
    def print_top_threats(self):
        with self.lock:
            rows = (
                self.session.query(IntelligenceEntry)
                .order_by(IntelligenceEntry.threat_level.desc())
                .limit(10)
                .all()
            )
        if not rows:
            return
        print(f"\n{Y}  ┌── TOP-10 THREAT EVENTS ─────────────────────────────┐{RST}")
        for i, r in enumerate(rows, 1):
            tc = tier_color(r.threat_tier)
            print(f"  {GR}#{i:>2}{RST}  {tc}{r.threat_level:>3}%{RST}  {C}{r.signature_type:<18}{RST}  {W}{r.city}{RST}")
        print(f"{Y}  └─────────────────────────────────────────────────────┘{RST}\n")

    # ── Boot Sequence ────────────────────────────────────────
    def boot_sequence(self):
        clear()
        print(BANNER)
        time.sleep(0.3)

        steps = [
            ("KERNEL",   f"Loading phantom-grid OS kernel...     {G}OK{RST}"),
            ("CRYPTO",   f"Initializing AES-256 / RSA-4096...    {G}OK{RST}"),
            ("DATABASE", f"Persistent SQLite uplink: {DB_URL}"),
            ("GEOSCAN",  f"Geospatial nodes loaded: {G}{len(self.geo_nodes)}{RST} sectors"),
            ("SIGS",     f"Signature library: {G}{len(self.signatures)}{RST} profiles"),
            ("THREADS",  f"Spawning intercept + HUD + alarm threads..."),
            ("UPLINK",   f"Uplink status: {G}● SECURE{RST}  {GR}[TLS-1.3]{RST}"),
        ]
        for tag, msg in steps:
            sys.stdout.write(f"  {LC}[{tag:<8}]{RST}  ")
            sys.stdout.flush()
            time.sleep(random.uniform(0.15, 0.45))
            print(msg)

        decrypt_animation("MASTER-KEY", length=40, steps=10)
        print()
        typewrite("  ► PHANTOM-GRID ONLINE. COMMENCING GLOBAL SIGNAL INTERCEPTION.", delay=0.02, color=G)
        print()
        time.sleep(0.5)

# ─────────────────────────────────────────────────────────────
#  CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="Phantom-Grid UAP Intelligence Suite")
    p.add_argument("--verbose",  "-v", action="store_true", help="Print decrypted payloads inline")
    p.add_argument("--export",   "-e", action="store_true", help="Auto-export JSON on anomaly + every 60s")
    p.add_argument("--top",      "-t", action="store_true", help="Print top-10 threat report on exit")
    p.add_argument("--interval", "-i", type=float, default=None, help="Override scan interval (seconds)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()

    if args.interval:
        SCAN_INTERVAL = (args.interval * 0.5, args.interval * 1.5)

    suite = PhantomGridSuite(verbose=args.verbose, export=args.export)
    suite.boot_sequence()

    threads = [
        threading.Thread(target=suite.intercept_stream,  daemon=True, name="INTERCEPT"),
        threading.Thread(target=suite.render_hud,        daemon=True, name="HUD"),
        threading.Thread(target=suite.alarm_monitor,     daemon=True, name="ALARM"),
    ]
    if args.export:
        threads.append(threading.Thread(target=suite.export_scheduler, daemon=True, name="EXPORT"))

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        suite.active = False
        print(f"\n\n  {R}[!] OPERATOR DISCONNECTED — INITIATING SECURE SHUTDOWN...{RST}")
        time.sleep(0.4)

        if args.top:
            suite.print_top_threats()

        if args.export:
            suite._export_to_json()

        print(f"  {GR}[✓] Session log saved → {LOG_FILE}{RST}")
        print(f"  {GR}[✓] Database closed.{RST}")
        print(f"  {M}[PHANTOM-GRID OFFLINE]{RST}\n")
        sys.exit(0)