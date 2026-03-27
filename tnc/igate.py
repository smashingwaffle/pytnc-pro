"""
igate.py — IGate mixin for PyTNC Pro
Handles: IGate tab UI, RX/TX gate logic, log, beacon
Used as a mixin: class MainWindow(IGateMixin, ...)
"""

import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QCheckBox, QLabel, QSpinBox,
    QLineEdit, QTextBrowser, QPushButton, QMessageBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer


class IGateMixin:
    """Mixin providing all IGate-related methods for MainWindow."""

    # ------------------------------------------------------------------
    # Tab builder
    # ------------------------------------------------------------------

    def _build_igate_tab(self):
        """Build the IGate tab - RX (RF→IS) and TX (IS→RF)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        GRP = """
            QGroupBox {
                color: #a0c4ff; font-weight: bold;
                border: 1px solid #1e3a5f; border-radius: 8px;
                margin-top: 6px; padding-top: 8px; background: #0d2137;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 12px;
                padding: 0 6px; background: #0d2137;
            }
        """
        BTN = """
            QPushButton {{
                background: {bg}; color: #fff; font-weight: bold;
                border: 1px solid {bd}; border-radius: 4px;
                padding: 4px 14px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {hv}; }}
            QPushButton:disabled {{ background: #1a3a5c; color: #607d8b; border-color: #2a5a8a; }}
        """
        LBL = "color: #b0bec5; font-size: 12px;"
        VAL = "color: #ffd54f; font-weight: bold; font-size: 12px;"

        # ── Top row: RX + TX boxes ────────────────────────────────────────────
        top_row = QHBoxLayout()

        # ── RX IGate ─────────────────────────────────────────────────────────
        rx_grp = QGroupBox("📡 RX IGate  (RF → Internet)")
        rx_grp.setStyleSheet(GRP)
        rx_l = QVBoxLayout(rx_grp)

        rx_top = QHBoxLayout()
        self.igate_rx_check = QCheckBox("Enable RX IGate")
        self.igate_rx_check.setStyleSheet("color: #69f0ae; font-weight: bold; font-size: 12px;")
        self.igate_rx_check.setToolTip("Gate RF packets to APRS-IS (requires APRS-IS connected + valid passcode)")
        self.igate_rx_check.stateChanged.connect(self._igate_rx_toggled)
        rx_top.addWidget(self.igate_rx_check)
        rx_top.addStretch()
        self.igate_rx_status_lbl = QLabel("⚫ Inactive")
        self.igate_rx_status_lbl.setStyleSheet("color: #607d8b; font-size: 12px;")
        rx_top.addWidget(self.igate_rx_status_lbl)
        rx_l.addLayout(rx_top)

        rx_stats = QGridLayout()
        rx_stats.setSpacing(4)
        rx_stats.addWidget(QLabel("Packets gated:"), 0, 0)
        self.igate_rx_count_lbl = QLabel("0")
        self.igate_rx_count_lbl.setStyleSheet(VAL)
        rx_stats.addWidget(self.igate_rx_count_lbl, 0, 1)
        rx_stats.addWidget(QLabel("Uptime:"), 1, 0)
        self.igate_uptime_lbl = QLabel("--")
        self.igate_uptime_lbl.setStyleSheet(VAL)
        rx_stats.addWidget(self.igate_uptime_lbl, 1, 1)
        for i in range(rx_stats.count()):
            w = rx_stats.itemAt(i).widget()
            if w and isinstance(w, QLabel) and w.styleSheet() == "":
                w.setStyleSheet(LBL)
        rx_l.addLayout(rx_stats)

        rx_note = QLabel(
            "Rules: skips our own TX, duplicate suppression,\n"
            "won't re-gate TCPIP/qA traffic."
        )
        rx_note.setStyleSheet("color: #7a8f9a; font-size: 12px;")
        rx_l.addWidget(rx_note)
        rx_l.addStretch()
        top_row.addWidget(rx_grp)

        # ── TX IGate ─────────────────────────────────────────────────────────
        tx_grp = QGroupBox("📶 TX IGate  (Internet → RF)")
        tx_grp.setStyleSheet(GRP)
        tx_l = QVBoxLayout(tx_grp)

        tx_top = QHBoxLayout()
        self.igate_tx_check = QCheckBox("Enable TX IGate")
        self.igate_tx_check.setStyleSheet("color: #ffd54f; font-weight: bold; font-size: 12px;")
        self.igate_tx_check.setToolTip(
            "Gate APRS-IS messages to RF for stations recently heard locally.\n"
            "Requires RF running + APRS-IS connected + valid passcode."
        )
        self.igate_tx_check.setEnabled(False)
        self.igate_tx_check.stateChanged.connect(self._igate_tx_toggled)
        tx_top.addWidget(self.igate_tx_check)
        tx_top.addStretch()
        self.igate_tx_status_lbl = QLabel("⚫ Inactive")
        self.igate_tx_status_lbl.setStyleSheet("color: #607d8b; font-size: 12px;")
        tx_top.addWidget(self.igate_tx_status_lbl)
        tx_l.addLayout(tx_top)

        tx_cfg = QGridLayout()
        tx_cfg.setSpacing(4)
        tx_cfg.addWidget(QLabel("RF-heard window:"), 0, 0)
        self.igate_heard_window = QSpinBox()
        self.igate_heard_window.setRange(10, 120)
        self.igate_heard_window.setValue(30)
        self.igate_heard_window.setSuffix(" min")
        self.igate_heard_window.setFixedWidth(80)
        self.igate_heard_window.setToolTip("Only gate to RF stations heard within this window")
        self.igate_heard_window.setStyleSheet("""
            QSpinBox { background: #0a1929; color: #ffd54f;
                       border: 1px solid #1e3a5f; border-radius: 3px; padding: 2px 4px; }
        """)
        tx_cfg.addWidget(self.igate_heard_window, 0, 1)
        self.igate_msg_only_check = QCheckBox("Messages only (recommended)")
        self.igate_msg_only_check.setChecked(True)
        self.igate_msg_only_check.setStyleSheet("color: #b0bec5; font-size: 12px;")
        self.igate_msg_only_check.setToolTip("Only gate :message: packets, not position reports")
        tx_cfg.addWidget(self.igate_msg_only_check, 1, 0, 1, 2)
        for i in range(tx_cfg.count()):
            w = tx_cfg.itemAt(i).widget()
            if w and isinstance(w, QLabel):
                w.setStyleSheet(LBL)
        tx_l.addLayout(tx_cfg)

        tx_stats = QGridLayout()
        tx_stats.setSpacing(4)
        tx_stats.addWidget(QLabel("Packets gated:"), 0, 0)
        self.igate_tx_count_lbl = QLabel("0")
        self.igate_tx_count_lbl.setStyleSheet(VAL)
        tx_stats.addWidget(self.igate_tx_count_lbl, 0, 1)
        tx_stats.addWidget(QLabel("RF stations heard:"), 1, 0)
        self.igate_heard_count_lbl = QLabel("0")
        self.igate_heard_count_lbl.setStyleSheet(VAL)
        tx_stats.addWidget(self.igate_heard_count_lbl, 1, 1)
        for i in range(tx_stats.count()):
            w = tx_stats.itemAt(i).widget()
            if w and isinstance(w, QLabel) and w.styleSheet() == "":
                w.setStyleSheet(LBL)
        tx_l.addLayout(tx_stats)

        tx_note = QLabel(
            "Only gates messages addressed to stations\n"
            "recently heard on RF by this station."
        )
        tx_note.setStyleSheet("color: #7a8f9a; font-size: 12px;")
        tx_l.addWidget(tx_note)
        tx_l.addStretch()
        top_row.addWidget(tx_grp)
        layout.addLayout(top_row)

        # ── Recent gated packets log ──────────────────────────────────────────
        log_grp = QGroupBox("📋 Recently Gated Packets")
        log_grp.setStyleSheet(GRP)
        log_l = QVBoxLayout(log_grp)

        self.igate_log_filter = QLineEdit()
        self.igate_log_filter.setPlaceholderText("🔍 Filter by callsign or keyword...")
        self.igate_log_filter.setClearButtonEnabled(True)
        self.igate_log_filter.setStyleSheet("""
            QLineEdit {
                background: #0a1929; color: #ffd54f;
                border: 1px solid #1e3a5f; border-radius: 4px;
                padding: 4px 8px; font: 11px Consolas, monospace;
            }
            QLineEdit:focus { border-color: #42a5f5; }
        """)
        self.igate_log_filter.textChanged.connect(self._igate_filter_log)
        log_l.addWidget(self.igate_log_filter)

        self.igate_log = QTextBrowser()
        self.igate_log.setReadOnly(True)
        self.igate_log.setFont(QFont("Consolas", 10))
        self.igate_log.setStyleSheet("""
            QTextBrowser {
                background: #0a1628; color: #80cbc4;
                border: 1px solid #1e3a5f; border-radius: 6px; padding: 6px;
            }
        """)
        log_l.addWidget(self.igate_log)

        log_bottom = QHBoxLayout()
        self.igate_log_count_lbl = QLabel("0 entries")
        self.igate_log_count_lbl.setStyleSheet("color: #546e7a; font-size: 11px;")
        log_bottom.addWidget(self.igate_log_count_lbl)
        log_bottom.addStretch()
        clear_btn = QPushButton("🗑️ Clear Log")
        clear_btn.setFixedWidth(110)
        clear_btn.setStyleSheet(BTN.format(bg="#37474f", bd="#546e7a", hv="#455a64"))
        clear_btn.clicked.connect(self._igate_clear_log)
        log_bottom.addWidget(clear_btn)
        log_l.addLayout(log_bottom)
        layout.addWidget(log_grp, 1)

        self.igate_log_history = []

        self._igate_uptime_timer = QTimer()
        self._igate_uptime_timer.timeout.connect(self._igate_update_uptime)
        self._igate_uptime_timer.start(5000)

        self.tabs.addTab(tab, "🌐 IGate")

    # ------------------------------------------------------------------
    # Toggle handlers
    # ------------------------------------------------------------------

    def _igate_rx_toggled(self, state):
        enabled = bool(state)
        self.igate_rx_enabled = enabled
        if enabled:
            if not self.aprs_is_running:
                QMessageBox.warning(self, "IGate", "Connect to APRS-IS first (START IS button).")
                self.igate_rx_check.setChecked(False)
                return
            passcode = ""
            if hasattr(self, 'settings_aprs_passcode'):
                passcode = self.settings_aprs_passcode.text().strip()
            if not passcode or passcode == "-1":
                QMessageBox.warning(self, "IGate",
                    "RX IGate requires a valid APRS-IS passcode.\n"
                    "Set it in Settings → APRS-IS.")
                self.igate_rx_check.setChecked(False)
                return
            self.igate_start_time = datetime.now()
            self.igate_rx_status_lbl.setText("🟢 Active")
            self.igate_rx_status_lbl.setStyleSheet("color: #69f0ae; font-size: 12px;")
            self.igate_tx_check.setEnabled(True)
            self._igate_log_entry("✅ RX IGate started", "#69f0ae")
            self._log("🌐 IGate: RX IGate enabled (RF→IS)")
            QTimer.singleShot(500, self._send_igate_beacon)
        else:
            self.igate_rx_enabled = False
            self.igate_rx_status_lbl.setText("⚫ Inactive")
            self.igate_rx_status_lbl.setStyleSheet("color: #607d8b; font-size: 12px;")
            self.igate_tx_check.setChecked(False)
            self.igate_tx_check.setEnabled(False)
            self._log("🌐 IGate: RX IGate disabled")

    def _igate_tx_toggled(self, state):
        enabled = bool(state)
        self.igate_tx_enabled = enabled
        if enabled:
            self.igate_tx_status_lbl.setText("🟡 Active")
            self.igate_tx_status_lbl.setStyleSheet("color: #ffd54f; font-size: 12px;")
            self._igate_log_entry("✅ TX IGate started", "#ffd54f")
            self._log("🌐 IGate: TX IGate enabled (IS→RF)")
        else:
            self.igate_tx_enabled = False
            self.igate_tx_status_lbl.setText("⚫ Inactive")
            self.igate_tx_status_lbl.setStyleSheet("color: #607d8b; font-size: 12px;")
            self._log("🌐 IGate: TX IGate disabled")

    # ------------------------------------------------------------------
    # Uptime / housekeeping timer
    # ------------------------------------------------------------------

    def _igate_update_uptime(self):
        """Update uptime label and prune stale entries every 5s"""
        if self.igate_rx_enabled and self.igate_start_time:
            delta = datetime.now() - self.igate_start_time
            h, rem = divmod(int(delta.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            self.igate_uptime_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")
        if hasattr(self, 'igate_heard_window'):
            window_secs = self.igate_heard_window.value() * 60
            cutoff = time.time() - window_secs
            self.igate_rf_heard = {k: v for k, v in self.igate_rf_heard.items() if v > cutoff}
            if hasattr(self, 'igate_heard_count_lbl'):
                self.igate_heard_count_lbl.setText(str(len(self.igate_rf_heard)))
        if hasattr(self, 'igate_dedup'):
            cutoff = time.time() - 60
            self.igate_dedup = {k: v for k, v in self.igate_dedup.items() if v > cutoff}

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _igate_log_entry(self, text, color="#80cbc4"):
        """Append a line to the IGate log panel"""
        if not hasattr(self, 'igate_log'):
            return
        ts = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:#546e7a">[{ts}]</span> <span style="color:{color}">{text}</span>'
        if hasattr(self, 'igate_log_history'):
            self.igate_log_history.append((html, text))
            if len(self.igate_log_history) > 500:
                self.igate_log_history = self.igate_log_history[-500:]
        filter_text = ""
        if hasattr(self, 'igate_log_filter'):
            filter_text = self.igate_log_filter.text().strip().upper()
        if not filter_text or filter_text in text.upper():
            self.igate_log.append(html)
            self.igate_log.verticalScrollBar().setValue(
                self.igate_log.verticalScrollBar().maximum())
        if hasattr(self, 'igate_log_count_lbl') and hasattr(self, 'igate_log_history'):
            self.igate_log_count_lbl.setText(f"{len(self.igate_log_history)} entries")

    def _igate_filter_log(self, filter_text):
        """Filter the IGate log by callsign or keyword"""
        if not hasattr(self, 'igate_log_history'):
            return
        filter_text = filter_text.strip().upper()
        self.igate_log.clear()
        for html, raw in self.igate_log_history:
            if not filter_text or filter_text in raw.upper():
                self.igate_log.append(html)
        self.igate_log.verticalScrollBar().setValue(
            self.igate_log.verticalScrollBar().maximum())

    def _igate_clear_log(self):
        """Clear IGate log and history"""
        if hasattr(self, 'igate_log_history'):
            self.igate_log_history = []
        if hasattr(self, 'igate_log'):
            self.igate_log.clear()
        if hasattr(self, 'igate_log_count_lbl'):
            self.igate_log_count_lbl.setText("0 entries")

    # ------------------------------------------------------------------
    # Core gating logic
    # ------------------------------------------------------------------

    def _gate_packet_to_is(self, src, dst, via_str, info, pkt):
        """Gate an RF-heard packet to APRS-IS (RX IGate).
        Format per spec: SRC>DST,PATH,qAR,MYCALL:info
        """
        try:
            if not self.aprs_is_running or not self.aprs_is_socket:
                self._igate_log_entry(f"⛔ {src} — APRS-IS not connected", "#ef5350")
                return
            my_call = self.callsign_edit.text().strip().upper()
            my_ssid = self.ssid_combo.currentData()
            my_full = f"{my_call}-{my_ssid}" if my_ssid > 0 else my_call
            if src.upper() == my_full.upper():
                self._igate_log_entry(f"⏭️ {src} — skipped (our own TX)", "#546e7a")
                return
            path_parts = [p.strip() for p in via_str.split(',') if p.strip()]
            for p in path_parts:
                if p.startswith(('TCPIP', 'qA', 'NOGATE', 'RFONLY')):
                    self._igate_log_entry(f"⏭️ {src} — skipped (internet path: {p})", "#546e7a")
                    return
            if info.startswith('}'):
                self._igate_log_entry(f"⏭️ {src} — skipped (third-party frame)", "#546e7a")
                return
            dedup_key = (src.upper(), info)
            now_t = time.time()
            last_gated = self.igate_dedup.get(dedup_key, 0)
            if now_t - last_gated < 30:
                self._igate_log_entry(f"⏭️ {src} — duplicate (gated {int(now_t - last_gated)}s ago)", "#546e7a")
                return
            self.igate_dedup[dedup_key] = now_t
            if via_str and via_str != "-":
                new_path = f"{dst},{via_str},qAR,{my_full}"
            else:
                new_path = f"{dst},qAR,{my_full}"
            packet = f"{src}>{new_path}:{info}\r\n"
            self._igate_log_entry(f"📡→🌐 Sending: {src}>{new_path}", "#90caf9")
            self.aprs_is_socket.send(packet.encode('latin-1', errors='replace'))
            self.igate_rx_count += 1
            self.igate_rx_count_lbl.setText(str(self.igate_rx_count))
            self._igate_log_entry(f"✅ Gated: {src}>{dst}  {info[:50]}", "#69f0ae")
        except Exception as e:
            self._igate_log_entry(f"⚠️ RX gate error: {e}", "#ef5350")

    def _gate_packet_to_rf(self, line):
        """Gate an APRS-IS packet to RF (TX IGate).
        Only gates :message: packets addressed to stations recently heard on RF.
        """
        try:
            if not self.igate_tx_enabled:
                return
            if '>' not in line or ':' not in line:
                return
            src, rest = line.split('>', 1)
            path_part, payload = rest.split(':', 1)
            if hasattr(self, 'igate_msg_only_check') and self.igate_msg_only_check.isChecked():
                if not payload.startswith(':'):
                    return
            if payload.startswith(':'):
                if len(payload) < 11:
                    return
                addressee = payload[1:10].strip().upper()
                if not addressee:
                    return
                heard_time = self.igate_rf_heard.get(addressee)
                if not heard_time:
                    base = addressee.split('-')[0]
                    heard_time = next(
                        (v for k, v in self.igate_rf_heard.items() if k.split('-')[0] == base),
                        None
                    )
                if not heard_time:
                    return
                window_secs = self.igate_heard_window.value() * 60 if hasattr(self, 'igate_heard_window') else 1800
                if time.time() - heard_time > window_secs:
                    return
            else:
                return
            if 'TCPIP' in path_part or 'qA' in path_part:
                return
            my_call = self.callsign_edit.text().strip().upper()
            my_ssid = self.ssid_combo.currentData()
            my_full = f"{my_call}-{my_ssid}" if my_ssid > 0 else my_call
            inner = f"{src}>{path_part}:{payload}"
            tp_info = f"}}{inner}"
            if hasattr(self, '_queue_rf_packet'):
                self._queue_rf_packet(my_full, "APPR01", "WIDE1-1", tp_info)
            else:
                self._igate_log_entry("⚠️ TX Gate: no RF TX method available", "#ef5350")
                return
            self.igate_tx_count += 1
            self.igate_tx_count_lbl.setText(str(self.igate_tx_count))
            self._igate_log_entry(f"🌐→📻 {src}→{addressee}: {payload[11:50]}", "#ffd54f")
        except Exception as e:
            self._igate_log_entry(f"⚠️ TX gate error: {e}", "#ef5350")

    # ------------------------------------------------------------------
    # IGate beacon
    # ------------------------------------------------------------------

    def _send_igate_beacon(self):
        """Beacon IGate position to APRS-IS with I& overlay symbol"""
        try:
            if not self.aprs_is_running or not self.aprs_is_socket:
                return
            callsign = self.callsign_edit.text().strip().upper()
            ssid = self.ssid_combo.currentData()
            full_call = f"{callsign}-{ssid}" if ssid > 0 else callsign
            if not callsign or callsign == "N0CALL":
                return
            lat = self.gps_lat if (hasattr(self, 'gps_has_fix') and self.gps_has_fix) else None
            if lat is None:
                manual_text = self.manual_location.text().strip() if hasattr(self, 'manual_location') else ""
                if manual_text:
                    try:
                        parts = manual_text.replace(" ", "").split(",")
                        if len(parts) == 2:
                            lat = float(parts[0])
                            lon = float(parts[1])
                    except ValueError:
                        pass
            if lat is None:
                lat = self.lat_edit.value()
                lon = self.lon_edit.value()
            lat_deg = int(abs(lat))
            lat_min = (abs(lat) - lat_deg) * 60
            lat_dir = "N" if lat >= 0 else "S"
            lon_deg = int(abs(lon))
            lon_min = (abs(lon) - lon_deg) * 60
            lon_dir = "E" if lon >= 0 else "W"
            symbol_table = "I"
            symbol_code = "&"
            comment = self.comment_edit.text().strip() if hasattr(self, 'comment_edit') else "PyTNC Pro IGate"
            if not comment:
                comment = "PyTNC Pro IGate"
            pos = f"!{lat_deg:02d}{lat_min:05.2f}{lat_dir}{symbol_table}{lon_deg:03d}{lon_min:05.2f}{lon_dir}{symbol_code}{comment[:43]}"
            packet = f"{full_call}>APPR01,TCPIP*:{pos}\r\n"
            self.aprs_is_socket.send(packet.encode())
            self._igate_log_entry(f"📡 IGate beacon sent: {full_call} I& symbol", "#69f0ae")
            self._log(f"🌐 IGate beacon: {full_call} with IGate symbol")
        except Exception as e:
            self._igate_log_entry(f"⚠️ IGate beacon error: {e}", "#ef5350")
