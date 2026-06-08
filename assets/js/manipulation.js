/**
 * Visual manipulation — image & video.
 * Detects staging and emotional-persuasion techniques.
 * Activated when ?m=io2 is present in the URL.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(location.search);
    if ((params.get('m') || '').toLowerCase() !== 'io2') return;

    const cfg = {
      title: 'Visual manipulation — image & video',
      badge: 'Manipulation & persuasion',
      badgeStyle: 'background:#fef3c7;color:#78350f;',
      description: 'Detects the staging and emotional-persuasion techniques used in advertising, propaganda and viral content.',
    };

    document.getElementById('m-badge').textContent = cfg.badge;
    document.getElementById('m-badge').setAttribute('style', cfg.badgeStyle + 'display:inline-block;');
    document.getElementById('m-title').textContent = cfg.title;
    document.getElementById('m-desc').textContent = cfg.description;

    ['pane-io3', 'pane-io6', 'pane-generic'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    const pane = document.getElementById('pane-io2');
    if (pane) pane.style.display = '';

    initIo2();
  });

  const API_URL = (window.VERIFY_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
  const IO2 = `${API_URL}/api/io2`;

  // ─── SVG icons (subset) ───────────────────────────────────────────────────
  const ICONS = {
    image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3.5" width="18" height="17" /><circle cx="9" cy="9.5" r="1.6" /><path d="M3 17l5-5 4 4 3-3 6 5" /></svg>',
    video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="14" height="14" /><path d="M17 9.5l4-2.5v10l-4-2.5z" /></svg>',
    upload:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16v3a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3M16.5 8L12 3.5 7.5 8M12 3.5v13.5" /></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 12 10 17 19 7" /></svg>',
    warn:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2L12 3.5z" /><line x1="12" y1="10" x2="12" y2="14" /><circle cx="12" cy="17" r="1" fill="currentColor" /></svg>',
    cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>',
    text:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="18" x2="14" y2="18" /></svg>',
    box:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" /><line x1="4" y1="9" x2="9" y2="9" /><line x1="9" y1="4" x2="9" y2="9" /></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="9" /></svg>',
    spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 6.4L20 11l-6.4 1.6L12 19l-1.6-6.4L4 11l6.4-1.6L12 3z" /></svg>',
    eye:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>',
  };
  const svgIcon = (k, sz) => `<span class="icon ${sz || 'icon-16'} icon-stroke">${ICONS[k] || ''}</span>`;
  const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  // Hydrate static icons
  document.querySelectorAll('.icon[data-icon]').forEach(el => {
    if (ICONS[el.dataset.icon] && !el.firstChild) el.innerHTML = ICONS[el.dataset.icon];
  });

  // ─── Init ─────────────────────────────────────────────────────────────────
  let _mode = 'image'; // 'image' | 'video'

  function initIo2() {
    pingHealth();
    setupDropZone('drop-io2', 'file-io2');
    document.getElementById('btn-io2').addEventListener('click', analyze);
    document.querySelectorAll('[data-io2-mode]').forEach(b => {
      b.addEventListener('click', () => {
        document.querySelectorAll('[data-io2-mode]').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        _mode = b.dataset.io2Mode;
        const drop = document.getElementById('drop-io2');
        if (drop) drop.dataset.kind = _mode;
        const input = document.getElementById('file-io2');
        input.accept = _mode === 'video'
          ? 'video/mp4,video/avi,video/quicktime'
          : 'image/*';
      });
    });
  }

  async function pingHealth() {
    const banner = document.getElementById('api-status-io2');
    try {
      const r = await fetch(`${IO2}/health`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const info = data.info || {};
      if (data.status !== 'ok') {
        banner.className = 'api-banner desk';
        banner.innerHTML = `${svgIcon('settings','icon-14')} <span>Service starting up…</span>`;
        return;
      }
      banner.className = 'api-banner desk ok';
      banner.innerHTML = `${svgIcon('check','icon-14')} <span>Service available</span>`;
    } catch (e) {
      banner.className = 'api-banner desk err';
      banner.innerHTML = `${svgIcon('warn','icon-14')} <span>Service temporarily unavailable — try again in a moment.</span>`;
    }
  }

  // ─── Drop zone (sibling input pattern) ────────────────────────────────────
  function setupDropZone(zoneId, inputId) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    if (!zone || !input) return;

    zone.addEventListener('click', (e) => {
      if (e.target.closest('[data-clear]')) return;
      input.click();
    });
    zone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });
    ['dragenter', 'dragover'].forEach(ev =>
      zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('hover'); }));
    ['dragleave', 'drop'].forEach(ev =>
      zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('hover'); }));
    zone.addEventListener('drop', (e) => {
      const f = e.dataTransfer?.files?.[0];
      if (f) { input.files = e.dataTransfer.files; renderFilePreview(zone, input, f); }
    });
    input.addEventListener('change', () => {
      const f = input.files?.[0];
      if (f) renderFilePreview(zone, input, f);
    });
  }

  function renderFilePreview(zone, input, file) {
    zone.classList.add('has-file');
    const sizeMb = (file.size / 1024 / 1024).toFixed(1);
    const isImg = file.type.startsWith('image/');
    const previewSrc = isImg ? URL.createObjectURL(file) : null;
    zone.innerHTML = `
      <div style="display:flex; gap:18px; align-items:center;">
        ${previewSrc
          ? `<img src="${previewSrc}" style="width:90px; height:90px; object-fit:cover; border:1px solid var(--line);" />`
          : `<div style="width:60px; height:60px; background:var(--navy); color:#fff; display:flex; align-items:center; justify-content:center;">${svgIcon('video','icon-22')}</div>`}
        <div style="flex:1;">
          <div style="font-family:'Playfair Display',serif; font-size:18px; font-weight:600;">${escapeHtml(file.name)}</div>
          <div style="font-family:ui-monospace,Menlo,monospace; font-size:11px; color:var(--ink-soft); margin-top:4px; letter-spacing:.5px;">
            ${sizeMb} MB
          </div>
        </div>
        <button type="button" data-clear style="background:transparent; border:1px solid var(--line); color:var(--ink); cursor:pointer; font-family:'Playfair Display',serif; font-style:italic; font-size:13px; padding:8px 16px;">change</button>
      </div>`;
    setStatus('', `Received · ${sizeMb} MB · ready to analyze`);
    const clear = zone.querySelector('[data-clear]');
    clear.addEventListener('click', (e) => {
      e.stopPropagation();
      input.value = '';
      restoreDrop(zone);
      setStatus('', 'Ready');
    });
  }

  function restoreDrop(zone) {
    zone.classList.remove('has-file');
    zone.innerHTML = `
      <div class="io2-drop-circle">${svgIcon('image','icon-22')}</div>
      <div class="io2-drop-title">Drag and drop an image or a video</div>
      <div class="io2-drop-sub">JPG · PNG · WEBP · BMP · MP4 · AVI — for videos, the first frame of the video is analyzed.</div>`;
  }

  function setStatus(state, text) {
    const el = document.getElementById('status-io2');
    if (!el) return;
    el.className = `desk-status ${state || ''}`;
    el.innerHTML = `<span class="sc-led"></span><span class="sc-text">${text || ''}</span>`;
  }

  // ─── Analyze ──────────────────────────────────────────────────────────────
  async function analyze() {
    const btn = document.getElementById('btn-io2');
    const resultEl = document.getElementById('result-io2');
    const fileInput = document.getElementById('file-io2');
    const file = fileInput.files?.[0];
    if (!file) {
      resultEl.innerHTML = `<div class="coh-error">Please select an image or a video.</div>`;
      setStatus('error', 'No file selected');
      return;
    }

    btn.disabled = true;
    const t0 = performance.now();
    setStatus('busy', 'Analysis in progress…');
    resultEl.innerHTML = '';
    const isVideo = file.type.startsWith('video/') || _mode === 'video';
    const ctl = startProcessIndicator(document.getElementById('process-io2'), isVideo);

    try {
      const fd = new FormData();
      fd.append(isVideo ? 'video' : 'image', file);
      const endpoint = isVideo ? `${IO2}/analyze/video` : `${IO2}/analyze/image`;
      const resp = await fetch(endpoint, { method: 'POST', body: fd });
      if (!resp.ok) {
        const t = await resp.text();
        throw new Error(`HTTP ${resp.status} — ${t.slice(0, 300)}`);
      }
      const data = await resp.json();
      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      ctl.complete(elapsed);
      setStatus('', `Analysis completed in ${elapsed} s`);
      renderResult(resultEl, data, file);
    } catch (e) {
      ctl.fail();
      resultEl.innerHTML = `<div class="coh-error">An error occurred. Try again in a moment.</div>`;
      setStatus('error', 'Analysis interrupted');
    } finally {
      btn.disabled = false;
    }
  }

  // ─── Process indicator ────────────────────────────────────────────────────
  function startProcessIndicator(mount, isVideo) {
    if (!mount) return { complete: () => {}, fail: () => {} };
    const STEPS = isVideo
      ? [
          { ico: 'video',  lbl: 'Reading the video', detail: 'The first frame of the video is analyzed', dur: 600 },
          { ico: 'text',   lbl: 'Reading the text', detail: 'Detecting the words shown on screen', dur: 1200 },
          { ico: 'spark',  lbl: 'Analyzing content and tone', detail: 'Reading the message and its intent', dur: 800 },
          { ico: 'eye',    lbl: 'Detecting visual elements', detail: 'Identifying the elements being emphasized', dur: 1500 },
          { ico: 'box',    lbl: 'Assessing persuasion techniques', detail: 'Staging, urgency, promises', dur: 800 },
          { ico: 'settings', lbl: 'Preparing the report', detail: 'Summarizing the observations', dur: 600 },
        ]
      : [
          { ico: 'text',   lbl: 'Reading the text', detail: 'Detecting the words shown on screen', dur: 1200 },
          { ico: 'spark',  lbl: 'Analyzing content and tone', detail: 'Reading the message and its intent', dur: 800 },
          { ico: 'eye',    lbl: 'Detecting visual elements', detail: 'Identifying the elements being emphasized', dur: 1500 },
          { ico: 'box',    lbl: 'Assessing persuasion techniques', detail: 'Staging, urgency, promises', dur: 800 },
          { ico: 'settings', lbl: 'Preparing the report', detail: 'Summarizing the observations', dur: 600 },
        ];
    const totalDur = STEPS.reduce((a, s) => a + s.dur, 0);
    const checkMark = svgIcon('check', 'icon-14');

    mount.innerHTML = `
      <div class="process-card">
        <div class="process-head">
          <div class="ph-title">${svgIcon('settings','icon-18')} Analysis in progress</div>
          <div class="ph-status" data-process-status>0 / ${STEPS.length} steps</div>
        </div>
        <div class="process-track"><div data-process-bar></div></div>
        <div class="process-steps">
          ${STEPS.map((s, i) => `
            <div class="pstep" data-state="pending" data-idx="${i}">
              <div class="ps-icon">${svgIcon(s.ico, 'icon-14')}</div>
              <div>
                <div class="ps-label">${escapeHtml(s.lbl)}</div>
                <div class="ps-detail">${escapeHtml(s.detail)}</div>
              </div>
              <div class="ps-time">${(s.dur / 1000).toFixed(1)} s</div>
            </div>
          `).join('')}
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
    STEPS.forEach((s, i) => {
      timers.push(setTimeout(() => activate(i), elapsed));
      elapsed += s.dur;
      cumul = elapsed;
    });

    return {
      complete(t) {
        cancelled = true; timers.forEach(clearTimeout);
        stepEls.forEach(el => {
          el.dataset.state = 'done';
          const x = el.querySelector('.ps-time'); if (x) x.innerHTML = checkMark;
        });
        bar.style.width = '100%';
        statusTxt.innerHTML = `${checkMark} ${STEPS.length} / ${STEPS.length} in ${t} s`;
      },
      fail() {
        cancelled = true; timers.forEach(clearTimeout);
        if (activeIdx >= 0) stepEls[activeIdx].dataset.state = 'pending';
        statusTxt.innerHTML = `${svgIcon('cross','icon-14')} error`;
        statusTxt.style.color = 'var(--red)';
      },
    };
  }

  // ─── Render results ───────────────────────────────────────────────────────
  function renderResult(mount, data, file) {
    const score = +data.score_global || 0;
    const label = data.label || 'AUTHENTIC';
    const color = data.label_color || '#22C55E';
    const sm = data.scores_modules || {};
    const xai = data.xai || {};
    const moduleAccent = (getComputedStyle(document.body).getPropertyValue('--mc') || '').trim() || '#9d174d';
    const narrHTML = (window.VerifyXAI && data.narrative)
      ? window.VerifyXAI.narrativeCard(data.narrative, { accent: moduleAccent, verdictHint: data.label || data.verdict })
      : '';

    const verdictDeck = {
      'AUTHENTIC':            'No notable signs of staging or heavy-handed persuasion. The content appears authentic.',
      'SUSPECT':              'A few signals worth examining: some elements suggest staging meant to influence.',
      'MANIPULATIVE':         'Several markers converge: persuasion techniques are at work.',
      'HIGHLY MANIPULATIVE':  'This content combines several strong markers of staging and emotional persuasion.',
    }[label] || '';

    // Text tone (mapped from internal label, non-numeric)
    const toneRaw = (data.texte?.label_nlp || '').toLowerCase();
    const toneLabel = toneRaw.startsWith('manip') ? 'slanted / alarmist' : (toneRaw ? 'neutral' : '');
    const toneClass = toneRaw.startsWith('manip') ? 'manip' : 'neutre';

    // Image to display: highlighted-regions overlay if present, else preview from file
    let imgSrc = '';
    if (data.bbox_overlay_base64) {
      imgSrc = `data:image/png;base64,${data.bbox_overlay_base64}`;
    } else if (file && file.type.startsWith('image/')) {
      imgSrc = URL.createObjectURL(file);
    }

    const pctScore = Math.round(Math.max(0, Math.min(1, score)) * 100);

    mount.className = '';
    mount.innerHTML = `
      <div class="io6-grid">
        <!-- HERO : verdict + jauge -->
        <div class="col-12">
          <div class="io2-hero-grid-v2" style="--io2-bd:${color}; --io2-color:${color};">
            <div class="io2-verdict-side">
              <div class="io2-verdict-kicker">Verdict</div>
              <div class="io2-verdict-label">${escapeHtml(label)}</div>
              <div class="io2-verdict-deck">${escapeHtml(verdictDeck)}</div>
            </div>
            <div class="io2-hero-gauge-side">
              ${buildIo2Gauge(score, color)}
            </div>
          </div>
        </div>

        ${narrHTML ? `<div class="col-12">${narrHTML}</div>` : ''}

        <!-- Image with highlighted regions -->
        <div class="col-7">
          <div class="io2-image-card">
            <div class="io2-image-head">Elements detected in the image</div>
            ${imgSrc
              ? `<img src="${imgSrc}" alt="Analyzed image" />`
              : `<div class="io2-image-empty">No preview available</div>`}
            <div class="io2-bbox-legend"><span class="io2-bbox-pill">Highlighted regions</span></div>
          </div>
        </div>

        <!-- Text present in the image -->
        <div class="col-5">
          <div class="io2-text-card">
            <div class="ed-section-head" style="border:0; padding:0; margin:0 0 8px;">
              <span class="ed-section-num">02.</span>
              <span class="ed-section-title">Text present in the image</span>
            </div>
            <div class="io2-text-extract">“ ${escapeHtml(data.texte?.extrait || 'No text detected')} ”</div>
            <div class="io2-text-meta">
              ${data.texte?.traduit_en && data.texte.traduit_en !== data.texte.extrait ? `
              <div>
                <span class="k">Translation</span>
                <span class="v">${escapeHtml(data.texte.traduit_en)}</span>
              </div>` : ''}
              ${toneLabel ? `
              <div>
                <span class="k">Text tone</span>
                <span class="v ${toneClass}">${escapeHtml(toneLabel)}</span>
              </div>` : ''}
            </div>
          </div>
        </div>

        <!-- Analyzed regions -->
        <div class="col-12">
          <div class="ed-card" style="padding:18px 22px;">
            <div class="ed-section-head" style="margin-bottom:14px;">
              <span class="ed-section-num">03.</span>
              <span class="ed-section-title">Analyzed regions</span>
            </div>
            <div style="font-size:13px; color:var(--ink-soft); margin-bottom:14px;">
              The regions of the image that the analysis weighed most heavily.
            </div>
            <div class="io2-xai-strip">
              ${xaiCard('viridis', '', 'Analyzed regions', '', xai.gradient_saliency,
                'The brighter regions are the ones that weighed most heavily in the analysis.')}
            </div>
          </div>
        </div>
      </div>
    `;

    // Animate bars + gauge arc + count-up after layout
    requestAnimationFrame(() => {
      mount.querySelectorAll('[data-target-w]').forEach(el => {
        el.style.width = el.dataset.targetW + '%';
      });
      const arc = mount.querySelector('.io2-gauge .g-arc');
      if (arc) {
        arc.style.strokeDasharray = `${arc.dataset.arclen} ${arc.dataset.circ}`;
      }
      const num = mount.querySelector('.io2-gauge .g-num');
      if (num) animateNumber(num, 0, +num.dataset.count, 1300);
    });

    // Lightbox on image click
    mount.querySelectorAll('.io2-xai-card img').forEach(img => {
      img.addEventListener('click', () => openLightbox(img.src, img.alt));
    });

    mount.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function animateNumber(el, from, to, duration) {
    const start = performance.now();
    function step(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(from + (to - from) * eased) + ' %';
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // ─── New XAI builders ─────────────────────────────────────────────────────

  // Sub-verdict per module from a 0..1 score (4-band thresholds from readme)
  function subVerdictForScore(score) {
    if (score < 0.4)  return { cls: 'auth',  label: 'Authentic' };
    if (score < 0.6)  return { cls: 'susp',  label: 'Suspect' };
    if (score < 0.8)  return { cls: 'manip', label: 'Manipulative' };
    return                   { cls: 'tres',  label: 'Highly manip.' };
  }

  // Build SVG circular gauge for the io2 hero
  function buildIo2Gauge(score, color) {
    const R = 70, CIRC = 2 * Math.PI * R;
    const v = Math.max(0, Math.min(1, score));
    const arcLen = v * CIRC;
    const pct = Math.round(v * 100);
    return `
      <div class="io2-gauge">
        <svg viewBox="0 0 170 170" aria-hidden="true">
          <circle class="g-bg" cx="85" cy="85" r="${R}" />
          <circle class="g-arc" cx="85" cy="85" r="${R}"
                  data-arclen="${arcLen.toFixed(1)}"
                  data-circ="${CIRC.toFixed(1)}"
                  style="stroke:${color}" />
        </svg>
        <div class="g-center">
          <div class="g-num" data-count="${pct}">0</div>
          <div class="g-lbl">Manipulation level</div>
        </div>
      </div>`;
  }

  // XAI Suite banner
  function buildXaiBanner(data) {
    const sm = data.scores_modules || {};
    const bboxes = (data.bounding_boxes || []).length;
    return `
      <div class="io2-xai-banner">
        <div>
          <div class="xs-kicker">Explainable AI · 4 complementary methods</div>
          <h3>Understanding the decision: LIME, SHAP, counterfactual and per-module.</h3>
        </div>
        <div class="xs-meta">
          <strong>${Object.keys(sm).length}</strong> modules<br>
          <strong>${bboxes}</strong> bounding boxes<br>
          <strong>3</strong> ViT heatmaps
        </div>
      </div>`;
  }

  // LIME-style word salience on the extracted text (NLP)
  const LIME_PATTERNS = [
    { re: /\b(MIRACLE|MIRACLE|MIRACULEU|MAGIQUE|MAGICAL|WONDER)\w*/gi, w: 4, lbl: 'Magical wording' },
    { re: /\b\d+\s*%/gi, w: 3, lbl: 'Percentage' },
    { re: /\b\d+\s*(JOUR|HOUR|HEURE|JOURS|DAY|MIN|MINUTE|SECONDE|HEURES|MOIS|WEEK|SEMAINE)S?/gi, w: 3, lbl: 'Time-bound promise' },
    { re: /\b(GRATUIT|FREE|GAGNEZ|WIN|MAINTENANT|NOW|URGENT|EXPIRE|LIMITED)\b/gi, w: 3, lbl: 'Urgency/incentive' },
    { re: /\b(ABONNEZ|SUBSCRIBE|CLIQUEZ|CLICK|TÉLÉCHARGEZ|DOWNLOAD)\b/gi, w: 3, lbl: 'Call-to-action' },
    { re: /\b\d+\s*X\b|\b(DOUBLE|TRIPLE|QUADRUPLE)/gi, w: 3, lbl: 'Multiplier' },
    { re: /\b(MEILLEUR|BEST|N°1|NUMBER\s*ONE|TOP)\b/gi, w: 3, lbl: 'Superlative' },
    { re: /-\s*\d+\s*%/gi, w: 4, lbl: 'Aggressive discount' },
    { re: /[!]{2,}|\?{2,}/g, w: 2, lbl: 'Excessive punctuation' },
    { re: /\b(NATURNA|NATURAL|NATUREL|BIO|ORGANIC)\b/gi, w: 1, lbl: 'Natural claim' },
  ];

  function buildLimeNlpCard(texte) {
    const text = texte.extrait || '';
    if (!text) {
      return `
        <div class="ed-card">
          <div class="ed-section-head"><span class="ed-section-num">03.</span><span class="ed-section-title">LIME · word salience</span></div>
          <div class="empty-note">No text extracted by TrOCR.</div>
        </div>`;
    }
    // Highlight tokens
    const matches = [];
    LIME_PATTERNS.forEach(p => {
      const re = new RegExp(p.re.source, 'gi');
      let m;
      while ((m = re.exec(text)) !== null) {
        if (m[0].trim()) matches.push({ start: m.index, end: m.index + m[0].length, w: p.w, label: p.lbl });
      }
    });
    matches.sort((a, b) => a.start - b.start);
    let cursor = 0;
    const segments = [];
    matches.forEach(mm => {
      if (mm.start < cursor) return;
      if (mm.start > cursor) segments.push({ text: text.slice(cursor, mm.start), w: 0 });
      segments.push({ text: text.slice(mm.start, mm.end), w: mm.w, label: mm.label });
      cursor = mm.end;
    });
    if (cursor < text.length) segments.push({ text: text.slice(cursor), w: 0 });

    const tokensHtml = segments.map(s =>
      `<span class="io2-lime-tok" data-w="${s.w}"${s.label ? ` title="${escapeHtml(s.label)}"` : ''}>${escapeHtml(s.text)}</span>`
    ).join('');

    const triggers = [...new Set(matches.map(m => m.label))];

    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">03.</span>
          <span class="ed-section-title">LIME · word salience (extracted text)</span>
        </div>
        <div style="font-size:12px; color:var(--ink-soft); font-style:italic; margin-bottom:8px;">
          Ribeiro, Singh &amp; Guestrin · 2016 · KDD — token-level highlighting
        </div>
        <div class="io2-lime-claim">${tokensHtml}</div>
        ${triggers.length
          ? `<div style="font-size:13px; color:var(--ink-soft);"><strong style="color:var(--ink);">${matches.length}</strong> suspicious token${matches.length>1?'s':''} · rules: ${triggers.map(t => `<code style="background:#f1f5f9;padding:1px 6px;font-family:ui-monospace,Menlo,monospace;font-size:12px;">${escapeHtml(t)}</code>`).join(' · ')}</div>`
          : `<div class="empty-note">No manipulative pattern detected in this text.</div>`}
      </div>`;
  }

  // SHAP-like waterfall — module contributions to the global score
  function buildShapWaterfall(sm, score) {
    const FUSION_WEIGHTS = { nlp: 0.40, clickbait: 0.30, urgence: 0.30 };
    const modules = [
      { key: 'nlp',       mono: 'R', cls: 'roberta',  name: 'RoBERTa NLP' },
      { key: 'clickbait', mono: 'V', cls: 'vit',      name: 'ViT clickbait' },
      { key: 'urgence',   mono: 'D', cls: 'detr',     name: 'DETR urgency' },
    ];
    const max = Math.max(0.001, ...modules.map(m => (FUSION_WEIGHTS[m.key] * (sm[m.key] || 0))));
    const rows = modules.map(m => {
      const w = FUSION_WEIGHTS[m.key];
      const contrib = w * (+sm[m.key] || 0);
      const pct = (contrib / max * 50).toFixed(1);
      // We treat all contributions as positive (push toward "MANIPULATEUR")
      return `
        <div class="io2-shap-row">
          <div class="io2-mod-mono ${m.cls}">${m.mono}</div>
          <div class="nm">${escapeHtml(m.name)}<br><span style="font-weight:400;color:var(--ink-faint);font-size:10px;">weight ${(w*100).toFixed(0)}%</span></div>
          <div class="io2-shap-bar-wrap">
            <div class="io2-shap-bar pos" data-target-w="${pct}"></div>
          </div>
          <div class="v pos">+${contrib.toFixed(3)}</div>
        </div>`;
    }).join('');

    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">04.</span>
          <span class="ed-section-title">SHAP · contribution per module</span>
        </div>
        <div style="font-size:12px; color:var(--ink-soft); font-style:italic; margin-bottom:8px;">
          Lundberg &amp; Lee · 2017 · NeurIPS — weighted decomposition
        </div>
        <div class="io2-shap-list">${rows}</div>
        <div class="io2-shap-axis">
          <span>← push authentic</span>
          <span>push manipulative →</span>
        </div>
        <div style="margin-top:14px; font-size:13px; color:var(--ink-soft);">
          ManipNet global score: <strong style="color:var(--ink);font-variant-numeric:tabular-nums;">${score.toFixed(3)}</strong>
          (weighted-sum fallback)
        </div>
      </div>`;
  }

  // Per-module verdict — individual decision per sub-model
  function buildPerModuleVerdictCard(sm) {
    const modules = [
      { key: 'nlp',       mono: 'R', cls: 'roberta',  name: 'RoBERTa' },
      { key: 'clickbait', mono: 'V', cls: 'vit',      name: 'ViT'     },
      { key: 'urgence',   mono: 'D', cls: 'detr',     name: 'DETR'    },
      { key: 'manipnet',  mono: 'M', cls: 'manipnet', name: 'ManipNet'},
    ];
    const cells = modules.map(m => {
      const v = +sm[m.key] || 0;
      const sv = subVerdictForScore(v);
      return `
        <div class="io2-pmv-cell" data-v="${sv.cls}">
          <div class="pmv-head">
            <div class="io2-mod-mono ${m.cls}" style="width:22px;height:22px;font-size:11px;">${m.mono}</div>
            ${escapeHtml(m.name)}
          </div>
          <div class="pmv-score">${v.toFixed(3)}</div>
          <div class="pmv-verdict">${escapeHtml(sv.label)}</div>
        </div>`;
    }).join('');

    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">05.</span>
          <span class="ed-section-title">Verdict per sub-model</span>
        </div>
        <div style="font-size:12px; color:var(--ink-soft); font-style:italic; margin-bottom:14px;">
          What would each sub-model say, independently of the fusion?
        </div>
        <div class="io2-pmv-grid">${cells}</div>
      </div>`;
  }

  // Counterfactual leave-one-out card
  function buildCounterfactualCard(sm, score, label) {
    const FUSION_WEIGHTS = { nlp: 0.40, clickbait: 0.30, urgence: 0.30 };
    const total = (sm.nlp || 0) * 0.40 + (sm.clickbait || 0) * 0.30 + (sm.urgence || 0) * 0.30;
    const labelOf = (s) => {
      if (s < 0.4)  return { cls: 'auth',  label: 'AUTHENTIC' };
      if (s < 0.6)  return { cls: 'susp',  label: 'SUSPECT' };
      if (s < 0.8)  return { cls: 'manip', label: 'MANIPULATIVE' };
      return { cls: 'tres',  label: 'HIGHLY MANIP.' };
    };
    const baseLabel = labelOf(total);

    const modules = [
      { key: 'nlp',       mono: 'R', cls: 'roberta',  name: 'RoBERTa NLP' },
      { key: 'clickbait', mono: 'V', cls: 'vit',      name: 'ViT clickbait' },
      { key: 'urgence',   mono: 'D', cls: 'detr',     name: 'DETR urgency' },
    ];

    const rows = modules.map(m => {
      const w = FUSION_WEIGHTS[m.key];
      const contrib = w * (+sm[m.key] || 0);
      const newScore = Math.max(0, total - contrib);
      const newLabel = labelOf(newScore);
      const flipped = newLabel.cls !== baseLabel.cls;
      return `
        <div class="io2-cf-row">
          <div class="io2-mod-mono ${m.cls}">${m.mono}</div>
          <div class="cf-text">
            Without <strong>${escapeHtml(m.name)}</strong> →
            <strong>${newScore.toFixed(3)}</strong> · ${newLabel.label}
          </div>
          <div class="cf-arrow-num">−${contrib.toFixed(3)}</div>
          <div class="cf-flip ${flipped ? 'flip' : 'stable'}">${flipped ? 'flipped' : 'stable'}</div>
        </div>`;
    }).join('');

    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">06.</span>
          <span class="ed-section-title">Counterfactual · what would it take to flip?</span>
        </div>
        <div style="font-size:12px; color:var(--ink-soft); font-style:italic; margin-bottom:14px;">
          Wachter, Mittelstadt &amp; Russell · 2018 · Harvard JOLT — leave-one-out
        </div>
        <div class="io2-cf-list">${rows}</div>
      </div>`;
  }

  function xaiCard(cls, kicker, title, citation, b64, desc) {
    const src = b64 ? `data:image/png;base64,${b64}` : '';
    return `
      <div class="io2-xai-card ${cls}">
        ${kicker ? `<div class="xai-kicker">${escapeHtml(kicker)}</div>` : ''}
        <h4>${escapeHtml(title)}</h4>
        ${citation ? `<div class="xai-citation">${escapeHtml(citation)}</div>` : ''}
        ${src ? `<img src="${src}" alt="${escapeHtml(title)}" />` : '<div class="empty-note">Preview unavailable.</div>'}
        <div class="xai-desc">${escapeHtml(desc)}</div>
      </div>`;
  }

  // Simple lightbox (re-uses existing modal CSS classes)
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
    function close() {
      backdrop.classList.remove('open');
      setTimeout(() => backdrop.remove(), 250);
    }
    document.body.appendChild(backdrop);
    requestAnimationFrame(() => backdrop.classList.add('open'));
    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); }
    });
  }
})();
