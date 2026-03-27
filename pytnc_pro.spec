# -*- mode: python ; coding: utf-8 -*-
"""
PyTNC Pro - PyInstaller Spec File

Build with: pyinstaller pytnc_pro.spec

This bundles:
- Main application and all Python modules
- APRS symbol sets (hessu-symbols/)
- TNC module (map generator, AFSK modem, etc.)

IMPORTANT: PyQt6-WebEngine requires special handling
"""

import sys
import re
from pathlib import Path

block_cipher = None

# Get the source directory (where main.py is)
src_dir = Path('.').resolve()

# Read version from main.py
VERSION = "0.1.0-beta"  # Default fallback
try:
    main_py = src_dir / "main.py"
    if main_py.exists():
        content = main_py.read_text(encoding='utf-8')
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            VERSION = match.group(1)
            print(f"[SPEC] Found version: {VERSION}")
except Exception as e:
    print(f"[SPEC] Could not read version: {e}")

# Build name with version
APP_NAME = f"PyTNC-Pro_v{VERSION}"
print(f"[SPEC] Building: {APP_NAME}")

# Data files to bundle
datas = [
    # Application icon
    ('pytnc_pro.ico', '.'),
    ('pytnc_pro_256.png', '.'),
    
    # APRS symbol images (Hessu's symbols) - try both folder names
    ('hessu-symbols', 'hessu-symbols'),
    ('aprs_symbols_48', 'aprs_symbols_48'),
    
    # Python modules
    ('pytnc_config.py', '.'),
    ('aprs_parser.py', '.'),
    ('ax25_parser.py', '.'),
    ('pytnc_modem.py', '.'),
    ('ax25_demod.py', '.'),
    ('hdlc_bitbybit.py', '.'),
    
    # TNC module
    ('tnc', 'tnc'),
]

# Filter out non-existent paths
datas = [(src, dst) for src, dst in datas if Path(src).exists()]

# Hidden imports for PyQt6 WebEngine
hiddenimports = [
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebChannel',
    'PyQt6.QtPositioning',
    'PyQt6.sip',
    'sounddevice',
    '_sounddevice',
    '_sounddevice_data',
    '_sounddevice_data.portaudio-binaries',
    'cffi',
    '_cffi_backend',
    'numpy',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'serial',
    'serial.tools',
    'serial.tools.list_ports',
    'scipy',
    'scipy.signal',
    'scipy.signal.windows',
    'scipy.fft',
    'scipy.special',
    'scipy.special._cdflib',
    'scipy.ndimage',
    'pytnc_config',
    'aprs_parser',
    'ax25_parser',
    'pytnc_modem',
    'ax25_demod',
    'hdlc_bitbybit',
]

# Collect sounddevice - it's a single module, not a package, so collect manually
import os
import sys

# Check venv in current directory FIRST
site_packages = None
venv_sp = os.path.join(str(src_dir), '.venv', 'Lib', 'site-packages')
if os.path.exists(os.path.join(venv_sp, 'sounddevice.py')):
    site_packages = venv_sp
    print(f"[SPEC] Using .venv site-packages")

# Fall back to sys.path
if not site_packages:
    for p in sys.path:
        if 'site-packages' in p and os.path.exists(os.path.join(p, 'sounddevice.py')):
            site_packages = p
            break

if site_packages:
    print(f"[SPEC] Found site-packages: {site_packages}")
    
    # sounddevice.py
    sd_file = os.path.join(site_packages, 'sounddevice.py')
    if os.path.exists(sd_file):
        datas += [(sd_file, '.')]
        print(f"[SPEC] sounddevice.py: {sd_file}")
    
    # _sounddevice.py  
    sd_internal = os.path.join(site_packages, '_sounddevice.py')
    if os.path.exists(sd_internal):
        datas += [(sd_internal, '.')]
        print(f"[SPEC] _sounddevice.py: {sd_internal}")
    
    # _sounddevice_data folder (contains PortAudio DLLs)
    sd_data = os.path.join(site_packages, '_sounddevice_data')
    if os.path.exists(sd_data):
        datas += [(sd_data, '_sounddevice_data')]
        print(f"[SPEC] _sounddevice_data: {sd_data}")
    
    # _cffi_backend
    for f in os.listdir(site_packages):
        if f.startswith('_cffi_backend') and f.endswith('.pyd'):
            cffi_file = os.path.join(site_packages, f)
            binaries = [(cffi_file, '.')]
            print(f"[SPEC] _cffi_backend: {cffi_file}")
            break
    else:
        binaries = []
else:
    print("[SPEC] WARNING: Could not find site-packages with sounddevice!")
    binaries = []

# Collect scipy - ALL of it (data, binaries, submodules)
# First, ensure we're using the venv's scipy
if site_packages:
    sys.path.insert(0, site_packages)
    print(f"[SPEC] Added to sys.path: {site_packages}")

scipy_collected = False
try:
    from PyInstaller.utils.hooks import collect_all
    scipy_datas, scipy_binaries, scipy_hiddenimports = collect_all('scipy')
    if scipy_datas or scipy_binaries or scipy_hiddenimports:
        datas += scipy_datas
        binaries += scipy_binaries
        hiddenimports += scipy_hiddenimports
        scipy_collected = True
        print(f"[SPEC] Collected scipy: {len(scipy_datas)} datas, {len(scipy_binaries)} binaries, {len(scipy_hiddenimports)} imports")
    else:
        print(f"[SPEC] Warning: collect_all('scipy') returned empty")
except Exception as e:
    print(f"[SPEC] Warning: Could not collect scipy via hooks: {e}")

# Manual fallback - copy scipy folder directly if collect_all failed
if not scipy_collected and site_packages:
    scipy_path = os.path.join(site_packages, 'scipy')
    if os.path.exists(scipy_path):
        datas += [(scipy_path, 'scipy')]
        print(f"[SPEC] Manual scipy collection: {scipy_path}")
    else:
        print(f"[SPEC] ERROR: scipy not found at {scipy_path}")

# Also collect numpy
numpy_collected = False
try:
    from PyInstaller.utils.hooks import collect_all
    numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
    if numpy_datas or numpy_binaries or numpy_hiddenimports:
        datas += numpy_datas
        binaries += numpy_binaries
        hiddenimports += numpy_hiddenimports
        numpy_collected = True
        print(f"[SPEC] Collected numpy: {len(numpy_datas)} datas, {len(numpy_binaries)} binaries, {len(numpy_hiddenimports)} imports")
    else:
        print(f"[SPEC] Warning: collect_all('numpy') returned empty")
except Exception as e:
    print(f"[SPEC] Warning: Could not collect numpy via hooks: {e}")

# Manual fallback
if not numpy_collected and site_packages:
    numpy_path = os.path.join(site_packages, 'numpy')
    if os.path.exists(numpy_path):
        datas += [(numpy_path, 'numpy')]
        print(f"[SPEC] Manual numpy collection: {numpy_path}")
    else:
        print(f"[SPEC] ERROR: numpy not found at {numpy_path}")

a = Analysis(
    ['main.py'],
    pathex=[str(src_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='pytnc_pro.ico',  # Application icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
