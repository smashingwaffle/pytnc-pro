"""
Bit-by-bit HDLC Decoder
Matches Direwolf's hdlc_rec_bit() function

Processes ONE BIT at a time (not arrays!)
"""

import numpy as np


def calc_fcs(data):
    """Calculate FCS (CRC-CCITT)"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc ^ 0xFFFF


class BitByBitHDLC:
    """
    HDLC decoder that processes one bit at a time
    Matches Direwolf's hdlc_rec.c
    """
    
    def __init__(self, chan=0, subchan=0, slice_num=0, demodulator=None):
        self.chan = chan
        self.subchan = subchan
        self.slice_num = slice_num
        self.demodulator = demodulator  # Reference to demodulator
        
        # State
        self.prev_raw = 1
        self.pat_det = 0
        self.oacc = 0
        self.olen = -1  # -1 means don't accumulate
        self.frame_buf = bytearray()
        
        # Callbacks
        self.frame_callback = None
        
        # Stats
        self.frames_decoded = 0
        self.frames_failed_fcs = 0
        
    def set_frame_callback(self, callback):
        """Set callback for when complete frame is decoded"""
        self.frame_callback = callback
    
    def process_bit(self, raw_bit, quality=100):
        """
        Process one bit from demodulator
        This is called for EVERY bit!
        
        raw_bit: 0 or 1 from demodulator
        quality: confidence level 0-100
        """
        
        # NRZI decoding
        # 0 = transition, 1 = no transition
        dbit = 1 if (raw_bit == self.prev_raw) else 0
        self.prev_raw = raw_bit
        
        # Shift bit into pattern detector
        self.pat_det >>= 1
        if dbit:
            self.pat_det |= 0x80
        
        # Check for special patterns
        if self.pat_det == 0x7E:
            # FLAG pattern!
            self._handle_flag()
            
        elif self.pat_det == 0xFE:
            # Abort pattern (7 ones)
            self.olen = -1
            self.frame_buf = bytearray()
            
        elif (self.pat_det & 0xFC) == 0x7C:
            # Bit stuffing (5 ones + 0)
            # Discard this bit
            pass
            
        else:
            # Normal data bit
            if self.olen >= 0:
                self.oacc >>= 1
                if dbit:
                    self.oacc |= 0x80
                self.olen += 1
                
                if self.olen == 8:
                    # Complete octet
                    self.olen = 0
                    self.frame_buf.append(self.oacc)
                    self.oacc = 0
                    
                    # Prevent runaway
                    if len(self.frame_buf) > 330:
                        self.olen = -1
                        self.frame_buf = bytearray()
    
    def _handle_flag(self):
        """Handle HDLC flag (0x7E)"""
        # Check if we have a complete frame
        MIN_FRAME_LEN = 15
        
        if self.olen == 7 and len(self.frame_buf) >= MIN_FRAME_LEN:
            # Potential complete frame!
            actual_fcs = self.frame_buf[-2] | (self.frame_buf[-1] << 8)
            expected_fcs = calc_fcs(self.frame_buf[:-2])
            
            if actual_fcs == expected_fcs:
                # VALID FRAME!
                self.frames_decoded += 1
                if self.frame_callback:
                    # Remove FCS before passing up
                    self.frame_callback(bytes(self.frame_buf[:-2]), self.chan, self.subchan, self.slice_num)
            else:
                self.frames_failed_fcs += 1
        
        # NOTE: data_detect is now handled by energy-based detection in demodulator
        # No need to toggle it here
        
        # Start of new frame
        self.olen = 0
        self.frame_buf = bytearray()



class NRZIDecoder:
    """
    NRZI Decoder - but we do this inline in BitByBitHDLC now
    Keeping this for compatibility
    """
    def __init__(self):
        self.last_bit = 0
    
    def decode(self, bit):
        """Decode one NRZI bit"""
        if bit == self.last_bit:
            data_bit = 1
        else:
            data_bit = 0
        self.last_bit = bit
        return data_bit


if __name__ == "__main__":
    print("=" * 60)
    print("BIT-BY-BIT HDLC DECODER")
    print("=" * 60)
    print()
    print("Processes bits one at a time, like Direwolf!")
    print()
    print("Features:")
    print("  ✓ NRZI decoding")
    print("  ✓ Flag detection (0x7E)")
    print("  ✓ Bit unstuffing")
    print("  ✓ FCS validation")
    print("  ✓ Frame extraction")
    print()
    print("Called for EVERY BIT from demodulator!")
    print("=" * 60)
