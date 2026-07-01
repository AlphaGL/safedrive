/* SafeDrive landing — hero video carousel, nav scroll, testimonials, count-up */
(function () {
  // ---- Nav: solidify on scroll ----
  const nav = document.querySelector(".lp-nav");
  const onScroll = () => nav && nav.classList.toggle("scrolled", window.scrollY > 40);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  // ---- Hero video carousel ----
  const slides = Array.from(document.querySelectorAll(".lp-slide"));
  const dots = Array.from(document.querySelectorAll(".lp-dots button"));
  let current = 0;
  let timer = null;
  const INTERVAL = 6000;

  function playSlideVideo(i) {
    const v = slides[i] && slides[i].querySelector("video");
    if (v) { try { v.currentTime = 0; v.play().catch(() => {}); } catch (_) {} }
  }

  function go(i) {
    current = (i + slides.length) % slides.length;
    slides.forEach((s, idx) => s.classList.toggle("active", idx === current));
    dots.forEach((d, idx) => d.classList.toggle("active", idx === current));
    playSlideVideo(current);
    restart();
  }
  function next() { go(current + 1); }
  function restart() { clearInterval(timer); timer = setInterval(next, INTERVAL); }

  if (slides.length) {
    dots.forEach((d, idx) => d.addEventListener("click", () => go(idx)));
    go(0);
  }

  // ---- Testimonials carousel ----
  const quotes = Array.from(document.querySelectorAll(".lp-quote"));
  const qDots = Array.from(document.querySelectorAll(".lp-quote-dots button"));
  let q = 0, qTimer = null;
  function qGo(i) {
    q = (i + quotes.length) % quotes.length;
    quotes.forEach((el, idx) => el.classList.toggle("active", idx === q));
    qDots.forEach((el, idx) => el.classList.toggle("active", idx === q));
    clearInterval(qTimer); qTimer = setInterval(() => qGo(q + 1), 5000);
  }
  if (quotes.length) {
    qDots.forEach((d, idx) => d.addEventListener("click", () => qGo(idx)));
    qGo(0);
  }

  // ---- Count-up stats ----
  function countUp(el) {
    const target = parseFloat(el.dataset.count);
    const suffix = el.dataset.suffix || "";
    const decimals = (el.dataset.count.split(".")[1] || "").length;
    const dur = 1600, start = performance.now();
    function tick(now) {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // ---- Reveal + trigger count-up when in view ----
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in");
      entry.target.querySelectorAll && entry.target.querySelectorAll("[data-count]").forEach(countUp);
      io.unobserve(entry.target);
    });
  }, { threshold: 0.15 });
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
})();
