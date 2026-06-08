/**
 * Image or video — real or fake?
 * Detects a face swapped via a deepfake, or an image fabricated by an AI.
 * Activated when ?m=io1 is present in the URL.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(location.search);
    if ((params.get('m') || '').toLowerCase() !== 'io1') return;

    const cfg = {
      title: 'Image or video — real or fake?',
      badge: 'Fake detection',
      badgeStyle: 'background:#ede9fe;color:#5b21b6;',
      description: 'Analyzes an image or a video: a face swapped via a fake (deepfake), or an image entirely fabricated by artificial intelligence. You get a verdict, the regions that led to that conclusion, and a plain-language explanation.',
    };
    const badge = document.getElementById('m-badge');
    badge.textContent = cfg.badge;
    badge.setAttribute('style', cfg.badgeStyle + 'display:inline-block;');
    document.getElementById('m-title').textContent = cfg.title;
    document.getElementById('m-desc').textContent = cfg.description;

    ['pane-io2', 'pane-io3', 'pane-io4', 'pane-io6', 'pane-generic'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    const pane = document.getElementById('pane-io1');
    if (pane) pane.style.display = '';

    initIo1();
  });

  const API_URL = (window.VERIFY_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
  const IO1 = `${API_URL}/api/io1`;

  const ICONS = {
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 12 10 17 19 7" /></svg>',
    warn:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2L12 3.5z" /><line x1="12" y1="10" x2="12" y2="14" /><circle cx="12" cy="17" r="1" fill="currentColor" /></svg>',
    cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="9" /></svg>',
    spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 6.4L20 11l-6.4 1.6L12 19l-1.6-6.4L4 11l6.4-1.6L12 3z" /></svg>',
    video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="14" height="14" /><path d="M17 9.5l4-2.5v10l-4-2.5z" /></svg>',
    image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3.5" width="18" height="17" /><circle cx="9" cy="9.5" r="1.6" /><path d="M3 17l5-5 4 4 3-3 6 5" /></svg>',
    upload:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16v3a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3M16.5 8L12 3.5 7.5 8M12 3.5v13.5" /></svg>',
    face:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" /><path d="M8.5 14.5c1 1.2 2.2 1.8 3.5 1.8s2.5-.6 3.5-1.8" /><circle cx="9" cy="10" r="1" fill="currentColor" stroke="none" /><circle cx="15" cy="10" r="1" fill="currentColor" stroke="none" /></svg>',
    eye:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>',
    text:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="6"  x2="20" y2="6" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="18" x2="14" y2="18" /></svg>',
  };
  const svgIcon = (k, sz) => `<span class="icon ${sz || 'icon-16'} icon-stroke">${ICONS[k] || ''}</span>`;
  const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ─── Modes (3 distinct checks) ────────────────────────────────────────────
  const MODES = {
    'df-image': {
      kind: 'image', endpoint: 'image', extra: { mode: 'deepfake' },
      fieldLabel: 'Photo (with a face) to analyze',
      icon: 'face',
      title: 'Drag and drop a photo with a face',
      sub: 'We check whether the face has been swapped via a fake (deepfake).',
      formats: 'JPG · PNG · WEBP · BMP',
      accept: 'image/jpeg,image/png,image/webp,image/bmp',
      busy: 'Running deepfake detection…',
    },
    'df-video': {
      kind: 'video', endpoint: 'video', extra: {},
      fieldLabel: 'Video (with a face) to analyze',
      icon: 'video',
      title: 'Drag and drop a video with a face',
      sub: 'We locate the face in the video and check whether it has been faked.',
      formats: 'MP4 · MOV · AVI',
      accept: 'video/mp4,video/quicktime,video/avi',
      busy: 'Running deepfake detection…',
    },
    'ai-image': {
      kind: 'image', endpoint: 'image', extra: { mode: 'ai' },
      fieldLabel: 'Image to analyze',
      icon: 'spark',
      title: 'Drag and drop an image',
      sub: 'We check whether the image was entirely fabricated by artificial intelligence.',
      formats: 'JPG · PNG · WEBP · BMP',
      accept: 'image/jpeg,image/png,image/webp,image/bmp',
      busy: 'Checking for an AI-generated image…',
    },
  };
  let _mode = 'df-image';
  const M = () => MODES[_mode];

  // ─── Init ─────────────────────────────────────────────────────────────────
  function initIo1() {
    pingHealth();
    setupDropZone('drop-io1', 'file-io1');
    document.getElementById('btn-io1').addEventListener('click', analyze);
    document.querySelectorAll('[data-io1-mode]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (btn.dataset.io1Mode === _mode) return;
        document.querySelectorAll('[data-io1-mode]').forEach(b => b.classList.toggle('active', b === btn));
        _mode = btn.dataset.io1Mode;
        applyMode();
        document.getElementById('result-io1').innerHTML = '';
        document.getElementById('process-io1').innerHTML = '';
      });
    });
    document.querySelectorAll('.icon[data-icon]').forEach(el => {
      if (ICONS[el.dataset.icon] && !el.firstChild) el.innerHTML = ICONS[el.dataset.icon];
    });
    applyMode();
  }

  function applyMode() {
    const m = M();
    const input = document.getElementById('file-io1');
    if (input) { input.value = ''; input.setAttribute('accept', m.accept); }
    const lbl = document.getElementById('io1-field-label');
    if (lbl) lbl.textContent = m.fieldLabel;
    resetDropZone(document.getElementById('drop-io1'));
    setStatus('', 'Ready');
  }

  function resetDropZone(zone) {
    if (!zone) return;
    const m = M();
    zone.classList.remove('has-file');
    zone.innerHTML = `
      <div class="io2-drop-circle">${svgIcon(m.icon, 'icon-22')}</div>
      <div class="io2-drop-title">${escapeHtml(m.title)}</div>
      <div class="io2-drop-sub">${escapeHtml(m.sub)}</div>
      <div class="drop-hint">${svgIcon('upload', 'icon-12')} ${escapeHtml(m.formats || '')} <kbd>click to browse</kbd></div>`;
  }

  async function pingHealth() {
    const banner = document.getElementById('api-status-io1');
    if (!banner) return;
    try {
      const r = await fetch(`${IO1}/health`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      if (data.status !== 'ok') {
        banner.className = 'api-banner desk';
        banner.innerHTML = `${svgIcon('settings', 'icon-14')} <span>Preparing the service…</span>`;
        return;
      }
      banner.className = 'api-banner desk ok';
      banner.innerHTML = `${svgIcon('check', 'icon-14')} <span>Service available</span>`;
    } catch (e) {
      banner.className = 'api-banner desk err';
      banner.innerHTML = `${svgIcon('warn', 'icon-14')} <span>Service temporarily unavailable — try again in a moment.</span>`;
    }
  }

  // ─── Drop zone ────────────────────────────────────────────────────────────
  function setupDropZone(zoneId, inputId) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    if (!zone || !input) return;
    zone.addEventListener('click', (e) => { if (e.target.closest('[data-clear]')) return; input.click(); });
    zone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
    ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('hover'); }));
    ['dragleave', 'drop'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('hover'); }));
    zone.addEventListener('drop', (e) => {
      const f = e.dataTransfer?.files?.[0];
      if (!f) return;
      const want = M().kind;       // 'image' | 'video'
      if (f.type.startsWith(want + '/')) { input.files = e.dataTransfer.files; renderFilePreview(zone, input, f); }
    });
    input.addEventListener('change', () => { const f = input.files?.[0]; if (f) renderFilePreview(zone, input, f); });
  }

  function renderFilePreview(zone, input, file) {
    zone.classList.add('has-file');
    const sizeMb = (file.size / 1024 / 1024).toFixed(1);
    const isImg = (file.type || '').startsWith('image/');
    const thumb = isImg
      ? `<img src="${URL.createObjectURL(file)}" style="width:64px;height:64px;object-fit:cover;border:1px solid var(--line);" />`
      : `<div style="width:64px;height:64px;display:flex;align-items:center;justify-content:center;background:#0b1020;color:#fff;">${svgIcon('video', 'icon-28')}</div>`;
    zone.innerHTML = `
      <div style="display:flex; gap:18px; align-items:center;">
        ${thumb}
        <div style="flex:1;">
          <div style="font-family:'Playfair Display',serif; font-size:18px; font-weight:600;">${escapeHtml(file.name)}</div>
          <div style="font-family:ui-monospace,Menlo,monospace; font-size:11px; color:var(--ink-soft); margin-top:4px; letter-spacing:.5px;">${sizeMb} MB · ${isImg ? 'image' : 'video'}</div>
        </div>
        <button type="button" data-clear style="background:transparent; border:1px solid var(--line); color:var(--ink); cursor:pointer; font-family:'Playfair Display',serif; font-style:italic; font-size:13px; padding:8px 16px;">change</button>
      </div>`;
    setStatus('', `${isImg ? 'Image' : 'Video'} received · ready for analysis`);
    zone.querySelector('[data-clear]').addEventListener('click', (e) => {
      e.stopPropagation();
      input.value = '';
      resetDropZone(zone);
      setStatus('', 'Ready');
    });
  }

  function setStatus(state, text) {
    const el = document.getElementById('status-io1');
    if (!el) return;
    el.className = `desk-status ${state || ''}`;
    el.innerHTML = `<span class="sc-led"></span><span class="sc-text">${text || ''}</span>`;
  }

  // ─── Analyze ──────────────────────────────────────────────────────────────
  async function analyze() {
    const btn = document.getElementById('btn-io1');
    const resultEl = document.getElementById('result-io1');
    const m = M();
    const file = document.getElementById('file-io1').files?.[0];
    if (!file) {
      resultEl.innerHTML = `<div class="coh-error">Please choose ${m.kind === 'video' ? 'a video' : 'an image'}.</div>`;
      setStatus('error', 'No file');
      return;
    }
    if (!(file.type || '').startsWith(m.kind + '/')) {
      resultEl.innerHTML = `<div class="coh-error">This mode expects ${m.kind === 'video' ? 'a video' : 'an image'}. Switch tabs or pick another file.</div>`;
      setStatus('error', 'Unexpected file type');
      return;
    }
    btn.disabled = true;
    const t0 = performance.now();
    setStatus('busy', m.busy);
    resultEl.innerHTML = '';
    const ctl = startProcessIndicator(document.getElementById('process-io1'));
    try {
      const fd = new FormData();
      fd.append(m.endpoint === 'video' ? 'video' : 'image', file);
      Object.entries(m.extra || {}).forEach(([k, v]) => fd.append(k, v));
      const resp = await fetch(`${IO1}/analyze/${m.endpoint}`, { method: 'POST', body: fd });
      if (!resp.ok) {
        const t = await resp.text();
        throw new Error(`HTTP ${resp.status} — ${t.slice(0, 200)}`);
      }
      const data = await resp.json();
      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      ctl.complete(elapsed);
      setStatus('', 'Analysis complete');
      renderResult(resultEl, data);
    } catch (e) {
      ctl.fail();
      const msg = /no usable (face|frame)|no clear face|unreadable/i.test(String(e.message))
        ? (m.kind === 'video'
            ? 'Could not analyze this video (no usable face). Try a clip where the face is more visible and facing the camera.'
            : 'No usable face in this image. Try a photo where the face is more visible and facing the camera.')
        : 'Something went wrong. Try again in a moment.';
      resultEl.innerHTML = `<div class="coh-error">${msg}</div>`;
      setStatus('error', 'Analysis interrupted');
    } finally {
      btn.disabled = false;
    }
  }

  // ─── Process indicator ────────────────────────────────────────────────────
  function startProcessIndicator(mount) {
    if (!mount) return { complete: () => {}, fail: () => {} };
    const STEPS = [
      { ico: 'video',    lbl: 'Receiving the file',              dur: 300 },
      { ico: 'face',     lbl: 'Looking for a face',             dur: 900 },
      { ico: 'eye',      lbl: 'Examining the content',          dur: 1100 },
      { ico: 'spark',    lbl: 'Highlighting the decisive areas', dur: 700 },
      { ico: 'text',     lbl: 'Preparing the report',           dur: 500 },
    ];
    const totalDur = STEPS.reduce((a, s) => a + s.dur, 0);
    const checkMark = svgIcon('check', 'icon-14');
    mount.innerHTML = `
      <div class="process-card">
        <div class="process-head">
          <div class="ph-title">${svgIcon('settings', 'icon-18')} Analysis in progress</div>
          <div class="ph-status" data-process-status>0 / ${STEPS.length} steps</div>
        </div>
        <div class="process-track"><div data-process-bar></div></div>
        <div class="process-steps">
          ${STEPS.map((s, i) => `
            <div class="pstep" data-state="pending" data-idx="${i}">
              <div class="ps-icon">${svgIcon(s.ico, 'icon-14')}</div>
              <div><div class="ps-label">${escapeHtml(s.lbl)}</div></div>
              <div class="ps-time">·</div>
            </div>`).join('')}
        </div>
      </div>`;
    const stepEls = [...mount.querySelectorAll('.pstep')];
    const bar = mount.querySelector('[data-process-bar]');
    const statusTxt = mount.querySelector('[data-process-status]');
    let activeIdx = -1, cumul = 0, cancelled = false;
    const timers = [];
    function activate(i) {
      if (cancelled) return;
      if (activeIdx >= 0 && stepEls[activeIdx]) {
        stepEls[activeIdx].dataset.state = 'done';
        const t = stepEls[activeIdx].querySelector('.ps-time');
        if (t) t.innerHTML = checkMark;
      }
      activeIdx = i;
      if (i < stepEls.length) stepEls[i].dataset.state = 'active';
      const pct = i >= 0 ? ((cumul + (STEPS[i]?.dur || 0)) / totalDur) * 100 : 0;
      bar.style.width = Math.min(100, pct).toFixed(1) + '%';
      statusTxt.textContent = `${Math.min(i + 1, STEPS.length)} / ${STEPS.length} steps`;
    }
    let elapsed = 0;
    STEPS.forEach((s, i) => { timers.push(setTimeout(() => activate(i), elapsed)); elapsed += s.dur; cumul = elapsed; });
    return {
      complete(t) {
        cancelled = true; timers.forEach(clearTimeout);
        stepEls.forEach(el => { el.dataset.state = 'done'; const x = el.querySelector('.ps-time'); if (x) x.innerHTML = checkMark; });
        bar.style.width = '100%';
        statusTxt.innerHTML = `${checkMark} ${STEPS.length} / ${STEPS.length} in ${t} s`;
      },
      fail() {
        cancelled = true; timers.forEach(clearTimeout);
        if (activeIdx >= 0 && stepEls[activeIdx]) stepEls[activeIdx].dataset.state = 'pending';
        statusTxt.innerHTML = `${svgIcon('cross', 'icon-14')} interrupted`;
        statusTxt.style.color = 'var(--red)';
      },
    };
  }

  // ─── Render results ───────────────────────────────────────────────────────
  function hzTags(hz, surface) {
    if (!hz || hz.cx == null) return '';
    const cy = hz.cy, cx = hz.cx;
    const vert = cy < 0.36 ? `top ${surface}` : cy > 0.66 ? `bottom ${surface}` : `middle ${surface}`;
    const horiz = cx < 0.34 ? 'left side' : cx > 0.66 ? 'right side' : 'horizontally centered';
    const patMap = { 'centered': 'concentrated in the center', 'peripheral': 'spread toward the edges', 'off-center': 'shifted to one side', 'diffuse': 'scattered across the whole image' };
    const pat = patMap[hz.pattern] || hz.pattern || '';
    const hot = hz.pattern === 'centered' ? 'hot' : '';
    return `<div class="io1-zone-tags">
      <span class="zt">Areas: ${escapeHtml(vert)}</span>
      <span class="zt">${escapeHtml(horiz)}</span>
      ${pat ? `<span class="zt ${hot}">Pattern: ${escapeHtml(pat)}</span>` : ''}
    </div>`;
  }

  function animateCount(el, target) {
    const dur = 1100, start = performance.now();
    (function step(now) {
      const t = Math.min(1, (now - start) / dur);
      const e = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * e) + ' %';
      if (t < 1) requestAnimationFrame(step);
    })(performance.now());
  }

  function renderResult(mount, data) {
    mount.className = 'coh-results';
    // Case: AI-generated image detection is not available yet
    if (data.task === 'ai_unavailable') {
      mount.innerHTML = `
        <div class="io1-hero" data-v="real" style="--io1-bd:#6b7280;--io1-c:#374151;">
          <div>
            <div class="h-kicker">${svgIcon('settings', 'icon-14')}<span>Check not available</span></div>
            <div class="h-verdict" style="font-size:30px;">Coming soon</div>
            <div class="h-sub">${escapeHtml(data.explanation || 'Detection of AI-generated images is coming soon.')}</div>
            <div class="h-meta"><div><span class="k">In the meantime</span><span class="v">face deepfake detection is fully operational</span></div></div>
          </div>
        </div>`;
      mount.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    const isFake = String(data.verdict_class || data.verdict || '').toLowerCase() === 'fake';
    const v = isFake ? 'fake' : 'real';
    const task = data.task || 'image_deepfake';
    const isAi = task === 'image_ai_generated';
    const label = data.verdict_label || (isFake ? (isAi ? 'AI-generated image' : 'Faked face (deepfake)') : (isAi ? 'Authentic image' : 'Authentic face'));
    const confPct = data.confidence_pct != null ? data.confidence_pct : Math.round((data.confidence || 0) * 100);
    const faceDetected = !!data.face_detected;
    const xai = data.xai || {};
    const moduleAccent = (getComputedStyle(document.body).getPropertyValue('--mc') || '').trim() || '#5b21b6';
    const narrHTML = (window.VerifyXAI && data.narrative)
      ? window.VerifyXAI.narrativeCard(data.narrative, { accent: moduleAccent, verdictHint: data.verdict_class || data.verdict })
      : '';
    const hz = xai.hotzone || {};
    const isVideo = data.source === 'video';
    const surface = faceDetected ? 'of the face' : 'of the image';

    const analyseLabel = isAi ? 'AI-generated image' : (isVideo ? 'Deepfake — face (video)' : 'Deepfake — face');

    let sub;
    if (isAi) {
      sub = isFake
        ? 'The analysis finds in this image details typical of an image fabricated by artificial intelligence. The views below show the regions involved.'
        : 'The analysis found no sign of fabrication by artificial intelligence — this image appears to be a genuine photo.';
    } else {
      sub = isFake
        ? 'The analysis spots inconsistencies typical of a face manipulation. The views below show where they are located.'
        : 'The analysis found no sufficient sign of tampering — the content appears authentic.';
    }

    const R = 64, C = 2 * Math.PI * R;
    const arc = Math.max(0, Math.min(1, confPct / 100)) * C;
    const statusIco = isFake ? `<div class="status-ico inc">${ICONS.cross}</div>` : `<div class="status-ico coh">${ICONS.check}</div>`;

    // Card 01 — depends on whether a face was isolated
    let card01;
    if (xai.face_crop) {
      card01 = `
        <div class="coh-card">
          <div class="coh-card-head"><div class="coh-card-head-left"><span class="coh-card-num">01.</span><h3>The face analyzed</h3></div></div>
          <div class="coh-card-sub">The face located ${isVideo ? 'in the video' : 'in the image'}, isolated for analysis.</div>
          <div class="io1-face-wrap">
            <img src="data:image/png;base64,${xai.face_crop}" alt="Analyzed face" />
            <div class="fw-txt">This is the portion ${isVideo ? 'of the video' : 'of the image'} that was examined in detail. The verdict above concerns this face.</div>
          </div>
        </div>`;
    } else if (isAi) {
      card01 = `
        <div class="coh-card">
          <div class="coh-card-head"><div class="coh-card-head-left"><span class="coh-card-num">01.</span><h3>What was analyzed</h3></div></div>
          <div class="coh-card-sub">No face in this image: the analysis looks for traces of fabrication by artificial intelligence.</div>
          <div class="io1-noface" style="background:#eef2ff;border-color:#c7d2fe;color:#3730a3;">The whole image was examined — grain, textures, transitions, details — to distinguish a genuine photo from a computer-generated image.</div>
        </div>`;
    } else {
      card01 = `
        <div class="coh-card">
          <div class="coh-card-head"><div class="coh-card-head-left"><span class="coh-card-num">01.</span><h3>What was analyzed</h3></div></div>
          <div class="coh-card-sub">No clear face could be isolated — the analysis focused on the center of the image.</div>
          <div class="io1-noface">No clear face was found. The result should therefore be treated with caution — try again with a file where the face is more visible and facing the camera.</div>
        </div>`;
    }

    const heatSub = isAi
      ? 'The regions of the image that counted most for the decision. In warm colors (red, yellow), what weighed the most. Click an image to enlarge it.'
      : 'The regions ' + surface + ' that counted most for the decision. In warm colors (red, yellow), what weighed the most; in cool colors, what was set aside. Click an image to enlarge it.';
    const heatCap1 = xai.face_crop ? 'On the face' : 'On the image';

    mount.className = 'coh-results';
    mount.innerHTML = `
      <div class="io1-hero" data-v="${v}">
        <div>
          <div class="h-kicker">${statusIco}<span>Analysis verdict</span></div>
          <div class="h-verdict">${escapeHtml(label)}</div>
          <div class="h-sub">${sub}</div>
          <div class="h-meta">
            <div><span class="k">Confidence score</span><span class="v">${confPct}&nbsp;%</span></div>
            <div><span class="k">Analysis type</span><span class="v">${escapeHtml(analyseLabel)}</span></div>
            ${isVideo && data.frames_scanned ? `<div><span class="k">Frames examined</span><span class="v">${data.frames_scanned}${data.frames_with_face ? ` · ${data.frames_with_face} with a face` : ''}</span></div>` : ''}
          </div>
        </div>
        <div class="io1-gauge">
          <svg viewBox="0 0 160 160" aria-hidden="true">
            <circle class="g-bg" cx="80" cy="80" r="${R}" />
            <circle class="g-arc" cx="80" cy="80" r="${R}" data-arc="${arc.toFixed(1)} ${C.toFixed(1)}" />
          </svg>
          <div class="g-center"><div class="g-num" data-count="${confPct}">0 %</div><div class="g-lbl">confidence<br>score</div></div>
        </div>
      </div>

      ${narrHTML}

      ${card01}

      ${(xai.gradcam_overlay || xai.gradcam_pure) ? `
      <div class="coh-card">
        <div class="coh-card-head"><div class="coh-card-head-left"><span class="coh-card-num">02.</span><h3>Analyzed regions</h3></div></div>
        <div class="coh-card-sub">${heatSub}</div>
        <div class="io1-heat-grid">
          ${xai.gradcam_overlay ? `<div class="io1-heat"><img src="data:image/png;base64,${xai.gradcam_overlay}" alt="Analyzed regions" /><div class="cap">${heatCap1}</div></div>` : ''}
          ${xai.gradcam_pure ? `<div class="io1-heat"><img src="data:image/png;base64,${xai.gradcam_pure}" alt="Map of the decisive regions" /><div class="cap">Heatmap</div></div>` : ''}
        </div>
        ${hzTags(hz, surface)}
      </div>` : ''}

      ${(data.explanation && !narrHTML) ? `
      <div class="coh-card">
        <div class="coh-card-head"><div class="coh-card-head-left"><span class="coh-card-num">03.</span><h3>Our reading of the result</h3></div></div>
        <div class="coh-card-sub">What the analysis shows, explained simply.</div>
        <div class="io1-explain">${escapeHtml(data.explanation)}</div>
      </div>` : ''}
    `;

    requestAnimationFrame(() => {
      const a = mount.querySelector('.g-arc');
      if (a) requestAnimationFrame(() => { a.style.strokeDasharray = a.dataset.arc; });
      const num = mount.querySelector('.g-num');
      if (num) animateCount(num, +num.dataset.count);
    });
    mount.querySelectorAll('.io1-heat img').forEach(img => img.addEventListener('click', () => openLightbox(img.src, img.alt)));
    mount.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function openLightbox(src, caption) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    const box = document.createElement('div');
    box.className = 'modal-box lightbox-box';
    box.innerHTML = `
      <button type="button" class="modal-close" data-close>×</button>
      <img src="${src}" alt="${escapeHtml(caption || '')}" />
      ${caption ? `<div class="lightbox-caption">${escapeHtml(caption)}</div>` : ''}`;
    backdrop.appendChild(box);
    backdrop.addEventListener('click', e => { if (e.target === backdrop) close(); });
    box.querySelector('[data-close]').addEventListener('click', close);
    function close() { backdrop.classList.remove('open'); setTimeout(() => backdrop.remove(), 250); }
    document.body.appendChild(backdrop);
    requestAnimationFrame(() => backdrop.classList.add('open'));
    document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); } });
  }
})();
