/**
 * Editing & montage — photo forensic analysis.
 * Detects whether a photo has been modified and locates the affected regions.
 * Activated when ?m=io4 is present in the URL.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(location.search);
    if ((params.get('m') || '').toLowerCase() !== 'io4') return;

    const cfg = {
      title: 'Editing & montage — photo forensic analysis',
      badge: 'Photo authenticity',
      badgeStyle: 'background:#dcfce7;color:#14532d;',
      description: 'Detects whether a photo has been modified — added elements, cloning, photomontage, retouching — and locates the affected regions.',
    };

    document.getElementById('m-badge').textContent = cfg.badge;
    document.getElementById('m-badge').setAttribute('style', cfg.badgeStyle + 'display:inline-block;');
    document.getElementById('m-title').textContent = cfg.title;
    document.getElementById('m-desc').textContent = cfg.description;

    ['pane-io2', 'pane-io3', 'pane-io6', 'pane-generic'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    const pane = document.getElementById('pane-io4');
    if (pane) pane.style.display = '';

    initIo4();
  });

  const API_URL = (window.VERIFY_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
  const IO4 = `${API_URL}/api/io4`;

  const ICONS = {
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 12 10 17 19 7" /></svg>',
    warn:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2L12 3.5z" /><line x1="12" y1="10" x2="12" y2="14" /><circle cx="12" cy="17" r="1" fill="currentColor" /></svg>',
    cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="9" /></svg>',
    spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 6.4L20 11l-6.4 1.6L12 19l-1.6-6.4L4 11l6.4-1.6L12 3z" /></svg>',
    image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3.5" width="18" height="17" /><circle cx="9" cy="9.5" r="1.6" /><path d="M3 17l5-5 4 4 3-3 6 5" /></svg>',
    eye:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>',
    grid:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>',
  };
  const svgIcon = (k, sz) => `<span class="icon ${sz || 'icon-16'} icon-stroke">${ICONS[k] || ''}</span>`;
  const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  // Modification types (object keys and colors kept; only labels/monograms changed)
  const CLASS_DEFS = [
    { key: 'inpainting',  mono: 'A', cls: 'i', name: 'Added elements',       desc: 'Elements added to the image' },
    { key: 'copy_move',   mono: 'C', cls: 'c', name: 'Cloning',              desc: 'Part of the image duplicated' },
    { key: 'splicing',    mono: 'P', cls: 's', name: 'Photomontage',         desc: 'Elements from another image' },
    { key: 'enhancement', mono: 'R', cls: 'e', name: 'Aesthetic retouching', desc: 'Adjustments and enhancements' },
  ];

  // ─── Init ─────────────────────────────────────────────────────────────────
  let _lastResult = null;
  let _io4mode = 'single';  // 'single' | 'compare'

  function initIo4() {
    pingHealth();
    setupDropZone('drop-io4', 'file-io4');
    setupDropZone('drop-io4-ref', 'file-io4-ref');
    document.getElementById('btn-io4').addEventListener('click', analyze);

    // Mode toggle: single image vs compare-to-original
    document.querySelectorAll('[data-io4-mode]').forEach(btn => {
      btn.addEventListener('click', () => {
        const m = btn.dataset.io4Mode;
        if (m === _io4mode) return;
        _io4mode = m;
        document.querySelectorAll('[data-io4-mode]').forEach(b => b.classList.toggle('active', b === btn));
        const refWrap = document.getElementById('wrap-io4-ref');
        if (refWrap) refWrap.style.display = (m === 'compare') ? '' : 'none';
        const lbl1 = document.getElementById('io4-label-1');
        if (lbl1) lbl1.textContent = (m === 'compare') ? 'The photo to check (the suspect version)' : 'Photo to analyze';
        const res = document.getElementById('result-io4'); if (res) res.innerHTML = '';
        setStatus('', 'Ready');
      });
    });

    // Hydrate static icons
    document.querySelectorAll('.icon[data-icon]').forEach(el => {
      if (ICONS[el.dataset.icon] && !el.firstChild) el.innerHTML = ICONS[el.dataset.icon];
    });
  }

  async function pingHealth() {
    const banner = document.getElementById('api-status-io4');
    try {
      const r = await fetch(`${IO4}/health`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      if (data.status !== 'ok') {
        banner.className = 'api-banner desk';
        banner.innerHTML = `${svgIcon('settings','icon-14')} <span>Preparing the service…</span>`;
        return;
      }
      banner.className = 'api-banner desk ok';
      banner.innerHTML = `${svgIcon('check','icon-14')} <span>Service available</span>`;
    } catch (e) {
      banner.className = 'api-banner desk err';
      banner.innerHTML = `${svgIcon('warn','icon-14')} <span>Service temporarily unavailable — please try again in a moment.</span>`;
    }
  }

  // ─── Drop zone ────────────────────────────────────────────────────────────
  function setupDropZone(zoneId, inputId) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    if (!zone || !input) return;
    const placeholder = zone.innerHTML;  // restore this on "change"
    zone.addEventListener('click', (e) => {
      if (e.target.closest('[data-clear]')) return;
      input.click();
    });
    zone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });
    ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('hover'); }));
    ['dragleave', 'drop'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('hover'); }));
    zone.addEventListener('drop', (e) => {
      const f = e.dataTransfer?.files?.[0];
      if (f && f.type.startsWith('image/')) {
        input.files = e.dataTransfer.files;
        renderFilePreview(zone, input, f, placeholder);
      }
    });
    input.addEventListener('change', () => {
      const f = input.files?.[0];
      if (f) renderFilePreview(zone, input, f, placeholder);
    });
  }

  function renderFilePreview(zone, input, file, placeholder) {
    zone.classList.add('has-file');
    const sizeMb = (file.size / 1024 / 1024).toFixed(1);
    const url = URL.createObjectURL(file);
    zone.innerHTML = `
      <div style="display:flex; gap:18px; align-items:center;">
        <img src="${url}" style="width:80px; height:80px; object-fit:cover; border:1px solid var(--line);" />
        <div style="flex:1;">
          <div style="font-family:'Playfair Display',serif; font-size:18px; font-weight:600;">${escapeHtml(file.name)}</div>
          <div style="font-family:ui-monospace,Menlo,monospace; font-size:11px; color:var(--ink-soft); margin-top:4px; letter-spacing:.5px;">${sizeMb} Mo</div>
        </div>
        <button type="button" data-clear style="background:transparent; border:1px solid var(--line); color:var(--ink); cursor:pointer; font-family:'Playfair Display',serif; font-style:italic; font-size:13px; padding:8px 16px;">change</button>
      </div>`;
    setStatus('', `Photo received · ready for analysis`);
    zone.querySelector('[data-clear]').addEventListener('click', (e) => {
      e.stopPropagation();
      input.value = '';
      zone.classList.remove('has-file');
      zone.innerHTML = placeholder;
      setStatus('', 'Ready');
    });
  }

  function setStatus(state, text) {
    const el = document.getElementById('status-io4');
    if (!el) return;
    el.className = `desk-status ${state || ''}`;
    el.innerHTML = `<span class="sc-led"></span><span class="sc-text">${text || ''}</span>`;
  }

  // ─── Analyze ──────────────────────────────────────────────────────────────
  async function analyze() {
    const btn = document.getElementById('btn-io4');
    const resultEl = document.getElementById('result-io4');
    const file = document.getElementById('file-io4').files?.[0];
    const refFile = document.getElementById('file-io4-ref')?.files?.[0];
    const compare = (_io4mode === 'compare');
    if (!file) {
      resultEl.innerHTML = `<div class="coh-error">${compare ? 'Please select the photo to check.' : 'Please select a photo.'}</div>`;
      setStatus('error', 'No photo');
      return;
    }
    if (compare && !refFile) {
      resultEl.innerHTML = `<div class="coh-error">Compare mode needs the original photo too — drop it in box 02.</div>`;
      setStatus('error', 'Missing the original');
      return;
    }
    btn.disabled = true;
    const t0 = performance.now();
    setStatus('busy', 'Analysis in progress…');
    resultEl.innerHTML = '';
    const ctl = startProcessIndicator(document.getElementById('process-io4'), compare);
    try {
      const fd = new FormData();
      fd.append('image', file);
      let url = `${IO4}/analyze/image`;
      if (compare) { fd.append('reference', refFile); url = `${IO4}/analyze/compare`; }
      const resp = await fetch(url, { method: 'POST', body: fd });
      if (!resp.ok) {
        const t = await resp.text();
        throw new Error(`HTTP ${resp.status} — ${t.slice(0, 300)}`);
      }
      const data = await resp.json();
      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      ctl.complete(elapsed);
      setStatus('', `Analysis complete`);
      _lastResult = { data, file };
      try {
        renderResult(resultEl, data, file);
      } catch (re) {
        console.error('[io4] renderResult failed', re, data);
        resultEl.innerHTML = `<div class="coh-error">The analysis finished but the report could not be displayed.<br><small style="opacity:.7;">${escapeHtml(String(re && re.message || re))}</small></div>`;
        setStatus('error', 'Display error');
        return;
      }
    } catch (e) {
      ctl.fail();
      console.error('[io4] analyze failed', e);
      resultEl.innerHTML = `<div class="coh-error">An error occurred — please try again in a moment.<br><small style="opacity:.7;">${escapeHtml(String(e && e.message || e))}</small></div>`;
      setStatus('error', `Analysis failed`);
    } finally {
      btn.disabled = false;
    }
  }

  // ─── Process indicator ────────────────────────────────────────────────────
  function startProcessIndicator(mount, compare) {
    if (!mount) return { complete: () => {}, fail: () => {} };
    const STEPS = compare ? [
      { ico: 'image',    lbl: 'Aligning the two images',               dur: 200 },
      { ico: 'grid',     lbl: 'Computing the pixel difference',        dur: 200 },
      { ico: 'spark',    lbl: 'Measuring how much changed',            dur: 100 },
      { ico: 'spark',    lbl: 'Locating the changed region',           dur: 150 },
      { ico: 'eye',      lbl: 'Preparing the report',                  dur: 300 },
    ] : [
      { ico: 'image',    lbl: 'Preparing the photo',                  dur: 200 },
      { ico: 'grid',     lbl: 'Searching for modified regions',       dur: 200 },
      { ico: 'spark',    lbl: 'Identifying the modification type',    dur: 100 },
      { ico: 'spark',    lbl: 'Locating the regions',                 dur: 150 },
      { ico: 'eye',      lbl: 'Preparing the report',                 dur: 300 },
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
              </div>
              <div class="ps-time">·</div>
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
      elapsed += s.dur; cumul = elapsed;
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
        statusTxt.innerHTML = `${svgIcon('cross','icon-14')} interrupted`;
        statusTxt.style.color = 'var(--red)';
      },
    };
  }

  // ─── Render results ───────────────────────────────────────────────────────
  function renderResult(mount, data, file) {
    const probs = data.class_probabilities || {};
    const probEntries = Object.entries(probs);
    const winnerKey = probEntries.length ? probEntries.sort((a, b) => b[1] - a[1])[0][0] : null;
    const maxConf = data.max_confidence || 0;
    const maskPct = data.tamper_mask_pct || 0;

    // Verdict comes straight from the backend response.
    const rawVerdict = String(data.verdict || data.verdict_class || '').toUpperCase();
    const isFake = rawVerdict ? (rawVerdict === 'FAKE') : (maxConf >= 0.50);
    const verdict = isFake ? 'FAKE' : 'AUTHENTIC';
    const winnerDef = winnerKey ? CLASS_DEFS.find(c => c.key === winnerKey) : null;
    const typeName = winnerDef?.name || 'modification';
    const verdictLabel = data.verdict_label || (isFake ? 'Modified photo' : 'Authentic');

    const confPct = (maxConf * 100).toFixed(0);
    const confPct1 = (maxConf * 100).toFixed(1);
    const maskPct1 = maskPct.toFixed(1);

    const isCompare = (data.mode === 'compare') || (data.explanation_source === 'compare');
    const isSynthetic = !!data.is_synthetic;
    const changedPct = (typeof data.changed_pct === 'number') ? data.changed_pct : null;
    const isEla = !isCompare && !!(data.xai && data.xai.ela_overlay);
    const hasOverlays = !!(data.xai && data.xai.tamper_mask_overlay);
    let previewUrl = '';
    try { if (file) previewUrl = URL.createObjectURL(file); } catch (_) { previewUrl = ''; }
    const regionTxt = (() => {
      const r = String(data.region || '').trim().toLowerCase();
      return (!r || r === 'none' || r === 'n/a') ? '' : r;
    })();
    const cluesList = Array.isArray(data.clues) ? data.clues.map(c => String(c).trim()).filter(Boolean).slice(0, 6) : [];

    const verdictDeck = isSynthetic
      ? `This picture has the hallmarks of an AI/GAN-generated image — it was not captured by a camera. (For a dedicated AI-image analysis, use the Fake-Media module.)`
      : isCompare
        ? (isFake
            ? (regionTxt && changedPct !== null && changedPct < 25
                ? `Compared to the original, about ${changedPct}% of the pixels changed — concentrated in the ${escapeHtml(regionTxt)}. That is the signature of a local edit.`
                : `Compared to the original, ${changedPct !== null ? `about ${changedPct}% of` : 'a large share of'} the pixels differ — the change spans the whole frame (global re-processing, or a different picture).`)
            : `Pixel-for-pixel, the submitted image matches the original — nothing was edited.`)
        : (isFake
            ? `The analysis found signs of ${escapeHtml(typeName.toLowerCase())} in this photo. The visuals below show the affected regions.`
            : `The analysis did not find sufficient signs of modification — the photo appears authentic.`);

    const moduleAccent = (getComputedStyle(document.body).getPropertyValue('--mc') || '').trim() || '#b45309';
    const narrHTML = (window.VerifyXAI && data.narrative)
      ? window.VerifyXAI.narrativeCard(data.narrative, { accent: moduleAccent, verdictHint: data.verdict_label || data.verdict })
      : '';

    // Modification-type bars (4 types) — no threshold line, dominant type highlighted
    const barsHtml = CLASS_DEFS.map(c => {
      const v = +probs[c.key] || 0;
      const pct = (v * 100).toFixed(1);
      const isWinner = c.key === winnerKey && isFake;
      return `
        <div class="io4-cls-row">
          <div class="io4-cls-mono ${c.cls}">${c.mono}</div>
          <div class="io4-cls-info">
            <div class="nm">${escapeHtml(c.name)}${isWinner ? '<span class="winner">SELECTED</span>' : ''}</div>
            <div class="io4-cls-bar">
              <div class="${isWinner ? 'winner' : 'other'}" data-target-w="${pct}"></div>
            </div>
          </div>
          <div class="val ${isWinner ? 'winner' : ''}">${pct}%</div>
        </div>`;
    }).join('');

    const regionMetricLabel = isCompare ? 'Changed pixels' : 'Modified regions';
    const heroSub = isSynthetic ? 'AI-generated image' : (isCompare ? '' : typeName);
    mount.innerHTML = `
      <div class="io6-grid">
        <div class="col-12">
          <div class="io4-mast">
            <div class="io4-mast-title">${isCompare ? 'Original vs suspect — pixel comparison' : 'Editing & montage — forensic report'}</div>
            <div class="io4-mast-meta">
              <span>Verdict <strong>${escapeHtml(verdictLabel)}</strong></span>
              <span>Confidence score <strong>${confPct}%</strong></span>
              ${(isFake && !isSynthetic) ? `<span>${regionMetricLabel} <strong>${maskPct1}%</strong></span>` : ''}
            </div>
          </div>
        </div>

        <!-- Hero verdict -->
        <div class="col-12">
          <div class="io4-hero" data-v="${verdict}">
            <div>
              <div class="io4-hero-kicker">${isCompare ? 'Comparison verdict' : 'Forensic verdict'}</div>
              <div class="io4-hero-verdict">${escapeHtml(verdictLabel)}</div>
              ${(isFake && heroSub) ? `<div class="io4-hero-class">${escapeHtml(heroSub)}</div>` : ''}
              <div class="io4-hero-deck">${verdictDeck}</div>
              <div class="io4-hero-meta">
                <div><span class="k">Confidence score</span><span class="v">${confPct1}%</span></div>
                ${(isFake && !isSynthetic) ? `<div><span class="k">${regionMetricLabel}</span><span class="v">${maskPct1}%</span></div>` : ''}
              </div>
            </div>
            <div class="io4-hero-conf">
              <div class="num">${confPct}<small style="font-size:24px;">%</small></div>
              <div class="lbl">Confidence score</div>
            </div>
          </div>
        </div>

        ${narrHTML ? `<div class="col-12">${narrHTML}</div>` : ''}

        <!-- Section 02 — what changed / modification type -->
        ${isSynthetic ? `
        <div class="col-12">
          <div class="ed-card">
            <div class="ed-section-head">
              <span class="ed-section-num">02.</span>
              <span class="ed-section-title">Why this isn't an "edited photo"</span>
            </div>
            <p style="font-size:14px; line-height:1.75; color:var(--ink-soft); margin:0;">This image was produced by an AI image generator (a GAN face such as "thispersondoesnotexist", or a text-to-image model), so it is not a real photograph that has been <em>locally</em> edited — there is no "editing type" to attribute. For a dedicated AI-image analysis, run it through the <strong>Fake-Media</strong> module.</p>
          </div>
        </div>` : isCompare ? `
        <div class="col-12">
          <div class="ed-card">
            <div class="ed-section-head">
              <span class="ed-section-num">02.</span>
              <span class="ed-section-title">What changed vs the original</span>
            </div>
            <div style="display:flex; gap:34px; flex-wrap:wrap; align-items:flex-end; margin-bottom:10px;">
              <div>
                <div style="font-family:'Playfair Display',serif; font-size:40px; font-weight:700; color:${isFake ? 'var(--red)' : '#16a34a'}; line-height:1;">${changedPct !== null ? changedPct : '—'}<small style="font-size:20px;">%</small></div>
                <div style="font-size:10.5px; text-transform:uppercase; letter-spacing:1.4px; color:var(--ink-faint); margin-top:6px;">of pixels differ</div>
              </div>
              ${regionTxt ? `<div>
                <div style="font-family:'Playfair Display',serif; font-size:24px; font-weight:600; line-height:1;">${escapeHtml(regionTxt)}</div>
                <div style="font-size:10.5px; text-transform:uppercase; letter-spacing:1.4px; color:var(--ink-faint); margin-top:8px;">where the change is</div>
              </div>` : ''}
            </div>
            <div style="font-size:13.5px; color:var(--ink-soft); line-height:1.7;">${verdictDeck}</div>
          </div>
        </div>` : `
        <div class="col-12">
          <div class="ed-card">
            <div class="ed-section-head">
              <span class="ed-section-num">02.</span>
              <span class="ed-section-title">Most likely modification type</span>
            </div>
            <div style="font-size:12px; color:var(--ink-soft); font-style:italic; margin-bottom:14px;">
              ${isFake ? 'The selected type is highlighted.' : 'No type stands out clearly — a sign of an authentic photo.'}
            </div>
            <div class="io4-cls-grid">${barsHtml}</div>
          </div>
        </div>`}

        <!-- Our reading (fallback if no AI-written "Reading the result") -->
        ${(!narrHTML && !isCompare && !isSynthetic) ? `
        <div class="col-12">
          <div class="io4-logic-card">
            ${isFake
              ? `The analysis found signs of <em>${escapeHtml(typeName.toLowerCase())}</em> concentrated over <mark class="bad">${maskPct1}%</mark> of the image. The photo has likely been modified.`
              : `The analysis did not find sufficient signs of modification — the photo appears authentic. No editing type stands out, which is expected for an original photo.`}
            <span class="lc-byline">Our reading</span>
          </div>
        </div>` : ''}

        <!-- Section 03 — visual evidence -->
        <div class="col-12">
          <div class="ed-card" style="padding:18px 22px;">
            <div class="ed-section-head" style="margin-bottom:14px;">
              <span class="ed-section-num">03.</span>
              <span class="ed-section-title">What the analysis shows</span>
            </div>
            ${hasOverlays ? `
            <div class="io4-overlays">
              <div class="io4-overlay-card mask">
                <div class="head">${isCompare ? 'Changed pixels (highlighted)' : (isEla ? 'Error-Level Analysis (ELA)' : `Modified regions detected${isFake ? ` — ${maskPct1}%` : ''}`)}</div>
                <img src="data:image/png;base64,${data.xai.tamper_mask_overlay}" alt="${isCompare ? 'Changed pixels' : (isEla ? 'Error-Level Analysis' : 'Modified regions detected')}" />
                <div class="caption">${isCompare
                  ? (isFake ? `Every pixel that differs from the original is tinted magenta${regionTxt ? `, clustering in the <strong>${escapeHtml(regionTxt)}</strong>` : ''}.` : 'Nothing is tinted — the two images are identical.')
                  : (isEla
                      ? (isFake
                          ? 'Bright/warm areas were compressed differently from the rest — a typical trace of a pasted or re-saved patch.'
                          : 'Edges and detailed areas always light up in ELA. What flags tampering is an <em>isolated</em> bright patch — none stands out here.')
                      : 'The regions the analysis identifies as edited.')}</div>
              </div>
              <div class="io4-overlay-card cam">
                <div class="head">${isCompare ? 'Difference map' : (isEla ? 'ELA — amplified error map' : 'Analyzed regions')}</div>
                ${data.xai?.gradcam_overlay
                  ? `<img src="data:image/png;base64,${data.xai.gradcam_overlay}" alt="${isCompare ? 'Difference map' : (isEla ? 'Amplified error map' : 'Analyzed regions')}" />`
                  : '<div style="padding:60px; text-align:center; color:#475569;">Visual unavailable</div>'}
                <div class="caption">${isCompare
                  ? 'Brighter = bigger pixel difference between the two images. An all-black map means they are pixel-for-pixel identical.'
                  : (isEla
                      ? 'The raw error signal, contrast-stretched. Edges and texture always light up a little; what matters is an isolated bright blob.'
                      : 'The regions of the photo most decisive for the verdict.')}</div>
              </div>
            </div>` : `
            <div class="io4-overlays" style="grid-template-columns:1.1fr .9fr;">
              <div class="io4-overlay-card">
                <div class="head">Submitted image${(isFake && regionTxt) ? ` — focus on the ${escapeHtml(regionTxt)}` : ''}</div>
                ${previewUrl
                  ? `<img src="${previewUrl}" alt="Submitted image" />`
                  : '<div style="padding:60px; text-align:center; color:#475569;">Preview unavailable</div>'}
                <div class="caption">${isFake
                  ? (regionTxt ? `The forensic read places the suspected edit in the <strong>${escapeHtml(regionTxt)}</strong> of the frame.` : 'The forensic read flags this image as edited — see the clues below.')
                  : 'No localized edit found — lighting, shadows and textures are consistent across the frame.'}</div>
              </div>
              <div class="io4-overlay-card" style="display:block; padding:18px 20px;">
                <div class="head" style="margin-bottom:10px;">Forensic clues</div>
                ${cluesList.length
                  ? `<ul style="margin:0; padding-left:18px; font-size:13.5px; line-height:1.7; color:var(--ink-soft);">${cluesList.map(c => `<li>${escapeHtml(c)}</li>`).join('')}</ul>`
                  : `<div style="font-size:13.5px; color:var(--ink-soft); line-height:1.7;">${isFake ? 'The model is confident the image was edited but did not isolate individual cues.' : 'Nothing stood out — no compression seams, cloned textures or lighting mismatches.'}</div>`}
              </div>
            </div>`}
          </div>
        </div>
      </div>
    `;

    // Animate bars
    requestAnimationFrame(() => {
      mount.querySelectorAll('[data-target-w]').forEach(el => {
        el.style.width = el.dataset.targetW + '%';
      });
    });

    // Lightbox on overlay images
    mount.querySelectorAll('.io4-overlay-card img').forEach(img => {
      img.addEventListener('click', () => openLightbox(img.src, img.alt));
    });

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
