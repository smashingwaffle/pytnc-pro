# PyTNC Pro

A **free**, modern APRS transceiver for Windows with real-time mapping, emergency communications support, VARA FM integration, and RF TX/RX via soundcard. Built by a ham, for hams.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Version](https://img.shields.io/badge/Version-0.1.7--beta-orange.svg)

📖 **[Wiki & Documentation](https://github.com/smashingwaffle/pytnc-pro/wiki)**

---

## Features

### 📡 APRS Operations
- **APRS-IS Integration** — Connect to the worldwide APRS Internet System
- **RF TX/RX** — Transmit and receive over radio via soundcard modem (Bell 202 AFSK 1200 baud)
- **Pre-emphasis TX** — Improved RF decode rates via Bell 202 pre-emphasis filter
- **RX + TX IGate** — Full IGate spec compliance, third-party packet unwrapping
- **VARA FM Support** — High-speed digital APRS over VARA FM modem
- **SmartBeaconing™** — Adaptive beacon rate based on speed and course change
- **APRS Objects** — Create and beacon named objects (command posts, nets, events)
- **Full Symbol Support** — All APRS symbols with Hessu icon set

### 🗺️ Real-Time Mapping
- **Live Station Tracking** — All APRS stations on an interactive Leaflet map
- **Click to Pan** — Click any callsign in the live feed to center the map on that station
- **Station Popups** — Device type, elevation, speed, weather, path, timestamp
- **Trail History** — Track station movement over time
- **Station Age Fading** — Stations fade as they age (fresh/aging/old)
- **Show Last Filter** — Filter map by time: 15min → 24hr
- **Offline Map Cache** — Download tiles for offline operation
- **GPU Accelerated** — Smooth rendering via WebGL

### 🚨 Emergency Communications
- **NOAA Weather Alerts** — Real-time NWS warnings and watches
- **USGS Earthquakes** — Live earthquake data with magnitude and radius filtering
- **NASA FIRMS Wildfires** — Active fire detection from satellite
- **Air Quality Index** — Smoke and pollution monitoring via AirNow
- **Hospital Locations** — Nearby trauma centers and emergency rooms
- **Custom Locations** — Load CSV/Excel location files onto the map

### ⛰️ GPS & Elevation
- **Serial GPS** — NMEA-compatible GPS for automatic position updates
- **Auto-Elevation** — Fetches your elevation from Open-Meteo on GPS fix
- **Elevation in Beacons** — `/A=` altitude appended to all RF and APRS-IS packets

### 📻 Radio Integration
- **PTT Control** — RTS/DTR via USB-to-serial adapter
- **CM108 GPIO PTT** — DigiRig Lite, AllScan URI and similar USB audio interfaces
- **Audio Device Selection** — Independent TX/RX audio routing
- **30-second Dedup** — Duplicate packet suppression matching aprsc/Dire Wolf standard

---

## Supported Hardware

See the **[Supported Hardware Wiki page](https://github.com/smashingwaffle/pytnc-pro/wiki)** for a full list.

| Type | Examples |
|---|---|
| Sound card interface | SignaLink USB, DigiRig Mobile, DigiRig Lite, AllScan URI/URI160/ANH85 |
| PTT method | RTS/DTR serial, CM108 GPIO |
| GPS | Any NMEA serial/USB GPS |
| Radio | Any VHF/UHF radio with audio in/out |

---

## Installation

### Prerequisites
- Windows 10/11
- Python 3.10 or higher

### Quick Start

```bash
git clone https://github.com/smashingwaffle/pytnc-pro.git
cd pytnc-pro
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Dependencies

```
PyQt6>=6.5.0
PyQt6-WebEngine>=6.5.0
pyserial>=3.5
numpy>=1.24.0
scipy>=1.10.0
sounddevice>=0.4.6
Pillow>=9.0.0
openpyxl>=3.1.0
requests>=2.28.0
hid>=1.0.4
```

---

## Configuration

### First Run
1. **Settings tab** — Enter callsign, SSID, location, audio devices, PTT port
2. **APRS tab** — Set symbol, comment, path, beacon interval
3. **IGate tab** — Enable RX/TX IGate, set frequency and location description
4. **APRS-IS** — Server: `rotate.aprs2.net`, Port: `14580`, enter passcode

### Optional API Keys

| Feature | Provider | Link |
|---|---|---|
| Wildfires | NASA FIRMS | [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/api/area/) |
| Air Quality | AirNow | [docs.airnowapi.org](https://docs.airnowapi.org/) |

---

## VARA FM Setup

1. Download and install [VARA FM](https://rosmodem.wordpress.com/)
2. In PyTNC Pro → VARA FM tab, set ports: Command `8300`, Data `8301`, KISS `8100`
3. Click Connect

---

## File Structure

```
pytnc-pro/
├── main.py                  # Main application
├── aprs_parser.py           # APRS packet parser
├── pytnc_config.py          # Configuration and device database
├── requirements.txt         # Python dependencies
├── tnc/
│   ├── map.py              # Leaflet map generator
│   ├── monitors.py         # Overlay monitors (weather, quakes, fires...)
│   ├── igate.py            # IGate logic
│   ├── aprs_is.py          # APRS-IS connection
│   ├── vara.py             # VARA FM interface
│   ├── ptt.py              # PTT control
│   └── audio/
│       └── afsk.py         # Bell 202 AFSK modulator with pre-emphasis
├── aprs_symbols_48/         # APRS symbol icons (Hessu set)
└── aprs_map.html            # Generated map HTML
```

---

## Troubleshooting

### RF Decode Issues
- Ensure TX audio level isn't clipping (aim for 40-50% in Settings)
- Check PTT is triggering (green LED on interface)
- Verify correct audio device selected for TX

### Map Performance
NVIDIA GPU users: Add Python to NVIDIA Control Panel → High-performance NVIDIA processor

### APRS-IS Connection Failed
- Check port 14580 isn't blocked by firewall
- Verify callsign and passcode are correct

### GPS Not Working
- Check COM port and baud rate (usually 4800)
- GPS needs clear sky view for fix

---

## Contributing

Pull requests welcome. Please open an issue first for major changes.

---

## Acknowledgments

- [Hessu/OH7LZB](https://github.com/hessu) — APRS symbol icons
- [Leaflet](https://leafletjs.com/) — Map library
- [OpenStreetMap](https://www.openstreetmap.org/) — Map tiles
- [VARA](https://rosmodem.wordpress.com/) — VARA FM modem
- [Open-Meteo](https://open-meteo.com/) — Elevation API
- [APRS.fi](https://aprs.fi) — Reference and inspiration

## License

MIT License — see [LICENSE](LICENSE)

---

73 de KO6IKR 📻  
Stefaan Desmedt — Los Angeles CA / Torhout Belgium
