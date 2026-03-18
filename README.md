# PyTNC Pro

A FREE modern, feature-rich APRS transceiver for Windows with real-time mapping, emergency communications support, and VARA FM integration. The WIKI page is live.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

### 📡 APRS Operations
- **APRS-IS Integration** - Connect to the worldwide APRS Internet System
- **RF TX/RX** - Transmit and receive over radio via soundcard modem (AFSK 1200 baud)
- **VARA FM Support** - High-speed digital mode for APRS over VARA FM
- **Smart Beaconing** - Automatic position beacons with configurable intervals
- **Full Symbol Support** - All APRS symbols with Hessu icon set

### 🗺️ Real-Time Mapping
- **Live Station Tracking** - See all APRS stations on an interactive map
- **Clickable Callsigns** - Click any callsign in the feed to pan to their location
- **QRZ Popups** - Station info with profile photos (requires QRZ subscription)
- **Trail History** - Track station movement over time
- **GPU Accelerated** - Smooth 60fps map rendering

### 🚨 Emergency Communications (EmComm)
- **NOAA Weather Alerts** - Real-time NWS warnings and watches
- **USGS Earthquakes** - Live earthquake data with magnitude filtering
- **NASA FIRMS Wildfires** - Active fire detection from satellite data
- **Air Quality Index (AQI)** - Smoke and pollution monitoring via AirNow
- **Hospital Locations** - Nearby trauma centers and emergency rooms
- **DARN Network** - Disaster Amateur Radio Network repeater locations

### 📻 Radio Integration
- **PTT Control** - Serial port PTT (RTS/DTR)
- **CAT Control** - Rig frequency/mode control (Yaesu, Icom, Kenwood)
- **GPS Support** - Serial GPS for automatic position updates
- **Audio Device Selection** - Independent TX/RX audio routing

Future feature ::### 💬 Messaging
- **APRS Messaging** - Send and receive APRS messages
- **Message Acknowledgment** - Automatic retry with ACK/REJ
- **Conversation History** - Persistent chat logs

## Screenshots

*Coming soon*

## Installation

### Prerequisites
- Windows 10/11
- Python 3.10 or higher
- A soundcard interface for RF operations (SignaLink, Digirig, etc.)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/smashingwaffle/pytnc-pro.git
   cd pytnc-pro
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run PyTNC Pro**
   ```bash
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
requests>=2.28.0
```

## Configuration

### First Run Setup

1. **Station Settings** (Settings tab)
   - Enter your callsign and SSID
   - Set your location (manual coordinates or GPS)
   - Select your APRS symbol

2. **Audio Setup**
   - Select TX and RX audio devices
   - Adjust audio levels

3. **Serial Ports** (if using RF)
   - Configure PTT port and method (RTS/DTR)
   - Configure GPS port if available

4. **APRS-IS** (for internet gateway)
   - Server: `noam.aprs2.net` (North America) or `rotate.aprs2.net`
   - Port: `14580`
   - Enter your APRS-IS passcode

### API Keys (Optional)

For full functionality, obtain free API keys:

| Feature | API | Get Key |
|---------|-----|---------|
| Wildfires | NASA FIRMS | [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/api/area/) |
| Air Quality | AirNow | [docs.airnowapi.org](https://docs.airnowapi.org/) |
| QRZ Lookups | QRZ.com | [qrz.com/page/xml_data.html](https://www.qrz.com/page/xml_data.html) |

## Usage

### Tabs Overview

| Tab | Purpose |
|-----|---------|
| **RX** | Main map view with live feed and layer toggles |
| **Beacon** | Configure and send position beacons |
| **Message** | APRS messaging interface |
| **VARA FM** | VARA FM modem control and chat |
| **Settings** | All configuration options |

### Map Controls

- **Scroll** - Zoom in/out
- **Drag** - Pan the map
- **Click Station** - View popup with station details
- **Click Callsign** (in feed) - Pan to station on map

### Layer Toggles (RX Tab)

- 🏥 **Hospitals** - Emergency medical facilities
- ⚠️ **NOAA** - Weather alerts
- 🔴 **DARN** - Emergency repeaters
- 🔥 **Fires** - Active wildfires
- 🌍 **Quakes** - Recent earthquakes
- 💨 **AQI** - Air quality index

## VARA FM Setup

1. Download and install [VARA FM](https://rosmodem.wordpress.com/)
2. Configure VARA FM audio settings
3. In PyTNC Pro Settings, set VARA FM ports:
   - Command Port: `8300`
   - Data Port: `8301`
   - KISS Port: `8100`
4. Click "Connect" in the VARA FM tab

## Offline Operation

PyTNC Pro supports offline map caching:

1. Go to **Settings** → **Offline Cache**
2. Set cache radius and zoom level
3. Click **Cache Now** to download tiles
4. Maps will work without internet connection

## File Structure

```
pytnc-pro/
├── main.py              # Main application
├── aprs_parser.py       # APRS packet parser
├── pytnc_config.py      # Configuration management
├── requirements.txt     # Python dependencies
├── tnc/
│   ├── map.py          # Map HTML generator
│   ├── afsk.py         # AFSK modem
│   ├── ax25.py         # AX.25 protocol
│   └── hdlc.py         # HDLC framing
├── hessu-symbols/       # APRS symbol icons
│   ├── primary/        # Primary table (/)
│   └── secondary/      # Secondary table (\)
└── tile_cache/         # Cached map tiles
```

## Troubleshooting

### Map Performance Issues

If the map is slow or choppy:

1. **NVIDIA GPU Users**: Add Python to NVIDIA Control Panel
   - NVIDIA Control Panel → Manage 3D Settings → Program Settings
   - Add your `.venv\Scripts\python.exe`
   - Set to "High-performance NVIDIA processor"

2. **Delete cached HTML**: Delete `aprs_map.html` from your project folder and restart

### No Audio Output

- Check Windows sound settings
- Verify correct audio device selected in Settings
- Test with a lower audio level first

### APRS-IS Connection Failed

- Verify internet connection
- Check firewall settings (port 14580)
- Ensure callsign and passcode are correct

### GPS Not Working

- Check COM port selection
- Verify GPS baud rate (usually 4800 or 9600)
- Ensure GPS has clear sky view for fix

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Hessu/OH7LZB](https://github.com/hessu) - APRS symbol icons
- [APRS.fi](https://aprs.fi) - Inspiration and reference
- [Leaflet](https://leafletjs.com/) - Map library
- [OpenStreetMap](https://www.openstreetmap.org/) - Map tiles
- [VARA](https://rosmodem.wordpress.com/) - VARA FM modem

## Contact

- GitHub: [@smashingwaffle](https://github.com/smashingwaffle)
- QRZ: Look me up!

---

73 de PyTNC Pro Team
Stefaan Desmedt Los Angeles/Torhout Belgium
