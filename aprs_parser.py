"""
APRS Parsing Module for PyTNC Pro

Contains:
- Weather data parsing
- Mic-E position decoding
- NMEA GPS sentence parsing  
- APRS packet classification
"""

import re
from typing import Dict, Any, Optional

from pytnc_config import MIC_E_RADIOS, MIC_E_MSG_TYPES, MIC_E_DEST_TABLE, MICE_LEGACY, get_device_from_mice_legacy


# =============================================================================
# Regex Patterns
# =============================================================================

_UNCOMP_POS_RE = re.compile(
    r"""^(?P<dtype>[!=])(?P<lat>\d{4}\.\d{2}[NS])(?P<table>.)(?P<lon>\d{5}\.\d{2}[EW])(?P<sym>.)(?P<rest>.*)$"""
)

_UNCOMP_POS_TS_RE = re.compile(
    r"""^(?P<dtype>[@/])(?P<ts>.{7})(?P<lat>\d{4}\.\d{2}[NS])(?P<table>.)(?P<lon>\d{5}\.\d{2}[EW])(?P<sym>.)(?P<rest>.*)$"""
)

# Weather data pattern - symbol _ indicates weather station
_WX_DATA_RE = re.compile(
    r"""
    (?P<wind_dir>\d{3}|\.{3})      # Wind direction (degrees or ...)
    /(?P<wind_speed>\d{3}|\.{3})   # Wind speed (mph)
    (?:g(?P<gust>\d{3}|\.{3}))?    # Gust (optional)
    (?:t(?P<temp>-?\d{2,3}))?      # Temperature F (optional)
    (?:r(?P<rain_1h>\d{3}))?       # Rain last hour (optional)
    (?:p(?P<rain_24h>\d{3}))?      # Rain last 24h (optional)
    (?:P(?P<rain_mid>\d{3}))?      # Rain since midnight (optional)
    (?:h(?P<humidity>\d{2}))?      # Humidity % (optional)
    (?:b(?P<pressure>\d{5}))?      # Barometric pressure (optional)
    """,
    re.VERBOSE
)


# =============================================================================
# Weather Parsing
# =============================================================================

def parse_weather(data: str) -> Optional[Dict[str, Any]]:
    """Parse APRS weather data string."""
    m = _WX_DATA_RE.search(data)
    if not m:
        return None
    
    wx = {}
    
    # Wind direction
    wind_dir = m.group("wind_dir")
    if wind_dir and wind_dir != "...":
        wx["wind_dir"] = int(wind_dir)
    
    # Wind speed (mph)
    wind_speed = m.group("wind_speed")
    if wind_speed and wind_speed != "...":
        wx["wind_speed"] = int(wind_speed)
    
    # Gust
    gust = m.group("gust")
    if gust and gust != "...":
        wx["gust"] = int(gust)
    
    # Temperature (Fahrenheit)
    temp = m.group("temp")
    if temp:
        wx["temp_f"] = int(temp)
        wx["temp_c"] = round((int(temp) - 32) * 5 / 9, 1)
    
    # Rain last hour (hundredths of inch)
    rain_1h = m.group("rain_1h")
    if rain_1h:
        wx["rain_1h"] = int(rain_1h) / 100.0
    
    # Rain last 24h
    rain_24h = m.group("rain_24h")
    if rain_24h:
        wx["rain_24h"] = int(rain_24h) / 100.0
    
    # Rain since midnight
    rain_mid = m.group("rain_mid")
    if rain_mid:
        wx["rain_midnight"] = int(rain_mid) / 100.0
    
    # Humidity
    humidity = m.group("humidity")
    if humidity:
        h = int(humidity)
        wx["humidity"] = 100 if h == 0 else h  # 00 means 100%
    
    # Barometric pressure (tenths of millibars)
    pressure = m.group("pressure")
    if pressure:
        wx["pressure_mb"] = int(pressure) / 10.0
    
    return wx if wx else None


# =============================================================================
# Coordinate Conversion
# =============================================================================

def _dm_to_decimal(dm: str, hemi: str) -> float:
    """Convert degrees-minutes to decimal degrees."""
    if hemi in ("N", "S"):
        deg, minutes = int(dm[0:2]), float(dm[2:])
    else:
        deg, minutes = int(dm[0:3]), float(dm[3:])
    dec = deg + minutes / 60.0
    return -dec if hemi in ("S", "W") else dec


# =============================================================================
# Mic-E Decoder (APRS101 Chapter 10)
# =============================================================================

# Symbol descriptions for common Mic-E symbols
MIC_E_SYMBOLS = {
    ('/', '>'): "normal car (side view)",
    ('/', '<'): "motorcycle",
    ('/', 'k'): "truck",
    ('/', 'v'): "van",
    ('/', 'j'): "jeep",
    ('/', 'u'): "truck (18-wheeler)",
    ('/', 'b'): "bicycle",
    ('/', '['): "jogger",
    ('/', 's'): "boat",
    ('/', 'Y'): "yacht",
    ('/', 'f'): "fire truck",
    ('/', 'a'): "ambulance",
    ('/', 'p'): "police",
    ('/', '^'): "large aircraft",
    ('/', 'X'): "helicopter",
    ('/', 'R'): "recreational vehicle",
    ('\\', '>'): "car (alternate)",
    ('\\', 'k'): "SUV",
    ('/', '-'): "house QTH (VHF)",
    ('\\', '-'): "house HF",
    ('/', 'y'): "house (yagi)",
    ('/', 'O'): "balloon",
}


