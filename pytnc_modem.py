#!/usr/bin/env python3
"""
PyTNC Pro - AFSK Modem and Packet Builder

Bell 202 AFSK modulator for APRS TX (1200 baud, 1200/2200 Hz)
AX.25 packet building and FCS calculation
"""

import math
import numpy as np
from typing import List, Tuple

# =============================================================================
# Bell 202 AFSK Modulator for TX
# =============================================================================

# Larger sine table for better quality
_SINE_TABLE_SIZE = 2048
_SINE_TABLE = np.sin(2 * np.pi * np.arange(_SINE_TABLE_SIZE, dtype=np.float32) / _SINE_TABLE_SIZE)


def apply_cosine_ramp(x: np.ndarray, sample_rate: int, ramp_ms: float = 5.0) -> np.ndarray:
    """Apply a short cosine fade-in/out to reduce key-click and improve decoder lock."""
    n = int(sample_rate * (ramp_ms / 1000.0))
    if n <= 1 or n * 2 >= len(x):
        return x
    w = (1.0 - np.cos(np.linspace(0, np.pi, n, dtype=np.float32))) * 0.5
    y = x.copy()
    y[:n] *= w
    y[-n:] *= w[::-1]
    return y


class AFSKModulator:
    """
    Bell 202 AFSK modulator for APRS TX (1200 baud, 1200/2200 Hz)
    
    Features:
    - Fractional bit timing using Bresenham-style accumulator
    - Start in MARK state (Direwolf-like)
    - Proper NRZI encoding
    """
    
    def __init__(self, sample_rate: int):
        self.sample_rate = int(sample_rate)
        self.mark_freq = 1200.0
        self.space_freq = 2200.0
        self.baud_rate = 1200
        
        # Fractional samples/bit support
        self.samples_per_bit = self.sample_rate / self.baud_rate
        self._spb_int = int(math.floor(self.samples_per_bit))
        self._spb_frac = float(self.samples_per_bit - self._spb_int)
        self._frac_acc = 0.0
        
        # Phase in [0,1)
        self.phase = 0.0
        
        # Direwolf-like initial state: start on MARK
        # 0=space(2200), 1=mark(1200)
        self.tone = 1
        
        self.mark_inc = self.mark_freq / self.sample_rate
        self.space_inc = self.space_freq / self.sample_rate
    
    def reset(self):
        self.phase = 0.0
        self.tone = 1  # Start on MARK
        self._frac_acc = 0.0
    
    def _bit_nsamples(self) -> int:
        """
        Compute number of samples for this bit so the average equals samples_per_bit.
        Bresenham-style fractional accumulator.
        """
        n = self._spb_int
        self._frac_acc += self._spb_frac
        if self._frac_acc >= 1.0:
            n += 1
            self._frac_acc -= 1.0
        return max(1, n)
    
    def send_bit(self, data_bit: int, out: List[float]):
        """Append one NRZI-encoded bit worth of samples to `out`."""
        # NRZI: 0 => transition
        if data_bit == 0:
            self.tone = 1 - self.tone
        
        inc = self.mark_inc if self.tone == 1 else self.space_inc
        n = self._bit_nsamples()
        
        for _ in range(n):
            idx = int(self.phase * _SINE_TABLE_SIZE) & (_SINE_TABLE_SIZE - 1)
            out.append(float(_SINE_TABLE[idx]))
            self.phase += inc
            if self.phase >= 1.0:
                self.phase -= 1.0
    
    def generate_packet_audio(self, frame_with_fcs: bytes, 
                               preamble_flags: int = 60,
                               postamble_flags: int = 10) -> np.ndarray:
        """
        Generate complete AFSK audio for an AX.25 frame.
        """
        self.reset()
        
        # 0x7E = 01111110, LSB first
        flag_bits = [0, 1, 1, 1, 1, 1, 1, 0]
        
        # Convert bytes to LSB-first bits
        frame_bits = []
        for b in frame_with_fcs:
            for i in range(8):
                frame_bits.append((b >> i) & 1)
        
        # Bit-stuff after five consecutive ones
        stuffed = []
        ones = 0
        for bit in frame_bits:
            stuffed.append(bit)
            if bit == 1:
                ones += 1
                if ones == 5:
                    stuffed.append(0)
                    ones = 0
            else:
                ones = 0
        
        out: List[float] = []
        
        for _ in range(preamble_flags):
            for bit in flag_bits:
                self.send_bit(bit, out)
        
        for bit in stuffed:
            self.send_bit(bit, out)
        
        for _ in range(postamble_flags):
            for bit in flag_bits:
                self.send_bit(bit, out)
        
        return np.array(out, dtype=np.float32)


class APRSPacketBuilder:
    """Build AX.25 APRS packets"""
    
    @staticmethod
    def encode_callsign(call: str, ssid: int = 0, last: bool = False, c_bit: bool = False) -> bytes:
        """Encode callsign for AX.25 address field
        
        SSID byte format: CRRSSID0 (bit 7 to bit 0)
        - C = command/response bit (bit 7)
        - RR = reserved, set to 11 (bits 6-5)
        - SSID = 4-bit SSID value (bits 4-1)
        - Extension bit = 0 if more addresses follow, 1 if last (bit 0)
        """
        # Pad to 6 characters with spaces
        call = call.upper().ljust(6)[:6]
        
        # Shift left by 1 bit (all address bytes are shifted)
        encoded = bytes([ord(c) << 1 for c in call])
        
        # SSID byte: CRRSSID0 or CRRSSID1 (if last)
        # C = c_bit, RR = 11, SSID = 4 bits, extension = last
        ssid_byte = (0x80 if c_bit else 0x00) | 0x60 | ((ssid & 0x0F) << 1) | (0x01 if last else 0x00)
        
        return encoded + bytes([ssid_byte])
    
    @staticmethod
    def build_ui_packet(src_call: str, src_ssid: int, dst_call: str, dst_ssid: int,
                        path: List[Tuple[str, int]], info: str) -> bytes:
        """Build complete AX.25 UI frame for APRS
        
        UI frames are commands, so:
        - Destination C-bit = 1 (command)
        - Source C-bit = 0
        """
        # Destination address (C-bit=1 for command, never last)
        packet = APRSPacketBuilder.encode_callsign(dst_call, dst_ssid, last=False, c_bit=True)
        
        # Source address (C-bit=0, last only if no path)
        packet += APRSPacketBuilder.encode_callsign(src_call, src_ssid, last=(len(path) == 0), c_bit=False)
        
        # Path (digipeaters) - C-bit=0, H-bit would go in C position but we set 0
        for i, (call, ssid) in enumerate(path):
            is_last = (i == len(path) - 1)
            packet += APRSPacketBuilder.encode_callsign(call, ssid, last=is_last, c_bit=False)
        
        # Control field (UI frame = 0x03)
        packet += bytes([0x03])
        
        # Protocol ID (no layer 3 = 0xF0)
        packet += bytes([0xF0])
        
        # Information field
        packet += info.encode('ascii', errors='replace')
        
        return packet
    
    @staticmethod
    def compute_fcs(data: bytes) -> int:
        """
        AX.25 uses CRC-16/IBM (reversed poly 0x8408), init 0xFFFF, xorout 0xFFFF.
        This matches the common "PPP FCS-16" algorithm and Dire Wolf.
        """
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0x8408
                else:
                    crc >>= 1
        return crc ^ 0xFFFF
