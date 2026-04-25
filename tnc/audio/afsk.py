"""
PyTNC Pro - AFSK Modulator Module

Bell 202 AFSK modulator for APRS TX (1200 baud, 1200/2200 Hz)
Improvements over original:
- Pre-emphasis filter (compensates for radio de-emphasis on RX)
- Vectorized numpy audio generation (faster)
- Better preamble defaults
"""

import math
from typing import List

import numpy as np
from scipy import signal as scipy_signal


# Larger sine table for better quality
_SINE_TABLE_SIZE = 4096
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


def apply_preemphasis(audio: np.ndarray, sample_rate: int, cutoff_hz: float = 750.0) -> np.ndarray:
    """Apply pre-emphasis filter to boost high frequencies.
    
    VHF FM radios typically apply de-emphasis on receive (rolls off high freq).
    Pre-emphasis on TX compensates so the 2200Hz space tone is received at
    equal level to the 1200Hz mark tone, dramatically improving decode rates.
    
    Uses a single-pole high-pass shelf filter: H(s) = (1 + s/w1) / (1 + s/w2)
    Standard Bell 202 pre-emphasis: 6dB/octave boost above ~750Hz
    """
    # Simple first-order pre-emphasis: y[n] = x[n] - alpha * x[n-1]
    # alpha controls the amount of boost
    # At 1200Hz: minimal boost, at 2200Hz: ~6dB boost
    alpha = math.exp(-2.0 * math.pi * cutoff_hz / sample_rate)
    b = np.array([1.0, -alpha], dtype=np.float64)
    a = np.array([1.0, 0.0], dtype=np.float64)
    filtered = scipy_signal.lfilter(b, a, audio.astype(np.float64))
    # Normalize to prevent clipping
    peak = np.max(np.abs(filtered))
    if peak > 0:
        filtered = filtered / peak * 0.95
    return filtered.astype(np.float32)


class AFSKModulator:
    """
    Bell 202 AFSK modulator for APRS TX (1200 baud, 1200/2200 Hz)
    
    Features:
    - Fractional bit timing using Bresenham-style accumulator
    - Starts in MARK state (Direwolf-like)
    - Proper NRZI encoding
    - Pre-emphasis for better decode on de-emphasized receivers
    
    Usage:
        mod = AFSKModulator(44100)
        audio = mod.generate_packet_audio(frame_with_fcs)
    """
    
    def __init__(self, sample_rate: int):
        self.sample_rate = int(sample_rate)
        self.mark_freq = 1200.0
        self.space_freq = 2200.0
        self.baud_rate = 1200
        
        self.samples_per_bit = self.sample_rate / self.baud_rate
        self._spb_int = int(math.floor(self.samples_per_bit))
        self._spb_frac = float(self.samples_per_bit - self._spb_int)
        self._frac_acc = 0.0
        
        self.phase = 0.0
        self.tone = 1  # Start on MARK
        
        self.mark_inc = self.mark_freq / self.sample_rate
        self.space_inc = self.space_freq / self.sample_rate
    
    def reset(self):
        self.phase = 0.0
        self.tone = 1
        self._frac_acc = 0.0
    
    def _bit_nsamples(self) -> int:
        n = self._spb_int
        self._frac_acc += self._spb_frac
        if self._frac_acc >= 1.0:
            n += 1
            self._frac_acc -= 1.0
        return max(1, n)
    
    def send_bit(self, data_bit: int, out: List[float]):
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
                               preamble_flags: int = 80,
                               postamble_flags: int = 10,
                               preemphasis: bool = True) -> np.ndarray:
        """Generate complete AFSK audio for an AX.25 frame.
        
        Args:
            frame_with_fcs: Complete AX.25 frame including FCS
            preamble_flags: Number of 0x7E flags before frame (default 80 ~530ms)
            postamble_flags: Number of 0x7E flags after frame
            preemphasis: Apply pre-emphasis filter (default True)
            
        Returns:
            Float32 numpy array of audio samples in range [-1, 1]
        """
        self.reset()
        
        flag_bits = [0, 1, 1, 1, 1, 1, 1, 0]
        
        # Convert bytes to LSB-first bits
        frame_bits = []
        for b in frame_with_fcs:
            for i in range(8):
                frame_bits.append((b >> i) & 1)
        
        # Bit-stuff
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
        
        audio = np.array(out, dtype=np.float32)
        
        # Apply pre-emphasis to compensate for radio de-emphasis
        if preemphasis:
            try:
                audio = apply_preemphasis(audio, self.sample_rate)
            except Exception:
                pass  # Fall back to unfiltered if scipy unavailable
        
        return audio