def decode_mic_e(dest: str, info: str) -> Optional[Dict[str, Any]]:
    """
    Decode Mic-E position from destination callsign and info field.
    
    Destination (6 chars): encodes latitude + message type
    Info field: 
      - Byte 0: Data type indicator (` or ')
      - Bytes 1-3: Longitude (degrees, minutes, hundredths)
      - Byte 4: Speed + Course
      - Byte 5: Speed + Course  
      - Byte 6: Speed + Course
      - Byte 7: Symbol code
      - Byte 8: Symbol table
      - Rest: Optional altitude, radio type, telemetry, status
    """
    # Need at least 6 chars in dest and 9 bytes in info
    if len(dest) < 6 or len(info) < 9:
        return None
    
    dest = dest.upper()[:6]
    
    # Decode latitude from destination
    lat_digits = []
    msg_bits = []
    ns_bit = 0  # 0=South, 1=North
    lon_offset = 0  # 0=0, 1=100
    ew_bit = 0  # 0=East, 1=West
    
    for i, c in enumerate(dest):
        if c not in MIC_E_DEST_TABLE:
            # Try stripping SSID artifacts
            if c == '-':
                break
            return None
        
        digit, custom, msg = MIC_E_DEST_TABLE[c]
        lat_digits.append(digit)
        
        if i == 3:  # 4th char: N/S
            ns_bit = custom
        elif i == 4:  # 5th char: lon offset
            lon_offset = custom
        elif i == 5:  # 6th char: E/W
            ew_bit = custom
        
        msg_bits.append(msg)
    
    if len(lat_digits) < 6:
        return None
    
    # Build latitude: DD MM.HH
    lat_deg = lat_digits[0] * 10 + lat_digits[1]
    lat_min = lat_digits[2] * 10 + lat_digits[3]
    lat_hun = lat_digits[4] * 10 + lat_digits[5]
    lat = lat_deg + (lat_min + lat_hun / 100.0) / 60.0
    if ns_bit == 0:  # South
        lat = -lat
    
    # Decode longitude from info bytes 1-3
    try:
        d = ord(info[1]) - 28
        if lon_offset:
            d += 100
        if 180 <= d <= 189:
            d -= 80
        elif 190 <= d <= 199:
            d -= 190
        
        m = ord(info[2]) - 28
        if m >= 60:
            m -= 60
        
        h = ord(info[3]) - 28
        
        lon = d + (m + h / 100.0) / 60.0
        if ew_bit:  # West
            lon = -lon
    except (IndexError, ValueError):
        return None
    
    # Decode speed and course from info bytes 4-6
    try:
        sp = (ord(info[4]) - 28) * 10
        dc = ord(info[5]) - 28
        sp += dc // 10
        course = (dc % 10) * 100 + (ord(info[6]) - 28)
        
        # Speed is in knots, course in degrees
        if sp >= 800:
            sp -= 800
        if course >= 400:
            course -= 400
        
        speed_knots = sp
        speed_mph = sp * 1.15078
        speed_kmh = sp * 1.852
    except (IndexError, ValueError):
        speed_knots = 0
        speed_mph = 0
        speed_kmh = 0
        course = 0
    
    # Symbol: byte 7 = code, byte 8 = table
    try:
        sym_code = info[7]
        sym_table = info[8]
    except IndexError:
        sym_code = '>'
        sym_table = '/'
    
    # Message type from first 3 msg bits (Standard or Custom)
    msg_idx = (msg_bits[0] << 2) | (msg_bits[1] << 1) | msg_bits[2]
    msg_type = MIC_E_MSG_TYPES[msg_idx] if msg_idx < len(MIC_E_MSG_TYPES) else "Unknown"
    
    # Parse the rest of the info field (after symbol)
    rest = info[9:] if len(info) > 9 else ""
    
    # Detect radio type
    radio_type = None
    
    # First check for Kenwood legacy TYPE codes (first byte of info: '>' or ']')
    type_byte = info[0] if info else ''
    if type_byte in ('>', ']'):
        # Check last byte for version indicator
        last_byte = rest[-1] if rest else ''
        radio_type = get_device_from_mice_legacy(type_byte, last_byte)
        # Remove version byte from rest if it was a Kenwood indicator
        if radio_type and last_byte in ('=', '^', '&'):
            rest = rest[:-1]
    
    # If not Kenwood legacy, check for modern suffix codes (Yaesu, Byonics, etc.)
    if not radio_type:
        # Check longer suffixes first so "_1" matches before single chars
        for suffix in sorted(MIC_E_RADIOS.keys(), key=len, reverse=True):
            if suffix in rest:
                radio_type = MIC_E_RADIOS[suffix]
                # Remove the suffix from rest
                rest = rest.replace(suffix, "", 1)
                break
    
    # Look for altitude in format: xxx} (base91 encoded)
    altitude_m = None
    altitude_ft = None
    if '}' in rest:
        try:
            alt_idx = rest.index('}')
            if alt_idx >= 3:
                alt_chars = rest[alt_idx-3:alt_idx]
                # Validate base91 chars (33-124)
                if all(33 <= ord(c) <= 124 for c in alt_chars):
                    altitude_m = ((ord(alt_chars[0]) - 33) * 91 * 91 + 
                                 (ord(alt_chars[1]) - 33) * 91 + 
                                 (ord(alt_chars[2]) - 33)) - 10000
                    altitude_ft = int(altitude_m * 3.28084)
                    # Remove altitude from rest
                    rest = rest[:alt_idx-3] + rest[alt_idx+1:]
        except (ValueError, IndexError):
            # Altitude parsing failed - continue without altitude
            pass
    
    # Look for telemetry in format: |SSAA...| (sequence, analog values)
    telemetry = None
    status_text = None
    if '|' in rest:
        try:
            parts = rest.split('|')
            for idx, part in enumerate(parts):
                if len(part) >= 4 and part[0:2].isalnum():
                    # Base91 encoded telemetry
                    telemetry = {"raw": part}
                    # Decode sequence (first 2 chars)
                    if len(part) >= 2:
                        seq = (ord(part[0]) - 33) * 91 + (ord(part[1]) - 33)
                        telemetry["sequence"] = seq
                    # Decode analog values (pairs of chars)
                    analogs = []
                    for i in range(2, min(len(part), 12), 2):
                        if i + 1 < len(part):
                            val = (ord(part[i]) - 33) * 91 + (ord(part[i+1]) - 33)
                            analogs.append(val)
                    if analogs:
                        telemetry["analog"] = analogs
                    break
            # Status text is anything after the telemetry block
            if len(parts) > 2:
                status_text = parts[-1].strip() if parts[-1].strip() else None
        except (ValueError, IndexError):
            # Telemetry parsing failed - try to salvage status text
            clean_rest = ''.join(c for c in rest if c.isprintable())
            if clean_rest.strip():
                status_text = clean_rest.strip()
    else:
        # No telemetry - rest might be status text
        # Clean up the rest string - remove control characters and get printable text
        clean_rest = ''.join(c for c in rest if c.isprintable())
        if clean_rest.strip():
            status_text = clean_rest.strip()
    
    # Get symbol description
    sym_desc = MIC_E_SYMBOLS.get((sym_table, sym_code), None)
    
    return {
        "lat": lat,
        "lon": lon,
        "speed_knots": speed_knots,
        "speed_mph": speed_mph,
        "speed_kmh": speed_kmh,
        "course": course,
        "table": sym_table,
        "sym": sym_code,
        "sym_desc": sym_desc,
        "msg_type": msg_type,
        "altitude_m": altitude_m,
        "altitude_ft": altitude_ft,
        "radio_type": radio_type,
        "telemetry": telemetry,
        "status_text": status_text,
        "rest": rest
    }


