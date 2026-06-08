/**
 * "Image & caption" analysis — frontend logic + page dispatcher.
 *
 * Configurable service URL: set `window.VERIFY_API_URL` before this script loads
 * (legacy `window.YOUSSEF_API_URL` is also accepted), defaults to
 * `http://localhost:8000`.
 */
(function () {
  'use strict';

  const API_URL = (window.VERIFY_API_URL || window.YOUSSEF_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
  const IO3 = `${API_URL}/api/io3`;

  // ─── SVG icon library — replaces emojis throughout ───────────────────────
  const ICONS = {
    image:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3.5" width="18" height="17" /><circle cx="9" cy="9.5" r="1.6" /><path d="M3 17l5-5 4 4 3-3 6 5" /></svg>',
    video:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="14" height="14" /><path d="M17 9.5l4-2.5v10l-4-2.5z" /></svg>',
    upload:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16v3a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3M16.5 8L12 3.5 7.5 8M12 3.5v13.5" /></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16v3a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3M7.5 12L12 16.5 16.5 12M12 3v13.5" /></svg>',
    check:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 12 10 17 19 7" /></svg>',
    warn:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2L12 3.5z" /><line x1="12" y1="10" x2="12" y2="14" /><circle cx="12" cy="17" r="1" fill="currentColor" /></svg>',
    cross:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>',
    expand:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 9 4 4 9 4" /><polyline points="20 9 20 4 15 4" /><polyline points="20 15 20 20 15 20" /><polyline points="4 15 4 20 9 20" /></svg>',
    arrow:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="12" x2="20" y2="12" /><polyline points="14 6 20 12 14 18" /></svg>',
    clock:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" /><polyline points="12 7 12 12 16 14" /></svg>',
    wave:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><line x1="3"  y1="11" x2="3"  y2="13" /><line x1="7"  y1="8"  x2="7"  y2="16" /><line x1="11" y1="5"  x2="11" y2="19" /><line x1="15" y1="8"  x2="15" y2="16" /><line x1="19" y1="10" x2="19" y2="14" /></svg>',
    grid:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>',
    box:      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" /><line x1="4" y1="9" x2="9" y2="9" /><line x1="9" y1="4" x2="9" y2="9" /></svg>',
    text:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="6"  x2="20" y2="6" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="18" x2="14" y2="18" /></svg>',
    link:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1" /><path d="M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1" /></svg>',
    spark:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 6.4L20 11l-6.4 1.6L12 19l-1.6-6.4L4 11l6.4-1.6L12 3z" /></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19 12c0 .43-.03.85-.1 1.27l2.06 1.5-2 3.46-2.42-.86c-.66.5-1.4.9-2.21 1.18L14 21h-4l-.33-2.45c-.81-.28-1.55-.68-2.21-1.18l-2.42.86-2-3.46 2.06-1.5C5.03 12.85 5 12.43 5 12s.03-.85.1-1.27L3.04 9.23l2-3.46 2.42.86c.66-.5 1.4-.9 2.21-1.18L10 3h4l.33 2.45c.81.28 1.55.68 2.21 1.18l2.42-.86 2 3.46-2.06 1.5c.07.42.1.84.1 1.27z" /></svg>',
    eye:      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>',
    chart:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 5" /><polyline points="14 5 21 5 21 12" /></svg>',
    radar:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 3 21 9 18 20 6 20 3 9" /><polygon points="12 8 16 11 14 17 10 17 8 11" /></svg>',
    branch:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="5" r="2" /><circle cx="6" cy="19" r="2" /><circle cx="18" cy="12" r="2" /><path d="M6 7v10M6 12c0-3 4-5 10-5" /></svg>',
    quote:    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 7H5a2 2 0 0 0-2 2v6h6V9H6c0-1.1.9-2 2-2V7zm10 0h-4a2 2 0 0 0-2 2v6h6V9h-3c0-1.1.9-2 2-2V7z" /></svg>',
  };

  function svgIcon(key, sizeClass) {
    return `<span class="icon ${sizeClass || 'icon-16'} icon-stroke">${ICONS[key] || ''}</span>`;
  }

  function statusIcon(verdict) {
    const map = { COHERENT: ['coh', 'check'], SUSPECT: ['sus', 'warn'], INCOHERENT: ['inc', 'cross'] };
    const [cls, ico] = map[verdict] || map.INCOHERENT;
    return `<div class="status-ico ${cls}">${ICONS[ico] || ''}</div>`;
  }

  // Hydrate any inline icon placeholders that exist in static HTML
  function hydrateStaticIcons(root = document) {
    root.querySelectorAll('.icon[data-icon]').forEach(el => {
      const key = el.dataset.icon;
      if (ICONS[key] && !el.firstChild) el.innerHTML = ICONS[key];
    });
  }

  // ─── Module configuration (one entry per ?m= value) ──────────────────────
  const MODULES = {
    io1: {
      title: 'Image or video — real or fake?',
      badge: 'Tampering detection',
      badgeStyle: 'background:#ede9fe;color:#5b21b6;',
      description: 'Analyzes an image or a video: a face swapped with a fake (deepfake), or an image entirely fabricated by artificial intelligence. You get a verdict, the areas that led to that conclusion and a plain-language explanation.',
      pane: 'io1',  // handled by synthesis.js
    },
    io2: {
      title: 'Visual manipulation — image & video',
      badge: 'Manipulation & persuasion',
      badgeStyle: 'background:#fef3c7;color:#78350f;',
      description: 'Spots the staging and emotional persuasion techniques used in advertising, propaganda and viral content.',
      pane: 'io2',  // handled by manipulation.js
    },
    io4: {
      title: 'Retouching & editing — photo forensics',
      badge: 'Photo authenticity',
      badgeStyle: 'background:#dcfce7;color:#14532d;',
      description: 'Detects whether a photo has been altered — added elements, cloning, photomontage, retouching — and locates the affected areas.',
      pane: 'io4',  // handled by forensics.js
    },
    io5: {
      title: 'Image & caption — does the caption match the image?',
      badge: 'Caption coherence & fidelity',
      badgeStyle: 'background:#dbeafe;color:#1e3a8a;',
      description: 'Compares an image or a video with the caption that accompanies it: indicates whether they really tell the same story and with what fidelity — to spot images taken out of context, misleading captions, exaggerations and omissions.',
      pane: 'io3',
    },
    io6: {
      title: 'Advertising & cosmetics — verify the claims',
      badge: 'Advertising claims',
      badgeStyle: 'background:#ffedd5;color:#9a3412;',
      description: 'Verifies whether the claims in a cosmetics advertisement are accurate or misleading, in light of the European rules on cosmetic claims.',
      pane: 'io6',  // handled by cosmetic.js
    },
  };

  // ─── DOM ready ────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(location.search);
    const m = (params.get('m') || 'io1').toLowerCase();
    const cfg = MODULES[m] || MODULES.io1;

    // Populate header
    document.getElementById('m-badge').textContent = cfg.badge;
    document.getElementById('m-badge').setAttribute('style', cfg.badgeStyle + 'display:inline-block;');
    document.getElementById('m-title').textContent = cfg.title;
    document.getElementById('m-desc').textContent = cfg.description;

    // Show the right pane (io3 here; io1/io2/io4/io6 handled by their own scripts)
    const paneId = cfg.pane === 'io3' ? 'pane-io3'
                 : cfg.pane === 'io6' ? 'pane-io6'
                 : cfg.pane === 'io2' ? 'pane-io2'
                 : cfg.pane === 'io4' ? 'pane-io4'
                 : cfg.pane === 'io1' ? 'pane-io1'
                 : 'pane-generic';
    const pane = document.getElementById(paneId);
    if (pane) pane.style.display = '';

    if (cfg.pane === 'io3') initCoherenceModule();
    // io6 is initialized by cosmetic.js (which also overrides badge/title/desc)
    hydrateStaticIcons();
  });

  // ─── io3 init ─────────────────────────────────────────────────────────────
  function initCoherenceModule() {
    pingHealth();

    // Tabs
    document.querySelectorAll('.coh-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.coh-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.coh-pane').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.querySelector(`.coh-pane[data-pane="${tab.dataset.tab}"]`).classList.add('active');
      });
    });

    setupDropZone('drop-image', 'file-image', /^image\//);
    setupDropZone('drop-video', 'file-video', /^video\//);

    document.getElementById('btn-image').addEventListener('click', () => analyze('image'));
    document.getElementById('btn-video').addEventListener('click', () => analyze('video'));

    setupCaptionUX('text-image');
    setupCaptionUX('text-video');
    setupSuggestions();
    setupClipboardPaste();
  }

  // ─── Caption character counter ────────────────────────────────────────────
  function setupCaptionUX(textareaId) {
    const ta = document.getElementById(textareaId);
    if (!ta) return;
    const counter = document.querySelector(`[data-counter-for="${textareaId}"]`);
    if (!counter) return;
    const max = parseInt(ta.getAttribute('maxlength') || '500', 10);
    const update = () => {
      const len = ta.value.length;
      counter.textContent = `${len} / ${max}`;
      counter.classList.toggle('warn', len > max * 0.85);
    };
    ta.addEventListener('input', update);
    update();
  }

  // ─── Caption suggestions: click to fill ───────────────────────────────────
  function setupSuggestions() {
    document.querySelectorAll('.caption-suggestions').forEach(group => {
      const targetId = group.dataset.target;
      const ta = document.getElementById(targetId);
      if (!ta) return;
      group.querySelectorAll('.sg-pill').forEach(btn => {
        btn.addEventListener('click', () => {
          ta.value = btn.textContent.trim();
          ta.dispatchEvent(new Event('input'));
          ta.focus();
        });
      });
    });
  }

  // ─── Paste an image from clipboard into the active drop zone ──────────────
  function setupClipboardPaste() {
    document.addEventListener('paste', (e) => {
      const activePane = document.querySelector('.coh-pane.active');
      if (!activePane) return;
      const kind = activePane.dataset.pane;
      if (kind !== 'image') return;  // video paste is uncommon, skip
      const items = e.clipboardData?.items || [];
      for (const item of items) {
        if (item.type && item.type.startsWith('image/')) {
          const file = item.getAsFile();
          if (file) {
            const input = document.getElementById('file-image');
            const dt = new DataTransfer();
            dt.items.add(file);
            input.files = dt.files;
            input.dispatchEvent(new Event('change', { bubbles: true }));
            return;
          }
        }
      }
    });
  }

  // ─── Health probe ─────────────────────────────────────────────────────────
  async function pingHealth() {
    const banner = document.getElementById('api-status');
    try {
      const r = await fetch(`${IO3}/health`, { method: 'GET' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      if (data.status !== 'ok') {
        banner.className = 'api-banner';
        banner.innerHTML = `Preparing the service…`;
        return;
      }
      banner.className = 'api-banner ok';
      banner.innerHTML = `${svgIcon('check','icon-14')} Service available`;
    } catch (e) {
      banner.className = 'api-banner err';
      banner.innerHTML = `${svgIcon('warn','icon-14')} Service temporarily unavailable — please try again in a moment.`;
    }
  }

  // ─── Drop zone helper ─────────────────────────────────────────────────────
  // The <input type="file"> lives OUTSIDE the drop zone (sibling) so that
  // rewriting the zone's innerHTML to show a preview doesn't destroy it.
  function setupDropZone(zoneId, inputId, mimeRegex) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    if (!zone || !input) return;

    zone.addEventListener('click', (e) => {
      if (e.target.closest('[data-clear]')) return;  // "Change" button
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
      if (f && mimeRegex.test(f.type)) {
        input.files = e.dataTransfer.files;
        renderFilePreview(zone, input, f);
      }
    });

    input.addEventListener('change', () => {
      const f = input.files?.[0];
      if (f) renderFilePreview(zone, input, f);
    });
  }

  function renderFilePreview(zone, input, file) {
    const isImage = file.type.startsWith('image/');
    zone.classList.add('has-file');
    const sizeMb = (file.size / 1024 / 1024).toFixed(1);
    const previewHtml = isImage
      ? `<img src="${URL.createObjectURL(file)}" class="coh-preview" style="max-height:140px;max-width:200px;" />`
      : `<div style="width:64px;height:64px;display:flex;align-items:center;justify-content:center;background:#f1f5f9;color:var(--navy);">${svgIcon('video','icon-28')}</div>`;
    zone.innerHTML = `
      <div style="display:flex;gap:14px;align-items:center;">
        ${previewHtml}
        <div>
          <div class="font-semibold">${escapeHtml(file.name)}</div>
          <div class="text-sm text-gray-500">${sizeMb} MB · ${escapeHtml(file.type)}</div>
          <button type="button" class="text-sm text-navy underline" data-clear>Change</button>
        </div>
      </div>`;
    const clear = zone.querySelector('[data-clear]');
    if (clear) clear.addEventListener('click', (e) => {
      e.stopPropagation();
      input.value = '';
      restoreDropZone(zone);
    });
  }

  function restoreDropZone(zone) {
    const kind = zone.dataset.kind;  // "image" | "video"
    const isVideo = kind === 'video';
    zone.classList.remove('has-file');
    zone.innerHTML = `
      <div class="icon-up" style="font-size:36px;color:var(--navy);">⬆</div>
      <div class="font-semibold mt-2">Drag ${isVideo ? 'a video' : 'an image'} here</div>
      <div class="text-sm text-gray-500 mt-1">or click to browse — ${isVideo ? 'MP4, MOV (max 200 MB)' : 'JPG, PNG (max 20 MB)'}</div>`;
  }

  // ─── Analyze (image or video) ─────────────────────────────────────────────
  async function analyze(kind) {
    const btn = document.getElementById(`btn-${kind}`);
    const statusEl = document.getElementById(`status-${kind}`);
    const resultEl = document.getElementById(`result-${kind}`);
    const fileInput = document.getElementById(`file-${kind}`);
    const textArea = document.getElementById(`text-${kind}`);

    const file = fileInput.files?.[0];
    const text = textArea.value.trim();

    if (!file) {
      resultEl.innerHTML = `<div class="coh-error">Please choose ${kind === 'image' ? 'an image' : 'a video'}.</div>`;
      return;
    }
    if (!text) {
      resultEl.innerHTML = `<div class="coh-error">Please enter the caption to verify.</div>`;
      return;
    }

    btn.disabled = true;
    btn.style.opacity = '0.6';
    btn.style.cursor = 'wait';
    const t0 = performance.now();
    statusEl.innerHTML = `<span class="spinner"></span> Analysis in progress…`;
    resultEl.innerHTML = '';

    // Start the animated process indicator
    const processEl = document.getElementById(`process-${kind}`);
    const processCtl = startProcessIndicator(processEl, kind);

    try {
      const fd = new FormData();
      fd.append(kind, file);
      fd.append('text', text);

      const resp = await fetch(`${IO3}/analyze/${kind}`, { method: 'POST', body: fd });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`HTTP ${resp.status} — ${txt.slice(0, 300)}`);
      }
      const data = await resp.json();
      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      processCtl.complete(elapsed);
      statusEl.innerHTML = `${svgIcon('check','icon-14')} Analysis completed in ${elapsed} s`;
      renderResult(resultEl, data, kind);
    } catch (e) {
      processCtl.fail();
      resultEl.innerHTML = `<div class="coh-error">The analysis could not be completed. Please try again in a moment.</div>`;
      statusEl.textContent = 'Analysis interrupted';
    } finally {
      btn.disabled = false;
      btn.style.opacity = '';
      btn.style.cursor = '';
    }
  }

  // ─── Process indicator (animated steps) ───────────────────────────────────
  // Steps use SVG icon keys (see ICONS object above) instead of emojis
  const STEPS_IMAGE = [
    { ico: 'upload', lbl: 'Receiving the file',            detail: 'Preparing the image',             dur: 200  },
    { ico: 'image',  lbl: 'Reading the image',             detail: 'Setting, colors, atmosphere',     dur: 1100 },
    { ico: 'box',    lbl: 'Analyzing the scene',           detail: 'Elements present in the image',    dur: 700  },
    { ico: 'text',   lbl: 'Reading the visible text',      detail: 'Text overlaid on the image',       dur: 600  },
    { ico: 'link',   lbl: 'Comparing with the caption',    detail: 'Image and caption matched up',     dur: 700  },
    { ico: 'spark',  lbl: 'Preparing the report',          detail: 'Verdict and analyzed areas',       dur: 600  },
  ];
  const STEPS_VIDEO = [
    { ico: 'upload', lbl: 'Receiving the file',            detail: 'Preparing the video',              dur: 300  },
    { ico: 'video',  lbl: 'Extracting key frames',         detail: 'A few representative frames',       dur: 1500 },
    { ico: 'wave',   lbl: 'Listening to the audio track',  detail: 'Transcribing the speech',          dur: 7000 },
    { ico: 'image',  lbl: 'Reading the frames',            detail: 'Setting, elements, visible text',   dur: 3500 },
    { ico: 'box',    lbl: 'Analyzing the scene',           detail: 'What the video really shows',       dur: 3500 },
    { ico: 'link',   lbl: 'Comparing with the caption',    detail: 'Image, audio and caption matched up', dur: 1500 },
    { ico: 'spark',  lbl: 'Preparing the report',          detail: 'Verdict and analyzed areas',       dur: 1500 },
  ];

  function startProcessIndicator(mount, kind) {
    if (!mount) return { complete: () => {}, fail: () => {} };
    const steps = kind === 'video' ? STEPS_VIDEO : STEPS_IMAGE;
    const totalDur = steps.reduce((a, s) => a + s.dur, 0);

    mount.innerHTML = `
      <div class="process-card">
        <div class="process-head">
          <div class="ph-title">${svgIcon('settings','icon-18')} Analysis in progress</div>
          <div class="ph-status" data-process-status>0 / ${steps.length} steps</div>
        </div>
        <div class="process-track"><div data-process-bar></div></div>
        <div class="process-steps">
          ${steps.map((s, i) => `
            <div class="pstep" data-state="pending" data-idx="${i}">
              <div class="ps-icon">${svgIcon(s.ico,'icon-14')}</div>
              <div>
                <div class="ps-label">${escapeHtml(s.lbl)}</div>
                <div class="ps-detail">${escapeHtml(s.detail)}</div>
              </div>
              <div class="ps-time">${(s.dur / 1000).toFixed(1)} s</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    const stepEls = [...mount.querySelectorAll('.pstep')];
    const bar = mount.querySelector('[data-process-bar]');
    const statusTxt = mount.querySelector('[data-process-status]');

    let cumul = 0;
    let activeIdx = -1;
    const timers = [];
    let cancelled = false;

    const checkMark = svgIcon('check','icon-14');
    function activate(i) {
      if (cancelled) return;
      if (activeIdx >= 0 && stepEls[activeIdx]) {
        stepEls[activeIdx].dataset.state = 'done';
        const t = stepEls[activeIdx].querySelector('.ps-time');
        if (t) t.innerHTML = checkMark;
      }
      activeIdx = i;
      if (i < stepEls.length) {
        stepEls[i].dataset.state = 'active';
      }
      const pct = i >= 0 ? ((cumul + (steps[i]?.dur || 0)) / totalDur) * 100 : 0;
      bar.style.width = Math.min(100, pct).toFixed(1) + '%';
      statusTxt.textContent = `${Math.min(i + 1, steps.length)} / ${steps.length} steps`;
    }

    // Schedule each step
    let elapsed = 0;
    steps.forEach((s, i) => {
      timers.push(setTimeout(() => activate(i), elapsed));
      elapsed += s.dur;
      cumul = elapsed;
    });

    return {
      complete(elapsedSec) {
        cancelled = true;
        timers.forEach(clearTimeout);
        stepEls.forEach((el) => {
          el.dataset.state = 'done';
          const t = el.querySelector('.ps-time');
          if (t) t.innerHTML = checkMark;
        });
        bar.style.width = '100%';
        statusTxt.innerHTML = `${checkMark} ${steps.length} / ${steps.length} in ${elapsedSec} s`;
        // Auto-collapse after 1.5s
        setTimeout(() => {
          if (mount.firstElementChild) {
            mount.firstElementChild.style.transition = 'opacity .4s ease, max-height .4s ease, padding .4s ease, margin .4s ease';
            mount.firstElementChild.style.opacity = '0.6';
          }
        }, 1500);
      },
      fail() {
        cancelled = true;
        timers.forEach(clearTimeout);
        if (activeIdx >= 0 && stepEls[activeIdx]) {
          stepEls[activeIdx].dataset.state = 'pending';
          stepEls[activeIdx].style.color = 'var(--red)';
        }
        statusTxt.innerHTML = `${svgIcon('cross','icon-14')} error`;
        statusTxt.style.color = 'var(--red)';
      },
    };
  }

  // ─── Short explanations (info popups) ────────────────────────────────
  const XAI_DOCS = {
    gradcam: {
      kicker: 'Understand',
      title: 'The analyzed areas',
      body: `
        <p>This view highlights the areas of the image that mattered most when deciding whether the caption matched — warm tones (red / yellow) for what weighed most, cool tones (blue) for what was set aside.</p>
        <ul>
          <li>If the warm areas land on what the caption describes, the verdict is based on the right element.</li>
          <li>If they land elsewhere (background, unrelated detail), treat the verdict with caution.</li>
        </ul>
        <div class="modal-tip"><strong>Tip:</strong> click the image to enlarge it.</div>
      `,
    },
  };

  // ─── Modal manager ────────────────────────────────────────────────────────
  let _activeBackdrop = null;

  function closeModal() {
    if (!_activeBackdrop) return;
    _activeBackdrop.classList.remove('open');
    setTimeout(() => {
      _activeBackdrop?.remove();
      _activeBackdrop = null;
    }, 250);
  }

  function openModal({ box, lightbox = false }) {
    closeModal();
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.appendChild(box);
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) closeModal();
    });
    document.body.appendChild(backdrop);
    _activeBackdrop = backdrop;
    requestAnimationFrame(() => backdrop.classList.add('open'));
  }

  function showInfoModal(key) {
    const doc = XAI_DOCS[key];
    if (!doc) return;
    const box = document.createElement('div');
    box.className = 'modal-box';
    box.innerHTML = `
      <button type="button" class="modal-close" aria-label="Close" data-close>×</button>
      <div class="modal-kicker">${escapeHtml(doc.kicker)}</div>
      <h2>${escapeHtml(doc.title)}</h2>
      ${doc.body}
    `;
    box.querySelector('[data-close]').addEventListener('click', closeModal);
    openModal({ box });
  }

  function showLightbox(src, caption) {
    const box = document.createElement('div');
    box.className = 'modal-box lightbox-box';
    box.innerHTML = `
      <button type="button" class="modal-close" aria-label="Close" data-close>×</button>
      <img src="${src}" alt="${escapeHtml(caption || 'XAI visualization')}" />
      ${caption ? `<div class="lightbox-caption">${escapeHtml(caption)}</div>` : ''}
    `;
    box.querySelector('[data-close]').addEventListener('click', closeModal);
    openModal({ box, lightbox: true });
  }

  // Global ESC + listeners (idempotent)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  // ─── Module metadata: monogram letter (CSS class), label, weight ──────────
  const MODULE_META_IMAGE = {
    clip:    { mono: 'C', cls: 'clip',    lbl: 'CLIP — semantics',      weight: '40%' },
    sam:     { mono: 'S', cls: 'sam',     lbl: 'SAM — segments',        weight: '25%' },
    whisper: { mono: 'W', cls: 'whisper', lbl: 'Whisper — audio',       weight: '15%' },
    yolo:    { mono: 'Y', cls: 'yolo',    lbl: 'YOLO — objects',        weight: '10%' },
    ocr:     { mono: 'O', cls: 'ocr',     lbl: 'OCR — image text',      weight: '10%' },
  };
  const MODULE_META_VIDEO = {
    text_image:  { mono: 'T', cls: 'text_image',  lbl: 'Text / Image',          weight: '40%' },
    text_audio:  { mono: 'A', cls: 'text_audio',  lbl: 'Text / Audio',          weight: '20%' },
    audio_image: { mono: 'X', cls: 'audio_image', lbl: 'Audio / Image',         weight: '10%' },
    temporal:    { mono: 'τ', cls: 'temporal',    lbl: 'Temporal coherence',    weight: '10%' },
    objects:     { mono: 'O', cls: 'objects',     lbl: 'Objects / Text',        weight: '10%' },
    ocr:         { mono: 'R', cls: 'ocr',         lbl: 'OCR / Text',            weight: '10%' },
  };

  // Helper to render a monogram from a meta entry
  function monoBadge(meta, size) {
    const sz = size === 'lg' ? 'mono-lg' : size === 'sm' ? 'mono-sm' : '';
    return `<span class="mono ${sz} ${meta.cls}">${meta.mono}</span>`;
  }

  // ─── Raw score → displayed coherence index ─────────────────────────────
  // The model's raw score is typically low (≈ 0.15–0.50): the verdict is
  // "coherent" from 0.25 (image) / 0.22 (video). As-is, "47%" looks weak
  // for a positive verdict. So we remap the scale to keep it intuitive:
  //   low threshold (SUSPECT) → 38%   ·   high threshold (COHERENT) → 62%   ·   strong score → ~98%.
  // Monotonic remapping: does not change the order, does not change the verdict (computed server-side).
  function thresholds(isVideo) {
    return isVideo ? { good: 0.22, susp: 0.12, cap: 0.50 } : { good: 0.25, susp: 0.15, cap: 0.55 };
  }
  function displayPct(rawScore, isVideo) {
    const t = thresholds(isVideo);
    const r = Math.max(0, Math.min(1, +rawScore || 0));
    let pct;
    if (r <= t.susp) {
      pct = (r / t.susp) * 38;                                   // 0 .. 38
    } else if (r <= t.good) {
      pct = 38 + ((r - t.susp) / (t.good - t.susp)) * 24;        // 38 .. 62
    } else {
      const k = Math.min(1, (r - t.good) / Math.max(1e-6, t.cap - t.good));
      pct = 62 + k * 36;                                         // 62 .. 98
    }
    return Math.max(0, Math.min(99, Math.round(pct)));
  }

  // ─── SVG gauge for the verdict score ──────────────────────────────────
  function buildGauge(score, isVideo) {
    const R = 84, CIRC = 2 * Math.PI * R;
    const pct = displayPct(score, isVideo);
    const arcLen = (pct / 100) * CIRC;
    return `
      <div class="vh-gauge">
        <svg viewBox="0 0 200 200" aria-hidden="true">
          <circle class="gauge-bg" cx="100" cy="100" r="${R}" />
          <circle class="gauge-arc" cx="100" cy="100" r="${R}"
                  data-arclen="${arcLen.toFixed(1)}"
                  data-circ="${CIRC.toFixed(1)}" />
        </svg>
        <div class="gauge-center">
          <div class="gauge-num" data-count="${pct}">0&nbsp;%</div>
          <div class="gauge-label">Coherence index</div>
        </div>
      </div>`;
  }

  // ─── Render results ───────────────────────────────────────────────────────
  function renderResult(mount, data, kind) {
    const verdict = data.verdict || 'INCOHERENT';
    const scoreGlobal = +data.score_global || 0;
    const isVideo = kind === 'video';
    const xai = data.xai || {};
    const moduleAccent = (getComputedStyle(document.body).getPropertyValue('--mc') || '').trim() || '#1e3a8a';
    const narrHTML = (window.VerifyXAI && data.narrative)
      ? window.VerifyXAI.narrativeCard(data.narrative, { accent: moduleAccent, verdictHint: data.verdict })
      : '';

    const verdictWord = { COHERENT: 'Coherent', SUSPECT: 'Needs nuance', INCOHERENT: 'Incoherent' };
    const verdictSubs = {
      COHERENT:   'The image and the caption tell the same story.',
      SUSPECT:    'The image and the caption only partly overlap — check more closely.',
      INCOHERENT: 'The image and the caption do not match. Be wary: possibly taken out of context.',
    };
    const statusKicker = {
      COHERENT:   'Match confirmed',
      SUSPECT:    'To be examined',
      INCOHERENT: 'Mismatch detected',
    };

    // What the image shows
    const objectsChips = (data.objects_detected || []).map(o => `<span class="chip chip-tag">${escapeHtml(o)}</span>`).join('')
      || '<span class="empty-note">No distinct element identified.</span>';
    const ocrChips = data.ocr_text
      ? `<div class="quote-block">${escapeHtml(data.ocr_text)}</div>`
      : '<span class="empty-note">No visible text in the image.</span>';

    // Video extras
    const audioChip = data.has_audio
      ? `<span class="chip chip-good">${svgIcon('wave','icon-12')} audio track present</span>`
      : `<span class="chip chip-mute">no audio</span>`;
    const videoExtras = isVideo ? `
      <div style="margin-top:18px;">
        <div class="kicker-tag">About the video</div>
        <div class="chips-row">
          ${data.keyframes_count ? `<span class="chip chip-num">${data.keyframes_count} key frames analyzed</span>` : ''}
          ${audioChip}
          ${data.audio_language ? `<span class="chip chip-num">language&nbsp;: ${escapeHtml(data.audio_language)}</span>` : ''}
        </div>
      </div>
      ${data.audio_transcription ? `
        <div style="margin-top:18px;">
          <div class="kicker-tag">Audio track transcription</div>
          <div class="quote-block">${escapeHtml(data.audio_transcription)}</div>
        </div>` : ''}
    ` : '';

    // ────────────────── Build HTML ──────────────────
    mount.className = 'coh-results';
    mount.innerHTML = `
      <!-- HERO -->
      <div class="verdict-hero" data-v="${verdict}">
        <div class="vh-left">
          <div class="vh-status">
            ${statusIcon(verdict)}
            <div class="vh-status-label">
              ${escapeHtml(statusKicker[verdict] || '')}
              <strong>${isVideo ? 'Video & caption' : 'Image & caption'}</strong>
            </div>
          </div>
          <div class="vh-verdict">${escapeHtml(verdictWord[verdict] || verdict)}</div>
          <div class="vh-sub">${escapeHtml(verdictSubs[verdict] || '')}</div>
          <div class="vh-meta">
            <div><span class="k">Analysis</span><span class="v">${isVideo ? 'Video & caption' : 'Image & caption'}</span></div>
            ${isVideo ? `<div><span class="k">Audio track</span><span class="v">${data.has_audio ? 'present' : 'absent'}</span></div>` : ''}
          </div>
        </div>
        ${buildGauge(scoreGlobal, isVideo)}
      </div>

      ${narrHTML}

      <!-- 01 — WHAT THE IMAGE SHOWS -->
      <div class="coh-card">
        <div class="coh-card-head">
          <div class="coh-card-head-left">
            <span class="coh-card-num">01.</span>
            <h3>What ${isVideo ? 'the video' : 'the image'} shows</h3>
          </div>
        </div>
        <div class="coh-card-sub">The elements recognized in the visual, compared with what the caption states.</div>
        <div class="coh-grid-2">
          <div>
            <div class="kicker-tag">Recognized elements</div>
            <div class="chips-row">${objectsChips}</div>
          </div>
          <div>
            <div class="kicker-tag">Text read in ${isVideo ? 'the video' : 'the image'}</div>
            ${ocrChips}
          </div>
        </div>
        ${videoExtras}
      </div>

      ${xai.gradcam_base64 ? `
        <div class="coh-card">
          <div class="coh-card-head">
            <div class="coh-card-head-left">
              <span class="coh-card-num">02.</span>
              <h3>Analyzed areas</h3>
            </div>
            <button type="button" class="info-pill" data-info="gradcam" aria-label="Learn more" title="Learn more">i</button>
          </div>
          <div class="coh-card-sub">The areas of the image that mattered most for the verdict. Warm tones for what weighed most. Click to enlarge.</div>
          <div class="xai-img-wrap" data-lightbox="gradcam">
            <img src="data:image/png;base64,${xai.gradcam_base64}" alt="Analyzed areas" />
          </div>
        </div>` : ''}

      ${narrHTML ? '' : buildExplanationCard(data, verdict, isVideo)}
    `;

    // Wire interactivity
    mount.querySelectorAll('[data-info]').forEach(btn =>
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        showInfoModal(btn.dataset.info);
      })
    );
    mount.querySelectorAll('[data-lightbox]').forEach(wrap =>
      wrap.addEventListener('click', () => {
        const img = wrap.querySelector('img');
        if (img) showLightbox(img.src, 'Analyzed areas');
      })
    );

    // Animate
    requestAnimationFrame(() => {
      mount.querySelectorAll('[data-target-w]').forEach(el => {
        el.style.width = el.dataset.targetW + '%';
      });
      const arc = mount.querySelector('.gauge-arc');
      if (arc) {
        const arclen = parseFloat(arc.dataset.arclen);
        const circ = parseFloat(arc.dataset.circ);
        arc.style.strokeDasharray = `${arclen} ${circ}`;
      }
      const counter = mount.querySelector('.gauge-num');
      if (counter) animateNumber(counter, 0, +counter.dataset.count, 1200);
    });

    mount.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function scoreRow(key, meta, value, isVideo, tGood, tSusp) {
    const v = Number.isFinite(value) ? value : 0;
    const w = Math.max(0, Math.min(1, v)) * 100;
    const cls = v >= tGood ? 'bar-good' : v >= tSusp ? 'bar-warn' : 'bar-bad';
    const thresholdMarkers = !isVideo ? `
      <span class="thresh" style="left:${(tSusp * 100).toFixed(1)}%" data-l=""></span>
      <span class="thresh" style="left:${(tGood * 100).toFixed(1)}%" data-l=""></span>
    ` : '';
    return `
      <div class="score-row">
        <div class="lbl">
          ${monoBadge(meta, 'sm')}
          <span>${escapeHtml(meta.lbl)}</span>
          <span class="lbl-weight">${meta.weight}</span>
        </div>
        <div class="score-bar">
          <div class="fill ${cls}" data-target-w="${w.toFixed(1)}"></div>
          ${thresholdMarkers}
        </div>
        <div class="val">${v.toFixed(3)}</div>
      </div>`;
  }

  function animateNumber(el, from, to, duration) {
    const start = performance.now();
    function step(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      el.innerHTML = Math.round(from + (to - from) * eased) + '&nbsp;%';
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // ─────────────── XAI CARD: per-module mini-verdicts ───────────────
  function buildPerModuleCard(data, isVideo, tGood, tSusp) {
    const meta = isVideo ? MODULE_META_VIDEO : MODULE_META_IMAGE;
    const cells = Object.entries(meta).map(([key, m]) => {
      const v = +data.scores?.[key] || 0;
      const verdict = v >= tGood ? 'COHERENT' : v >= tSusp ? 'SUSPECT' : 'INCOHERENT';
      return `
        <div class="pmv-cell" data-v="${verdict}">
          <div class="pmv-mod">${monoBadge(m, 'sm')}<span>${escapeHtml(m.lbl.split(' — ')[0])}</span></div>
          <div class="pmv-score">${v.toFixed(3)}</div>
          <div class="pmv-mini">${verdict}</div>
        </div>`;
    }).join('');
    return `
      <div class="coh-card">
        <div class="coh-card-head">
          <div class="coh-card-head-left">
            <span class="coh-card-num">06.</span>
            <h3>Verdict per isolated module</h3>
          </div>
          <button type="button" class="info-pill" data-info="permodule" aria-label="Learn more" title="Learn more">i</button>
        </div>
        <div class="coh-card-sub">If each module were asked for its decision independently, here is what it would have answered. Detects disagreements hidden by the weighting.</div>
        <div class="pmv-grid">${cells}</div>
      </div>`;
  }

  // ─────────────── XAI CARD: SVG radar chart ───────────────
  function buildRadarCard(data, isVideo, verdict) {
    const meta = isVideo ? MODULE_META_VIDEO : MODULE_META_IMAGE;
    const entries = Object.entries(meta);
    const N = entries.length;
    const cx = 200, cy = 200, R = 140;
    const angles = entries.map((_, i) => (Math.PI * 2 * i) / N - Math.PI / 2);
    const polyColor = verdict === 'COHERENT' ? '#16a34a' : verdict === 'SUSPECT' ? '#f59e0b' : '#dc2626';
    const polyFill  = verdict === 'COHERENT' ? 'rgba(22,163,74,.18)' : verdict === 'SUSPECT' ? 'rgba(245,158,11,.18)' : 'rgba(220,38,38,.18)';

    // Concentric grid (circles for each 0.25 step)
    const grid = [0.25, 0.5, 0.75, 1].map(r => {
      const points = angles.map(a => `${(cx + Math.cos(a) * R * r).toFixed(1)},${(cy + Math.sin(a) * R * r).toFixed(1)}`).join(' ');
      return `<polygon class="radar-grid-line" points="${points}" />`;
    }).join('');

    // Axes lines + labels
    const axes = entries.map(([k, m], i) => {
      const ax = (cx + Math.cos(angles[i]) * R).toFixed(1);
      const ay = (cy + Math.sin(angles[i]) * R).toFixed(1);
      const lx = (cx + Math.cos(angles[i]) * (R + 22)).toFixed(1);
      const ly = (cy + Math.sin(angles[i]) * (R + 22)).toFixed(1);
      const anchor = Math.cos(angles[i]) > 0.3 ? 'start' : Math.cos(angles[i]) < -0.3 ? 'end' : 'middle';
      const lbl = m.lbl.split(' — ')[0].slice(0, 14);
      return `
        <line class="radar-axis-line" x1="${cx}" y1="${cy}" x2="${ax}" y2="${ay}" />
        <text class="radar-axis-label" x="${lx}" y="${ly}" text-anchor="${anchor}" dy="0.35em">${escapeHtml(lbl)}</text>
      `;
    }).join('');

    // Threshold polygon (at 0.25)
    const thrR = 0.25 * R;
    const thrPts = angles.map(a => `${(cx + Math.cos(a) * thrR).toFixed(1)},${(cy + Math.sin(a) * thrR).toFixed(1)}`).join(' ');

    // Actual polygon (clamped 0..1)
    const dataPts = entries.map(([k, m], i) => {
      const v = Math.max(0, Math.min(1, +data.scores?.[k] || 0));
      return `${(cx + Math.cos(angles[i]) * R * v).toFixed(1)},${(cy + Math.sin(angles[i]) * R * v).toFixed(1)}`;
    }).join(' ');
    const dataPoints = entries.map(([k, m], i) => {
      const v = Math.max(0, Math.min(1, +data.scores?.[k] || 0));
      return `<circle class="radar-point" cx="${(cx + Math.cos(angles[i]) * R * v).toFixed(1)}" cy="${(cy + Math.sin(angles[i]) * R * v).toFixed(1)}" r="3.5" />`;
    }).join('');

    return `
      <div class="coh-card">
        <div class="coh-card-head">
          <div class="coh-card-head-left">
            <span class="coh-card-num">07.</span>
            <h3>Radar profile — 360° view</h3>
          </div>
          <button type="button" class="info-pill" data-info="radar" aria-label="Learn more" title="Learn more">i</button>
        </div>
        <div class="coh-card-sub">Each axis is a module. The wider and more regular the polygon, the more robust the verdict across all dimensions.</div>
        <div class="radar-wrap">
          <div class="radar-svg-wrap">
            <svg viewBox="0 0 400 400" style="--radar-fill:${polyFill};--radar-stroke:${polyColor};">
              ${grid}
              ${axes}
              <polygon class="radar-poly-thresh" points="${thrPts}" />
              <polygon class="radar-poly-actual" points="${dataPts}" />
              ${dataPoints}
            </svg>
          </div>
          <div class="radar-legend">
            <div class="rl-item">
              <span class="rl-swatch" style="background:${polyColor};"></span>
              <span class="rl-text"><strong>Current profile</strong><small>Actual score per module</small></span>
            </div>
            <div class="rl-item">
              <span class="rl-swatch" style="background:transparent;border:1px dashed #16a34a;"></span>
              <span class="rl-text"><strong>COHERENT threshold</strong><small>Polygon at 0.25 on all axes</small></span>
            </div>
            <div class="rl-item">
              <span class="rl-swatch" style="background:#f1f5f9;"></span>
              <span class="rl-text"><strong>Grid</strong><small>0.25 / 0.50 / 0.75 / 1.00</small></span>
            </div>
          </div>
        </div>
      </div>`;
  }

  // ─────────────── XAI CARD: counterfactual analysis ───────────────
  function buildCounterfactualCard(data, currentVerdict, tGood, tSusp) {
    const WEIGHTS = { clip: 0.40, sam: 0.25, whisper: 0.15, yolo: 0.10, ocr: 0.10 };
    const total = +data.score_global || 0;
    const verdictOf = s => s >= tGood ? 'COHERENT' : s >= tSusp ? 'SUSPECT' : 'INCOHERENT';
    const verdictBg = v => v === 'COHERENT' ? '#dcfce7;color:#166534' : v === 'SUSPECT' ? '#fef3c7;color:#92400e' : '#fee2e2;color:#991b1b';

    const rows = Object.entries(WEIGHTS).map(([key, w]) => {
      const score = +data.scores?.[key] || 0;
      const contribution = w * score;
      const newScore = total - contribution;
      const newVerdict = verdictOf(newScore);
      const flipped = newVerdict !== currentVerdict;
      const meta = MODULE_META_IMAGE[key];
      return `
        <div class="cf-row">
          <div class="cf-mod">${monoBadge(meta, 'sm')}<span>${escapeHtml(meta.lbl.split(' — ')[0])}</span></div>
          <div class="cf-arrow">contribution&nbsp;<strong>${contribution.toFixed(3)}</strong> · score would become <strong>${newScore.toFixed(3)}</strong></div>
          <div class="cf-delta neg">−${contribution.toFixed(3)}</div>
          <div style="text-align:right;">
            <span class="cf-mini-verdict" style="background:${verdictBg(newVerdict)};">${newVerdict}</span>
            ${flipped
              ? `<div class="cf-flag flipped">${svgIcon('warn','icon-12')} verdict flipped</div>`
              : `<div class="cf-flag stable">stable</div>`}
          </div>
        </div>`;
    }).join('');

    return `
      <div class="coh-card">
        <div class="coh-card-head">
          <div class="coh-card-head-left">
            <span class="coh-card-num">08.</span>
            <h3>Counterfactual — without this module?</h3>
          </div>
          <button type="button" class="info-pill" data-info="counterfactual" aria-label="Learn more" title="Learn more">i</button>
        </div>
        <div class="coh-card-sub">For each module, we remove its contribution and see whether the verdict flips. Measures the robustness of the result.</div>
        <div class="cf-list">${rows}</div>
      </div>`;
  }

  // ─────────────── Plain-language reading of the result ───────────────
  function buildExplanationCard(data, verdict, isVideo) {
    const pct = displayPct(+data.score_global || 0, isVideo);
    const visuel = isVideo ? 'the video' : 'the image';
    const objs = (data.objects_detected || []).filter(Boolean);
    const objPhrase = objs.length
      ? ` In ${visuel}, we notably recognize ${objs.slice(0, 4).map(escapeHtml).join(', ')}.`
      : '';

    let phrase;
    if (verdict === 'COHERENT') {
      phrase = `According to the analysis, <span class="verdict-mark COHERENT">${visuel} and the caption tell the same story</span>: the caption accurately describes what we see.`;
    } else if (verdict === 'SUSPECT') {
      phrase = `The analysis is <span class="verdict-mark SUSPECT">inconclusive</span>: the caption partly matches ${visuel}, but some elements do not overlap. Check more closely before sharing.`;
    } else {
      phrase = `The analysis finds a <span class="verdict-mark INCOHERENT">mismatch</span> between ${visuel} and the caption: what we see does not match what the text states. Possibly an image taken out of context.`;
    }

    return `
      <div class="coh-card">
        <div class="coh-card-head">
          <div class="coh-card-head-left">
            <span class="coh-card-num">03.</span>
            <h3>Our reading</h3>
          </div>
        </div>
        <div class="coh-card-sub">The result, explained simply.</div>
        <div class="explain-card">
          ${phrase}${objPhrase} <em style="color:var(--ink-soft);">Coherence index: ${pct}&nbsp;%.</em>
        </div>
      </div>`;
  }

  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }
})();
