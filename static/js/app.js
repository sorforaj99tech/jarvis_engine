(function () {
  'use strict';
  const cfg = JSON.parse(document.getElementById('jarvis-config').textContent);
  const V = window.JarvisVoice;
  const $ = (s) => document.querySelector(s);
  const csrf = document.querySelector('meta[name="csrf-token"]').content;

  async function api(url, method, body) {
    const opt = { method, headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' } };
    if (body) opt.body = JSON.stringify(body);
    const res = await fetch(url, opt);
    let data;
    try { data = await res.json(); } catch (e) { data = { ok: false, error: 'Unexpected server response.' }; }
    return { status: res.status, data };
  }

  /* ---- top bar: clock, system status, voice status ---- */
  const clock = $('#clock');
  const tick = () => { clock.textContent = new Date().toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' }); };
  tick(); setInterval(tick, 1000);

  const sys = $('#sys-pill');
  const setText = (id, text) => { const n = document.getElementById(id); if (n) n.textContent = text; };
  function loadStatus() {
    return api('/api/status/', 'GET').then(({ data }) => {
      const ok = data && data.status === 'online';
      sys.dataset.state = ok ? 'online' : 'offline';
      sys.querySelector('span').textContent = ok ? 'System online' : 'System offline';
      if (ok) {
        setText('kpi-today', data.commands_today);
        setText('kpi-rate', data.success_rate === null ? '\u2013' : data.success_rate + '%');
        setText('kpi-last', data.last_command || 'None yet');
      }
    }).catch(() => { sys.dataset.state = 'offline'; sys.querySelector('span').textContent = 'System offline'; });
  }
  loadStatus();

  const themeBtn = $('#theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('jarvis-theme', next); } catch (e) { /* storage unavailable */ }
  });

  const voicePill = $('#voice-pill');
  const setPill = (cls, text) => { voicePill.className = 'pill ' + cls; voicePill.querySelector('span').textContent = text; };
  if (!V.supported) setPill('unsupported', 'Voice: not supported');
  setText('kpi-voice', V.supported ? 'Ready' : 'Not supported');

  /* ---- settings page: voice picker ---- */
  const picker = $('#voice-picker');
  if (picker) {
    const hidden = $('#id_voice_name');
    const fill = () => {
      const voices = V.voices();
      picker.innerHTML = '<option value="">Automatic</option>';
      voices.forEach((v) => {
        const o = document.createElement('option');
        o.value = v.name; o.textContent = v.name + ' (' + v.lang + ')';
        if (v.name === picker.dataset.saved) o.selected = true;
        picker.appendChild(o);
      });
      const note = $('#bn-voice-note');
      if (!('speechSynthesis' in window)) note.textContent = 'This browser has no speech synthesis, so responses will be shown as text only.';
      else note.textContent = V.hasVoiceFor('bn-BD')
        ? 'A Bengali voice is installed on this device.'
        : 'No Bengali voice is installed on this device. Bengali responses will be shown as text only. Install a Bengali voice in Windows Settings > Time & language > Speech.';
    };
    picker.addEventListener('change', () => { hidden.value = picker.value; });
    fill();
    if ('speechSynthesis' in window) window.speechSynthesis.onvoiceschanged = fill;
  }

  /* ---- history page: search + status filter ---- */
  const table = $('#history-table');
  if (table) {
    const q = $('#h-search');
    let status = 'all';
    const apply = () => {
      const term = q.value.trim().toLowerCase();
      let shown = 0;
      table.querySelectorAll('tbody tr[data-status]').forEach((tr) => {
        const vis = (status === 'all' || tr.dataset.status === status) && tr.textContent.toLowerCase().includes(term);
        tr.hidden = !vis; if (vis) shown += 1;
      });
      $('#h-empty').hidden = shown !== 0 || !table.querySelector('tbody tr[data-status]');
    };
    q.addEventListener('input', apply);
    document.querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => {
      document.querySelectorAll('.chip').forEach((x) => x.classList.toggle('active', x === c));
      status = c.dataset.filter; apply();
    }));
  }

  /* ---- dashboard ---- */
  const hero = $('#hero');
  if (!hero) return;

  const el = { badge: $('#state-badge'), rec: $('#recognized'), resp: $('#response'), lang: $('#lang-select'),
    note: $('#voice-note'), body: $('#recent-body'), dialog: $('#shutdown-dialog'),
    abortBox: $('#abort-box'), abortText: $('#abort-text') };
  el.lang.value = cfg.language;
  const lang = () => el.lang.value;
  const LABELS = { idle: 'Idle', listening: 'Listening', processing: 'Processing', success: 'Success', error: 'Error' };
  let hadError = false, pendingToken = null, expiryTimer = null, countdown = null;

  const viz = $('#viz');
  for (let i = 0; i < 25; i++) { const b = document.createElement('span'); b.style.animationDelay = (i % 9) * 0.09 + 's'; viz.appendChild(b); }

  function setState(state) {
    hero.dataset.state = state;
    el.badge.dataset.state = state;
    el.badge.textContent = LABELS[state];
    if (state === 'listening') setPill('listening', 'Voice: listening');
    else if (V.supported) setPill('', 'Voice: ready');
  }
  const show = (node, text, muted) => { node.textContent = text; node.classList.toggle('muted', !!muted); };
  const notify = (text) => { el.note.textContent = text; el.note.hidden = !text; };

  if (!V.supported) $('#support-warning').hidden = false;

  function addRow(h) {
    const empty = el.body.querySelector('.empty-row');
    if (empty) empty.remove();
    const tr = document.createElement('tr');
    [h.command_text, h.result, h.created_at].forEach((t) => { const td = document.createElement('td'); td.textContent = t; tr.appendChild(td); });
    const td = document.createElement('td'); const b = document.createElement('span');
    b.className = 'badge'; b.dataset.state = h.status;
    b.textContent = h.status === 'success' ? 'Success' : h.status === 'pending' ? 'Pending' : 'Failed';
    td.appendChild(b); tr.appendChild(td);
    el.body.prepend(tr);
    while (el.body.rows.length > 6) el.body.deleteRow(-1);
    loadStatus();
  }

  function speak(text, then) {
    notify('');
    if (!cfg.voice_enabled) return then && then();
    const started = V.speak(text, lang(), cfg.voice_name, then);
    if (!started) {
      if (lang() === 'bn-BD') notify('No Bengali voice is installed on this device, so this reply is shown as text only.');
      else if (!('speechSynthesis' in window)) notify('This browser has no speech synthesis, so replies are shown as text only.');
      if (then) then();
    }
  }

  async function run(text) {
    text = text.trim();
    if (!text) return;
    show(el.rec, text); show(el.resp, 'Working on it...', true);
    setState('processing');
    try {
      const { status, data } = await api('/api/command/', 'POST', { text, language: lang() });
      const msg = data.message || data.error || 'Something went wrong.';
      const failed = status !== 200 || data.status === 'error';
      show(el.resp, msg); setState(failed ? 'error' : 'success');
      if (data.history) addRow(data.history);
      if (data.confirm_token) openShutdown(data.confirm_token, data.expires_in);
      if (status === 200) speak(msg, () => {
        if (cfg.auto_listen && !failed && !pendingToken && !V.listening) setTimeout(() => V.start(lang()), 400);
      });
    } catch (err) {
      show(el.resp, 'Could not reach the JARVIS server. Make sure runserver is still running.'); setState('error');
    }
  }

  /* ---- shutdown confirmation ---- */
  function closeDialog() {
    clearTimeout(expiryTimer); clearInterval(countdown);
    pendingToken = null;
    if (el.dialog.open) el.dialog.close();
  }
  function openShutdown(token, ttl) {
    pendingToken = token;
    let left = ttl || 60;
    $('#dialog-timer').textContent = left;
    clearInterval(countdown);
    countdown = setInterval(() => { left -= 1; $('#dialog-timer').textContent = Math.max(left, 0); }, 1000);
    expiryTimer = setTimeout(() => { closeDialog(); setState('idle'); show(el.resp, 'The shutdown request expired. Nothing was shut down.'); }, (ttl || 60) * 1000);
    if (!el.dialog.open) el.dialog.showModal();
  }
  async function cancelShutdown(message) {
    closeDialog();
    await api('/api/shutdown/cancel/', 'POST', {});
    el.abortBox.hidden = true;
    setState('idle'); show(el.resp, message);
    speak(message);
  }
  $('#cancel-shutdown').addEventListener('click', () => cancelShutdown('Shutdown cancelled.'));
  el.dialog.addEventListener('cancel', (e) => { e.preventDefault(); cancelShutdown('Shutdown cancelled.'); });
  $('#confirm-shutdown').addEventListener('click', async () => {
    const token = pendingToken;
    closeDialog();
    setState('processing');
    const { data } = await api('/api/shutdown/', 'POST', { token, confirm: true });
    const msg = data.message || data.error || 'Shutdown failed.';
    show(el.resp, msg); setState(data.ok ? 'success' : 'error');
    if (data.history) addRow(data.history);
    if (data.ok) { el.abortText.textContent = msg; el.abortBox.hidden = false; }
    speak(msg);
  });
  $('#abort-btn').addEventListener('click', () => cancelShutdown('Shutdown aborted.'));

  /* ---- voice wiring ---- */
  V.on('start', () => { hadError = false; setState('listening'); show(el.rec, 'Listening...', true); });
  V.on('interim', (t) => show(el.rec, t));
  V.on('error', (code, msg) => { hadError = true; setState('error'); show(el.resp, msg); notify(''); });
  V.on('end', (text) => {
    if (hadError) return;
    if (text) run(text); else { setState('idle'); show(el.rec, 'No speech detected.', true); }
  });

  const toggle = () => (V.listening ? V.stop() : V.start(lang()));
  $('#mic-btn').addEventListener('click', toggle);
  $('#start-btn').addEventListener('click', () => V.start(lang()));
  $('#stop-btn').addEventListener('click', () => { V.stop(); if (!V.listening) setState('idle'); });

  document.querySelectorAll('.action').forEach((b) => b.addEventListener('click', () => {
    if (b.dataset.prefill) { const i = $('#text-input'); i.value = b.dataset.prefill; i.focus(); return; }
    run(b.dataset.command);
  }));
  $('#text-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('#text-input');
    const v = input.value; input.value = '';
    run(v);
  });
  setState('idle');
})();
