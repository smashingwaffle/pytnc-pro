"""
MOP VARA FM Interface

This module provides a TCP interface to communicate with VARA FM modem software.
VARA FM is an external application that must be running separately.

VARA FM TCP API:
- Command Port (default 8300): Send commands, receive status
- Data Port (default 8301): Send/receive actual data frames

Connection Flow:
1. Connect to command port → get VARA status
2. Connect to data port → ready to send/receive
3. Send MOP message bytes through data port
4. Receive incoming bytes from data port
5. VARA FM handles all the modem/audio/RF stuff

Commands (sent to command port):
- "MYCALL {callsign}" - Set your callsign
- "LISTEN ON" / "LISTEN OFF" - Enable/disable receive
- "CONNECT {callsign}" - Connect to remote station
- "DISCONNECT" - Disconnect
- "ABORT" - Abort connection attempt

Status Messages (received from command port):
- "PTT ON" / "PTT OFF" - Radio transmitting
- "CONNECTED {callsign}" - Connected to station
- "DISCONNECTED" - Disconnected
- "BUFFER {bytes}" - TX buffer space available
- "BUSY TRUE" / "BUSY FALSE" - Channel busy status

Why VARA FM?
- Fastest HF/VHF digital mode available
- Reliable error correction
- Adaptive modulation
- Works well on poor conditions
- But... closed source and hasn't been updated in 6 years 😞
"""

import socket
import threading
import time
from typing import Optional, Callable
from queue import Queue


