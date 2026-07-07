/* SOS button handler. Expects SOS_CONFIG = { url, csrf }. */
(function () {
  const cfg = window.SOS_CONFIG;
  const btn = document.getElementById("sos-btn");
  if (!cfg || !btn) return;

  function toast(msg) {
    const t = document.getElementById("toast");
    if (!t) return alert(msg);
    t.textContent = msg;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 5000);
  }

  function fire(lat, lng) {
    const body = new URLSearchParams();
    if (lat != null) body.append("lat", lat);
    if (lng != null) body.append("lng", lng);
    fetch(cfg.url, {
      method: "POST",
      headers: { "X-CSRFToken": cfg.csrf, "Content-Type": "application/x-www-form-urlencoded" },
      body,
    })
      .then((r) => r.json())
      .then((d) =>
        toast(`🚨 SOS sent. ${d.contacts_notified} trusted contact(s) and admin notified.`)
      )
      .catch(() => toast("Could not send SOS. Try again."));
  }

  btn.addEventListener("click", () => {
    if (!confirm("Trigger an emergency SOS alert?")) return;
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => fire(pos.coords.latitude, pos.coords.longitude),
        () => fire(null, null),
        { enableHighAccuracy: true, timeout: 8000 }
      );
    } else {
      fire(null, null);
    }
  });
})();
