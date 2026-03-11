"""
PyTNC Pro - Map HTML Generator
Generates the Leaflet-based APRS map HTML file
"""

from pathlib import Path


def write_map_html(base_dir: Path, http_port: int = 8080) -> Path:
    """Write map HTML that loads tiles via HTTP (better network compat)."""
    
    # Local tile server URL for cached tiles
    local_tile_url = f"http://127.0.0.1:{http_port}/tile_cache/{{z}}/{{x}}/{{y}}.png"
    
    html = '''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>APRS Map</title>
  <!-- Leaflet CSS: local first, CDN fallback for clean installs -->
  <link rel="stylesheet" href="leaflet.css" id="leaflet-css-local">
  <style>
    html, body, #map { height: 100%; margin: 0; background: #2d3748; }
    .leaflet-container { background: #2d3748 !important; }
    
    /* Hide tooltips during zoom */
    .map-zooming .leaflet-tooltip,
    .map-zooming .leaflet-popup {
      display: none !important;
    }
    
    /* Pause pulse animations during zoom */
    .map-zooming .earthquake-pulse-active,
    .map-zooming .weather-tooltip-pulsing { 
      animation: none !important; 
    }
    
    #status {
      position: absolute; top: 10px; left: 10px; z-index: 9999;
      background: rgba(0,0,0,0.85); color: #fff; padding: 8px 14px;
      border-radius: 6px; font: 13px/1.4 Consolas, monospace;
      border: 2px solid #666;
    }
    #status.ok { border-color: #4f4; }
    #status.error { border-color: #f44; }
    #status.warn { border-color: #fa0; }
    
    /* Tooltip styling */
    .leaflet-tooltip {
      background: rgba(13,33,55,0.95) !important;
      color: #e0e0e0 !important;
      border: 1px solid #42a5f5 !important;
      border-radius: 6px !important;
      padding: 8px 10px !important;
      font: 11px/1.4 Consolas, monospace !important;
      box-shadow: 0 2px 8px rgba(0,0,0,0.5) !important;
    }
    .leaflet-tooltip b { color: #ffd54f; }
    
    /* Permanent callsign label (aprs.fi style) */
    .callsign-label {
      background: rgba(0,0,0,0.7) !important;
      color: #ffffff !important;
      border: none !important;
      border-radius: 2px !important;
      padding: 1px 4px !important;
      font: bold 10px/1.2 Arial, sans-serif !important;
      box-shadow: 1px 1px 2px rgba(0,0,0,0.5) !important;
      white-space: nowrap !important;
    }
    .callsign-label::before {
      display: none !important;
    }
    
    /* Custom location marker - clean with alpha */
    .custom-location-marker {
      background: transparent !important;
      border: none !important;
    }
    
    /* Earthquake tooltip */
    .earthquake-tooltip {
      background: rgba(80,20,20,0.95) !important;
      border: 1px solid #ff6600 !important;
    }
    
    /* Earthquake pulsing marker */
    .earthquake-pulse {
      position: relative;
    }
    .earthquake-pulse .eq-outer {
      position: absolute;
      border-radius: 50%;
      opacity: 0.3;
    }
    .earthquake-pulse .eq-inner {
      position: absolute;
      border-radius: 50%;
      opacity: 0.7;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
    }
    .earthquake-pulse .eq-label {
      position: absolute;
      top: -18px;
      left: 50%;
      transform: translateX(-50%);
      font-size: 9px;
      font-weight: bold;
      padding: 1px 3px;
      border-radius: 3px;
      white-space: nowrap;
    }
    
    /* Active pulsing for recent earthquakes */
    .earthquake-pulse-active {
      position: relative;
    }
    .earthquake-pulse-active .eq-outer {
      position: absolute;
      border-radius: 50%;
      opacity: 0.6;
      animation: eq-pulse 1.5s ease-out infinite;
    }
    .earthquake-pulse-active .eq-inner {
      position: absolute;
      border-radius: 50%;
      opacity: 0.9;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      box-shadow: 0 0 10px rgba(255,0,0,0.8);
    }
    .earthquake-pulse-active .eq-label {
      position: absolute;
      top: -18px;
      left: 50%;
      transform: translateX(-50%);
      font-size: 10px;
      font-weight: bold;
      padding: 2px 4px;
      border-radius: 3px;
      white-space: nowrap;
      animation: eq-label-blink 1s ease-in-out infinite;
    }
    @keyframes eq-pulse {
      0% { transform: scale(1); opacity: 0.6; }
      100% { transform: scale(3); opacity: 0; }
    }
    @keyframes eq-label-blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    
    /* Earthquake magnitude label (non-recent) */
    .eq-mag-label {
      background: rgba(0,0,0,0.7) !important;
      color: #ffcc00 !important;
      border: none !important;
      border-radius: 2px !important;
      padding: 1px 4px !important;
      font: bold 10px/1.2 Arial, sans-serif !important;
      box-shadow: 1px 1px 2px rgba(0,0,0,0.5) !important;
      white-space: nowrap !important;
    }
    .eq-mag-label::before {
      display: none !important;
    }
    
    /* Recent earthquake tooltip */
    .earthquake-tooltip-recent {
      background: rgba(150,20,20,0.95) !important;
      border: 2px solid #ff0000 !important;
      box-shadow: 0 0 15px rgba(255,0,0,0.5) !important;
    }
    
    /* Hospital marker - big bold H */
    .hospital-marker {
      text-align: center;
    }
    .hospital-marker .hospital-h {
      width: 24px;
      height: 24px;
      background: #0066cc;
      color: #fff;
      font-size: 18px;
      font-weight: bold;
      line-height: 24px;
      text-align: center;
      border-radius: 4px;
      border: 2px solid #fff;
      box-shadow: 0 2px 6px rgba(0,0,0,0.5);
    }
    
    /* Hospital tooltip */
    .hospital-tooltip {
      background: rgba(0,50,100,0.95) !important;
      border: 1px solid #4da6ff !important;
    }
    
    /* Weather alert marker */
    .weather-alert-marker {
      text-align: center;
    }
    .weather-alert-marker .weather-alert {
      width: 28px;
      height: 28px;
      font-size: 18px;
      line-height: 28px;
      text-align: center;
      border-radius: 50%;
      border: 3px solid;
      box-shadow: 0 0 10px rgba(255,100,0,0.7);
      animation: weather-pulse 1.5s ease-in-out infinite;
    }
    @keyframes weather-pulse {
      0%, 100% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.1); opacity: 0.8; }
    }
    
    /* Weather tooltip */
    .weather-tooltip {
      background: rgba(100,50,0,0.95) !important;
      border: 2px solid #ff6600 !important;
      max-width: 300px !important;
      white-space: normal !important;
      word-wrap: break-word !important;
      overflow-wrap: break-word !important;
    }
    
    /* Repeater marker */
    .repeater-marker {
      text-align: center;
    }
    .repeater-marker .repeater-icon {
      font-size: 20px;
      text-shadow: 0 0 4px rgba(0,0,0,0.8);
    }
    .repeater-marker .repeater-loc {
      position: absolute;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(0,100,0,0.9);
      color: #fff;
      font-size: 9px;
      font-weight: bold;
      padding: 1px 4px;
      border-radius: 3px;
      white-space: nowrap;
      max-width: 100px;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    /* DARN emergency repeater marker (red) */
    .darn-marker {
      text-align: center;
    }
    .darn-marker .darn-icon {
      font-size: 22px;
      text-shadow: 0 0 6px rgba(255,0,0,0.8);
    }
    .darn-marker .darn-loc {
      position: absolute;
      top: 22px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(180,0,0,0.95);
      color: #fff;
      font-size: 9px;
      font-weight: bold;
      padding: 2px 5px;
      border-radius: 3px;
      white-space: nowrap;
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
      border: 1px solid #ff6b6b;
    }
    
    /* DARN tooltip */
    .darn-tooltip {
      background: rgba(120,0,0,0.95) !important;
      border: 1px solid #ff6b6b !important;
      color: #fff !important;
    }
    
    /* Repeater tooltip */
    .repeater-tooltip {
      background: rgba(0,80,0,0.95) !important;
      border: 1px solid #69f0ae !important;
    }
    
    /* Popup styling */
    .leaflet-popup-content-wrapper {
      background: rgba(13,33,55,0.98) !important;
      color: #e0e0e0 !important;
      border: 1px solid #42a5f5 !important;
      border-radius: 8px !important;
      box-shadow: 0 3px 12px rgba(0,0,0,0.6) !important;
      min-width: 200px !important;
    }
    .leaflet-popup-content {
      font: 11px/1.5 Consolas, monospace !important;
      margin: 10px 12px !important;
      white-space: nowrap !important;
    }
    .leaflet-popup-tip {
      background: rgba(13,33,55,0.98) !important;
      border: 1px solid #42a5f5 !important;
    }
    .leaflet-popup-close-button {
      color: #42a5f5 !important;
    }
    .qrz-link {
      color: #ffd54f !important;
      text-decoration: none;
      font-weight: bold;
      cursor: pointer;
    }
    .qrz-link:hover {
      color: #ffeb3b !important;
      text-decoration: underline;
    }
    
    /* Digi range circle */
    .digi-range {
      fill: #42a5f5;
      fill-opacity: 0.1;
      stroke: #42a5f5;
      stroke-width: 2;
      stroke-opacity: 0.5;
    }
    
    /* Crisp icon rendering */
    .leaflet-marker-icon {
      image-rendering: -webkit-optimize-contrast;
      image-rendering: crisp-edges;
    }
  </style>
</head>
<body>
  <div id="status">Loading...</div>
  <div id="map"></div>
  
  <!-- Leaflet JS: try local first, CDN fallback -->
  <script src="leaflet.js" onerror="window._leafletLocalFailed=true"></script>
  <script>
    // CDN fallback if local leaflet.js failed to load
    (function() {
      function initMap() {
        var status = document.getElementById('status');
        window._mapReady = false;
        window._mapError = null;
        window._tilesLoaded = 0;
        window._tileErrors = 0;
        
        // Check GPU/WebGL availability
        window._gpuInfo = 'unknown';
        try {
          var canvas = document.createElement('canvas');
          var gl = canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
          if (gl) {
            var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (debugInfo) {
              window._gpuInfo = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
              console.log('GPU: ' + window._gpuInfo);
            } else {
              window._gpuInfo = 'WebGL enabled (no debug info)';
            }
          } else {
            window._gpuInfo = 'WebGL not available - using software rendering';
            console.warn('WebGL not available - map performance may be reduced');
          }
        } catch(e) {
          window._gpuInfo = 'GPU detection failed: ' + e.message;
        }
        
        var map = L.map('map', {
          center: [34.05, -118.25],
          zoom: 10,
          preferCanvas: true,
          renderer: L.canvas()
        });
        
        // Create a canvas renderer for all circle markers
        var canvasRenderer = L.canvas({ padding: 0.5 });
        
        // Track zoom state for conditional updates
        var zoomTimeout;
        var isZooming = false;
        map.on('zoomstart', function() {
          isZooming = true;
          document.body.classList.add('map-zooming');
        });
        map.on('zoomend', function() {
          clearTimeout(zoomTimeout);
          // Short delay to let tiles settle
          zoomTimeout = setTimeout(function() {
            isZooming = false;
            document.body.classList.remove('map-zooming');
            
            // Flush any pending updates that came in during zoom
            if (pendingUpdates && pendingUpdates.length > 0) {
              console.log('Flushing ' + pendingUpdates.length + ' deferred updates');
              var updates = pendingUpdates.slice();
              pendingUpdates = [];
              updates.forEach(function(u) {
                window.updateStation(u[0], u[1], u[2], u[3], u[4], u[5], u[6]);
              });
            }
          }, 100);
        });
        
        // Expose zoom state for conditional rendering
        window.isMapZooming = function() { return isZooming; };
        
        // Track if a popup is open
        var popupOpen = false;
        var openPopupMarker = null;
        
        map.on('popupopen', function(e) {
          popupOpen = true;
          openPopupMarker = e.popup._source;
          // Don't close tooltip - callsign label should stay visible
        });
        
        map.on('popupclose', function(e) {
          popupOpen = false;
          openPopupMarker = null;
        });
        
        // Permanent callsign labels stay visible always
        
        // Tile URL - local proxy handles caching and fallback to OSM
        var tileUrl = '___LOCAL_TILE_URL___';
        
        // Direct OSM URL as fallback
        var osmDirectUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
        
        // OpenStreetMap tiles via local proxy (primary)
        var tiles = L.tileLayer(tileUrl, {
          attribution: '© OpenStreetMap',
          maxZoom: 19,
          crossOrigin: true
        });
        
        tiles.on('tileload', function(e) { 
          window._tilesLoaded++;
        });
        tiles.on('tileerror', function(e) { 
          window._tileErrors++;
          // Server now returns transparent PNG for missing tiles, so errors are rare
          console.log('[TILES] Error loading:', e.coords);
        });
        tiles.addTo(map);
      
      // Station markers
      var markers = {};
      var digiCircles = {};
      var pathLines = {};
      var pendingUpdates = [];  // Queue updates during zoom
      
      // Digipeaters heard tracking (for stats)
      var digisHeard = {};
      
      // Icon cache - avoid recreating Leaflet icons for same URL
      var iconCache = {};
      function getIcon(iconUrl) {
        if (!iconCache[iconUrl]) {
          iconCache[iconUrl] = L.icon({
            iconUrl: iconUrl,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
            popupAnchor: [0, -12]
          });
        }
        return iconCache[iconUrl];
      }
      
      // Prune old station markers to keep map responsive (max 500 markers)
      var MAX_STATION_MARKERS = 500;
      function pruneOldMarkers() {
        var calls = Object.keys(markers);
        if (calls.length <= MAX_STATION_MARKERS) return;
        
        // Sort by last update time, oldest first
        calls.sort(function(a, b) {
          return (markers[a]._lastUpdate || 0) - (markers[b]._lastUpdate || 0);
        });
        
        // Remove oldest markers until under limit
        var toRemove = calls.length - MAX_STATION_MARKERS;
        for (var i = 0; i < toRemove; i++) {
          var call = calls[i];
          map.removeLayer(markers[call]);
          delete markers[call];
        }
        console.log('Pruned ' + toRemove + ' old markers');
      }
      
      // Run pruning periodically
      setInterval(pruneOldMarkers, 60000);  // Every minute
      
      // HTML escape function to prevent XSS from untrusted APRS data
      function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        var div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
      }
      
      // Escape HTML but restore allowed formatting tags and linkify URLs
      function safeTooltipHtml(str) {
        if (!str) return '';
        var escaped = escapeHtml(str);
        var result = escaped
          .replace(/&lt;br&gt;/g, '<br>')
          .replace(/&lt;b&gt;/g, '<b>')
          .replace(/&lt;[/]b&gt;/g, '</b>')
          .replace(/&lt;i&gt;/g, '<i>')
          .replace(/&lt;[/]i&gt;/g, '</i>')
          .replace(/&lt;span([^<]*)&gt;/g, function(m, attrs) {
            return '<span' + attrs.replace(/&quot;/g, '"') + '>';
          })
          .replace(/&lt;[/]span&gt;/g, '</span>')
          // Restore anchor tags - match &lt;a ...&gt; pattern
          .replace(/&lt;a\\s+(.*?)&gt;/g, function(match, attrs) {
            attrs = attrs.replace(/&quot;/g, '"').replace(/&amp;/g, '&');
            return '<a ' + attrs + '>';
          })
          .replace(/&lt;[/]a&gt;/g, '</a>');
        
        return result;
      }
      
      // Pan to station
      window.panToStation = function(call) {
        if (markers[call]) {
          var ll = markers[call].getLatLng();
          map.setView(ll, 14);
          markers[call].openPopup();
        }
      };
      
      // ========== RENDER QUEUE ==========
      // Latest-wins queue keyed by callsign - coalesces rapid updates
      var stationQueue = Object.create(null);
      var flushScheduled = false;
      
      window.queueStation = function(call, lat, lon, iconUrl, tooltip, isDigi, path) {
        // Store latest update for this callsign (overwrites previous)
        stationQueue[call] = [call, lat, lon, iconUrl, tooltip, isDigi, path];
        
        if (!flushScheduled) {
          flushScheduled = true;
          // RAF aligns with display refresh (~60fps max)
          requestAnimationFrame(flushStationQueue);
        }
        return true;
      };
      
      function flushStationQueue() {
        flushScheduled = false;
        
        // If zooming, reschedule but don't process yet
        if (isZooming) {
          if (Object.keys(stationQueue).length) {
            flushScheduled = true;
            requestAnimationFrame(flushStationQueue);
          }
          return;
        }
        
        // Swap queue (allows new items during processing)
        var updates = stationQueue;
        stationQueue = Object.create(null);
        
        // Apply latest update per callsign
        for (var call in updates) {
          var u = updates[call];
          window.updateStation(u[0], u[1], u[2], u[3], u[4], u[5], u[6]);
        }
        
        // If more came in during flush, schedule again
        if (Object.keys(stationQueue).length) {
          flushScheduled = true;
          requestAnimationFrame(flushStationQueue);
        }
      }
      
      // ========== STATION MARKER ==========
      // Add/update station marker (called from flush, not directly from Python)
      window.updateStation = function(call, lat, lon, iconUrl, tooltip, isDigi, path) {
        // Defer updates while zooming to prevent jank
        if (isZooming) {
          pendingUpdates.push([call, lat, lon, iconUrl, tooltip, isDigi, path]);
          return true;
        }
        
        // Check if we can skip the expensive Leaflet updates
        var existing = markers[call];
        if (existing) {
          var ll = existing.getLatLng();
          if (
            Math.abs(ll.lat - lat) < 0.00001 &&
            Math.abs(ll.lng - lon) < 0.00001 &&
            existing._iconUrl === iconUrl &&
            existing._tooltipRaw === tooltip &&
            existing._pathRaw === path
          ) {
            // Nothing meaningful changed - skip ALL work
            existing._lastUpdate = Date.now();
            return true;
          }
        }
        
        // Escape all untrusted inputs (only when we actually update)
        var safeCall = escapeHtml(call);
        var safeTooltip = tooltip ? safeTooltipHtml(tooltip) : '';
        var safePath = escapeHtml(path);
        
        // Use cached icon to avoid DOM churn
        var icon = getIcon(iconUrl);
        
        // Cache base popup HTML (QRZ link never changes for a callsign)
        var basePopup;
        if (existing && existing._basePopup) {
          basePopup = existing._basePopup;
        } else {
          var baseCall = encodeURIComponent(call.split('-')[0]);
          basePopup = '<b><a class="qrz-link" href="https://www.qrz.com/db/' + baseCall + '" target="_blank">' + safeCall + '</a></b>';
        }
        
        // Build popup with cached base + dynamic parts (all details go here now)
        var popupHtml = basePopup + '<br>' + lat.toFixed(5) + ', ' + lon.toFixed(5);
        if (safeTooltip) popupHtml += '<br>' + safeTooltip;
        if (safePath) popupHtml += '<br><span style="color:#ce93d8">via ' + safePath + '</span>';
        
        // Callsign label - permanent, always visible (aprs.fi style)
        var labelHtml = safeCall;
        
        if (existing) {
          existing.setLatLng([lat, lon]);
          existing.setIcon(icon);
          existing.setPopupContent(popupHtml);
          existing.setTooltipContent(labelHtml);
        } else {
          markers[call] = L.marker([lat, lon], { icon: icon })
            .addTo(map)
            .bindPopup(popupHtml, { autoPan: false })
            .bindTooltip(labelHtml, { 
              permanent: true,
              direction: 'right',
              offset: [6, 0],
              className: 'callsign-label'
            });
          markers[call]._basePopup = basePopup;
        }
        
        // Cache state for change detection
        markers[call]._lastUpdate = Date.now();
        markers[call]._iconUrl = iconUrl;
        markers[call]._tooltipRaw = tooltip;
        markers[call]._pathRaw = path;
        
        // Track digipeaters
        if (path) {
          path.split(',').forEach(function(digi) {
            digi = digi.replace('*', '').trim();
            if (digi && !digi.match(/^(WIDE|RELAY|TRACE|qA)/i)) {
              if (!digisHeard[digi]) {
                digisHeard[digi] = { count: 0, lat: null, lon: null };
              }
              digisHeard[digi].count++;
            }
          });
        }
        
        return true;
      };
      
      // Update digi position (when we decode their beacon)
      window.updateDigiPosition = function(call, lat, lon) {
        if (digisHeard[call]) {
          digisHeard[call].lat = lat;
          digisHeard[call].lon = lon;
        }
      };
      
      // Draw path line between stations
      window.drawPath = function(call1, call2, color) {
        if (!markers[call1] || !markers[call2]) return;
        var key = call1 + '-' + call2;
        var latlngs = [markers[call1].getLatLng(), markers[call2].getLatLng()];
        
        if (pathLines[key]) {
          pathLines[key].setLatLngs(latlngs);
        } else {
          pathLines[key] = L.polyline(latlngs, {
            color: color || '#42a5f5',
            weight: 2,
            opacity: 0.6,
            dashArray: '5, 5'
          }).addTo(map);
        }
      };
      
      // Show digi coverage circle
      window.showDigiRange = function(call, lat, lon, radiusKm) {
        if (digiCircles[call]) {
          digiCircles[call].setLatLng([lat, lon]);
          digiCircles[call].setRadius(radiusKm * 1000);
        } else {
          digiCircles[call] = L.circle([lat, lon], {
            radius: radiusKm * 1000,
            className: 'digi-range'
          }).addTo(map);
        }
      };
      
      // Center map on station
      window.centerOn = function(call) {
        if (markers[call]) {
          map.setView(markers[call].getLatLng(), 13);
          markers[call].openPopup();
        }
      };
      
      // Center map on coordinates
      window.setCenter = function(lat, lon, zoom) {
        map.setView([lat, lon], zoom || 12);
      };
      
      // Refresh map tiles
      window.refreshMap = function() {
        tiles.redraw();
      };
      
      // Toggle callsign label visibility
      window.toggleCallsignLabels = function(show) {
        var labels = document.querySelectorAll('.callsign-label');
        labels.forEach(function(label) {
          label.style.display = show ? 'block' : 'none';
        });
      };
      
      // Earthquake markers
      var earthquakeMarkers = [];
      
      // Add earthquake to map with pulsing effect for recent ones
      window.addEarthquake = function(lat, lon, mag, color, size, tooltip, isRecent) {
        var safeTooltip = safeTooltipHtml(tooltip);
        var pulseClass = isRecent ? 'earthquake-pulse-active' : 'earthquake-pulse';
        var pulseIcon = L.divIcon({
          className: pulseClass,
          html: '<div class="eq-outer" style="background:'+color+';width:'+size+'px;height:'+size+'px;"></div>' +
                '<div class="eq-inner" style="background:'+color+';width:'+(size/2)+'px;height:'+(size/2)+'px;' + 
                (isRecent ? 'border:2px solid #fff;' : 'border:1px solid #888;') + '"></div>' +
                '<div class="eq-label" style="' + (isRecent ? 'background:#ff0000;color:#fff;' : 'background:rgba(0,0,0,0.6);color:#aaa;') + 
                '">M'+mag.toFixed(1)+'</div>',
          iconSize: [size, size],
          iconAnchor: [size/2, size/2]
        });
        
        var marker = L.marker([lat, lon], {icon: pulseIcon}).addTo(map);
        
        marker.bindTooltip('<b>🌋 Earthquake' + (isRecent ? ' (RECENT)' : '') + '</b><br>' + safeTooltip, {
          className: isRecent ? 'earthquake-tooltip-recent' : 'earthquake-tooltip'
        });
        
        marker.bindPopup('<b>🌋 Earthquake M' + mag.toFixed(1) + (isRecent ? ' (RECENT)' : '') + '</b><br>' + safeTooltip);
        
        earthquakeMarkers.push(marker);
        return true;
      };
      
      // Bulk load earthquakes - much faster than Python→JS per marker
      window.setEarthquakesBulk = function(quakes) {
        // Clear existing
        earthquakeMarkers.forEach(function(m) { map.removeLayer(m); });
        earthquakeMarkers = [];
        
        // Add all in tight JS loop
        // Use CircleMarker for non-recent (canvas-rendered, much faster)
        // Use DivIcon only for recent earthquakes that need animation
        quakes.forEach(function(q) {
          var safeTooltip = safeTooltipHtml(q.tooltip);
          var marker;
          
          if (q.isRecent) {
            // Recent earthquakes get fancy animated DivIcon
            var pulseIcon = L.divIcon({
              className: 'earthquake-pulse-active',
              html: '<div class="eq-outer" style="background:'+q.color+';width:'+q.size+'px;height:'+q.size+'px;"></div>' +
                    '<div class="eq-inner" style="background:'+q.color+';width:'+(q.size/2)+'px;height:'+(q.size/2)+'px;border:2px solid #fff;"></div>' +
                    '<div class="eq-label" style="background:#ff0000;color:#fff;">M'+q.mag.toFixed(1)+'</div>',
              iconSize: [q.size, q.size],
              iconAnchor: [q.size/2, q.size/2]
            });
            marker = L.marker([q.lat, q.lon], {icon: pulseIcon}).addTo(map);
          } else {
            // Non-recent earthquakes use lightweight CircleMarker (canvas-rendered)
            marker = L.circleMarker([q.lat, q.lon], {
              radius: q.size / 2,
              fillColor: q.color,
              color: '#333',
              weight: 1,
              opacity: 0.8,
              fillOpacity: 0.6,
              renderer: canvasRenderer
            }).addTo(map);
            
            // Add magnitude label as permanent tooltip
            marker.bindTooltip('M' + q.mag.toFixed(1), {
              permanent: true,
              direction: 'right',
              offset: [8, 0],
              className: 'eq-mag-label'
            });
          }
          
          // Recent quakes get hover tooltip, non-recent already have permanent mag label
          if (q.isRecent) {
            marker.bindTooltip('<b>🌋 Earthquake (RECENT)</b><br>' + safeTooltip, {
              className: 'earthquake-tooltip-recent',
              sticky: false,
              direction: 'top'
            });
          }
          marker.bindPopup('<b>🌋 Earthquake M' + q.mag.toFixed(1) + (q.isRecent ? ' (RECENT)' : '') + '</b><br>' + safeTooltip, { autoPan: false });
          earthquakeMarkers.push(marker);
        });
        console.log('Bulk loaded ' + quakes.length + ' earthquakes');
        return quakes.length;
      };
      
      // Clear all earthquakes
      window.clearEarthquakes = function() {
        earthquakeMarkers.forEach(function(m) {
          map.removeLayer(m);
        });
        earthquakeMarkers = [];
      };
      
      // Fire/hotspot markers (NASA FIRMS)
      var fireMarkers = [];
      
      // Add fire hotspot to map
      window.addFire = function(lat, lon, brightness, confidence, satellite, acq_time, tooltip) {
        var safeTooltip = safeTooltipHtml(tooltip);
        
        // Size and color based on brightness (typically 300-500 Kelvin)
        var intensity = Math.min(1, Math.max(0, (brightness - 300) / 200));
        var size = 12 + intensity * 12;  // 12-24px
        
        // Color from yellow to red based on brightness
        var r = 255;
        var g = Math.round(255 - intensity * 200);  // 255 to 55
        var b = 0;
        var color = 'rgb(' + r + ',' + g + ',' + b + ')';
        
        var fireIcon = L.divIcon({
          className: 'fire-marker',
          html: '<div class="fire-outer" style="background:'+color+';width:'+size+'px;height:'+size+'px;border-radius:50%;opacity:0.7;position:relative;">' +
                '<div class="fire-inner" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:'+(size*0.7)+'px;">🔥</div>' +
                '</div>',
          iconSize: [size, size],
          iconAnchor: [size/2, size/2]
        });
        
        var marker = L.marker([lat, lon], {icon: fireIcon}).addTo(map);
        
        marker.bindTooltip('<b>🔥 Fire Hotspot</b><br>' + safeTooltip, {
          className: 'fire-tooltip'
        });
        
        marker.bindPopup('<b>🔥 Fire Hotspot</b><br>' + safeTooltip);
        
        fireMarkers.push(marker);
        return true;
      };
      
      // Bulk load fires - much faster than Python→JS per marker
      window.setFiresBulk = function(fires) {
        // Clear existing
        fireMarkers.forEach(function(m) { map.removeLayer(m); });
        fireMarkers = [];
        
        // Add all in tight JS loop using lightweight CircleMarkers
        fires.forEach(function(f) {
          var safeTooltip = safeTooltipHtml(f.tooltip);
          
          // Size and color based on brightness
          var intensity = Math.min(1, Math.max(0, (f.brightness - 300) / 200));
          var radius = 6 + intensity * 6;  // 6-12px radius
          var r = 255;
          var g = Math.round(255 - intensity * 200);
          var color = 'rgb(' + r + ',' + g + ',0)';
          
          // Use CircleMarker instead of DivIcon (canvas-rendered, much faster)
          var marker = L.circleMarker([f.lat, f.lon], {
            radius: radius,
            fillColor: color,
            color: '#ff4400',
            weight: 2,
            opacity: 0.9,
            fillOpacity: 0.7,
            renderer: canvasRenderer
          }).addTo(map);
          
          marker.bindTooltip('<b>🔥 Fire Hotspot</b><br>' + safeTooltip, { 
            className: 'fire-tooltip',
            sticky: false,
            direction: 'top'
          });
          marker.bindPopup('<b>🔥 Fire Hotspot</b><br>' + safeTooltip, { autoPan: false });
          fireMarkers.push(marker);
        });
        console.log('Bulk loaded ' + fires.length + ' fire hotspots');
        return fires.length;
      };
      
      // Clear all fires
      window.clearFires = function() {
        fireMarkers.forEach(function(m) {
          map.removeLayer(m);
        });
        fireMarkers = [];
      };
      
      // Hospital markers
      var hospitalMarkers = [];
      
      // Add hospital to map - simple H icon
      window.addHospital = function(lat, lon, name, tooltip) {
        var safeName = escapeHtml(name);
        var safeTooltip = safeTooltipHtml(tooltip);
        
        var hospitalIcon = L.divIcon({
          className: 'hospital-marker',
          html: '<div class="hospital-h">H</div>',
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        });
        
        var marker = L.marker([lat, lon], {icon: hospitalIcon}).addTo(map);
        
        marker.bindTooltip('<b>🏥 ' + safeName + '</b><br>' + safeTooltip, {
          className: 'hospital-tooltip',
          sticky: false,
          direction: 'top'
        });
        
        marker.bindPopup('<b>🏥 ' + safeName + '</b><br>' + safeTooltip + 
          '<br><a href="https://www.google.com/maps/dir/?api=1&destination='+lat+','+lon+'" target="_blank">📍 Directions</a>',
          { autoPan: false });
        
        hospitalMarkers.push(marker);
        return true;
      };
      
      // Bulk load hospitals - faster than Python→JS per marker
      window.setHospitalsBulk = function(hospitals) {
        // Clear existing
        hospitalMarkers.forEach(function(m) { map.removeLayer(m); });
        hospitalMarkers = [];
        
        // Add all in tight JS loop
        hospitals.forEach(function(h) {
          var safeName = escapeHtml(h.name);
          var safeTooltip = safeTooltipHtml(h.tooltip);
          
          var hospitalIcon = L.divIcon({
            className: 'hospital-marker',
            html: '<div class="hospital-h">H</div>',
            iconSize: [24, 24],
            iconAnchor: [12, 12]
          });
          
          var marker = L.marker([h.lat, h.lon], {icon: hospitalIcon}).addTo(map);
          marker.bindTooltip('<b>🏥 ' + safeName + '</b><br>' + safeTooltip, {
            className: 'hospital-tooltip',
            sticky: false,
            direction: 'top'
          });
          marker.bindPopup('<b>🏥 ' + safeName + '</b><br>' + safeTooltip + 
            '<br><a href="https://www.google.com/maps/dir/?api=1&destination='+h.lat+','+h.lon+'" target="_blank">📍 Directions</a>',
            { autoPan: false });
          hospitalMarkers.push(marker);
        });
        console.log('Bulk loaded ' + hospitals.length + ' hospitals');
        return hospitals.length;
      };
      
      // Clear all hospitals
      window.clearHospitals = function() {
        hospitalMarkers.forEach(function(m) {
          map.removeLayer(m);
        });
        hospitalMarkers = [];
      };
      
      // Custom location markers
      var customLocationMarkers = [];
      
      // Add custom location to map
      window.addCustomLocation = function(name, lat, lon, symbol, comment, address) {
        var safeName = escapeHtml(name);
        var safeComment = escapeHtml(comment || '');
        var safeAddress = escapeHtml(address || '');
        
        // Parse APRS symbol (e.g., backslash-h = store, /h = hospital)
        var symbolChar = symbol && symbol.length > 1 ? symbol[1] : 'h';
        var symbolTable = symbol && symbol.length > 0 ? symbol[0] : '\\\\';
        
        // Calculate icon index: ASCII 33 (!) = 00, ASCII 126 (~) = 93
        var charCode = symbolChar.charCodeAt(0);
        var iconNum = charCode - 33;
        if (iconNum < 0 || iconNum > 93) iconNum = 71; // Default to 'h'
        
        // Select folder based on table
        var folder = (symbolTable === '/') ? 'primary' : 'secondary';
        var iconUrl = '/aprs_symbols_48/' + folder + '/' + ('0' + iconNum).slice(-2) + '.png';
        
        // Use individual PNG icon
        var locationIcon = L.icon({
          iconUrl: iconUrl,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
          popupAnchor: [0, -16]
        });
        
        var marker = L.marker([lat, lon], {icon: locationIcon}).addTo(map);
        
        var tooltipHtml = '<b>' + safeName + '</b>';
        if (safeComment) tooltipHtml += '<br>' + safeComment;
        
        var popupHtml = '<b style="color:#ce93d8;font-size:14px;">' + safeName + '</b>';
        if (safeAddress) popupHtml += '<br><span style="color:#aaa;">' + safeAddress + '</span>';
        if (safeComment) popupHtml += '<br>' + safeComment;
        popupHtml += '<br><span style="color:#888;font-size:11px;">Symbol: ' + symbol + '</span>';
        popupHtml += '<br><a href="https://www.google.com/maps/dir/?api=1&destination='+lat+','+lon+'" target="_blank" style="color:#64b5f6;">📍 Directions</a>';
        
        marker.bindTooltip(tooltipHtml, { className: 'custom-location-tooltip' });
        marker.bindPopup(popupHtml);
        
        customLocationMarkers.push(marker);
        return true;
      };
      
      // Clear all custom locations
      window.clearCustomLocations = function() {
        customLocationMarkers.forEach(function(m) {
          map.removeLayer(m);
        });
        customLocationMarkers = [];
      };
      
      // Weather alert markers
      var weatherMarkers = [];
      
      // Add weather alert to map
      window.addWeatherAlert = function(lat, lon, event, color, tooltip) {
        var safeTooltip = safeTooltipHtml(tooltip);
        
        var alertIcon = L.divIcon({
          className: 'weather-alert-marker',
          html: '<div class="weather-alert" style="background:'+color+';border-color:'+color+';">⚠️</div>',
          iconSize: [32, 32],
          iconAnchor: [16, 16]
        });
        
        var marker = L.marker([lat, lon], {icon: alertIcon}).addTo(map);
        
        marker.bindTooltip(safeTooltip, {
          className: 'weather-tooltip'
        });
        
        marker.bindPopup(safeTooltip);
        
        weatherMarkers.push(marker);
        return true;
      };
      
      // Clear all weather alerts
      window.clearWeatherAlerts = function() {
        weatherMarkers.forEach(function(m) {
          map.removeLayer(m);
        });
        weatherMarkers = [];
      };
      
      // AQI markers
      var aqiMarkers = [];
      
      // Add AQI marker to map
      window.addAQIMarker = function(lat, lon, aqi, color, tooltip) {
        var safeTooltip = safeTooltipHtml(tooltip);
        
        var aqiIcon = L.divIcon({
          className: 'aqi-marker',
          html: '<div class="aqi-badge" style="background:'+color+';border-color:'+color+';color:#fff;font-weight:bold;padding:4px 8px;border-radius:12px;font-size:12px;text-shadow:1px 1px 1px rgba(0,0,0,0.5);">AQI '+aqi+'</div>',
          iconSize: [60, 24],
          iconAnchor: [30, 12]
        });
        
        var marker = L.marker([lat, lon], {icon: aqiIcon}).addTo(map);
        
        marker.bindTooltip(safeTooltip, {
          className: 'aqi-tooltip'
        });
        
        marker.bindPopup(safeTooltip);
        
        aqiMarkers.push(marker);
        return true;
      };
      
      // Clear all AQI markers
      window.clearAQI = function() {
        aqiMarkers.forEach(function(m) {
          map.removeLayer(m);
        });
        aqiMarkers = [];
      };
      
      // Repeater markers
      var repeaterMarkers = [];
      
      // Add repeater to map (location is shown instead of freq)
      window.addRepeater = function(lat, lon, call, location, tooltip) {
        var safeLocation = escapeHtml(location);
        var safeTooltip = safeTooltipHtml(tooltip);
        
        var repeaterIcon = L.divIcon({
          className: 'repeater-marker',
          html: '<div class="repeater-icon">📻</div><div class="repeater-loc">' + safeLocation + '</div>',
          iconSize: [80, 30],
          iconAnchor: [40, 15]
        });
        
        var marker = L.marker([lat, lon], {icon: repeaterIcon}).addTo(map);
        
        marker.bindTooltip(safeTooltip, {
          className: 'repeater-tooltip'
        });
        
        marker.bindPopup(safeTooltip);
        
        repeaterMarkers.push(marker);
        return true;
      };
      
      // DARN emergency repeater markers (red)
      var darnMarkers = [];
      
      window.addDarn = function(lat, lon, name, location, tooltip, status) {
        var safeLocation = escapeHtml(location);
        var safeTooltip = safeTooltipHtml(tooltip);
        
        var statusColor = status === 'Online' ? '#00ff00' : (status === 'Degraded' ? '#ffaa00' : '#ff4444');
        var darnIcon = L.divIcon({
          className: 'darn-marker',
          html: '<div class="darn-icon">🔴</div><div class="darn-loc">' + safeLocation + '</div>',
          iconSize: [100, 35],
          iconAnchor: [50, 17]
        });
        
        var marker = L.marker([lat, lon], {icon: darnIcon}).addTo(map);
        
        marker.bindTooltip(safeTooltip, {
          className: 'darn-tooltip'
        });
        
        marker.bindPopup(safeTooltip);
        
        darnMarkers.push(marker);
        return true;
      };
      
      window.clearDarn = function() {
        darnMarkers.forEach(function(m) {
          map.removeLayer(m);
        });
        darnMarkers = [];
      };
      
      // Clear all repeaters
      window.clearRepeaters = function() {
        repeaterMarkers.forEach(function(m) {
          map.removeLayer(m);
        });
        repeaterMarkers = [];
      };
      
      // Get map status
      window.getMapDiagnostics = function() {
        return {
          mapReady: window._mapReady,
          mapError: window._mapError,
          tilesLoaded: window._tilesLoaded,
          tileErrors: window._tileErrors,
          tileSource: 'local-proxy',
          leafletVersion: L.version,
          gpuInfo: window._gpuInfo || 'unknown',
          stationCount: Object.keys(markers).length,
          digiCount: Object.keys(digisHeard).length,
          earthquakeCount: earthquakeMarkers.length,
          fireCount: fireMarkers.length,
          hospitalCount: hospitalMarkers.length,
          weatherCount: weatherMarkers.length,
          repeaterCount: repeaterMarkers.length,
          customLocationCount: customLocationMarkers.length
        };
      };
      
      window._mapReady = true;
      var gpuShort = window._gpuInfo ? window._gpuInfo.split('/')[0].substring(0, 30) : '';
      status.textContent = 'Leaflet ' + L.version + ' | ' + (gpuShort || 'GPU unknown');
      status.className = 'ok';
      
      // Check if tiles are loading
      setTimeout(function() {
        if (window._tilesLoaded === 0 && window._tileErrors > 0) {
          console.log('No tiles loaded - may be offline with uncached area');
          status.textContent = 'Offline - some tiles not cached';
          status.className = 'warn';
        } else if (window._tilesLoaded > 0) {
          status.textContent = 'Map OK (' + window._tilesLoaded + ' tiles)';
        }
      }, 5000);
      
      // Update status when tiles finish loading
      tiles.on('load', function() {
        status.textContent = 'Map OK (' + window._tilesLoaded + ' tiles)';
      });
      
      } // end initMap
      
      // Check if Leaflet loaded, otherwise load from CDN
      if (typeof L !== 'undefined') {
        console.log('Leaflet loaded from local file');
        initMap();
      } else if (window._leafletLocalFailed) {
        console.log('Local leaflet.js failed, loading from CDN...');
        document.getElementById('status').textContent = 'Loading Leaflet from CDN...';
        
        // Load CSS from CDN
        var cssLink = document.createElement('link');
        cssLink.rel = 'stylesheet';
        cssLink.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
        document.head.appendChild(cssLink);
        
        // Load JS from CDN
        var script = document.createElement('script');
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        script.onload = function() {
          console.log('Leaflet loaded from CDN');
          initMap();
        };
        script.onerror = function() {
          document.getElementById('status').textContent = 'ERROR: Cannot load Leaflet (offline?)';
          document.getElementById('status').className = 'error';
          window._mapError = 'Leaflet failed to load from both local and CDN';
        };
        document.head.appendChild(script);
      } else {
        // Leaflet should have loaded - maybe still loading?
        setTimeout(function() {
          if (typeof L !== 'undefined') {
            initMap();
          } else {
            document.getElementById('status').textContent = 'ERROR: Leaflet not available';
            document.getElementById('status').className = 'error';
          }
        }, 100);
      }
    })();
  </script>
</body>
</html>'''
    
    # Replace placeholder with actual local tile URL
    html = html.replace('___LOCAL_TILE_URL___', local_tile_url)
    
    path = base_dir / "aprs_map.html"
    path.write_text(html, encoding="utf-8")
    return path
