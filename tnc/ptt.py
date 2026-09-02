"""
ptt.py — PTT control mixin for PyTNC Pro
Supports: RTS/DTR serial, Icom CI-V CAT, Yaesu CAT, CM108 GPIO
Used as a mixin: class MainWindow(PTTMixin, QMainWindow)
"""

import serial
from PyQt6.QtWidgets import QApplication


class PTTMixin:
    """Mixin providing all PTT-related methods for MainWindow."""

    def _ptt_is_connected(self) -> bool:
        method = getattr(self, 'civ_ptt_method', 'RTS/DTR')
        if method == "CI-V CAT":
            return bool(getattr(self, 'civ_serial', None) and self.civ_serial.is_open)
        if method == "Yaesu CAT":
            return bool(getattr(self, 'yaesu_serial', None) and self.yaesu_serial.is_open)
        if method == "CM108 GPIO":
            return getattr(self, 'cm108_device', None) is not None
        return bool(getattr(self, 'ptt_serial', None) and self.ptt_serial.is_open)

    def _ptt_port_label(self) -> str:
        method = getattr(self, 'civ_ptt_method', 'RTS/DTR')
        if method == "CI-V CAT" and getattr(self, 'civ_serial', None) and self.civ_serial.is_open:
            addr = self.civ_addr_edit.text().strip().upper() if hasattr(self, 'civ_addr_edit') else "88"
            return f"CI-V {self.civ_serial.port} 0x{addr}"
        if method == "Yaesu CAT" and getattr(self, 'yaesu_serial', None) and self.yaesu_serial.is_open:
            return f"Yaesu CAT {self.yaesu_serial.port}"
        if method == "CM108 GPIO" and getattr(self, 'cm108_device', None) is not None:
            label = self.cm108_device_combo.currentText() if hasattr(self, 'cm108_device_combo') else "CM108"
            return label.lstrip("🎙 ")
        if getattr(self, 'ptt_serial', None) and self.ptt_serial.is_open:
            return self.ptt_serial.port
        return "Not connected"

    def _get_ptt_mode(self):
        return getattr(self, 'civ_ptt_method', 'RTS/DTR')

    def _on_ptt_method_changed(self, method: str):
        self.civ_ptt_method = method
        is_serial = (method == "RTS/DTR")
        is_civ    = (method == "CI-V CAT")
        is_yaesu  = (method == "Yaesu CAT")
        is_cm108  = (method == "CM108 GPIO")
        if hasattr(self, 'ptt_serial_widget'):  self.ptt_serial_widget.setVisible(is_serial)
        if hasattr(self, 'ptt_lines_widget'):   self.ptt_lines_widget.setVisible(is_serial)
        if hasattr(self, 'civ_widget'):         self.civ_widget.setVisible(is_civ)
        if hasattr(self, 'yaesu_widget'):       self.yaesu_widget.setVisible(is_yaesu)
        if hasattr(self, 'cm108_widget'):       self.cm108_widget.setVisible(is_cm108)
        if is_cm108 and hasattr(self, 'cm108_device_combo') and self.cm108_device_combo.count() == 0:
            self._cm108_scan()

    # ------------------------------------------------------------------
    # Master PTT dispatcher
    # ------------------------------------------------------------------

    def _set_ptt(self, on: bool):
        method = getattr(self, 'civ_ptt_method', 'RTS/DTR')
        if method == "CI-V CAT":
            self._set_ptt_civ(on)
        elif method == "Yaesu CAT":
            self._set_ptt_yaesu(on)
        elif method == "CM108 GPIO":
            self._cm108_set_gpio(on)
        else:
            self._set_ptt_serial(on)
        if hasattr(self, 'tx_ptt_status'):
            if on:
                self.tx_ptt_status.setText("🔴 PTT: TX")
                self.tx_ptt_status.setStyleSheet("color: #ff1744; font-weight: bold;")
            else:
                self.tx_ptt_status.setText("🟢 PTT: Connected")
                self.tx_ptt_status.setStyleSheet("color: #69f0ae;")
            QApplication.processEvents()

    # ------------------------------------------------------------------
    # RTS/DTR
    # ------------------------------------------------------------------

    def _toggle_ptt(self):
        if getattr(self, 'ptt_serial', None) and self.ptt_serial.is_open:
            self._set_ptt(False)
            self.ptt_serial.close()
            self.ptt_serial = None
            self.settings_ptt_btn.setText("Connect")
            self.settings_ptt_status.setText("⚫")
            self.settings_ptt_status.setStyleSheet("color: #607d8b;")
            self._sync_beacon_connection_status()
        else:
            port = self.settings_ptt_combo.currentData()
            if port:
                try:
                    self.ptt_serial = serial.Serial(port, 9600, timeout=0.1)
                    self._set_ptt(False)
                    self.settings_ptt_btn.setText("Disconnect")
                    self.settings_ptt_status.setText("🟢")
                    self.settings_ptt_status.setStyleSheet("color: #69f0ae;")
                    self._log(f"✅ RTS/DTR PTT connected: {port}")
                    self._sync_beacon_connection_status()
                except Exception as e:
                    self.settings_ptt_status.setText("🔴")
                    self.settings_ptt_status.setStyleSheet("color: #ef5350;")
                    self._log(f"❌ PTT error: {e}")

    def _set_ptt_serial(self, on: bool):
        s = getattr(self, 'ptt_serial', None)
        if not s or not s.is_open:
            return
        rts_mode = self.ptt_rts_combo.currentText() if hasattr(self, 'ptt_rts_combo') else "Off"
        dtr_mode = self.ptt_dtr_combo.currentText() if hasattr(self, 'ptt_dtr_combo') else "High=TX"
        s.rts = on if rts_mode == "High=TX" else (not on if rts_mode == "Low=TX" else False)
        s.dtr = on if dtr_mode == "High=TX" else (not on if dtr_mode == "Low=TX" else False)

    # ------------------------------------------------------------------
    # Icom CI-V CAT
    # ------------------------------------------------------------------

    def _toggle_civ(self):
        if getattr(self, 'civ_serial', None) and self.civ_serial.is_open:
            self._set_ptt(False)
            self.civ_serial.close()
            self.civ_serial = None
            self.civ_connect_btn.setText("Connect")
            self.civ_status.setText("⚫")
            self.civ_status.setStyleSheet("color: #607d8b;")
            self._sync_beacon_connection_status()
        else:
            port = self.civ_port_combo.currentData()
            if not port:
                self._log("❌ CI-V: No port selected")
                return
            baud = int(self.civ_baud_combo.currentText())
            data_bits = int(self.civ_data_combo.currentText())
            parity_map = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, "Odd": serial.PARITY_ODD}
            parity = parity_map.get(self.civ_parity_combo.currentText(), serial.PARITY_NONE)
            stop_bits = float(self.civ_stop_combo.currentText())
            try:
                self.civ_serial = serial.Serial(port=port, baudrate=baud, bytesize=data_bits,
                                                parity=parity, stopbits=stop_bits, timeout=0.5)
                self._set_ptt(False)
                self.civ_connect_btn.setText("Disconnect")
                self.civ_status.setText("🟢")
                self.civ_status.setStyleSheet("color: #69f0ae;")
                addr_hex = self.civ_addr_edit.text().strip() or "88"
                self._log(f"✅ CI-V connected: {port} @ {baud} baud, addr 0x{addr_hex.upper()}")
                self._sync_beacon_connection_status()
            except Exception as e:
                self.civ_status.setText("🔴")
                self.civ_status.setStyleSheet("color: #ef5350;")
                self._log(f"❌ CI-V error: {e}")

    def _set_ptt_civ(self, on: bool):
        s = getattr(self, 'civ_serial', None)
        if not s or not s.is_open:
            return
        try:
            radio_addr = int(self.civ_addr_edit.text().strip() or "88", 16)
        except ValueError:
            radio_addr = 0x88
        cmd = bytes([0xFE, 0xFE, radio_addr, 0xE0, 0x1C, 0x00, 0x01 if on else 0x00, 0xFD])
        try:
            s.write(cmd)
        except Exception as e:
            self._log(f"❌ CI-V PTT error: {e}")

    # ------------------------------------------------------------------
    # Yaesu CAT (FT-991A, FT-891, FT-710 etc.)
    # ------------------------------------------------------------------

    def _toggle_yaesu_cat(self):
        if getattr(self, 'yaesu_serial', None) and self.yaesu_serial.is_open:
            self._set_ptt(False)
            self.yaesu_serial.close()
            self.yaesu_serial = None
            if hasattr(self, 'yaesu_connect_btn'): self.yaesu_connect_btn.setText("Connect")
            if hasattr(self, 'yaesu_status'):
                self.yaesu_status.setText("⚫")
                self.yaesu_status.setStyleSheet("color: #607d8b;")
            self._log("🔌 Yaesu CAT disconnected")
            self._sync_beacon_connection_status()
        else:
            port = self.yaesu_port_combo.currentData() if hasattr(self, 'yaesu_port_combo') else None
            if not port:
                self._log("❌ Yaesu CAT: No port selected")
                return
            baud = int(self.yaesu_baud_combo.currentText()) if hasattr(self, 'yaesu_baud_combo') else 38400
            try:
                self.yaesu_serial = serial.Serial(port=port, baudrate=baud, bytesize=8,
                                                  parity=serial.PARITY_NONE, stopbits=1,
                                                  rtscts=False, timeout=0.5)
                self._set_ptt(False)
                if hasattr(self, 'yaesu_connect_btn'): self.yaesu_connect_btn.setText("Disconnect")
                if hasattr(self, 'yaesu_status'):
                    self.yaesu_status.setText("🟢")
                    self.yaesu_status.setStyleSheet("color: #69f0ae;")
                self._log(f"✅ Yaesu CAT connected: {port} @ {baud} baud")
                self._sync_beacon_connection_status()
            except Exception as e:
                if hasattr(self, 'yaesu_status'):
                    self.yaesu_status.setText("🔴")
                    self.yaesu_status.setStyleSheet("color: #ef5350;")
                self._log(f"❌ Yaesu CAT error: {e}")

    def _set_ptt_yaesu(self, on: bool):
        """Send Yaesu CAT PTT: TX1; = TX, RX; = RX"""
        s = getattr(self, 'yaesu_serial', None)
        if not s or not s.is_open:
            return
        try:
            s.write(b"TX1;" if on else b"RX;")
        except Exception as e:
            self._log(f"❌ Yaesu CAT PTT error: {e}")

    # ------------------------------------------------------------------
    # CM108 GPIO
    # ------------------------------------------------------------------

    def _cm108_scan(self):
        if not hasattr(self, 'cm108_device_combo') or self.cm108_device_combo is None:
            return
        self.cm108_device_combo.clear()
        try:
            import hid
        except ImportError:
            self.cm108_device_combo.addItem("⚠ hidapi not installed — pip install hidapi")
            return
        CM108_IDS = {(0x0d8c,0x000c),(0x0d8c,0x0008),(0x0d8c,0x0012),(0x0d8c,0x013c),
                     (0x0d8c,0x0013),(0x0d8c,0x0014),(0x0d8c,0x0019),(0x0c76,0x1605),(0x0c76,0x1607)}
        found = []
        try:
            for dev in hid.enumerate():
                vid, pid = dev['vendor_id'], dev['product_id']
                if (vid, pid) in CM108_IDS:
                    label = dev.get('product_string') or f"CM108 {vid:04x}:{pid:04x}"
                    found.append((label, dev['path']))
        except Exception as e:
            self._log(f"❌ CM108 scan error: {e}")
            return
        if found:
            for label, path in found:
                self.cm108_device_combo.addItem(f"🎙 {label}", path)
            self._log(f"✅ CM108 scan: {len(found)} device(s)")
        else:
            self.cm108_device_combo.addItem("No CM108 device found")

    def _toggle_cm108(self):
        try:
            import hid
        except ImportError:
            self._log("❌ CM108 PTT: hidapi not installed")
            return
        if getattr(self, 'cm108_device', None) is not None:
            try:
                self._cm108_set_gpio(False)
                self.cm108_device.close()
            except Exception:
                pass
            self.cm108_device = None
            if hasattr(self, 'cm108_status'): self.cm108_status.setText("⚫")
            if hasattr(self, 'cm108_connect_btn'): self.cm108_connect_btn.setText("Connect")
            self._log("🔌 CM108 disconnected")
            return
        path = self.cm108_device_combo.currentData() if hasattr(self, 'cm108_device_combo') else None
        if not path:
            self._log("❌ No CM108 device selected")
            return
        try:
            dev = hid.device()
            dev.open_path(path)
            self.cm108_device = dev
            if hasattr(self, 'cm108_status'): self.cm108_status.setText("🟢")
            if hasattr(self, 'cm108_connect_btn'): self.cm108_connect_btn.setText("Disconnect")
            self._log(f"✅ CM108 connected: {self.cm108_device_combo.currentText()}")
        except Exception as e:
            self.cm108_device = None
            self._log(f"❌ CM108 connect failed: {e}")

    def _cm108_set_gpio(self, on: bool):
        if getattr(self, 'cm108_device', None) is None:
            return
        try:
            self.cm108_device.write(bytes([0x00, 0x08 if on else 0x00, 0x08, 0x00, 0x00]))
        except Exception as e:
            self._log(f"❌ CM108 GPIO error: {e}")

    # ------------------------------------------------------------------
    # Test buttons
    # ------------------------------------------------------------------

    def _ptt_test_on(self):
        if not self._ptt_is_connected():
            self._log("❌ PTT not connected — connect first!")
            return
        self._set_ptt(True)
        self.ptt_test_btn.setText("🔴 TX ON!")
        self.ptt_test_btn.setStyleSheet(
            "QPushButton { background: #ff1744; color: white; font-weight: bold; border-radius: 4px; padding: 4px; }")
        self._log("🔴 PTT TEST: TX ON")

    def _ptt_test_off(self):
        self._set_ptt(False)
        self._log("⚪ PTT TEST: TX OFF")
        self.ptt_test_btn.setText("🔴 Test PTT")
        self.ptt_test_btn.setStyleSheet("""
            QPushButton { background: #c62828; color: white; font-weight: bold; border-radius: 4px; padding: 4px; }
            QPushButton:hover { background: #e53935; }
            QPushButton:pressed { background: #b71c1c; }
        """)