class VARAFMInterface:
    """
    Interface to VARA FM modem via TCP.
    
    Usage:
        vara = VARAFMInterface("localhost", 8300, 8301)
        vara.on_data_received = lambda data: print(f"Got: {data}")
        vara.on_status = lambda msg: print(f"Status: {msg}")
        
        vara.connect()
        vara.set_mycall("KO6IKR-1")
        vara.listen_on()
        
        # Send data
        vara.send_data(b"Hello World!")
        
        # Later...
        vara.disconnect()
    """
    
    def __init__(self, host: str = "localhost", 
                 cmd_port: int = 8300, 
                 data_port: int = 8301):
        """
        Initialize VARA FM interface.
        
        Args:
            host: VARA FM host (usually "localhost")
            cmd_port: Command port (default 8300)
            data_port: Data port (default 8301)
        """
        self.host = host
        self.cmd_port = cmd_port
        self.data_port = data_port
        
        # Sockets
        self.cmd_socket: Optional[socket.socket] = None
        self.data_socket: Optional[socket.socket] = None
        
        # Threads
        self.cmd_thread: Optional[threading.Thread] = None
        self.data_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Callbacks (set these to handle events)
        self.on_connected: Optional[Callable[[str], None]] = None  # Connected to remote station
        self.on_disconnected: Optional[Callable[[], None]] = None  # Disconnected
        self.on_data_received: Optional[Callable[[bytes], None]] = None  # Data received
        self.on_status: Optional[Callable[[str], None]] = None  # Status message
        self.on_ptt: Optional[Callable[[bool], None]] = None  # PTT on/off
        self.on_busy: Optional[Callable[[bool], None]] = None  # Channel busy
        
        # State
        self.is_connected_to_vara = False
        self.is_connected_to_remote = False
        self.remote_callsign: Optional[str] = None
        self.ptt_active = False
        self.channel_busy = False
        self.buffer_available = 0
        self.link_state = "DISCONNECTED"  # DISCONNECTED, CONNECTING, CONNECTED, FAILED
        
        # Logging callback
        self.on_log: Optional[Callable[[str], None]] = None
    
    def _log(self, msg: str):
        """Log a message via callback or print"""
        if self.on_log:
            self.on_log(msg)
        else:
            print(f"[VARA] {msg}")
    
    def connect(self) -> bool:
        """
        Connect to VARA FM (both command and data ports).
        
        Returns:
            True if connected successfully
            
        Raises:
            ConnectionError: If VARA FM is not running or ports are wrong
        """
        try:
            print(f"🔌 Connecting to VARA FM at {self.host}...")
            
            # Connect command port
            self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.cmd_socket.settimeout(5.0)
            self.cmd_socket.connect((self.host, self.cmd_port))
            print(f"✅ Command port connected: {self.cmd_port}")
            
            # Connect data port
            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.data_socket.settimeout(5.0)
            self.data_socket.connect((self.host, self.data_port))
            print(f"✅ Data port connected: {self.data_port}")
            
            # Start reader threads
            self.running = True
            
            self.cmd_thread = threading.Thread(target=self._cmd_reader, daemon=True)
            self.cmd_thread.start()
            
            self.data_thread = threading.Thread(target=self._data_reader, daemon=True)
            self.data_thread.start()
            
            self.is_connected_to_vara = True
            print("✅ VARA FM interface ready!")
            
            return True
            
        except ConnectionRefusedError:
            raise ConnectionError(
                "Could not connect to VARA FM. "
                "Make sure VARA FM is running and ports are correct."
            )
        except Exception as e:
            raise ConnectionError(f"VARA FM connection failed: {e}")
    
    def disconnect(self):
        """Disconnect from VARA FM."""
        print("🔌 Disconnecting from VARA FM...")
        
        self.running = False
        
        # Graceful shutdown - wake up any threads blocked in recv()
        if self.cmd_socket:
            try:
                self.cmd_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.cmd_socket.close()
            except:
                pass
        
        if self.data_socket:
            try:
                self.data_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.data_socket.close()
            except:
                pass
        
        self.is_connected_to_vara = False
        self.is_connected_to_remote = False
        print("✅ Disconnected from VARA FM")
    
    def send_command(self, command: str):
        """
        Send command to VARA FM.
        
        Args:
            command: Command string (e.g., "MYCALL KO6IKR-1")
        """
        if not self.cmd_socket:
            raise RuntimeError("Not connected to VARA FM")
        
        try:
            cmd_bytes = (command + "\r").encode('utf-8')
            self.cmd_socket.sendall(cmd_bytes)
            print(f"📤 CMD: {command}")
        except Exception as e:
            print(f"❌ Command send failed: {e}")
    
    def set_mycall(self, callsign: str):
        """
        Set your callsign in VARA FM.
        
        Args:
            callsign: Your callsign (e.g., "KO6IKR-1")
        """
        self.send_command(f"MYCALL {callsign}")
    
    def listen_on(self):
        """Enable VARA FM receive mode."""
        self.send_command("LISTEN ON")
    
    def listen_off(self):
        """Disable VARA FM receive mode."""
        self.send_command("LISTEN OFF")
    
    def connect_to_station(self, callsign: str, source_call: str = None):
        """
        Initiate connection to remote station.
        
        Args:
            callsign: Remote station callsign (e.g., "W1ABC-5")
            source_call: Your callsign (required for VARA FM)
        """
        # VARA FM requires: CONNECT Source Destination
        # VARA HF uses: CONNECT Destination
        if source_call:
            cmd = f"CONNECT {source_call} {callsign}"
            print(f"🔗 Connecting: {source_call} → {callsign}")
        else:
            cmd = f"CONNECT {callsign}"
            print(f"🔗 Connecting to: {callsign}")
        
        self.send_command(cmd)
        print(f"📤 Sent: {cmd}")
    
    def disconnect_from_station(self):
        """Disconnect from remote station."""
        self.send_command("DISCONNECT")
    
    def abort_connection(self):
        """Abort connection attempt."""
        self.send_command("ABORT")
    
    def send_data(self, data: bytes) -> bool:
        """
        Send data through VARA FM.
        
        Args:
            data: Raw bytes to send
            
        Returns:
            True if sent successfully
        """
        if not self.data_socket:
            print("❌ No data socket!")
            raise RuntimeError("Not connected to VARA FM data port")
        
        if not self.is_connected_to_remote:
            print("⚠️ Not connected to remote station - data won't be sent")
            print(f"   is_connected_to_remote = {self.is_connected_to_remote}")
            print(f"   remote_callsign = {self.remote_callsign}")
            return False
        
        try:
            print(f"📤 DATA PORT 8301: Sending {len(data)} bytes...")
            print(f"   First 20 bytes: {data[:20].hex()}")
            
            # VARA data port is a raw byte bridge - no framing!
            # Use sendall() to guarantee full payload transmission
            self.data_socket.sendall(data)
            
            print(f"✅ DATA PORT 8301: Sent {len(data)} bytes successfully")
            return True
        except Exception as e:
            print(f"❌ Data send failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _cmd_reader(self):
        """Background thread to read command port."""
        print("🧵 Command reader thread started")
        buffer = ""
        
        while self.running:
            try:
                data = self.cmd_socket.recv(1024)
                if not data:
                    break
                
                buffer += data.decode('utf-8', errors='ignore')
                
                # Process complete lines
                while '\r' in buffer:
                    line, buffer = buffer.split('\r', 1)
                    line = line.strip()
                    
                    if line:
                        self._handle_status(line)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Command reader error: {e}")
                break
        
        print("🧵 Command reader thread stopped")
    
    def _data_reader(self):
        """Background thread to read data port."""
        print("🧵 Data reader thread started")
        
        while self.running:
            try:
                # VARA data port is a raw byte bridge
                # Just read whatever data arrives
                data = self.data_socket.recv(4096)
                if not data:
                    break
                
                print(f"📥 DATA: Received {len(data)} bytes")
                
                # Call callback with raw data
                if self.on_data_received:
                    self.on_data_received(data)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Data reader error: {e}")
                break
        
        print("🧵 Data reader thread stopped")
    
    def _handle_status(self, status: str):
        """Handle status message from VARA FM."""
        print(f"📊 STATUS: {status}")
        
        # Parse common status messages
        if status.startswith("PTT "):
            ptt_on = status.endswith("ON")
            self.ptt_active = ptt_on
            state = "🔴 TRANSMITTING" if ptt_on else "🟢 RECEIVING"
            print(f"   📡 PTT: {state}")
            if self.on_ptt:
                self.on_ptt(ptt_on)
        
        elif status.startswith("CONNECTED "):
            # Format: "CONNECTED <source> <dest> <bw>" or "CONNECTED <source> <dest> NARROW"
            # Example: "CONNECTED KO6IKR W1ABC NARROW"
            parts = status.split()
            if len(parts) >= 3:
                # parts[0] = "CONNECTED"
                # parts[1] = source (us)
                # parts[2] = destination (remote)
                # parts[3+] = bandwidth/mode (ignore)
                self.remote_callsign = parts[2]  # Destination is 3rd field
                self.is_connected_to_remote = True
                self.link_state = "CONNECTED"
                print(f"   ✅ RF LINK UP: Connected to {self.remote_callsign}")
                print(f"      Full status: {status}")
                if self.on_connected:
                    self.on_connected(self.remote_callsign)
            else:
                print(f"   ⚠️ Unexpected CONNECTED format: {status}")
        
        elif status == "DISCONNECTED":
            self.is_connected_to_remote = False
            self.link_state = "DISCONNECTED"
            old_call = self.remote_callsign
            self.remote_callsign = None
            print(f"   ❌ RF LINK DOWN: Disconnected from {old_call}")
            if self.on_disconnected:
                self.on_disconnected()
        
        elif status.startswith("BUSY "):
            # Handle both "BUSY TRUE/FALSE" and "BUSY ON/OFF" formats
            tail = status.split(None, 1)[1].strip().upper() if len(status.split()) > 1 else ""
            busy = tail in ("TRUE", "ON", "1", "YES")
            self.channel_busy = busy
            state = "🔴 BUSY" if busy else "🟢 CLEAR"
            print(f"   📻 Channel: {state}")
            if self.on_busy:
                self.on_busy(busy)
        
        elif status.startswith("BUFFER "):
            # Format: "BUFFER 1024"
            try:
                self.buffer_available = int(status.split()[1])
                print(f"   📦 TX Buffer: {self.buffer_available} bytes")
            except:
                pass
        
        elif status == "PENDING":
            print(f"   ⏳ Incoming connection request detected...")
            
        elif status == "CANCELPENDING":
            print(f"   ⚠️ Connection request cancelled or failed")
            
        elif status == "WRONG":
            print(f"   ❌ WRONG COMMAND! Check syntax!")
            
        elif status == "OK":
            print(f"   ✅ Command accepted by VARA")
            
        elif "REGISTERED" in status:
            parts = status.split()
            if len(parts) >= 2:
                call = parts[1]
                print(f"   ✅ Callsign {call} registered in VARA")
        
        # Call generic status callback
        if self.on_status:
            self.on_status(status)


# Simple test/demo
if __name__ == "__main__":
    print("\n" + "="*60)
    print("MOP VARA FM Interface Test")
    print("="*60 + "\n")
    
    print("⚠️  Make sure VARA FM is running first!")
    print("   Default ports: 8300 (command), 8301 (data)\n")
    
    # Create interface
    vara = VARAFMInterface()
    
    # Set up callbacks
    vara.on_status = lambda msg: print(f"   Status: {msg}")
    vara.on_connected = lambda call: print(f"   🎉 Connected to {call}!")
    vara.on_disconnected = lambda: print(f"   👋 Disconnected")
    vara.on_ptt = lambda on: print(f"   📻 PTT: {'ON' if on else 'OFF'}")
    vara.on_data_received = lambda data: print(f"   📥 Received: {len(data)} bytes")
    
    try:
        # Connect to VARA FM
        vara.connect()
        
        # Set callsign
        vara.set_mycall("KO6IKR-1")
        
        # Enable listening
        vara.listen_on()
        
        print("\n✅ VARA FM interface is working!")
        print("   Commands sent successfully")
        print("   Listening for incoming connections...")
        print("\nPress Ctrl+C to stop\n")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n👋 Stopping...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure VARA FM.exe is running")
        print("2. Check ports in VARA FM settings (default 8300/8301)")
        print("3. Make sure no firewall is blocking")
    finally:
        vara.disconnect()
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60 + "\n")


