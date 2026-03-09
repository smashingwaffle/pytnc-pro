"""
TNC - PyTNC Pro Core Module

A modern APRS transceiver application with support for:
- RF (AFSK 1200 baud) transmission and reception
- VARA FM digital mode
- APRS-IS internet gateway
- GPS integration
- CAT radio control
"""

__version__ = "0.21"
__author__ = "PyTNC Team"

# Capability flags - set to True if module loaded successfully
HAS_AX25 = False
HAS_AFSK = False
HAS_VARA = False
HAS_MAP = False

# Protocol modules (AX.25 packet building)
try:
    from .protocol.ax25 import AX25PacketBuilder, APRSPacketBuilder
    HAS_AX25 = True
except ImportError as e:
    AX25PacketBuilder = None
    APRSPacketBuilder = None
    print(f"⚠️ AX.25 module not available: {e}")

# Audio modules (AFSK modulation)
try:
    from .audio.afsk import AFSKModulator, apply_cosine_ramp
    HAS_AFSK = True
except ImportError as e:
    AFSKModulator = None
    apply_cosine_ramp = None
    print(f"⚠️ AFSK module not available: {e}")

# VARA FM module
try:
    from .vara import VARAFMInterface
    HAS_VARA = True
    # Alias for compatibility
    VARAInterface = VARAFMInterface
except ImportError as e:
    VARAFMInterface = None
    VARAInterface = None
    print(f"⚠️ VARA FM module not available: {e}")

# Map HTML generator
try:
    from .map import write_map_html
    HAS_MAP = True
except ImportError as e:
    write_map_html = None
    print(f"⚠️ Map module not available: {e}")


def get_capabilities() -> dict:
    """Return dict of available capabilities."""
    return {
        "ax25": HAS_AX25,
        "afsk": HAS_AFSK,
        "vara": HAS_VARA,
        "map": HAS_MAP,
    }


def check_requirements() -> list:
    """Return list of missing optional features."""
    missing = []
    if not HAS_AX25:
        missing.append("AX.25 protocol (protocol/ax25.py)")
    if not HAS_AFSK:
        missing.append("AFSK audio (audio/afsk.py) - needs numpy")
    if not HAS_VARA:
        missing.append("VARA FM interface (vara.py)")
    if not HAS_MAP:
        missing.append("Map generator (map.py)")
    return missing
