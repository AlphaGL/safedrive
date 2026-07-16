/* Real-time ride tracking via Leaflet + Django Channels WebSocket.
 *
 * Expects a global `RIDE_CONFIG` object on the page:
 *   { rideId, wsScheme, host, token, canWrite, plannedRoute, pickup, destination }
 */
(function () {
  const cfg = window.RIDE_CONFIG;
  if (!cfg) return;


  const map = L.map("map", { zoomControl: true, attributionControl: false });
  // A clean, muted basemap (like Uber/Bolt use) instead of default OSM styling.
  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    maxZoom: 20,
    subdomains: "abcd",
  }).addTo(map);
  L.control.attribution({ prefix: false, position: "bottomright" })
    .addAttribution("&copy; OpenStreetMap &copy; CARTO").addTo(map);

  const pickup = cfg.pickup;
  const dest = cfg.destination;


  // --- Uber/Bolt-style pin icons ---
  const pickupIcon = L.divIcon({
    className: "ride-pin",
    html: '<div class="pin-dot pin-pickup"><span></span></div>',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
  const destIcon = L.divIcon({
    className: "ride-pin",
    html: '<div class="pin-flag">'
      + '<svg width="26" height="34" viewBox="0 0 26 34"><path d="M13 34c-.6-4.4-2.2-7.7-4.8-11C4.7 18.8 2 15.6 2 11a11 11 0 0 1 22 0c0 4.6-2.7 7.8-6.2 12-2.6 3.3-4.2 6.6-4.8 11z" fill="#1a1a1a"/><circle cx="13" cy="11" r="6.5" fill="#fff"/></svg>'
      + '</div>',
    iconSize: [26, 34],
    iconAnchor: [13, 34],
  });

  const pickupMarker = L.marker([pickup.lat, pickup.lng], { icon: pickupIcon }).addTo(map).bindPopup("Pickup");
  const destMarker = L.marker([dest.lat, dest.lng], { icon: destIcon }).addTo(map).bindPopup("Destination");

  // Planned route: solid blue "confirmed route" line with a soft halo underneath,
  // same visual language as Uber/Bolt's trip line.
  if (cfg.plannedRoute && cfg.plannedRoute.length) {
    L.polyline(cfg.plannedRoute, {
      color: "#0a5cff", weight: 9, opacity: 0.16, lineCap: "round", lineJoin: "round",
    }).addTo(map);
    L.polyline(cfg.plannedRoute, {
      color: "#1e6bff", weight: 5, opacity: 0.95, lineCap: "round", lineJoin: "round",
    }).addTo(map);
  }
  // Travelled path: brighter, drawn on top as the vehicle actually moves.
  const actualPath = L.polyline([], {
    color: "#0a5cff", weight: 5, opacity: 1, lineCap: "round", lineJoin: "round",
  }).addTo(map);

  // --- Rotating car marker (points in the direction of travel, like Uber/Bolt) ---
  function carHtml(bearing) {
    return `<div class="car-marker" style="transform:rotate(${bearing}deg)">
      <svg width="30" height="30" viewBox="0 0 30 30">
        <circle cx="15" cy="15" r="14" fill="#fff" stroke="#0a5cff" stroke-width="1.5"/>
        <path d="M15 6l6 12H9l6-12z" fill="#0a5cff"/>
      </svg>
    </div>`;
  }
  function bearingBetween(a, b) {
    const toRad = (d) => (d * Math.PI) / 180;
    const toDeg = (r) => (r * 180) / Math.PI;
    const y = Math.sin(toRad(b[1] - a[1])) * Math.cos(toRad(b[0]));
    const x = Math.cos(toRad(a[0])) * Math.sin(toRad(b[0]))
      - Math.sin(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.cos(toRad(b[1] - a[1]));
    return (toDeg(Math.atan2(y, x)) + 360) % 360;
  }
  let vehicleMarker = null;
  let lastLatLng = null;

  function setVehicle(lat, lng, trace) {
    const latlng = [lat, lng];
    const bearing = lastLatLng ? bearingBetween(lastLatLng, latlng) : 0;
    if (!vehicleMarker) {
      vehicleMarker = L.marker(latlng, {
        icon: L.divIcon({ className: "car-icon-wrap", html: carHtml(bearing), iconSize: [30, 30], iconAnchor: [15, 15] }),
      }).addTo(map).bindPopup("Vehicle");
    } else {
      vehicleMarker.setLatLng(latlng);
      if (lastLatLng && (lastLatLng[0] !== lat || lastLatLng[1] !== lng)) {
        vehicleMarker.setIcon(
          L.divIcon({ className: "car-icon-wrap", html: carHtml(bearing), iconSize: [30, 30], iconAnchor: [15, 15] })
        );
      }
    }
    lastLatLng = latlng;
    if (trace !== false) actualPath.addLatLng(latlng);
    checkDeviation(lat, lng);
  }

  // --- Route deviation detection (passenger safety) ---
  // Compares the vehicle's live position against the planned route and warns
  // the passenger if the driver strays too far from it.
  const DEVIATION_ON = 350;   // metres off-route to raise a warning
  const DEVIATION_OFF = 180;  // metres to consider "back on route" (hysteresis)
  let offRoute = false, deviationReported = false;

  function haversineM(aLat, aLng, bLat, bLng) {
    const R = 6371000, toRad = (d) => (d * Math.PI) / 180;
    const dLat = toRad(bLat - aLat), dLng = toRad(bLng - aLng);
    const s = Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  }
  function distanceToRouteM(lat, lng) {
    const route = (cfg.plannedRoute && cfg.plannedRoute.length)
      ? cfg.plannedRoute : [[pickup.lat, pickup.lng], [dest.lat, dest.lng]];
    let min = Infinity;
    for (const p of route) { const d = haversineM(lat, lng, p[0], p[1]); if (d < min) min = d; }
    return min;
  }
  function checkDeviation(lat, lng) {
    const d = distanceToRouteM(lat, lng);
    if (!offRoute && d > DEVIATION_ON) { offRoute = true; onDeviation(lat, lng, d); }
    else if (offRoute && d < DEVIATION_OFF) { offRoute = false; onBackOnRoute(); }
    else if (offRoute) { showDeviationBanner(Math.round(d)); }
  }
  function beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = "sine"; o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
      g.gain.setValueAtTime(0.12, ctx.currentTime); o.start();
      o.stop(ctx.currentTime + 0.25);
    } catch (_) {}
  }
  function showDeviationBanner(meters) {
    const b = document.getElementById("deviation-banner");
    if (!b) return;
    b.innerHTML = `🧭 <strong>Route deviation detected</strong> — your driver is about ${meters} m off the planned route. `
      + `Stay alert. If you feel unsafe, use the <strong>SOS</strong> button.`;
    b.style.display = "block";
  }
  function onDeviation(lat, lng, d) {
    actualPath.setStyle({ color: "#eb4d4b" });
    showDeviationBanner(Math.round(d));
    beep();
    // Record on the server (notifies admin + trusted contacts). Rider/driver only.
    if (cfg.deviationUrl && cfg.csrf && !deviationReported) {
      deviationReported = true;
      const body = new URLSearchParams();
      body.append("lat", lat); body.append("lng", lng); body.append("distance", Math.round(d));
      fetch(cfg.deviationUrl, {
        method: "POST",
        headers: { "X-CSRFToken": cfg.csrf, "Content-Type": "application/x-www-form-urlencoded" },
        body,
      }).catch(() => {});
    }
  }
  function onBackOnRoute() {
    actualPath.setStyle({ color: "#0a5cff" });
    const b = document.getElementById("deviation-banner");
    if (b) b.style.display = "none";
    deviationReported = false;
  }

  // Demo helper: nudge the vehicle progressively off-route so the deviation
  // alert can be witnessed without a second device.
  function demoDeviate() {
    realReceived = true; stopSimulation();
    const route = (cfg.plannedRoute && cfg.plannedRoute.length > 1)
      ? cfg.plannedRoute : [[pickup.lat, pickup.lng], [dest.lat, dest.lng]];
    const mid = route[Math.floor(route.length / 2)];
    let step = 0;
    clearInterval(window._demoTimer);
    window._demoTimer = setInterval(() => {
      step++;
      setVehicle(mid[0] + 0.0025 * step, mid[1] + 0.0016 * step);
      if (step >= 6) clearInterval(window._demoTimer);
    }, 650);
  }

  map.fitBounds(L.latLngBounds([pickup.lat, pickup.lng], [dest.lat, dest.lng]).pad(0.3));

  // --- WebSocket ---
  let socket;
  function connect() {
    let url = `${cfg.wsScheme}://${cfg.host}/ws/ride/${cfg.rideId}/`;
    if (cfg.token) url += `?token=${cfg.token}`;
    socket = new WebSocket(url);

    socket.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "init") {
        if (data.last) setVehicle(data.last.lat, data.last.lng);
      } else if (data.type === "location") {
        realReceived = true;          // a real driver GPS stream — stop simulating
        stopSimulation();
        setVehicle(data.lat, data.lng);
      } else if (data.type === "alert") {
        showAlertBanner(data.alert);
      } else if (data.type === "status") {
        const el = document.getElementById("ride-status");
        if (el) el.textContent = data.status;
        handleStatus(data.status);
      }
    };
    socket.onclose = () => setTimeout(connect, 3000); // auto-reconnect
  }
  connect();

  // --- Demo simulation: animate the vehicle along the planned route so the
  //     map is always "live". Cancels the moment a real GPS update arrives.
  let realReceived = false, simTimer = null;
  function buildDensePath() {
    const route = (cfg.plannedRoute && cfg.plannedRoute.length > 1)
      ? cfg.plannedRoute
      : [[pickup.lat, pickup.lng], [dest.lat, dest.lng]];
    const pts = [];
    for (let i = 0; i < route.length - 1; i++) {
      const a = route[i], b = route[i + 1];
      for (let s = 0; s < 8; s++) pts.push([a[0] + (b[0] - a[0]) * s / 8, a[1] + (b[1] - a[1]) * s / 8]);
    }
    pts.push(route[route.length - 1]);
    return pts;
  }
  function startSimulation() {
    if (!cfg.simulate || cfg.canWrite || realReceived) return;
    const pts = buildDensePath();
    let i = 0;
    stopSimulation();
    simTimer = setInterval(() => {
      if (realReceived) return stopSimulation();
      if (i === 0) actualPath.setLatLngs([]);   // reset trail each loop
      setVehicle(pts[i][0], pts[i][1]);
      i = (i + 1) % pts.length;
    }, 450);
  }
  function stopSimulation() { if (simTimer) { clearInterval(simTimer); simTimer = null; } }
  // Give a real driver a few seconds to appear before falling back to sim.
  setTimeout(startSimulation, 3500);

  function showAlertBanner(alert) {
    const banner = document.getElementById("alert-banner");
    if (!banner) return;
    banner.textContent = `⚠️ ${alert.kind || "Alert"}: ${alert.message || ""}`;
    banner.style.display = "block";
  }

  function handleStatus(status) {

    if (window.updateRideStepper) window.updateRideStepper(status);
    const banner = document.getElementById("alert-banner");
    if (!banner) return;
    if (status === "accepted" || status === "ongoing") {
      // Driver is active — animate movement even if the page was loaded earlier.
      cfg.simulate = true;
      startSimulation();
    }
    if (status === "accepted") {
      banner.style.borderColor = "var(--success)";
      banner.style.background = "rgba(52,211,153,.12)";
      banner.innerHTML = "✅ Your driver accepted and is on the way!";
      banner.style.display = "block";
    } else if (status === "ongoing") {
      banner.style.display = "none";
    } else if (status === "rejected" || status === "cancelled") {
      banner.style.borderColor = "var(--danger)";
      banner.style.background = "rgba(255,77,99,.12)";
      banner.innerHTML =
        `❌ This driver is unavailable. <a href="${cfg.rebookUrl || "#"}">Choose another driver →</a>`;
      banner.style.display = "block";
    } else if (status === "completed") {
      stopSimulation();
      banner.style.borderColor = "var(--success)";
      banner.style.background = "rgba(52,211,153,.12)";
      banner.innerHTML = cfg.rateUrl
        ? `🏁 Trip completed! <a href="${cfg.rateUrl}"><strong>Rate your driver →</strong></a>`
        : "🏁 Trip completed. Thank you for riding with SafeDrive!";
      banner.style.display = "block";
    } else if (status === "cancelled") {
      stopSimulation();
    }
  }

  // --- Driver location streaming ---
  if (cfg.canWrite && navigator.geolocation) {
    navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        setVehicle(latitude, longitude);
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ action: "location", lat: latitude, lng: longitude }));
        }
      },
      (err) => console.warn("Geolocation error", err),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
  }

  window.SafeDriveMap = { map, setVehicle, demoDeviate };
})();
