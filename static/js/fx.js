/* Dashboard hero effect: a pixel-grid star with a travelling wave and a dotted
   red curve with a moving green head. Pure canvas, no libraries. It reacts to the
   voice state (#hero[data-state]) and to the pointer, pauses when off-screen, and
   draws one still frame when the OS asks for reduced motion. */
(function () {
  'use strict';
  const canvas = document.getElementById('fx-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const holder = canvas.parentElement;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const CELL = 9, DOTS = 72;

  let W = 0, H = 0, cells = [], pts = [], maxD = 1;
  let colors = { primary: [34, 197, 94], danger: [239, 68, 68] };
  let speed = 1, targetSpeed = 1, boost = 0, targetBoost = 0, phase = 0;
  let mouse = null, ripples = [], visible = true, raf = 0;
  const t0 = performance.now();
  let last = t0;

  const clamp = (v) => Math.max(0, Math.min(1, v));
  const ease = (t) => 1 - Math.pow(1 - t, 3);

  function hexToRgb(v) {
    v = (v || '').trim();
    if (v[0] === '#') {
      if (v.length === 4) v = '#' + v[1] + v[1] + v[2] + v[2] + v[3] + v[3];
      const n = parseInt(v.slice(1), 16);
      return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    }
    const m = v.match(/\d+/g);
    return m && m.length >= 3 ? m.slice(0, 3).map(Number) : null;
  }

  function readColors() {
    const cs = getComputedStyle(document.documentElement);
    colors = {
      primary: hexToRgb(cs.getPropertyValue('--primary')) || colors.primary,
      danger: hexToRgb(cs.getPropertyValue('--danger')) || colors.danger,
    };
    if (reduce) draw(performance.now(), true);
  }

  function build() {
    cells = [];
    const a = W * 0.36, b = H * 0.47, cx = W / 2, cy = H / 2;
    maxD = Math.hypot(a, b);
    for (let gy = 0; gy < Math.ceil(H / CELL); gy++) {
      for (let gx = 0; gx < Math.ceil(W / CELL); gx++) {
        const x = gx * CELL + CELL / 2, y = gy * CELL + CELL / 2;
        // astroid: a four-pointed star with concave sides
        const s = Math.pow(Math.abs((x - cx) / a), 2 / 3) + Math.pow(Math.abs((y - cy) / b), 2 / 3);
        if (s > 1) continue;
        cells.push({ x, y, v: Math.pow(1 - s, 0.55), dp: Math.hypot(x - cx, y - cy) });
      }
    }
    // dots follow an ease-in-out curve: slow start, steep middle, flat finish
    pts = [];
    const x0 = W * 0.05, x1 = W * 0.95, yTop = H * 0.2, yBot = H * 0.84;
    const f = (t) => 1 / (1 + Math.exp(-11 * (t - 0.64)));
    const f0 = f(0), f1 = f(1);
    for (let i = 0; i < DOTS; i++) {
      const t = i / (DOTS - 1);
      const v = ((f(t) - f0) / (f1 - f0)) * 0.92 + 0.08 * t;
      pts.push({ x: x0 + (x1 - x0) * t, y: yBot - (yBot - yTop) * v });
    }
  }

  function resize() {
    const r = holder.getBoundingClientRect();
    W = r.width; H = r.height;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build();
    if (reduce) draw(performance.now(), true);
  }

  function draw(now, still) {
    const el = still ? 99 : (now - t0) / 1000;
    ctx.clearRect(0, 0, W, H);
    const [pr, pg, pb] = colors.primary;
    const live = ripples.map((r) => ({ x: r.x, y: r.y, rr: ((now - r.t0) / 1000) * 340, fade: Math.max(0, 1 - (now - r.t0) / 1800) }));

    for (const c of cells) {
      const e = ease(clamp((el * 0.9 - (c.dp / maxD) * 0.8) / 0.35));
      if (e <= 0) continue;
      const wave = 0.5 + 0.5 * Math.sin(c.dp * 0.045 - phase * 2.4);
      let b = c.v * (0.3 + 0.5 * wave) + boost * 0.3 * c.v;
      if (mouse) {
        const dx = c.x - mouse.x, dy = c.y - mouse.y;
        b += 0.6 * Math.exp(-(dx * dx + dy * dy) / (2 * 70 * 70));
      }
      for (const r of live) {
        const d = Math.hypot(c.x - r.x, c.y - r.y) - r.rr;
        b += 0.9 * r.fade * Math.exp(-(d * d) / (2 * 28 * 28));
      }
      b = Math.min(b, 1);
      const size = CELL * (0.5 + 0.5 * b) * e;
      ctx.fillStyle = 'rgba(' + pr + ',' + pg + ',' + pb + ',' + ((0.05 + 0.6 * b) * e).toFixed(3) + ')';
      ctx.fillRect(c.x - size / 2, c.y - size / 2, size, size);
    }

    const [dr, dg, db] = colors.danger;
    for (let i = 0; i < pts.length; i++) {
      const dotIn = ease(clamp((el - 0.35 - i * 0.012) / 0.4));
      if (dotIn <= 0) continue;
      const pulse = Math.pow(0.5 + 0.5 * Math.sin(i * 0.2 - phase * 3), 3);
      ctx.fillStyle = 'rgba(' + dr + ',' + dg + ',' + db + ',' + (0.55 + 0.45 * pulse).toFixed(3) + ')';
      ctx.beginPath();
      ctx.arc(pts[i].x, pts[i].y, (2.1 + 2 * pulse) * dotIn, 0, Math.PI * 2);
      ctx.fill();
    }

    if (!still && el > 1.6) {
      const pos = ((phase * 0.2) % 1) * (pts.length - 1);
      const i = Math.floor(pos), k = pos - i, p = pts[i], q = pts[Math.min(i + 1, pts.length - 1)];
      const x = p.x + (q.x - p.x) * k, y = p.y + (q.y - p.y) * k;
      ctx.save();
      ctx.shadowBlur = 14;
      ctx.shadowColor = 'rgb(' + pr + ',' + pg + ',' + pb + ')';
      ctx.fillStyle = 'rgb(' + pr + ',' + pg + ',' + pb + ')';
      ctx.beginPath(); ctx.arc(x, y, 3.2, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = 'rgba(' + pr + ',' + pg + ',' + pb + ',.7)';
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(x, y, 8, 0, Math.PI * 2); ctx.stroke();
      ctx.restore();
    }
  }

  function frame(now) {
    raf = 0;
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    speed += (targetSpeed - speed) * Math.min(1, dt * 4);
    boost += (targetBoost - boost) * Math.min(1, dt * 3);
    phase += dt * speed;
    ripples = ripples.filter((r) => now - r.t0 < 1800);
    draw(now, false);
    if (visible) raf = requestAnimationFrame(frame);
  }

  function run() {
    if (reduce || raf || !visible) return;
    last = performance.now();
    raf = requestAnimationFrame(frame);
  }

  // pointer: a soft glow follows the cursor, a click sends a ripple
  holder.addEventListener('pointermove', (e) => {
    const r = holder.getBoundingClientRect();
    mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
  });
  holder.addEventListener('pointerleave', () => { mouse = null; });
  holder.addEventListener('click', (e) => {
    if (reduce) return;
    const r = holder.getBoundingClientRect();
    ripples.push({ x: e.clientX - r.left, y: e.clientY - r.top, t0: performance.now() });
  });

  // voice state drives the energy of the animation
  const hero = document.getElementById('hero');
  if (hero) {
    const states = { idle: [1, 0], listening: [2.6, 0.9], processing: [1.8, 0.4], success: [1.2, 0.3], error: [1.2, 0.1] };
    const apply = () => {
      const s = hero.dataset.state;
      [targetSpeed, targetBoost] = states[s] || states.idle;
      if (!reduce && (s === 'success' || s === 'error')) ripples.push({ x: W / 2, y: H / 2, t0: performance.now() });
    };
    new MutationObserver(apply).observe(hero, { attributes: true, attributeFilter: ['data-state'] });
    apply();
  }

  new MutationObserver(readColors).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  if ('ResizeObserver' in window) new ResizeObserver(resize).observe(holder);
  else window.addEventListener('resize', resize);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; if (visible) run(); }).observe(holder);
  }

  readColors();
  resize();
  run();
})();
