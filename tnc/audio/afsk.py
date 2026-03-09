"""
PyTNC Pro - AFSK Modulator Module

Bell 202 AFSK modulator for APRS TX (1200 baud, 1200/2200 Hz)
"""

import math
from typing import List

import numpy as np


# Larger sine table for better quality
_SINE_TABLE_SIZE = 2048
_SINE_TABLE = np.sin(2 * np.pi * np.arange(_SINE_TABLE_SIZE, dtype=np.float32) / _SINE_TABLE_SIZE)


def apply_cosine_ramp(x: np.ndarray, sample_rate: int, ramp_ms: float = 5.0) -> np.ndarray:
    """Apply a short cosine fade-in/out to reduce key-click and improve decoder lock.
    
    Args:
        x: Audio samples
        sample_rate: Sample rate in Hz
        ramp_ms: Ramp duration in milliseconds
        
    Returns:
        Audio with cosine ramp applied
    """
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
    - Starts in MARK state (Direwolf-like)
    - Proper NRZI encoding
    
    Usage:
        mod = AFSKModulator(22050)
        audio = mod.generate_packet_audio(frame_with_fcs)
    """
    
    def __init__(self, sample_rate: int):
        """Initialize modulator.
        
        Args:
            sample_rate: Audio sample rate in Hz (e.g., 22050, 44100, 48000)
        """
        self.sample_rate = int(sample_rate)
        self.mark_freq = 1200.0   # Mark frequency (binary 1)
        self.space_freq = 2200.0  # Space frequency (binary 0)
        self.baud_rate = 1200     # Bell 202 baud rate
        
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
        """Reset modulator state for new packet."""
        self.phase = 0.0
        self.tone = 1  # Start on MARK
        self._frac_acc = 0.0
    
    def _bit_nsamples(self) -> int:
        """
        Compute number of samples for this bit so the average equals samples_per_bit.
        Uses Bresenham-style fractional accumulator for sub-sample accuracy.
        """
        n = self._spb_int
        self._frac_acc += self._spb_frac
        if self._frac_acc >= 1.0:
            n += 1
            self._frac_acc -= 1.0
        return max(1, n)
    
    def send_bit(self, data_bit: int, out: List[float]):
        """Append one NRZI-encoded bit worth of samples to output list.
        
        NRZI encoding: 0 = frequency transition, 1 = no transition
        
        Args:
            data_bit: Bit value (0 or 1)
            out: List to append samples to
        """
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
        """Generate complete AFSK audio for an AX.25 frame.
        
        Args:
            frame_with_fcs: Complete AX.25 frame including FCS
            preamble_flags: Number of 0x7E flags before frame (default 60 = ~400ms)
            postamble_flags: Number of 0x7E flags after frame (default 10)
            
        Returns:
            Float32 numpy array of audio samples in range [-1, 1]
        """
        self.reset()
        
        # 0x7E = 01111110, LSB first
        flag_bits = [0, 1, 1, 1, 1, 1, 1, 0]
        
        # Convert bytes to LSB-first bits
        frame_bits = []
        for b in frame_with_fcs:
            for i in range(8):
                frame_bits.append((b >> i) & 1)
        
        # Bit-stuff after five consecutive ones (except flags)
        stuffed = []
        ones = 0
        for bit in frame_bits:
            stuffed.append(bit)
            if bit == 1:
                ones += 1
                if ones == 5:
                    stuffed.append(0)  # Stuff a zero
                    ones = 0
            else:
                ones = 0
        
        out: List[float] = []
        
        # Preamble flags
        for _ in range(preamble_flags):
            for bit in flag_bits:
                self.send_bit(bit, out)
        
        # Frame data (bit-stuffed)
        for bit in stuffed:
            self.send_bit(bit, out)
        
        # Postamble flags
        for _ in range(postamble_flags):
            for bit in flag_bits:
                self.send_bit(bit, out)
        
        return np.array(out, dtype=np.float32)
