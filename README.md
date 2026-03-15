# PyTNC Pro v0.1.2-beta

**APRS Transceiver with Real-Time Map Display**

Created by KO6IKR | Official TOCALL: `APPR01`

---

## Features

- **APRS RX/TX** - Receive and transmit APRS packets via RF (AFSK 1200 baud)
- **Real-Time Map** - Live station plotting with OpenStreetMap
- **Station Trails** - Pink movement trails for mobile stations (NEW!)
- **APRS-IS Gateway** - Connect to the worldwide APRS network
- **Configurable Range** - Set how far you see stations (10-500 km)
- **Mic-E Decoding** - Full support for compressed position reports
- **Device Detection** - Identifies 200+ radios and software from TOCALL
- **GPS Support** - NMEA input via serial port
- **VARA FM** - Optional VARA FM modem integration
- **EmComm Layers** - Earthquakes, Fires, Weather, AQI, Hospitals

## Requirements

- Windows 10/11 (64-bit)
- Python 3.10+ (for running from source)
- Sound card for RF TX/RX
- Serial port for PTT control

## Quick Start

### Option 1: Run from Source

```bash
# Clone the repository
git clone https://github.com/smashingwaffle/pytnc-pro.git
cd pytnc-pro

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### Option 2: Download Release

Download the latest release from [Releases](https://github.com/smashingwaffle/pytnc-pro/releases) and run `PyTNC_Pro.exe`.

## Configuration

1. **Settings Tab** - Configure your callsign, audio devices, and serial ports
2. **APRS Range** - Set radius to see stations (10-500 km)
3. **PTT Control** - Configure Serial RTS/DTR for transmission
4. **APRS-IS** - Enter your callsign and passcode to connect

## Map Features

| Feature | Description |
|---------|-------------|
| Station Icons | APRS symbols with callsign labels |
| 〰️ Trails | Pink movement trails for mobile stations |
| 🏥 Hospitals | Medical facilities |
| ⚠️ NOAA | Weather alerts |
| 🔥 Fires | NASA FIRMS hotspots |
| 🟡 Quakes | USGS earthquakes |
| 🟢 AQI | Air quality index |

## File Structure

```
pytnc-pro/
├── main.py              # Main application
├── pytnc_config.py      # Configuration and constants
├── pytnc_modem.py       # AFSK modem
├── aprs_parser.py       # APRS packet parser
├── ax25_parser.py       # AX.25 frame parser
├── tnc/                 # TNC module (map, AFSK, AX.25)
├── aprs_symbols_48/     # APRS symbol icons
├── requirements.txt     # Python dependencies
└── pytnc_pro.spec       # PyInstaller build spec
```

## Building from Source

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller pytnc_pro.spec

# Output in dist/PyTNC_Pro/
```

## Version History

### v0.1.2-beta (Current)
- Station trails for mobile stations
- APRS Range control box
- Kenwood Mic-E detection fix
- VOX mode removed (PTT simplified)
- Weather data filtering improved

### v0.1.1-beta
- Initial public release
- TOCALL APPR01 registered

## Contributing

Bug reports and pull requests welcome! Please open an issue first to discuss changes.

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [APRS Working Group](http://www.aprs.org/) - Protocol specification
- [Hessu/aprs.fi](https://github.com/hessu/aprs-symbols) - APRS symbol set
- [OpenStreetMap](https://www.openstreetmap.org/) - Map tiles

## Contact

- **Author:** KO6IKR
- **GitHub:** [smashingwaffle/pytnc-pro](https://github.com/smashingwaffle/pytnc-pro)
- **TOCALL:** APPR01 (registered)

---

**73 de KO6IKR** 📻
