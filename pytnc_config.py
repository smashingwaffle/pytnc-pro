#!/usr/bin/env python3
"""
PyTNC Pro - Configuration and Constants

Contains paths, audio settings, and device databases.
All paths are relative to BASE_DIR for portability.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# =============================================================================
# Paths - All relative to BASE_DIR for portability
# =============================================================================

# Detect if running as frozen exe (PyInstaller)
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BASE_DIR = Path(sys.executable).resolve().parent
    # PyInstaller stores bundled data in sys._MEIPASS
    BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', BASE_DIR))
else:
    # Running as script
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

def _find_path(name: str) -> Path:
    """Find data path - check BUNDLE_DIR first (for PyInstaller), then BASE_DIR"""
    # For frozen exe, bundled data is in _MEIPASS
    bundle_path = BUNDLE_DIR / name
    if bundle_path.exists():
        return bundle_path
    # Fallback to BASE_DIR
    base_path = BASE_DIR / name
    if base_path.exists():
        return base_path
    # Also check _internal (PyInstaller 6.x alternative location)
    internal_path = BASE_DIR / "_internal" / name
    if internal_path.exists():
        return internal_path
    return bundle_path  # Return default even if doesn't exist

# For backwards compatibility
INTERNAL_DIR = BASE_DIR / "_internal" if getattr(sys, 'frozen', False) else None

# User data directory - survives reinstalls, always writable
USER_DATA_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / "PyTNC_Pro"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cache directories - in user data folder for persistence
CACHE_DIR = USER_DATA_DIR / "pytnc_cache"
TILE_CACHE_DIR = USER_DATA_DIR / "tile_cache"

# Data directories - use _find_path for bundled data
ICON_CACHE_DIR = BASE_DIR / "aprs_icon_cache"  # Generated locally

# Hessu symbols - check both old and new folder names
_hessu_new = _find_path("hessu-symbols")
_hessu_old = _find_path("aprs_symbols_48")
HESSU_SYMBOLS_DIR = _hessu_new if _hessu_new.exists() else _hessu_old

# Web resources
LEAFLET_JS_PATH = _find_path("leaflet.js")
LEAFLET_CSS_PATH = _find_path("leaflet.css")

# Settings file - in user data folder so it survives reinstalls
SETTINGS_FILE = USER_DATA_DIR / "pytnc_settings.json"

# Icon lookup table
LUT_FILENAME = "KWFAPRS_LUTv2.png"

# =============================================================================
# Audio / Network Constants
# =============================================================================

SAMPLE_RATE = 22050       # RX sample rate
TX_SAMPLE_RATE = 48000    # TX sample rate (higher for better AFSK quality)
HTTP_PORT = 18732         # Local HTTP server for map

# =============================================================================
# Directory Management
# =============================================================================

def ensure_directories():
    """Create required directories if they don't exist."""
    for dir_path in [ICON_CACHE_DIR, HESSU_SYMBOLS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# TOCALL Device Database (expanded from official APRS tocall list)
# =============================================================================

TOCALL_DEVICES = {
    # === Kantronics TNCs ===
    "APN382": "Kantronics KPC-3",
    "APN383": "Kantronics KPC-3+",
    "APN391": "Kantronics KPC-9612",
    "APNK01": "Kantronics KPC-3+",
    "APNK80": "Kantronics KAM",
    "APN": "Kantronics TNC",
    
    # === Byonics TinyTrak ===
    "APT310": "Byonics TinyTrak3",
    "APT311": "Byonics TinyTrak3+",
    "APT312": "Byonics TinyTrak3",
    "APT3": "Byonics TinyTrak3",
    "APT4": "Byonics TinyTrak4",
    "APTT": "Byonics TinyTrak",
    "APMI": "Byonics Micro-Trak",
    
    # === DireWolf ===
    "APDW": "DireWolf",
    "APDW15": "DireWolf 1.5",
    "APDW16": "DireWolf 1.6",
    "APDW17": "DireWolf 1.7",
    
    # === Kenwood Radios ===
    "APK0": "Kenwood TH-D7",
    "APK003": "Kenwood TH-D72",
    "APK004": "Kenwood TH-D74",
    "APK005": "Kenwood TH-D75",
    "APK1": "Kenwood TM-D700",
    "APK102": "Kenwood TM-D710",
    "APK": "Kenwood APRS",
    
    # === Yaesu Radios ===
    "APY01D": "Yaesu FT1D",
    "APY02D": "Yaesu FT2D",
    "APY03D": "Yaesu FT3D",
    "APY05D": "Yaesu FT5D",
    "APY400": "Yaesu FTM-400",
    "APY300": "Yaesu FTM-300",
    "APY500": "Yaesu FTM-500",
    "APYS": "Yaesu System Fusion",
    "APY": "Yaesu APRS",
    
    # === Icom Radios ===
    "API282": "Icom IC-2820",
    "API31": "Icom ID-31",
    "API51": "Icom ID-51",
    "API52": "Icom ID-52",
    "API410": "Icom ID-4100",
    "API510": "Icom ID-5100",
    "API710": "Icom IC-7100",
    "API80": "Icom IC-80",
    "API880": "Icom ID-880",
    "API910": "Icom IC-9100",
    "API970": "Icom IC-9700",
    "API9": "Icom IC-9100",
    "APIC": "Icom APRS",
    
    # === Anytone Radios ===
    "APAT51": "Anytone AT-D578",
    "APAT81": "Anytone AT-D878",
    "APAT": "Anytone APRS",
    
    # === Alinco ===
    "APAL": "Alinco DR-135/235/435",
    
    # === Trackers ===
    "APOT": "Argent OpenTracker",
    "APOT2": "Argent OpenTracker2",
    "APOT3": "Argent OpenTracker3",
    "APOTW": "Argent OpenTracker+Weather",
    "APDR": "APRSdroid",
    "APAND": "APRSdroid",
    "APRNOW": "APRSdroid (new)",
    "APZDA": "DroidAPRS",
    "APJY": "JYaos APRS",
    "APRS": "Generic APRS",
    
    # === Mobile/Tracking Apps ===
    "APMI": "Micro-Trak",
    "APLM": "LOCUS Map",
    "APRAR": "RADAR",
    "APSTPO": "SpotsApp",
    "APWM": "WinMobile APRSce",
    
    # === Windows Software ===
    "APWW": "APRSIS32",
    "APW": "WinAPRS",
    "APAGW": "AGWPE",
    "APBPQ": "BPQ32",
    "APRS+": "APRS+SA",
    "APC": "APRS/CE",
    "APIC": "APRSisce",
    "APRNOW": "APRSnow",
    "APRRT": "APRSrt",
    "APCL": "maprs.me",
    
    # === Mac Software ===
    "APMA": "MacAPRS",
    "APXX": "X-APRS",
    
    # === Linux Software ===
    "APRX": "aprx",
    "APLX": "LinuxAPRS",
    "APXS": "Xastir",
    "APNX": "Xrouter",
    
    # === Web/Online Services ===
    "APFI": "aprs.fi",
    "APRS": "Generic APRS",
    
    # === JS8Call ===
    "APJ8": "JS8Call",
    
    # === Weather Stations ===
    "APWX": "WX Station",
    "APXR": "WX Report",
    "APCWP": "CWOP (Citizen Weather)",
    "APGW": "GW Weather",
    "DW": "Davis Weather",
    "APAW": "AmbientWX",
    
    # === Network/Infrastructure ===
    "APSC": "aprsc (server)",
    "APU2": "UIdigi",
    "APU": "UIdigi",
    "APDG": "ircDDB Gateway",
    "APDI": "DIGI",
    "APND": "DIGI_NED",
    "APJID": "Java IGate",
    "APRSD": "aprsd (Python)",
    "APNC": "NoCalls",
    "APRS": "javAPRSSrvr",
    
    # === LoRa APRS ===
    "APLO": "LoRa APRS",
    "APLT": "LoRa Tracker",
    "APLS": "LoRa Station",
    "APLIB": "LoRa iGate",
    "APLLW": "LoRaWAN",
    "APLRT": "LoRa T-Beam",
    "APLM": "LoRa Mesh",
    "TTGO": "TTGO T-Beam",
    
    # === PicoAPRS / ESP ===
    "APPIC": "PicoAPRS",
    "APESP": "ESP8266/ESP32",
    "APESPG": "ESP8266 iGate",
    "APESPT": "ESP8266 Tracker",
    
    # === Packet/AX.25 ===
    "APS": "APRS+SA",
    "APRS": "Generic APRS",
    "APX": "Xrouter",
    
    # === Raspberry Pi ===
    "APRPI": "RPi APRS",
    "APZRPI": "RPi Tracker",
    
    # === Arduino/Embedded ===
    "APAVT": "AVR Tracker",
    "APAT": "Arduino Tracker",
    
    # === VARA/Winlink ===
    "APVARA": "VARA",
    "APWL": "Winlink",
    "APWL2K": "Winlink 2000",
    
    # === PyTNC Pro (official TOCALL: APPR0? registered to KO6IKR) ===
    "APPR01": "PyTNC Pro v0.1.6-beta",
    "APPR0": "PyTNC Pro",
    "APZ": "Experimental Software",
    
    # === Generic/Unknown ===
    "AP": "Unknown APRS",
}

# Mic-E device suffixes (from aprs.org/aprs12/mic-e-types.txt - official spec)
# These are the "Mv" bytes at the END of the Mic-E info field
# ` prefix = message capable, ' prefix = tracker only
MICE_DEVICES = {
    # Yaesu (` prefix = message capable) - "_x" suffixes
    "_ ": "Yaesu VX-8",         # _<space>
    "_\"": "Yaesu FTM-350",     # _"
    "_#": "Yaesu VX-8G",        # _#
    "_$": "Yaesu FT1D",         # _$
    "_%": "Yaesu FTM-400DR",    # _%
    "_)": "Yaesu FTM-100D",     # _)
    "_(": "Yaesu FT2D",         # _(
    "_0": "Yaesu FT3D",         # _0
    "_1": "Yaesu FTM-300D",     # _1
    "_2": "Yaesu FTM-200D",     # _2
    "_3": "Yaesu FT5D",         # _3
    "_4": "Yaesu FTM-500D",     # _4
    "_5": "Yaesu FTM-510D",     # _5
    # Byonics (' prefix = tracker, not message capable)
    "|3": "Byonics TinyTrak3",
    "|4": "Byonics TinyTrak4",
    # Anytone
    "(5": "Anytone D578UV",     # message capable
    "(8": "Anytone D878UV",     # NOT message capable (tracker)
    # SCS GmbH modems (not message capable)
    ":4": "SCS P4dragon DR-7400",
    ":8": "SCS P4dragon DR-7800",
    # SQ8L
    ":2": "SQ8L VP-Tracker",
    # SainSonic
    " X": "SainSonic AP510",
    # APRSdroid
    "[1": "APRSdroid",
    # HinzTec
    "^v": "HinzTec anyfrog",
    # KissOZ
    "*v": "KissOZ Tracker",
}

# Mic-E legacy TYPE codes - Kenwood radios
# These use the SYMBOL TABLE byte (info[8]) as '>' or ']'
# NOT the data type indicator (info[0] which is ` or ')
MICE_LEGACY = {
    ">": "Kenwood TH-D7A",      # > alone
    ">=": "Kenwood TH-D72",     # > with = suffix
    ">&": "Kenwood TH-D75",     # > with & suffix  
    ">^": "Kenwood TH-D74",     # > with ^ suffix
    "]": "Kenwood TM-D700",     # ] alone
    "]=": "Kenwood TM-D710",    # ] with = suffix
}



# =============================================================================
# Runtime TOCALL loader from aprsorg/aprs-deviceid
# =============================================================================

import json, threading, urllib.request, time as _time

_TOCALL_CACHE_FILE = USER_DATA_DIR / "aprs_deviceid_cache.json"
_TOCALL_CACHE_AGE  = 7 * 24 * 3600   # Re-fetch weekly
_TOCALL_URL = "https://raw.githubusercontent.com/aprsorg/aprs-deviceid/main/tocalls.pretty.json"

def _load_tocall_from_cache() -> bool:
    """Load tocall overrides from local cache. Returns True if cache is fresh."""
    try:
        if not _TOCALL_CACHE_FILE.exists():
            return False
        age = _time.time() - _TOCALL_CACHE_FILE.stat().st_mtime
        if age > _TOCALL_CACHE_AGE:
            return False
        with open(_TOCALL_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        _apply_tocall_data(data)
        return True
    except Exception:
        return False

def _apply_tocall_data(data: dict):
    """Apply fetched tocall data into TOCALL_DEVICES, longest keys first."""
    tocalls = data.get("tocalls", {})
    for tocall, info in tocalls.items():
        # Skip wildcards (contain n or x — variable digits/chars)
        if "n" in tocall.lower() or tocall.endswith("x") or tocall.endswith("X"):
            continue
        model = info.get("model") or info.get("vendor") or ""
        vendor = info.get("vendor") or ""
        desc = f"{vendor} {model}".strip() if vendor and model else model or vendor
        if desc and tocall not in TOCALL_DEVICES:
            TOCALL_DEVICES[tocall] = desc

def _fetch_tocall_background():
    """Fetch latest tocall list from GitHub in background thread."""
    try:
        req = urllib.request.Request(
            _TOCALL_URL,
            headers={"User-Agent": f"PyTNC-Pro/{__import__('pytnc_config', fromlist=[]).get('VERSION', '0.1')}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _apply_tocall_data(data)
        with open(_TOCALL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass  # Network unavailable — use built-in table

def init_tocall_db():
    """Called at startup: load cache, then refresh in background if stale."""
    if not _load_tocall_from_cache():
        t = threading.Thread(target=_fetch_tocall_background, daemon=True)
        t.start()

def get_device_from_tocall(tocall: str) -> Optional[str]:
    """Look up device type from destination callsign."""
    tocall = tocall.upper().split("-")[0]
    
    if tocall in TOCALL_DEVICES:
        return TOCALL_DEVICES[tocall]
    
    for prefix_len in range(len(tocall), 2, -1):
        prefix = tocall[:prefix_len]
        if prefix in TOCALL_DEVICES:
            return TOCALL_DEVICES[prefix]
    
    return None


def get_device_from_mice(suffix: str) -> Optional[str]:
    """Look up device type from Mic-E suffix (last 2 chars of info field)."""
    if len(suffix) >= 2:
        # Try 2-char suffix first
        key = suffix[:2]
        if key in MICE_DEVICES:
            return MICE_DEVICES[key]
        # Try 1-char suffix
        key = suffix[0]
        if key in MICE_DEVICES:
            return MICE_DEVICES[key]
    return None


def get_device_from_mice_legacy(type_byte: str, last_byte: str = None) -> Optional[str]:
    """Look up Kenwood device from Mic-E legacy TYPE byte and optional suffix.
    
    Args:
        type_byte: First byte of Mic-E info field ('>' or ']')
        last_byte: Last byte of info field (version indicator like '=', '^', '&')
    """
    if last_byte:
        # Try type + suffix combo first (e.g., ">=" for TH-D72)
        key = type_byte + last_byte
        if key in MICE_LEGACY:
            return MICE_LEGACY[key]
    # Fall back to type byte alone
    if type_byte in MICE_LEGACY:
        return MICE_LEGACY[type_byte]
    return None


# Alias for backward compatibility
MIC_E_RADIOS = MICE_DEVICES

MIC_E_MSG_TYPES = [
    "Emergency", "Priority", "Special", "Committed",
    "Returning", "In Service", "En Route", "Off Duty"
]

MIC_E_DEST_TABLE = {
    '0': (0, 0, 0), '1': (1, 0, 0), '2': (2, 0, 0), '3': (3, 0, 0), '4': (4, 0, 0),
    '5': (5, 0, 0), '6': (6, 0, 0), '7': (7, 0, 0), '8': (8, 0, 0), '9': (9, 0, 0),
    'A': (0, 1, 0), 'B': (1, 1, 0), 'C': (2, 1, 0), 'D': (3, 1, 0), 'E': (4, 1, 0),
    'F': (5, 1, 0), 'G': (6, 1, 0), 'H': (7, 1, 0), 'I': (8, 1, 0), 'J': (9, 1, 0),
    'K': (0, 1, 0), 'L': (1, 1, 0), 'P': (0, 1, 1), 'Q': (1, 1, 1), 'R': (2, 1, 1),
    'S': (3, 1, 1), 'T': (4, 1, 1), 'U': (5, 1, 1), 'V': (6, 1, 1), 'W': (7, 1, 1),
    'X': (8, 1, 1), 'Y': (9, 1, 1), 'Z': (0, 1, 1),
}

# =============================================================================
# SSID Descriptions
# =============================================================================

SSID_TYPES = {
    0: "Primary", 1: "Secondary", 2: "Secondary", 3: "Additional", 4: "Additional",
    5: "IGate", 6: "Satellite", 7: "Handheld", 8: "Boat", 9: "Mobile",
    10: "Internet", 11: "Balloon", 12: "Portable", 13: "Weather", 14: "Truck", 15: "Digipeater"
}