# =============================================================================
# Helper function for APRS beacon via VARA FM
# =============================================================================

def send_aprs_beacon_vara(vara: VARAFMInterface, 
                          callsign: str, 
                          digi: str,
                          lat: float, 
                          lon: float,
                          symbol_table: str = "/",
                          symbol_code: str = "-",
                          comment: str = "",
                          timeout: float = 30.0,
                          listen_time: float = 5.0) -> bool:
    """
    Send an APRS beacon via VARA FM.
    
    Args:
        vara: VARAFMInterface instance (can be unconnected)
        callsign: Your callsign with SSID (e.g., "KO6IKR-1")
        digi: Digipeater callsign (e.g., "W2JCL-10")
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        symbol_table: APRS symbol table (default "/" primary)
        symbol_code: APRS symbol code (default "-" house)
        comment: Optional comment string
        timeout: Connection timeout in seconds
        listen_time: Time to listen for response after sending
        
    Returns:
        True if beacon was sent successfully
    """
    import time
    
    # Track if we connected (so we know if we should disconnect)
    we_connected = False
    
    # Format position for APRS
    lat_deg = int(abs(lat))
    lat_min = (abs(lat) - lat_deg) * 60
    lat_dir = "N" if lat >= 0 else "S"
    
    lon_deg = int(abs(lon))
    lon_min = (abs(lon) - lon_deg) * 60
    lon_dir = "E" if lon >= 0 else "W"
    
    # Build APRS position string
    pos = f"!{lat_deg:02d}{lat_min:05.2f}{lat_dir}{symbol_table}{lon_deg:03d}{lon_min:05.2f}{lon_dir}{symbol_code}"
    if comment:
        pos += comment[:43]
    
    # Build APRS packet
    aprs_packet = f"{callsign}>APZ021,{digi}:{pos}\r"
    
    vara._log(f"📍 Sending APRS beacon via VARA FM...")
    vara._log(f"   From: {callsign}")
    vara._log(f"   Via: {digi}")
    vara._log(f"   Position: {lat:.6f}, {lon:.6f}")
    vara._log(f"   Packet: {aprs_packet.strip()}")
    
    try:
        # Connect if not already connected
        if not vara.is_connected_to_vara:
            if not vara.connect():
                return False
            we_connected = True  # We initiated this connection
        
        # Set callsign and enable listening
        vara.send_command(f"MYCALL {callsign}")
        time.sleep(0.3)
        
        vara.send_command("LISTEN ON")
        time.sleep(0.3)
        
        # Connect to digipeater
        vara._log(f"📡 Calling {digi}...")
        vara.send_command(f"CONNECT {callsign} {digi}")
        
        # Wait for connection
        start = time.time()
        connected = False
        while time.time() - start < timeout:
            # Check for connection status
            if vara.link_state == "CONNECTED":
                connected = True
                break
            if vara.link_state in ["DISCONNECTED", "FAILED"]:
                vara._log(f"❌ Connection failed")
                return False
            time.sleep(0.5)
        
        if not connected:
            vara._log("❌ Connection timeout")
            return False
        
        # Send beacon
        time.sleep(0.3)
        vara._log(f"📤 Sending beacon data ({len(aprs_packet)} bytes)...")
        vara.send_data(aprs_packet.encode())
        vara._log(f"✅ Beacon sent!")
        
        # Listen for response
        vara._log(f"👂 Listening for response...")
        time.sleep(listen_time)
        
        # Disconnect the link (not VARA itself)
        vara._log(f"🔌 Disconnecting link...")
        vara.send_command("DISCONNECT")
        time.sleep(1.0)
        
        vara._log("✅ Beacon complete!")
        return True
        
    except Exception as e:
        vara._log(f"❌ Error: {e}")
        return False
    finally:
        # Only disconnect from VARA if we were the ones who connected
        if we_connected:
            vara.disconnect()