# =============================================================================
# NMEA GPS Sentence Parser
# =============================================================================

def parse_nmea(sentence: str) -> Optional[Dict[str, Any]]:
    """
    Parse NMEA GPS sentences ($GPRMC, $GPGGA, $GPGLL).
    Returns dict with lat, lon, speed, course, etc. or None if invalid/no fix.
    """
    sentence = sentence.strip()
    
    # Verify checksum if present
    if '*' in sentence:
        data, checksum = sentence.rsplit('*', 1)
        if data.startswith('$'):
            data = data[1:]
        calc_checksum = 0
        for c in data:
            calc_checksum ^= ord(c)
        try:
            if int(checksum, 16) != calc_checksum:
                return None  # Checksum mismatch
        except ValueError:
            pass  # Invalid checksum format, continue anyway
    
    parts = sentence.replace('$', '').split('*')[0].split(',')
    if len(parts) < 3:
        return None
    
    sentence_type = parts[0].upper()
    
    # Helper to parse lat/lon from NMEA format
    def parse_coord(value: str, hemisphere: str) -> Optional[float]:
        if not value or not hemisphere:
            return None
        try:
            if hemisphere in ('N', 'S'):
                # Latitude: DDMM.MMMM
                deg = int(value[:2])
                minutes = float(value[2:])
            else:
                # Longitude: DDDMM.MMMM
                deg = int(value[:3])
                minutes = float(value[3:])
            
            decimal = deg + minutes / 60.0
            if hemisphere in ('S', 'W'):
                decimal = -decimal
            return decimal
        except (ValueError, IndexError):
            return None
    
    result = {
        "sentence_type": sentence_type,
        "valid": False,
        "lat": None,
        "lon": None,
        "speed_knots": None,
        "speed_mph": None,
        "course": None,
        "altitude": None,
        "time_utc": None,
        "date": None,
    }
    
    try:
        if sentence_type in ("GPRMC", "GNRMC", "GLRMC"):
            # $GPRMC,HHMMSS.ss,A,DDMM.MMM,N,DDDMM.MMM,W,speed,course,DDMMYY,mag,E*cs
            #        0         1 2        3 4         5 6     7      8
            if len(parts) >= 10:
                result["time_utc"] = parts[1][:6] if parts[1] else None
                result["valid"] = parts[2] == 'A'  # A=Active, V=Void
                result["lat"] = parse_coord(parts[3], parts[4])
                result["lon"] = parse_coord(parts[5], parts[6])
                
                if parts[7]:
                    try:
                        result["speed_knots"] = float(parts[7])
                        result["speed_mph"] = result["speed_knots"] * 1.15078
                    except ValueError:
                        pass
                
                if parts[8]:
                    try:
                        result["course"] = float(parts[8])
                    except ValueError:
                        pass
                
                result["date"] = parts[9] if len(parts) > 9 else None
        
        elif sentence_type in ("GPGGA", "GNGGA", "GLGGA"):
            # $GPGGA,HHMMSS.ss,DDMM.MMM,N,DDDMM.MMM,W,Q,sats,hdop,alt,M,geoid,M,age,ref*cs
            #        0         1        2 3         4 5 6    7    8   9
            if len(parts) >= 10:
                result["time_utc"] = parts[1][:6] if parts[1] else None
                result["lat"] = parse_coord(parts[2], parts[3])
                result["lon"] = parse_coord(parts[4], parts[5])
                
                # Quality: 0=invalid, 1=GPS, 2=DGPS, etc.
                quality = int(parts[6]) if parts[6] else 0
                result["valid"] = quality > 0
                result["gps_quality"] = quality
                result["satellites"] = int(parts[7]) if parts[7] else 0
                
                if parts[9]:
                    try:
                        result["altitude"] = float(parts[9])  # meters
                    except ValueError:
                        pass
        
        elif sentence_type in ("GPGLL", "GNGLL", "GLGLL"):
            # $GPGLL,DDMM.MMM,N,DDDMM.MMM,W,HHMMSS.ss,A,mode*cs
            #        0        1 2         3 4         5 6
            if len(parts) >= 6:
                result["lat"] = parse_coord(parts[1], parts[2])
                result["lon"] = parse_coord(parts[3], parts[4])
                result["time_utc"] = parts[5][:6] if parts[5] else None
                result["valid"] = parts[6] == 'A' if len(parts) > 6 else (result["lat"] is not None)
        
        else:
            return None  # Unknown sentence type
    
    except (IndexError, ValueError) as e:
        return None
    
    return result


