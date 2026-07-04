/* Real-time ride tracking via Leaflet + Django Channels WebSocket.
 *
 * Expects a global `RIDE_CONFIG` object on the page:
 *   { rideId, wsScheme, host, token, canWrite, plannedRoute, pickup, destination }
 */
(function () {
  const cfg = window.RIDE_CONFIG;
  if (!cfg) return;

  const map = L.map("map");
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  const pickup = cfg.pickup;
  const dest = cfg.destination;

  // Markers for pickup, destination, vehicle.
  const pickupMarker = L.marker([pickup.lat, pickup.lng]).addTo(map).bindPopup("Pickup");
  const destMarker = L.marker([dest.lat, dest.lng]).addTo(map).bindPopup("Destination");

  // Planned route (dashed) + actual travelled path (solid).
  if (cfg.plannedRoute && cfg.plannedRoute.length) {
    L.polyline(cfg.plannedRoute, { color: "#9aa3c0", dashArray: "6 8", weight: 3 }).addTo(map);
  }
  const actualPath = L.polyline([], { color: "#4f7cff", weight: 4 }).addTo(map);

  const carIcon = L.divIcon({
    html: '<div style="font-size:26px">🚗</div>',
    className: "car-icon",
    iconSize: [26, 26],
  });
  let vehicleMarker = null;

  function setVehicle(lat, lng, trace) {
    const latlng = [lat, lng];
    if (!vehicleMarker) {
      vehicleMarker = L.marker(latlng, { icon: carIcon }).addTo(map).bindPopup("Vehicle");
    } else {
      vehicleMarker.setLatLng(latlng);
    }
    if (trace !== false) actualPath.addLatLng(latlng);
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
      banner.style.borderColor = "var(--success)";
      banner.style.background = "rgba(52,211,153,.12)";
      banner.innerHTML = "🏁 Trip completed. Thank you for riding with SafeDrive!";
      banner.style.display = "block";
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

  window.SafeDriveMap = { map, setVehicle };
})();
