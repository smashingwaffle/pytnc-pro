"""
PyTNC Pro - AX.25 Protocol Module

AX.25 packet building and encoding for APRS.
"""

from typing import List, Tuple


class AX25PacketBuilder:
    """Build AX.25 UI frames for APRS"""
    
    @staticmethod
    def encode_callsign(call: str, ssid: int = 0, last: bool = False, c_bit: bool = False) -> bytes:
        """Encode callsign for AX.25 address field
        
        SSID byte format: CRRSSID0 (bit 7 to bit 0)
        - C = command/response bit (bit 7)
        - RR = reserved, set to 11 (bits 6-5)
        - SSID = 4-bit SSID value (bits 4-1)
        - Extension bit = 0 if more addresses follow, 1 if last (bit 0)
        
        Args:
            call: Callsign (up to 6 characters)
            ssid: SSID (0-15)
            last: True if this is the last address in the path
            c_bit: Command/response bit
            
        Returns:
            7 bytes: 6 shifted callsign bytes + 1 SSID byte
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
        
        Args:
            src_call: Source callsign
            src_ssid: Source SSID
            dst_call: Destination callsign (usually APxxxx tocall)
            dst_ssid: Destination SSID (usually 0)
            path: List of (callsign, ssid) tuples for digipeater path
            info: Information field (APRS data)
            
        Returns:
            Complete AX.25 UI packet (without FCS)
        """
        # Destination address (C-bit=1 for command, never last)
        packet = AX25PacketBuilder.encode_callsign(dst_call, dst_ssid, last=False, c_bit=True)
        
        # Source address (C-bit=0, last only if no path)
        packet += AX25PacketBuilder.encode_callsign(src_call, src_ssid, last=(len(path) == 0), c_bit=False)
        
        # Path (digipeaters) - C-bit=0, H-bit would go in C position but we set 0
        for i, (call, ssid) in enumerate(path):
            is_last = (i == len(path) - 1)
            packet += AX25PacketBuilder.encode_callsign(call, ssid, last=is_last, c_bit=False)
        
        # Control field (UI frame = 0x03)
        packet += bytes([0x03])
        
        # Protocol ID (no layer 3 = 0xF0)
        packet += bytes([0xF0])
        
        # Information field
        packet += info.encode('ascii', errors='replace')
        
        return packet
    
    @staticmethod
    def compute_fcs(data: bytes) -> int:
        """Compute AX.25 FCS (Frame Check Sequence)
        
        AX.25 uses CRC-16/IBM (reversed poly 0x8408), init 0xFFFF, xorout 0xFFFF.
        This matches the common "PPP FCS-16" algorithm and Dire Wolf.
        
        Args:
            data: Packet data (without FCS)
            
        Returns:
            16-bit FCS value
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
    
    @staticmethod
    def build_complete_frame(src_call: str, src_ssid: int, dst_call: str, dst_ssid: int,
                             path: List[Tuple[str, int]], info: str) -> bytes:
        """Build complete AX.25 frame with FCS
        
        Returns:
            Complete frame ready for HDLC encoding
        """
        packet = AX25PacketBuilder.build_ui_packet(src_call, src_ssid, dst_call, dst_ssid, path, info)
        fcs = AX25PacketBuilder.compute_fcs(packet)
        # FCS is transmitted LSB first
        return packet + bytes([fcs & 0xFF, (fcs >> 8) & 0xFF])


# Alias for backward compatibility
APRSPacketBuilder = AX25PacketBuilder