# =============================================================================
# APRS Packet Classification
# =============================================================================

def aprs_classify(dest: str, info: str) -> Dict[str, Any]:
    """
    Classify and parse an APRS packet.
    Returns dict with 'kind', 'summary', and 'fields'.
    """
    s = info.strip("\r\n")
    if not s:
        return {"kind": "Empty", "summary": "", "fields": {}}

    # Mic-E: starts with ` or '
    if s[0] in ("`", "'"):
        mic_e = decode_mic_e(dest, s)
        if mic_e:
            # Build detailed summary like Direwolf
            summary_parts = []
            
            # Symbol description
            if mic_e.get('sym_desc'):
                summary_parts.append(mic_e['sym_desc'])
            
            # Radio type (show UNKNOWN if not recognized)
            if mic_e.get('radio_type'):
                summary_parts.append(mic_e['radio_type'])
            else:
                summary_parts.append("UNKNOWN vendor/model")
            
            # Message type
            summary_parts.append(f"[{mic_e['msg_type']}]")
            
            summary = ", ".join(summary_parts)
            
            # Position and movement - always show speed and course
            pos_info = f"N {abs(mic_e['lat']):.4f}, W {abs(mic_e['lon']):.4f}"
            pos_info += f", {mic_e['speed_kmh']:.0f} km/h ({mic_e['speed_mph']:.0f} mph), course {mic_e['course']}°"
            
            # Altitude
            if mic_e.get('altitude_m') is not None:
                pos_info += f", alt {mic_e['altitude_m']} m ({mic_e['altitude_ft']} ft)"
            
            # Telemetry
            telem_str = ""
            if mic_e.get('telemetry'):
                t = mic_e['telemetry']
                telem_parts = []
                if 'sequence' in t:
                    telem_parts.append(f"Seq={t['sequence']}")
                if 'analog' in t:
                    for i, v in enumerate(t['analog']):
                        telem_parts.append(f"A{i+1}={v}")
                if telem_parts:
                    telem_str = ", ".join(telem_parts)
            
            full_summary = summary + "\n  " + pos_info
            if telem_str:
                full_summary += "\n  " + telem_str
            if mic_e.get('status_text'):
                full_summary += "\n  " + mic_e['status_text']
            
            return {
                "kind": "Mic-E",
                "summary": full_summary,
                "fields": {
                    "lat": mic_e["lat"],
                    "lon": mic_e["lon"],
                    "table": mic_e["table"],
                    "sym": mic_e["sym"],
                    "sym_desc": mic_e.get("sym_desc"),
                    "speed_knots": mic_e["speed_knots"],
                    "speed_mph": mic_e["speed_mph"],
                    "speed_kmh": mic_e["speed_kmh"],
                    "course": mic_e["course"],
                    "msg_type": mic_e["msg_type"],
                    "altitude_m": mic_e.get("altitude_m"),
                    "altitude_ft": mic_e.get("altitude_ft"),
                    "radio_type": mic_e.get("radio_type"),
                    "telemetry": mic_e.get("telemetry"),
                    "status_text": mic_e.get("status_text"),
                    "rest": mic_e["rest"]
                }
            }
        else:
            return {"kind": "Mic-E", "summary": f"(decode failed) {s[:60]}", "fields": {}}

    # Status message
    if s[0] == ">":
        return {"kind": "Status", "summary": s[1:].strip(), "fields": {}}

    # Telemetry packet: T#seq,A1,A2,A3,A4,A5,DDDDDDDD
    if s.startswith("T#"):
        try:
            parts = s[2:].split(",")
            if len(parts) >= 6:
                seq = int(parts[0])
                analogs = [int(parts[i]) if parts[i].isdigit() else 0 for i in range(1, 6)]
                
                # Digital bits (8 bits as string of 0/1)
                digitals = []
                if len(parts) >= 7 and len(parts[6]) >= 8:
                    for i in range(8):
                        digitals.append(int(parts[6][i]) if parts[6][i] in '01' else 0)
                
                summary = f"Seq={seq}, A1={analogs[0]}, A2={analogs[1]}, A3={analogs[2]}, A4={analogs[3]}, A5={analogs[4]}"
                if digitals:
                    summary += f", D={parts[6][:8]}"
                
                return {
                    "kind": "Telemetry",
                    "summary": summary,
                    "fields": {
                        "sequence": seq,
                        "analog": analogs,
                        "digital": digitals,
                        "raw": s
                    }
                }
        except (ValueError, IndexError):
            pass
        return {"kind": "Telemetry", "summary": s[:60], "fields": {}}

    # APRS Message: :ADDRESSEE:message
    # Standard is 9-char padded addressee, but handle variable length and odd padding
    if s[0] == ":":
        # Find second colon (addressee is between first and second colon)
        second_colon = s.find(":", 1)
        if second_colon > 1 and second_colon <= 10:  # Allow 1-9 char addressee
            addressee = s[1:second_colon].strip().upper()  # Normalize: strip + uppercase
            message = s[second_colon + 1:]
            
            # Only process if addressee is valid (not empty after stripping)
            if addressee:
                # Check for telemetry definitions (sent as messages to self)
                if message.startswith("PARM."):
                    # Parameter names: PARM.name1,name2,name3,...
                    params = message[5:].split(",")
                    return {"kind": "Telem-PARM", "summary": f"Params: {', '.join(params[:5])}", 
                            "fields": {"for": addressee, "params": params}}
                
                elif message.startswith("UNIT."):
                    # Units: UNIT.unit1,unit2,unit3,...
                    units = message[5:].split(",")
                    return {"kind": "Telem-UNIT", "summary": f"Units: {', '.join(units[:5])}", 
                            "fields": {"for": addressee, "units": units}}
                
                elif message.startswith("EQNS."):
                    # Equations: EQNS.a1,b1,c1,a2,b2,c2,... (3 coefficients per channel)
                    coeffs = message[5:].split(",")
                    # Group into triplets (a, b, c) for each channel
                    eqns = []
                    for i in range(0, min(len(coeffs), 15), 3):
                        if i + 2 < len(coeffs):
                            try:
                                eqns.append((float(coeffs[i]), float(coeffs[i+1]), float(coeffs[i+2])))
                            except ValueError:
                                eqns.append((0, 1, 0))  # Default: value = x
                    return {"kind": "Telem-EQNS", "summary": f"Equations for {len(eqns)} channels", 
                            "fields": {"for": addressee, "eqns": eqns}}
                
                elif message.startswith("BITS."):
                    # Digital bit labels
                    bits = message[5:].split(",")
                    return {"kind": "Telem-BITS", "summary": f"Bit labels: {message[5:40]}", 
                            "fields": {"for": addressee, "bits": bits}}
                
                # Check for ack/rej
                elif message.startswith("ack"):
                    return {"kind": "Message-ACK", "summary": f"ACK to {addressee}: {message}", "fields": {"to": addressee, "ack": message[3:]}}
                elif message.startswith("rej"):
                    return {"kind": "Message-REJ", "summary": f"REJ to {addressee}: {message}", "fields": {"to": addressee, "rej": message[3:]}}
                else:
                    return {"kind": "Message", "summary": f"To {addressee}: {message[:60]}", "fields": {"to": addressee, "message": message}}

    # Object: ;name_____*DDHHMMzDDMM.hhN/DDDMM.hhW...
    if s[0] == ";" and len(s) > 10:
        obj_name = s[1:10].strip()
        obj_status = "live" if s[10] == "*" else "killed"
        return {"kind": "Object", "summary": f"{obj_name} ({obj_status})", "fields": {"name": obj_name, "status": obj_status, "data": s[11:]}}

    # Item: )name!DDMM.hhN/DDDMM.hhW... or )name_...
    if s[0] == ")" and len(s) > 1:
        # Find the status character (! or _)
        for i in range(1, min(10, len(s))):
            if s[i] in ("!", "_"):
                item_name = s[1:i]
                item_status = "live" if s[i] == "!" else "killed"
                return {"kind": "Item", "summary": f"{item_name} ({item_status})", "fields": {"name": item_name, "status": item_status, "data": s[i+1:]}}
        return {"kind": "Item", "summary": s[1:40], "fields": {}}

    # NMEA GPS sentences
    if s.startswith("$GP") or s.startswith("$GN") or s.startswith("$GL"):
        nmea = parse_nmea(s)
        if nmea:
            if nmea["valid"] and nmea["lat"] is not None and nmea["lon"] is not None:
                summary = f"{nmea['lat']:.4f}, {nmea['lon']:.4f}"
                if nmea.get("speed_mph"):
                    summary += f" {nmea['speed_mph']:.0f}mph"
                if nmea.get("course"):
                    summary += f" {nmea['course']:.0f}°"
                if nmea.get("altitude"):
                    summary += f" {nmea['altitude']:.0f}m"
                return {
                    "kind": "NMEA",
                    "summary": summary,
                    "fields": {
                        "lat": nmea["lat"],
                        "lon": nmea["lon"],
                        "speed_knots": nmea.get("speed_knots"),
                        "speed_mph": nmea.get("speed_mph"),
                        "course": nmea.get("course"),
                        "altitude": nmea.get("altitude"),
                        "table": "/",  # Default symbol: car
                        "sym": ">",
                    }
                }
            else:
                # No valid fix
                reason = "No GPS fix" if not nmea["valid"] else "No position"
                return {
                    "kind": "NMEA",
                    "summary": f"({reason}) {nmea['sentence_type']}",
                    "fields": {}
                }
        else:
            return {"kind": "NMEA", "summary": f"(parse error) {s[:50]}", "fields": {}}

    for regex, kind in [(_UNCOMP_POS_RE, "Position"), (_UNCOMP_POS_TS_RE, "Position+Time")]:
        m = regex.match(s)
        if m:
            d = m.groupdict()
            lat = _dm_to_decimal(d["lat"][0:7], d["lat"][7])
            lon = _dm_to_decimal(d["lon"][0:8], d["lon"][8])
            
            sym = d["sym"]
            table = d["table"]
            rest = d.get("rest", "")
            
            # Check if this is a weather station (symbol _ )
            if sym == "_":
                wx = parse_weather(rest)
                if wx:
                    # Build weather summary
                    summary_parts = []
                    if "temp_f" in wx:
                        summary_parts.append(f"{wx['temp_f']}°F")
                    if "wind_speed" in wx:
                        wind_str = f"💨 {wx['wind_speed']}mph"
                        if "wind_dir" in wx:
                            wind_str += f" {wx['wind_dir']}°"
                        if "gust" in wx:
                            wind_str += f" (g{wx['gust']})"
                        summary_parts.append(wind_str)
                    if "humidity" in wx:
                        summary_parts.append(f"💧{wx['humidity']}%")
                    if "pressure_mb" in wx:
                        summary_parts.append(f"📊{wx['pressure_mb']:.1f}mb")
                    if "rain_1h" in wx and wx["rain_1h"] > 0:
                        summary_parts.append(f"🌧️{wx['rain_1h']:.2f}\"")
                    
                    summary = " | ".join(summary_parts) if summary_parts else "Weather station"
                    
                    return {
                        "kind": "Weather",
                        "summary": summary,
                        "fields": {
                            "lat": lat,
                            "lon": lon,
                            "table": table,
                            "sym": sym,
                            "rest": rest,
                            **wx  # Include all weather data
                        }
                    }
            
            # Parse extra data from rest: PHG, altitude, course/speed, frequency, comment
            phg = None
            altitude_ft = None
            altitude_m = None
            course = None
            speed_kmh = None
            speed_mph = None
            frequency = None
            comment = rest
            
            # PHG data: PHGxxxx (Power, Height, Gain, Directivity)
            phg_match = re.search(r'PHG(\d)(\d)(\d)(\d)', rest)
            if phg_match:
                p_idx, h_idx, g_idx, dir_idx = [int(x) for x in phg_match.groups()]
                # Power in watts: 0,1,4,9,16,25,36,49,64,81
                power_watts = p_idx * p_idx
                # Height in feet: 10, 20, 40, 80, 160, 320, 640, 1280, 2560, 5120
                height_ft = 10 * (2 ** h_idx)
                height_m = int(height_ft * 0.3048)
                # Gain in dB
                gain_db = g_idx
                # Directivity: 0=omni, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW, 8=N
                dir_names = ["omni", "45°NE", "90°E", "135°SE", "180°S", "225°SW", "270°W", "315°NW", "360°N"]
                directivity = dir_names[dir_idx] if dir_idx < len(dir_names) else "?"
                phg = {
                    "power_w": power_watts,
                    "height_ft": height_ft,
                    "height_m": height_m,
                    "gain_db": gain_db,
                    "directivity": directivity,
                    "raw": phg_match.group(0)
                }
                # Remove PHG from comment
                comment = comment.replace(phg_match.group(0), "")
            
            # Course/Speed: CCC/SSS format (3 digits each) - often at start of comment
            cse_spd_match = re.search(r'(\d{3})/(\d{3})', comment)
            if cse_spd_match:
                course = int(cse_spd_match.group(1))
                speed_kmh = int(cse_spd_match.group(2))
                speed_mph = int(speed_kmh * 0.621371)
                # Remove from comment
                comment = comment.replace(cse_spd_match.group(0), "", 1)
            
            # Frequency: NNN.NNNMHz or NNN.NNNN MHz
            freq_match = re.search(r'(\d{2,3}\.\d{2,4})\s*[Mm][Hh][Zz]', comment)
            if freq_match:
                frequency = freq_match.group(1) + " MHz"
                # Remove from comment
                comment = comment.replace(freq_match.group(0), "")
            
            # Altitude: /A=xxxxxx (exactly 6 digits per APRS spec)
            alt_match = re.search(r'/A=(-?\d{6})', rest)
            if alt_match:
                altitude_ft = int(alt_match.group(1))
                altitude_m = int(altitude_ft * 0.3048)
                # Remove altitude from comment (don't require word boundary)
                comment = re.sub(r'/A=-?\d{6}', '', comment)
            
            # Also remove altitude without leading slash (might be partially stripped elsewhere)
            comment = re.sub(r'(?<![a-zA-Z])A=-?\d{6}', '', comment)
            
            # Clean up comment - remove weather tokens for display
            # Weather tokens pattern
            weather_tokens = r'(?:b\d{5}|[Ll]\d{3}|#\d{3,5}|c\d{3}|s\d{3}|g\d{3}|t-?\d{3}|r\d{3}|p\d{3}|P\d{3}|h\d{2})'
            
            # Remove positionless weather format: _MMDDHHMM followed by weather data
            comment = re.sub(r'^_\d{8}' + weather_tokens + r'+\.?', '', comment)
            
            # Remove .../SSS or DDD/SSS at start (wind direction/speed)
            comment = re.sub(r'^\.{0,3}/\d{3}', '', comment)
            comment = re.sub(r'^\d{3}/\d{3}', '', comment)
            
            # Remove concatenated weather tokens at start
            comment = re.sub(r'^' + weather_tokens + r'+', '', comment)
            
            # Remove standalone weather tokens elsewhere (with word boundaries)
            comment = re.sub(r'(?<!\w)' + weather_tokens + r'(?!\w)', '', comment)
            
            # Clean up leading dots/slashes/underscores
            comment = re.sub(r'^[./_]+', '', comment)
            
            # Clean up comment - remove leading slashes and extra whitespace
            comment = comment.strip()
            while comment.startswith("/"):
                comment = comment[1:]
            comment = ' '.join(comment.split()) if comment else None  # Collapse whitespace
            
            # Build enhanced summary like Direwolf
            summary_parts = [f"N {abs(lat):.4f}, W {abs(lon):.4f}"]
            
            # Course/Speed if present
            if course is not None and speed_kmh is not None:
                summary_parts.append(f"{speed_kmh} km/h ({speed_mph} mph)")
                summary_parts.append(f"course {course}°")
            
            # Altitude
            if altitude_ft:
                summary_parts.append(f"alt {altitude_m} m ({altitude_ft} ft)")
            
            # Frequency
            if frequency:
                summary_parts.append(frequency)
            
            summary = ", ".join(summary_parts)
            
            # PHG on its own line
            if phg:
                summary += f"\n  {phg['power_w']} W height={phg['height_ft']}ft={phg['height_m']}m {phg['gain_db']}dBi {phg['directivity']}"
            
            # Comment on its own line (if anything left after parsing)
            if comment:
                summary += f"\n  {comment}"
            
            # Regular position packet
            return {
                "kind": kind, 
                "summary": summary, 
                "fields": {
                    "lat": lat, 
                    "lon": lon,
                    "lat_raw": d["lat"],
                    "lon_raw": d["lon"],
                    "table": table,
                    "sym": sym,
                    "course": course,
                    "speed_kmh": speed_kmh,
                    "speed_mph": speed_mph,
                    "altitude_ft": altitude_ft,
                    "altitude_m": altitude_m,
                    "frequency": frequency,
                    "phg": phg,
                    "comment": comment,
                    "rest": rest,
                    "dtype": d.get("dtype", ""),
                    "ts": d.get("ts", "")
                }
            }

    # Positionless Weather: _MMDDHHMM followed by weather data
    if s and s[0] == '_' and len(s) >= 9:
        # Try to parse positionless weather
        try:
            # Format: _MMDDHHMM c###s###g###t###r###p###P###h##b#####
            ts_str = s[1:9]  # MMDDHHMM
            wx_data = s[9:]  # Weather data
            
            # Parse weather tokens (allow dots for missing data)
            wx_fields = {}
            
            # Wind direction c### (degrees, ... for missing)
            m = re.search(r'c([\d.]{3})', wx_data)
            if m and m.group(1) != '...':
                wx_fields['wind_dir'] = int(m.group(1))
            
            # Wind speed s### (mph)
            m = re.search(r's([\d.]{3})', wx_data)
            if m and m.group(1) != '...':
                wx_fields['wind_speed'] = int(m.group(1))
            
            # Gust g### (mph)
            m = re.search(r'g([\d.]{3})', wx_data)
            if m and m.group(1) != '...':
                wx_fields['wind_gust'] = int(m.group(1))
            
            # Temperature t### or t-## (F)
            m = re.search(r't(-?[\d.]{2,3})', wx_data)
            if m and '.' not in m.group(1):
                wx_fields['temp_f'] = int(m.group(1))
            
            # Rain r### (hundredths of inch, last hour)
            m = re.search(r'r([\d.]{3})', wx_data)
            if m and m.group(1) != '...':
                wx_fields['rain_1h'] = int(m.group(1)) / 100.0
            
            # Rain p### (last 24h)
            m = re.search(r'(?<!a)p([\d.]{3})', wx_data)  # Negative lookbehind to avoid 'ap'
            if m and m.group(1) != '...':
                wx_fields['rain_24h'] = int(m.group(1)) / 100.0
            
            # Rain P### (since midnight)
            m = re.search(r'P([\d.]{3})', wx_data)
            if m and m.group(1) != '...':
                wx_fields['rain_midnight'] = int(m.group(1)) / 100.0
            
            # Humidity h## (%)
            m = re.search(r'h([\d.]{2})', wx_data)
            if m and m.group(1) != '..':
                h = int(m.group(1))
                wx_fields['humidity'] = 100 if h == 0 else h  # h00 means 100%
            
            # Barometric pressure b##### (tenths of millibars)
            m = re.search(r'b([\d.]{5})', wx_data)
            if m and '.' not in m.group(1):
                wx_fields['pressure_mb'] = int(m.group(1)) / 10.0
            
            # Build summary
            summary_parts = []
            if 'temp_f' in wx_fields:
                summary_parts.append(f"{wx_fields['temp_f']}°F")
            if 'wind_speed' in wx_fields:
                wind_str = f"💨 {wx_fields['wind_speed']}mph"
                if 'wind_dir' in wx_fields:
                    wind_str += f" {wx_fields['wind_dir']}°"
                if 'wind_gust' in wx_fields:
                    wind_str += f" (g{wx_fields['wind_gust']})"
                summary_parts.append(wind_str)
            if 'humidity' in wx_fields:
                summary_parts.append(f"💧{wx_fields['humidity']}%")
            if 'pressure_mb' in wx_fields:
                summary_parts.append(f"📊{wx_fields['pressure_mb']:.1f}mb")
            
            summary = " | ".join(summary_parts) if summary_parts else "Positionless weather"
            wx_fields['timestamp'] = ts_str
            
            return {
                "kind": "Weather",
                "summary": summary,
                "fields": wx_fields
            }
        except:
            pass  # Fall through to Other

    # Fallback: try to identify packet type from first character
    # APRS data type identifiers per spec
    dtype_map = {
        '!': "Position (no timestamp)",
        '/': "Position (with timestamp)",
        '@': "Position (with timestamp/msg)",
        '=': "Position (no timestamp/msg)", 
        ';': "Object",
        ')': "Item",
        ':': "Message/Bulletin",
        '>': "Status",
        '<': "Capabilities",
        '?': "Query",
        'T': "Telemetry",
        '#': "Raw WX",
        '*': "Complete WX",
        '_': "Positionless WX",
        '{': "User-defined",
        '}': "Third-party",
        '$': "NMEA",
        '`': "Mic-E (current)",
        "'": "Mic-E (old)",
    }
    
    dtype_hint = dtype_map.get(s[0], None) if s else None
    
    # Try to extract any coordinates that might be present
    coord_match = re.search(r'(\d{2,4}\.\d{2}[NS]).*?(\d{3,5}\.\d{2}[EW])', s)
    
    if dtype_hint:
        summary = f"[{dtype_hint}] {s[:100]}"
    elif coord_match:
        summary = f"[Has coords] {s[:100]}"
    else:
        summary = s[:120]
    
    return {"kind": "Other", "summary": summary, "fields": {"raw": s, "dtype_char": s[0] if s else None}}
