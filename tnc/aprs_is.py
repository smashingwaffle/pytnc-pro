"""
aprs_is.py — APRS-IS mixin for PyTNC Pro
Handles: connection/disconnection, worker thread, packet parsing,
         position parsing, filter building, Mic-E, compressed/uncompressed
Used as a mixin: class MainWindow(APRSISMixin, ...)
"""

import re
import json
import socket
import threading
from datetime import datetime

from PyQt6.QtWidgets import QMessageBox

# icon_path, make_overlay, clean_aprs_comment, callsigns_match, TOCALL_DEVICES
# and BASE_DIR are all defined in main.py and available via self.__class__'s
# module globals — imported lazily at call time to avoid circular imports.

_APRS_MSG_RE = re.compile(r'^:(?P<addressee>.{9}):(?P<text>.*)$')


class APRSISMixin:
    """Mixin providing all APRS-IS connection and packet parsing methods."""

    # ------------------------------------------------------------------
    # Filter builder
    # ------------------------------------------------------------------

    def _build_aprs_filter(self):
        """Build APRS-IS filter string from location and radius"""
        radius = self.settings_aprs_radius.value() if hasattr(self, 'settings_aprs_radius') else 100
        lat, lon = None, None
        if hasattr(self, 'gps_lat') and self.gps_lat is not None:
            lat, lon = self.gps_lat, self.gps_lon
        if lat is None and hasattr(self, 'lat_edit') and hasattr(self, 'lon_edit'):
            lv = self.lat_edit.value()
            ln = self.lon_edit.value()
            if lv != 0.0 and ln != 0.0:
                lat, lon = lv, ln
        if lat is None and hasattr(self, 'manual_location'):
            manual_text = self.manual_location.text().strip()
            if manual_text:
                try:
                    parts = manual_text.replace(" ", "").split(",")
                    if len(parts) == 2:
                        lat, lon = float(parts[0]), float(parts[1])
                except ValueError:
                    pass
        if lat is None:
            lat, lon = 34.05, -118.25
        return f"r/{lat:.2f}/{lon:.2f}/{radius}"

    # ------------------------------------------------------------------
    # Connect / disconnect
    # ------------------------------------------------------------------

    def _toggle_aprs_is_from_settings(self):
        """Toggle APRS-IS connection from settings tab"""
        if hasattr(self, 'settings_aprs_server'):
            self.aprs_is_server.setText(self.settings_aprs_server.text())
        if hasattr(self, 'settings_aprs_port'):
            self.aprs_is_port.setValue(self.settings_aprs_port.value())
        self.aprs_is_filter.setText(self._build_aprs_filter())
        self.toggle_aprs_is()
        if self.aprs_is_running:
            self.settings_aprs_status.setText("🟢 Connected")
            self.settings_aprs_status.setStyleSheet("color: #69f0ae;")
            self.settings_aprs_connect_btn.setText("Disconnect")
        else:
            self.settings_aprs_status.setText("⚫ Disconnected")
            self.settings_aprs_status.setStyleSheet("color: #ef5350;")
            self.settings_aprs_connect_btn.setText("Connect")

    def toggle_aprs_is(self):
        """Connect or disconnect from APRS-IS server"""
        if self.aprs_is_running:
            self.aprs_is_running = False
            self.aprs_is_connected = False
            if self.aprs_is_socket:
                try:
                    self.aprs_is_socket.close()
                except OSError:
                    pass
                self.aprs_is_socket = None
            self.aprs_is_connect_btn.setText("🌐 START IS")
            self.aprs_is_connect_btn.setStyleSheet("""
                QPushButton {
                    background: #0277bd; color: #fff;
                    font-weight: bold; padding: 2px 10px;
                    border-radius: 3px; border: 1px solid #0288d1;
                    font-size: 10px;
                }
                QPushButton:hover { background: #0288d1; }
            """)
            self.aprs_is_status.setStyleSheet("color: #ff6b6b; font-size: 14px;")
            self.aprs_is_info_label.setText("")
            self._log("🌐 Disconnected from APRS-IS")
            if hasattr(self, 'settings_aprs_status'):
                self.settings_aprs_status.setText("⚫ Disconnected")
                self.settings_aprs_status.setStyleSheet("color: #ef5350;")
                self.settings_aprs_connect_btn.setText("Connect")
            self._sync_beacon_connection_status()
        else:
            if hasattr(self, 'settings_aprs_server'):
                self.aprs_is_server.setText(self.settings_aprs_server.text())
            if hasattr(self, 'settings_aprs_port'):
                self.aprs_is_port.setValue(self.settings_aprs_port.value())
            self.aprs_is_filter.setText(self._build_aprs_filter())
            server = self.aprs_is_server.text().strip()
            port = self.aprs_is_port.value()
            filter_str = self.aprs_is_filter.text().strip()
            callsign = self.callsign_edit.text().strip().upper()
            if not callsign or callsign == "N0CALL":
                QMessageBox.warning(self, "Error", "Set your callsign first in the Transmit tab")
                return
            self._log(f"🌐 Connecting to APRS-IS: {server}:{port}")
            self.aprs_is_info_label.setText(f"{server}:{port}")
            self.aprs_is_thread = threading.Thread(
                target=self._aprs_is_worker,
                args=(server, port, callsign, filter_str),
                daemon=True
            )
            self.aprs_is_running = True
            self.aprs_is_thread.start()
            self.aprs_is_connect_btn.setText("■ STOP IS")
            self.aprs_is_connect_btn.setStyleSheet("""
                QPushButton {
                    background: #01579b; color: #fff;
                    font-weight: bold; padding: 2px 10px;
                    border-radius: 3px; border: 1px solid #0277bd;
                    font-size: 10px;
                }
                QPushButton:hover { background: #0277bd; }
            """)
            self.aprs_is_status.setStyleSheet("color: #ffb74d; font-size: 14px;")

    def _auto_connect_aprs_is(self):
        """Auto-connect to APRS-IS"""
        if not self.aprs_is_running:
            self._log("🚀 Auto-connecting APRS-IS...")
            self._toggle_aprs_is_from_settings()

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _aprs_is_worker(self, server, port, callsign, filter_str):
        """Background thread for APRS-IS connection"""
        try:
            self.aprs_is_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.aprs_is_socket.settimeout(10)
            self.aprs_is_socket.connect((server, port))
            passcode = "-1"
            if hasattr(self, 'settings_aprs_passcode'):
                pc = self.settings_aprs_passcode.text().strip()
                if pc:
                    passcode = pc
            login = f"user {callsign} pass {passcode} vers PyTNC-Pro 0.1.3"
            if filter_str:
                login += f" filter {filter_str}"
            login += "\r\n"
            self.aprs_is_socket.send(login.encode())
            self.aprs_is_connected_signal.emit()
            buffer = ""
            self.aprs_is_socket.settimeout(1)
            while self.aprs_is_running:
                try:
                    data = self.aprs_is_socket.recv(1024)
                    if not data:
                        break
                    buffer += data.decode('latin-1', errors='ignore')
                    while '\r\n' in buffer:
                        line, buffer = buffer.split('\r\n', 1)
                        if line and not line.startswith('#'):
                            try:
                                self.aprs_is_packet_signal.emit(line)
                            except RuntimeError:
                                self.aprs_is_running = False
                                return
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.aprs_is_running:
                        try:
                            self.aprs_is_error_signal.emit(f"⚠️ APRS-IS error: {e}")
                        except RuntimeError:
                            pass
                    break
        except Exception as e:
            try:
                self.aprs_is_error_signal.emit(f"❌ APRS-IS connection failed: {e}")
            except RuntimeError:
                pass
        finally:
            self.aprs_is_running = False
            try:
                self.aprs_is_disconnected_signal.emit()
            except RuntimeError:
                pass

    # ------------------------------------------------------------------
    # Signal handlers (called on main thread via signals)
    # ------------------------------------------------------------------

    def _aprs_is_connected(self):
        """Called when APRS-IS connects successfully"""
        self.aprs_is_connected = True
        self.aprs_is_status.setStyleSheet("color: #69f0ae; font-size: 14px;")
        self.aprs_is_connect_btn.setText("■ STOP IS")
        self.aprs_is_connect_btn.setStyleSheet("""
            QPushButton {
                background: #01579b; color: #fff;
                font-weight: bold; padding: 2px 10px;
                border-radius: 3px; border: 1px solid #0277bd;
                font-size: 10px;
            }
            QPushButton:hover { background: #0277bd; }
        """)
        self._log("✅ Connected to APRS-IS")
        server = self.aprs_is_server.text().strip()
        port = self.aprs_is_port.value()
        self._igate_log_entry(f"🌐 APRS-IS connected → {server}:{port}", "#69f0ae")
        if hasattr(self, 'igate_rx_check') and self.igate_rx_check.isChecked():
            self._igate_log_entry("✅ RX IGate active — ready to gate RF packets", "#69f0ae")
        else:
            self._igate_log_entry("ℹ️ APRS-IS up — enable RX IGate checkbox to start gating", "#64b5f6")
        if hasattr(self, 'settings_aprs_status'):
            self.settings_aprs_status.setText("🟢 Connected")
            self.settings_aprs_status.setStyleSheet("color: #69f0ae;")
            self.settings_aprs_connect_btn.setText("Disconnect")
        self._sync_beacon_connection_status()

    def _aprs_is_disconnected(self):
        """Called when APRS-IS disconnects"""
        self.aprs_is_connected = False
        self.aprs_is_connect_btn.setText("🌐 START IS")
        self.aprs_is_connect_btn.setStyleSheet("""
            QPushButton {
                background: #0277bd; color: #fff;
                font-weight: bold; padding: 2px 10px;
                border-radius: 3px; border: 1px solid #0288d1;
                font-size: 10px;
            }
            QPushButton:hover { background: #0288d1; }
        """)
        self.aprs_is_status.setStyleSheet("color: #ff6b6b; font-size: 14px;")
        self.aprs_is_info_label.setText("")
        self._igate_log_entry("🔴 APRS-IS disconnected — IGate offline", "#ef5350")
        if hasattr(self, 'settings_aprs_status'):
            self.settings_aprs_status.setText("⚫ Disconnected")
            self.settings_aprs_status.setStyleSheet("color: #ef5350;")
            self.settings_aprs_connect_btn.setText("Connect")
        self._sync_beacon_connection_status()

    # ------------------------------------------------------------------
    # Packet handler
    # ------------------------------------------------------------------

    def _handle_aprs_is_packet(self, line):
        """Handle incoming APRS-IS packet"""
        import sys
        _g = sys.modules['__main__'].__dict__
        callsigns_match = _g['callsigns_match']
        clean_aprs_comment = _g['clean_aprs_comment']
        try:
            if '>' not in line or ':' not in line:
                return
            if self.igate_tx_enabled:
                self._gate_packet_to_rf(line)
            src, rest = line.split('>', 1)
            path_part, payload = rest.split(':', 1)
            path_parts = path_part.split(',')
            dst = path_parts[0] if path_parts else ""
            via = ','.join(path_parts[1:]) if len(path_parts) > 1 else ""
            my_call = self.callsign_edit.text().strip().upper()
            my_ssid = self.ssid_combo.currentData()
            my_full = f"{my_call}-{my_ssid}" if my_ssid > 0 else my_call
            if callsigns_match(src, my_full):
                digis_used = [p.rstrip('*') for p in path_parts[1:] if '*' in p and not p.startswith(('qA', 'TCPIP'))]
                if digis_used:
                    digi_str = ' → '.join(digis_used)
                    self._log(f"<span style='color:#69f0ae;font-weight:bold'>📡 YOUR PACKET via: {digi_str}</span>")
                else:
                    for p in path_parts:
                        if p.startswith('qAR') or p.startswith('qAO'):
                            idx = path_parts.index(p)
                            if idx + 1 < len(path_parts):
                                igate = path_parts[idx + 1]
                                self._log(f"<span style='color:#69f0ae;font-weight:bold'>📡 YOUR PACKET heard by IGate: {igate}</span>")
                            break
            timestamp = datetime.now().strftime("%H:%M:%S")
            for digi in path_parts[1:]:
                digi_clean = digi.rstrip('*').upper()
                if digi_clean and not digi_clean.startswith(('TCPIP', 'qA', 'WIDE', 'RELAY')):
                    if digi_clean not in self.digi_traffic:
                        self.digi_traffic[digi_clean] = []
                    self.digi_traffic[digi_clean].append((src, timestamp))
                    self.digi_traffic[digi_clean] = self.digi_traffic[digi_clean][-20:]
            self._log(f"🌐 <a href='aprs://pan/{src}' style='color:#ffd54f;text-decoration:none;font-weight:bold'>{src}</a><span style='color:#ffd54f'>&gt;{dst} via {via}</span>")
            self.packets += 1
            self.pkt_lbl.setText(f"Packets: {self.packets}")
            if payload.startswith('>'):
                status_text = payload[1:].strip()
                self.station_status[src] = status_text
                clean_status = clean_aprs_comment(status_text, 80)
                if clean_status:
                    self._log(f"  📝 {clean_status}", "#64b5f6")
            if payload.startswith(':'):
                m = _APRS_MSG_RE.match(payload)
                if m:
                    msg_dest = m.group("addressee").strip().upper()
                    msg_content = m.group("text")
                    if msg_dest:
                        is_for_me = callsigns_match(msg_dest, my_full)
                        if is_for_me:
                            if msg_content.startswith('ack'):
                                self._handle_ack(src, msg_content[3:].strip())
                            elif msg_content.startswith('rej'):
                                self._log(f"❌ Message {msg_content[3:].strip()} rejected by {src}")
                            elif msg_content:
                                seq = None
                                if '{' in msg_content:
                                    msg_text, seq = msg_content.rsplit('{', 1)
                                    seq = seq.strip()
                                else:
                                    msg_text = msg_content
                                self._handle_incoming_message(src, msg_dest, msg_text.strip(), seq)
            self._parse_aprs_is_position(src, dst, via, payload)
        except Exception as e:
            if hasattr(self, '_aprs_parse_errors'):
                self._aprs_parse_errors += 1
            else:
                self._aprs_parse_errors = 1
            if self._aprs_parse_errors <= 10:
                self._log(f"⚠️ APRS-IS parse: {e}")

    # ------------------------------------------------------------------
    # Position parser
    # ------------------------------------------------------------------

    def _parse_aprs_is_position(self, callsign, dst, via, payload):
        """Extract position from APRS-IS payload and add to map with detailed tooltip"""
        import sys
        _g = sys.modules['__main__'].__dict__
        icon_path = _g['icon_path']
        make_overlay = _g['make_overlay']
        clean_aprs_comment = _g['clean_aprs_comment']
        TOCALL_DEVICES = _g['TOCALL_DEVICES']
        BASE_DIR = _g['BASE_DIR']
        try:
            if len(payload) < 1:
                return
            data_type = payload[0]
            lat = lon = None
            sym_table = "/"
            sym_code = ">"
            comment = ""
            speed_mph = None
            course = None
            altitude_ft = None
            weather = {}

            if data_type in '!=':
                pos_data = payload[1:]
                if len(pos_data) >= 13 and pos_data[0] in '/\\ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                    lat, lon, sym_table, sym_code, comment, speed_mph, course = self._parse_compressed_pos(pos_data)
                elif len(payload) >= 20:
                    lat, lon, sym_table, sym_code, comment = self._parse_uncompressed_pos(payload[1:])
                    if len(comment) >= 7 and comment[3] == '/':
                        try:
                            course = int(comment[0:3])
                            speed_mph = int(comment[4:7]) * 1.15078
                            comment = comment[7:].strip()
                        except (ValueError, IndexError):
                            pass

            elif data_type in '/@':
                pos_data = payload[8:] if len(payload) >= 8 else ""
                if len(pos_data) >= 13 and pos_data[0] in '/\\ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                    lat, lon, sym_table, sym_code, comment, speed_mph, course = self._parse_compressed_pos(pos_data)
                elif len(payload) >= 27:
                    lat, lon, sym_table, sym_code, comment = self._parse_uncompressed_pos(payload[8:])
                    if len(comment) >= 7 and comment[3] == '/':
                        try:
                            course = int(comment[0:3])
                            speed_mph = int(comment[4:7]) * 1.15078
                            comment = comment[7:].strip()
                        except (ValueError, IndexError):
                            pass

            elif data_type == ';':
                if len(payload) >= 31:
                    obj_name = payload[1:10].strip()
                    if payload[10] == '*':
                        pos_data = payload[18:]
                        if len(pos_data) >= 13 and pos_data[0] in '/\\ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                            try:
                                lat, lon, sym_table, sym_code, comment, speed_mph, course = self._parse_compressed_pos(pos_data)
                            except Exception:
                                lat, lon, sym_table, sym_code, comment = self._parse_uncompressed_pos(pos_data)
                        else:
                            lat, lon, sym_table, sym_code, comment = self._parse_uncompressed_pos(pos_data)
                        callsign = obj_name

            elif data_type == '`' or data_type == "'":
                lat, lon, speed_mph, course, sym_table, sym_code = self._parse_mice(dst, payload)

            if comment:
                alt_match = re.search(r'/A=(-?\d{6})', comment)
                if alt_match:
                    altitude_ft = int(alt_match.group(1))
                    comment = re.sub(r'/A=-?\d{6}', '', comment).strip()
                wx_match = re.search(r'(\d{3})/(\d{3})(?:g(\d{3}))?t(-?\d{3})', comment)
                if wx_match:
                    weather['wind_dir'] = int(wx_match.group(1))
                    weather['wind_speed'] = int(wx_match.group(2))
                    if wx_match.group(3):
                        weather['wind_gust'] = int(wx_match.group(3))
                    weather['temp_f'] = int(wx_match.group(4))
                if 't' in comment and not weather:
                    for pat, key in [(r't(-?\d{3})', 'temp_f'), (r'h(\d{2})', 'humidity'),
                                     (r'b(\d{5})', 'baro_mb'), (r'c(\d{3})', 'wind_dir'),
                                     (r's(\d{3})', 'wind_speed'), (r'g(\d{3})', 'wind_gust'),
                                     (r'r(\d{3})', 'rain_1h'), (r'[Ll](\d{3})', 'luminosity')]:
                        m = re.search(pat, comment)
                        if m:
                            val = int(m.group(1))
                            if key == 'humidity':
                                val = 100 if val == 0 else val
                            elif key == 'baro_mb':
                                val = val / 10.0
                            elif key == 'rain_1h':
                                val = val / 100.0
                            weather[key] = val
                if weather:
                    comment = re.sub(r'^\.{0,3}/\d{3}', '', comment)
                    comment = re.sub(r'^\d{3}/\d{3}', '', comment)
                    wt = r'(?:b\d{5}|[Ll]\d{3}|#\d{3,5}|c\d{3}|s\d{3}|g\d{3}|t-?\d{3}|r\d{3}|p\d{3}|P\d{3}|h\d{2})'
                    comment = re.sub(r'^' + wt + r'+', '', comment)
                    comment = re.sub(r'(?<!\w)' + wt + r'(?!\w)', '', comment)
                    comment = re.sub(r'^[./]+', '', comment)
                    comment = ' '.join(comment.split())

            phg_info = None
            if comment:
                phg_match = re.search(r'PHG(\d)(\d)(\d)(\d)', comment)
                if phg_match:
                    p, h, g, d = [int(x) for x in phg_match.groups()]
                    dir_names = ['omni', '45° NE', '90° E', '135° SE', '180° S', '225° SW', '270° W', '315° NW', '360° N']
                    phg_info = f"{p*p}W, {10*(2**h)}ft HAAT, {g}dBi {dir_names[d] if d < len(dir_names) else 'omni'}"
                    comment = re.sub(r'PHG\d{4}/?', '', comment).strip()

            grid_square = None
            if comment:
                gm = re.search(r'\b([A-R]{2}\d{2}[a-x]{0,2})\b', comment, re.IGNORECASE)
                if gm:
                    grid_square = gm.group(1).upper()

            if lat is not None and lon is not None:
                ic, ov = icon_path(sym_table, sym_code)
                if ov:
                    ic = make_overlay(ic, ov)
                try:
                    rel_path = ic.relative_to(BASE_DIR)
                    icon_url = f"http://127.0.0.1:{self.http_port}/{rel_path.as_posix()}"
                except ValueError:
                    icon_url = f"http://127.0.0.1:{self.http_port}/aprs_symbols_48/primary/29.png"

                is_digi = False
                ssid = callsign.split('-')[1] if '-' in callsign else ""
                if ssid in ['10', '11', '12', '15'] or sym_code == '#':
                    is_digi = True

                tooltip_parts = []
                if is_digi:
                    tooltip_parts.append("📡 Digipeater")
                    if callsign in self.digi_traffic and self.digi_traffic[callsign]:
                        recent = self.digi_traffic[callsign][-5:]
                        tooltip_parts.append(f"📶 Recent: {', '.join(s[0] for s in reversed(recent))}")
                device = TOCALL_DEVICES.get(dst[:6], TOCALL_DEVICES.get(dst[:5], TOCALL_DEVICES.get(dst[:4], TOCALL_DEVICES.get(dst[:3], ""))))
                if device:
                    tooltip_parts.append(f"📻 {device}")
                if grid_square:
                    tooltip_parts.append(f"🗺️ {grid_square}")
                if phg_info:
                    tooltip_parts.append(f"📶 {phg_info}")
                if speed_mph is not None and speed_mph > 0:
                    speed_str = f"🚗 {speed_mph:.0f} mph"
                    if course is not None:
                        speed_str += f" @ {course}°"
                    tooltip_parts.append(speed_str)
                if altitude_ft is not None:
                    tooltip_parts.append(f"📍 {altitude_ft:,} ft")
                if weather:
                    if 'temp_f' in weather:
                        tooltip_parts.append(f"🌡️ {weather['temp_f']}°F")
                    if 'humidity' in weather:
                        tooltip_parts.append(f"💧 {weather['humidity']}%")
                    if 'wind_speed' in weather or 'wind_dir' in weather:
                        wind_str = "💨"
                        if 'wind_dir' in weather:
                            wind_str += f" {weather['wind_dir']}°"
                        if 'wind_speed' in weather:
                            wind_str += f" {weather['wind_speed']} mph"
                        if 'wind_gust' in weather and weather['wind_gust'] > 0:
                            wind_str += f" (gust {weather['wind_gust']})"
                        tooltip_parts.append(wind_str)
                    if 'baro_mb' in weather:
                        tooltip_parts.append(f"📊 {weather['baro_mb']:.1f} mb")
                    rain_parts = []
                    if 'rain_1h' in weather:
                        rain_parts.append(f"{weather['rain_1h']:.2f}\"/1h")
                    if 'rain_24h' in weather:
                        rain_parts.append(f"{weather['rain_24h']:.2f}\"/24h")
                    if rain_parts:
                        tooltip_parts.append(f"🌧️ {' '.join(rain_parts)}")

                url_pat = r'((?:https?://|www\.)[^\s<>"\']+)'

                if comment and len(comment) > 2:
                    clean_comment = clean_aprs_comment(comment, 120)
                    def _lnk(m):
                        u = m.group(1)
                        h = u if u.startswith('http') else f'https://{u}'
                        return f'<a href="#" onclick="console.log(\'OPEN_EXTERNAL:{h}\');return false;" style="color:#64b5f6">{u}</a>'
                    clean_comment = re.sub(url_pat, _lnk, clean_comment)
                    if clean_comment:
                        tooltip_parts.append(f"💬 {clean_comment}")

                if callsign in self.station_status:
                    st = clean_aprs_comment(self.station_status[callsign], 150)
                    if st:
                        def _lnk_s(m):
                            u = m.group(1)
                            h = u if u.startswith('http') else f'https://{u}'
                            return f'<a href="#" onclick="console.log(\'OPEN_EXTERNAL:{h}\');return false;" style="color:#64b5f6">{u}</a>'
                        st = re.sub(url_pat, _lnk_s, st)
                        tooltip_parts.append(f"📝 {st}")

                tooltip_parts.append(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
                tooltip = "<br>".join(tooltip_parts)

                if comment and len(comment) > 2:
                    clean_cmt = clean_aprs_comment(comment, 80)
                    if clean_cmt:
                        self._log(f"  💬 {clean_cmt}", "#64b5f6")

                call_js = json.dumps(callsign)
                tooltip_js = json.dumps(tooltip)
                via_js = json.dumps(via if via else "")
                is_digi_js = "true" if is_digi else "false"
                js = f"queueStation({call_js},{lat},{lon},'{icon_url}',{tooltip_js},{is_digi_js},{via_js})"
                if self.map_ready:
                    self.map.page().runJavaScript(js)
                else:
                    self.pending_js.append(js)

        except Exception:
            pass

    # ------------------------------------------------------------------
    # Position format parsers
    # ------------------------------------------------------------------

    def _parse_uncompressed_pos(self, data):
        """Parse uncompressed APRS position: DDMM.MMN/DDDMM.MMWSymbol + comment"""
        try:
            if len(data) < 19:
                return None, None, "/", ">", ""
            lat_str, lat_dir = data[0:7], data[7]
            sym_table = data[8]
            lon_str, lon_dir = data[9:17], data[17]
            sym_code = data[18]
            comment = data[19:] if len(data) > 19 else ""
            if lat_dir in 'NS' and lon_dir in 'EW':
                lat = float(lat_str[:2]) + float(lat_str[2:]) / 60.0
                if lat_dir == 'S':
                    lat = -lat
                lon = float(lon_str[:3]) + float(lon_str[3:]) / 60.0
                if lon_dir == 'W':
                    lon = -lon
                return lat, lon, sym_table, sym_code, comment
        except (ValueError, IndexError):
            pass
        return None, None, "/", ">", ""

    def _parse_compressed_pos(self, data):
        """Parse compressed APRS position (base-91 encoded)"""
        try:
            if len(data) < 13:
                return None, None, "/", ">", "", None, None
            sym_table = data[0]
            lat_val = sum((ord(c) - 33) * (91 ** (3 - i)) for i, c in enumerate(data[1:5]))
            lon_val = sum((ord(c) - 33) * (91 ** (3 - i)) for i, c in enumerate(data[5:9]))
            lat = 90.0 - (lat_val / 380926.0)
            lon = -180.0 + (lon_val / 190463.0)
            sym_code = data[9]
            comment = data[13:] if len(data) > 13 else ""
            speed_mph = course = None
            cs = data[10:12] if len(data) >= 12 else "  "
            t_byte = data[12] if len(data) >= 13 else ' '
            if cs != "  " and cs[0] != ' ':
                c_val = ord(cs[0]) - 33
                s_val = ord(cs[1]) - 33
                t = ord(t_byte) - 33 if t_byte != ' ' else 0
                if not (t & 0x18 == 0x10) and 0 <= c_val <= 89:
                    course = c_val * 4
                    speed_mph = (1.08 ** s_val - 1) * 1.15078
            return lat, lon, sym_table, sym_code, comment, speed_mph, course
        except (ValueError, IndexError, TypeError):
            pass
        return None, None, "/", ">", "", None, None

    def _parse_mice(self, dst, payload):
        """Parse Mic-E encoded position from destination field"""
        try:
            if len(dst) < 6 or len(payload) < 9:
                return None, None, None, None, "/", ">"
            lat_digits = ""
            lat_dir = 'N'
            lon_offset = 0
            lon_dir = 'W'
            for i, c in enumerate(dst[:6]):
                if c.isdigit():
                    lat_digits += c
                elif c in 'ABCDEFGHIJ':
                    lat_digits += str(ord(c) - ord('A'))
                elif c in 'KLMNOPQRSTUVWXYZ':
                    lat_digits += str(ord(c) - ord('K'))
                elif c in 'abcdefghij':
                    lat_digits += str(ord(c) - ord('a'))
                else:
                    lat_digits += '0'
                if i == 3 and not (c.isupper() or c.isdigit()):
                    lat_dir = 'S'
                if i == 4 and (c.isupper() or c.isdigit()):
                    lon_offset = 100
                if i == 5 and not (c.isupper() or c.isdigit()):
                    lon_dir = 'E'
            lat = float(lat_digits[:2]) + float(lat_digits[2:4] + '.' + lat_digits[4:6]) / 60.0
            if lat_dir == 'S':
                lat = -lat
            d = ord(payload[1]) - 28 + lon_offset
            if 180 <= d <= 189:
                d -= 80
            elif 190 <= d <= 199:
                d -= 190
            m = ord(payload[2]) - 28
            if m >= 60:
                m -= 60
            h = ord(payload[3]) - 28
            lon = d + (m + h / 100.0) / 60.0
            if lon_dir == 'W':
                lon = -lon
            sp = (ord(payload[4]) - 28) * 10
            dc = ord(payload[5]) - 28
            sp += dc // 10
            course = (dc % 10) * 100 + (ord(payload[6]) - 28)
            speed_mph = sp * 1.15078
            if course >= 400:
                course -= 400
            return lat, lon, speed_mph, course, payload[8], payload[7]
        except Exception:
            return None, None, None, None, "/", ">"
