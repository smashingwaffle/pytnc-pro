#!/usr/bin/env python3
"""
PyTNC Pro - AX.25 Frame Parser

Parses AX.25 frames from HDLC-decoded data.
Properly handles C-bit (command/response) vs H-bit (has been repeated) semantics.

AX.25 Address Field Format (7 bytes per address):
- Bytes 0-5: Callsign (ASCII shifted left 1 bit, space-padded)
- Byte 6 (SSID byte): 
  - Bit 7: C/H bit (Command/Response for src/dst, Has-been-repeated for digis)
  - Bits 6-5: Reserved (set to 1)
  - Bits 4-1: SSID (0-15)
  - Bit 0: Extension bit (0 = more addresses follow, 1 = last address)

For UI frames (APRS):
- Destination C-bit = 1 (command frame)
- Source C-bit = 0
- Digipeater H-bit = 1 if packet has been repeated through this digi
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import re


@dataclass
class AX25Address:
    """Represents an AX.25 address (callsign + SSID + flags)"""
    callsign: str
    ssid: int
    
    # For destination/source addresses
    command_bit: bool = False  # C-bit: True for command frame destination
    
    # For digipeater addresses  
    has_been_repeated: bool = False  # H-bit: True if packet passed through this digi
    
    # Extension bit (internal use)
    is_last: bool = False  # True if this is the last address in the path
    
    def __str__(self):
        result = self.callsign
        if self.ssid > 0:
            result += f"-{self.ssid}"
        if self.has_been_repeated:
            result += "*"
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, is_digipeater: bool = False) -> Optional['AX25Address']:
        """Parse 7-byte AX.25 address field.
        
        Args:
            data: 7 bytes of address data
            is_digipeater: True if this is a digipeater address (uses H-bit),
                          False if destination/source (uses C-bit)
        """
        if len(data) < 7:
            return None
        
        # Extract callsign (6 bytes, each shifted left by 1)
        callsign = ""
        for i in range(6):
            char = (data[i] >> 1) & 0x7F
            if char != ord(' '):
                callsign += chr(char)
        
        # Parse SSID byte
        ssid_byte = data[6]
        ssid = (ssid_byte >> 1) & 0x0F
        is_last = bool(ssid_byte & 0x01)
        
        # Bit 7 meaning depends on address position
        bit7 = bool(ssid_byte & 0x80)
        
        if is_digipeater:
            # For digipeaters: bit 7 is H-bit (has been repeated)
            return cls(
                callsign=callsign,
                ssid=ssid,
                command_bit=False,
                has_been_repeated=bit7,
                is_last=is_last
            )
        else:
            # For destination/source: bit 7 is C-bit (command/response)
            return cls(
                callsign=callsign,
                ssid=ssid,
                command_bit=bit7,
                has_been_repeated=False,
                is_last=is_last
            )
    
    def to_bytes(self, is_digipeater: bool = False) -> bytes:
        """Encode address to 7 bytes.
        
        Args:
            is_digipeater: True to use H-bit semantics, False for C-bit
        """
        # Callsign padded to 6 chars, shifted left
        call = self.callsign.upper().ljust(6)[:6]
        encoded = bytes([ord(c) << 1 for c in call])
        
        # SSID byte
        if is_digipeater:
            bit7 = 0x80 if self.has_been_repeated else 0x00
        else:
            bit7 = 0x80 if self.command_bit else 0x00
        
        ssid_byte = bit7 | 0x60 | ((self.ssid & 0x0F) << 1) | (0x01 if self.is_last else 0x00)
        
        return encoded + bytes([ssid_byte])


@dataclass
class AX25Frame:
    """Represents a parsed AX.25 frame"""
    destination: AX25Address
    source: AX25Address
    digipeaters: List[AX25Address]
    control: int
    pid: int
    info: bytes
    
    # Derived properties
    is_command: bool = True  # True if this is a command frame (dest C-bit set)
    
    @property
    def path_str(self) -> str:
        """Return path as string like 'WIDE1-1,WIDE2-1*'"""
        return ",".join(str(d) for d in self.digipeaters)
    
    @property
    def is_ui_frame(self) -> bool:
        """True if this is a UI (Unnumbered Information) frame"""
        return (self.control & 0xEF) == 0x03
    
    @property
    def info_str(self) -> str:
        """Information field as string"""
        return self.info.decode('ascii', errors='replace')
    
    def to_tnc2(self) -> str:
        """Format as TNC2 monitor string: SRC>DST,PATH:INFO"""
        parts = [str(self.source), ">", str(self.destination)]
        if self.digipeaters:
            parts.append(",")
            parts.append(self.path_str)
        parts.append(":")
        parts.append(self.info_str)
        return "".join(parts)


class AX25Parser:
    """Parser for AX.25 frames"""
    
    def parse(self, data: bytes) -> Optional[AX25Frame]:
        """Parse AX.25 frame from raw bytes (after HDLC decoding, without flags/FCS).
        
        Args:
            data: Raw frame bytes (minimum 15 bytes for valid frame)
            
        Returns:
            Parsed AX25Frame or None if invalid
        """
        if len(data) < 15:  # Minimum: 7+7 addresses + 1 control
            return None
        
        try:
            # Parse destination address (first 7 bytes)
            # C-bit should be set for command frames
            dest = AX25Address.from_bytes(data[0:7], is_digipeater=False)
            if not dest:
                return None
            
            # Parse source address (next 7 bytes)
            # C-bit should be clear for command frames
            source = AX25Address.from_bytes(data[7:14], is_digipeater=False)
            if not source:
                return None
            
            # Determine if command or response frame
            # Command: dest C=1, source C=0
            # Response: dest C=0, source C=1
            is_command = dest.command_bit and not source.command_bit
            
            # Parse digipeater addresses (if extension bit not set on source)
            offset = 14
            digipeaters = []
            
            if not source.is_last:
                # More addresses follow
                while offset + 7 <= len(data):
                    digi = AX25Address.from_bytes(data[offset:offset+7], is_digipeater=True)
                    if not digi:
                        break
                    digipeaters.append(digi)
                    offset += 7
                    if digi.is_last:
                        break
            
            # Control field
            if offset >= len(data):
                return None
            control = data[offset]
            offset += 1
            
            # PID field (only for I and UI frames)
            pid = 0
            if (control & 0x01) == 0 or (control & 0xEF) == 0x03:
                if offset >= len(data):
                    return None
                pid = data[offset]
                offset += 1
            
            # Information field (rest of packet)
            info = data[offset:] if offset < len(data) else b""
            
            return AX25Frame(
                destination=dest,
                source=source,
                digipeaters=digipeaters,
                control=control,
                pid=pid,
                info=info,
                is_command=is_command
            )
            
        except Exception as e:
            return None
    
    def parse_tnc2(self, line: str) -> Optional[AX25Frame]:
        """Parse TNC2 format string: SRC>DST,PATH:INFO
        
        Args:
            line: TNC2 format string
            
        Returns:
            Parsed AX25Frame or None if invalid
        """
        # Pattern: CALL-N>CALL-N,DIGI1*,DIGI2:info
        match = re.match(r'^([A-Z0-9]{1,6})(?:-(\d+))?>'
                        r'([A-Z0-9]{1,6})(?:-(\d+))?'
                        r'(?:,([^:]+))?'
                        r':(.*)$', line, re.IGNORECASE)
        if not match:
            return None
        
        src_call, src_ssid, dst_call, dst_ssid, path_str, info = match.groups()
        
        # Build destination (C-bit set for command)
        dest = AX25Address(
            callsign=dst_call.upper(),
            ssid=int(dst_ssid) if dst_ssid else 0,
            command_bit=True
        )
        
        # Build source (C-bit clear for command)
        source = AX25Address(
            callsign=src_call.upper(),
            ssid=int(src_ssid) if src_ssid else 0,
            command_bit=False
        )
        
        # Parse digipeater path
        digipeaters = []
        if path_str:
            for digi_str in path_str.split(','):
                digi_str = digi_str.strip()
                if not digi_str:
                    continue
                    
                # Check for H-bit marker (*)
                repeated = digi_str.endswith('*')
                if repeated:
                    digi_str = digi_str[:-1]
                
                # Parse callsign-SSID
                if '-' in digi_str:
                    call, ssid = digi_str.split('-', 1)
                    ssid = int(ssid)
                else:
                    call = digi_str
                    ssid = 0
                
                digipeaters.append(AX25Address(
                    callsign=call.upper(),
                    ssid=ssid,
                    has_been_repeated=repeated
                ))
        
        # Mark last digipeater
        if digipeaters:
            digipeaters[-1].is_last = True
        else:
            source.is_last = True
        
        return AX25Frame(
            destination=dest,
            source=source,
            digipeaters=digipeaters,
            control=0x03,  # UI frame
            pid=0xF0,      # No layer 3
            info=info.encode('ascii', errors='replace'),
            is_command=True
        )


# =============================================================================
# Utility functions
# =============================================================================

def get_repeated_path(frame: AX25Frame) -> Tuple[List[str], List[str]]:
    """Get the path split into repeated and unrepeated portions.
    
    Returns:
        Tuple of (repeated_digis, unrepeated_digis) as callsign strings
    """
    repeated = []
    unrepeated = []
    
    for digi in frame.digipeaters:
        if digi.has_been_repeated:
            repeated.append(str(digi))
        else:
            unrepeated.append(str(digi))
    
    return repeated, unrepeated


def find_last_repeater(frame: AX25Frame) -> Optional[AX25Address]:
    """Find the last digipeater that repeated this packet.
    
    Returns:
        The last digipeater with H-bit set, or None
    """
    for digi in reversed(frame.digipeaters):
        if digi.has_been_repeated:
            return digi
    return None
