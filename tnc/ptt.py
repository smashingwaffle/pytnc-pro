"""
ptt.py — PTT control mixin for PyTNC Pro
Supports: RTS/DTR serial, Icom CI-V CAT, CM108 GPIO (DigiRig Lite)
Used as a mixin: class MainWindow(PTTMixin, QMainWindow)
"""

import serial
from PyQt6.QtWidgets import QApplication


class PTTMixin:
    """Mixin providing all PTT-related methods for MainWindow."""

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _ptt_is_connected(self) -> bool:
        """True if PTT is ready to key — RTS/DTR serial, CI-V CAT, or CM108 GPIO"""
        method = getattr(self, 'civ_ptt_method', 'RTS/DTR')
        if method == "CI-V CAT":
            return bool(self.civ_serial and self.civ_serial.is_open)
        if method == "CM108 GPIO":
            return self.cm108_device is not None
        return bool(self.ptt_serial and self.ptt_serial.is_open)

    def _ptt_port_label(self) -> str:
        """Return a short label for the connected PTT port"""
        method = getattr(self, 'civ_ptt_method', 'RTS/DTR')
        if method == "CI-V CAT" and self.civ_serial and self.civ_serial.is_open:
            addr = self.civ_addr_edit.text().strip().upper() if hasattr(self, 'civ_addr_edit') else "88"
            return f"CI-V {self.civ_serial.port} 0x{addr}"
        if method == "CM108 GPIO" and self.cm108_device is not None:
            label = self.cm108_device_combo.currentText() if hasattr(self, 'cm108_device_combo') else "CM108"
            return label.lstrip("🎙 ")
        if self.ptt_serial and self.ptt_serial.is_open:
            return self.ptt_serial.port
        return "Not connected"

    def _get_ptt_mode(self):
        """Get current PTT mode"""
        return getattr(self, 'civ_ptt_method', 'RTS/DTR')

    # ------------------------------------------------------------------
    # UI visibility
    # ------------------------------------------------------------------

    def _on_ptt_method_changed(self, method: str):
        """Show/hide appropriate PTT widgets when method changes"""
        self.civ_ptt_method = method
        is_civ    = (method == "CI-V CAT")
        is_cm108  = (method == "CM108 GPIO")
        is_serial = (method == "RTS/DTR")
        self.ptt_serial_widget.setVisible(is_serial)
        self.ptt_lines_widget.setVisible(is_serial)
        self.civ_widget.setVisible(is_civ)
        self.cm108_widget.setVisible(is_cm108)
        if is_cm108 and self.cm108_device_combo.count() == 0:
            self._cm108_scan()

    # ------------------------------------------------------------------
    # RTS/DTR
    # ------------------------------------------------------------------

    def _toggle_ptt(self):
        """Toggle RTS/DTR PTT serial connection"""
        if self.ptt_serial and self.ptt_serial.is_open:
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
                    self._sync_beacon_connection_status()
                except Exception as e:
                    self.settings_ptt_status.setText("🔴")
                    self.settings_ptt_status.setStyleSheet("color: #ef5350;")
                    self._log(f"❌ PTT error: {e}")

    # ------------------------------------------------------------------
    # CI-V CAT (Icom)
    # ------------------------------------------------------------------

    def _toggle_civ(self):
        """Toggle CI-V CAT serial connection for Icom radios"""
        if self.civ_serial and self.civ_serial.is_open:
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
                self.civ_serial = serial.Serial(
                    port=port, baudrate=baud,
                    bytesize=data_bits, parity=parity,
                    stopbits=stop_bits, timeout=0.5
                )
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

    def _get_civ_ptt_bytes(self, on: bool) -> bytes:
        """Build Icom CI-V PTT command bytes.
        Format: FE FE <radio_addr> E0 1C 00 <01=TX|00=RX> FD
        E0 = controller (us), radio addr from UI field.
        """
        try:
            radio_addr = int(self.civ_addr_edit.text().strip() or "88", 16)
        except ValueError:
            radio_addr = 0x88
        ptt_byte = 0x01 if on else 0x00
        return bytes([0xFE, 0xFE, radio_addr, 0xE0, 0x1C, 0x00, ptt_byte, 0xFD])

    # ------------------------------------------------------------------
    # CM108 GPIO (DigiRig Lite / USB audio dongles)
    # ------------------------------------------------------------------

    def _cm108_scan(self):
        """Enumerate HID devices and populate the CM108 combo with CM108/CM119 candidates"""
        self.cm108_device_combo.clear()
        try:
            import hid
        except ImportError:
            self.cm108_device_combo.addItem("⚠ hidapi not installed — run: pip install hidapi")
            self._log("⚠ CM108 PTT: hidapi not installed — run: pip install hidapi")
            return

        CM108_IDS = {
            (0x0d8c, 0x000c),  # CM108
            (0x0d8c, 0x0008),  # CM108 (alt)
            (0x0d8c, 0x0012),  # CM108B (DigiRig Lite)
            (0x0d8c, 0x013c),  # CM108 (generic)
            (0x0d8c, 0x0013),  # CM119
            (0x0d8c, 0x0014),  # CM119B
            (0x0d8c, 0x0019),  # CM119B (alt)
            (0x0c76, 0x1605),  # CM108 clone
            (0x0c76, 0x1607),  # CM108 clone
        }

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
            self._log(f"✅ CM108 scan: found {len(found)} device(s)")
        else:
            self.cm108_device_combo.addItem("No CM108 device found")
            self._log("⚠ CM108 scan: no CM108/CM119 devices found")

    def _toggle_cm108(self):
        """Open or close the CM108 HID device for GPIO PTT"""
        try:
            import hid
        except ImportError:
            self._log("❌ CM108 PTT: hidapi not installed — run: pip install hidapi")
            return

        if self.cm108_device is not None:
            try:
                self._cm108_set_gpio(False)
                self.cm108_device.close()
            except Exception:
                pass
            self.cm108_device = None
            self.cm108_connect_btn.setText("Connect")
            self.cm108_status.setText("⚫")
            self.cm108_status.setStyleSheet("color: #607d8b;")
            self._sync_beacon_connection_status()
            return

        path = self.cm108_device_combo.currentData()
        if not path:
            self._log("❌ CM108: no device selected — click Scan first")
            return
        try:
            dev = hid.device()
            dev.open_path(path)
            dev.set_nonblocking(True)
            self.cm108_device = dev
            self._cm108_set_gpio(False)
            self.cm108_connect_btn.setText("Disconnect")
            self.cm108_status.setText("🟢")
            self.cm108_status.setStyleSheet("color: #69f0ae;")
            mfr  = dev.get_manufacturer_string() or ""
            prod = dev.get_product_string() or "CM108"
            self._log(f"✅ CM108 PTT connected: {mfr} {prod}")
            self._sync_beacon_connection_status()
        except Exception as e:
            self.cm108_status.setText("🔴")
            self.cm108_status.setStyleSheet("color: #ef5350;")
            self._log(f"❌ CM108 open error: {e}")

    def _cm108_set_gpio(self, on: bool):
        """Send HID output report to set GPIO1 (PTT) on CM108.
        Report: [0x00, 0x00, gpio_byte, 0x00, 0x00]
        gpio_byte: bit0 = GPIO1 value, bit4 = GPIO1 direction (output)
        Direwolf-compatible.
        """
        if self.cm108_device is None:
            return
        gpio_byte = 0x11 if on else 0x10
        try:
            self.cm108_device.write([0x00, 0x00, gpio_byte, 0x00, 0x00])
        except Exception as e:
            self._log(f"❌ CM108 GPIO write error: {e}")

    # ------------------------------------------------------------------
    # Core PTT set — routes to whichever method is active
    # ------------------------------------------------------------------

    def _set_ptt(self, on: bool):
        """Set PTT state — routes to RTS/DTR, CI-V CAT, or CM108 GPIO"""
        method = getattr(self, 'civ_ptt_method', 'RTS/DTR')

        if method == "CM108 GPIO":
            self._cm108_set_gpio(on)

        elif method == "CI-V CAT":
            if not self.civ_serial or not self.civ_serial.is_open:
                return
            try:
                cmd = self._get_civ_ptt_bytes(on)
                self.civ_serial.write(cmd)
                self.civ_serial.flush()
            except Exception as e:
                self._log(f"❌ CI-V PTT error: {e}")

        else:  # RTS/DTR
            if not self.ptt_serial or not self.ptt_serial.is_open:
                return
            rts_mode = self.ptt_rts_combo.currentText() if hasattr(self, 'ptt_rts_combo') else "Off"
            dtr_mode = self.ptt_dtr_combo.currentText() if hasattr(self, 'ptt_dtr_combo') else "High=TX"
            if rts_mode == "High=TX":
                self.ptt_serial.rts = on
            elif rts_mode == "Low=TX":
                self.ptt_serial.rts = not on
            else:
                self.ptt_serial.rts = False
            if dtr_mode == "High=TX":
                self.ptt_serial.dtr = on
            elif dtr_mode == "Low=TX":
                self.ptt_serial.dtr = not on
            else:
                self.ptt_serial.dtr = False

        if hasattr(self, 'tx_ptt_status'):
            if on:
                self.tx_ptt_status.setText("🔴 PTT: TX")
                self.tx_ptt_status.setStyleSheet("color: #ff1744; font-weight: bold;")
            else:
                self.tx_ptt_status.setText("🟢 PTT: Connected")
                self.tx_ptt_status.setStyleSheet("color: #69f0ae;")
            QApplication.processEvents()

    # ------------------------------------------------------------------
    # Test button
    # ------------------------------------------------------------------

    def _ptt_test_on(self):
        """PTT test button pressed - key TX"""
        method = getattr(self, 'civ_ptt_method', 'RTS/DTR')
        connected = (self.civ_serial and self.civ_serial.is_open) if method == "CI-V CAT" \
                    else (self.ptt_serial and self.ptt_serial.is_open)
        if not connected:
            self._log("❌ PTT not connected - connect first!")
            return
        self._set_ptt(True)
        self.ptt_test_btn.setText("🔴 TX ON!")
        self.ptt_test_btn.setStyleSheet("""
            QPushButton { background: #ff1744; color: white; font-weight: bold; border-radius: 4px; padding: 4px; }
        """)
        self._log("🔴 PTT TEST: TX ON")

    def _ptt_test_off(self):
        """PTT test button released - unkey TX"""
        self._set_ptt(False)
        self._log("⚪ PTT TEST: TX OFF")
        self.ptt_test_btn.setText("🔴 Test PTT")
        self.ptt_test_btn.setStyleSheet("""
            QPushButton { background: #c62828; color: white; font-weight: bold; border-radius: 4px; padding: 4px; }
            QPushButton:hover { background: #e53935; }
            QPushButton:pressed { background: #b71c1c; }
        """)
