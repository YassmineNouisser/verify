/**
 * Advertising & cosmetics — verifying advertising claims.
 * Front-end of the "Advertising & cosmetics" space.
 */
(function () {
  'use strict';

  // Start as soon as the DOM is ready.
  document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(location.search);
    if ((params.get('m') || '').toLowerCase() !== 'io6') return;

    const cfg = {
      title: 'Advertising & cosmetics — checking the claims',
      badge: 'Advertising claims',
      badgeStyle: 'background:#ffedd5;color:#9a3412;',
      description: 'Checks whether the claims in a cosmetics ad are accurate or misleading, against the EU rules on cosmetic claims.',
    };

    // Override module header
    document.getElementById('m-badge').textContent = cfg.badge;
    document.getElementById('m-badge').setAttribute('style', cfg.badgeStyle + 'display:inline-block;');
    document.getElementById('m-title').textContent = cfg.title;
    document.getElementById('m-desc').textContent = cfg.description;

    // Hide other panes, show io6
    ['pane-io3', 'pane-generic'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    const pane = document.getElementById('pane-io6');
    if (pane) pane.style.display = '';

    initIo6();
  });

  const API_URL = (window.VERIFY_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
  const IO6 = `${API_URL}/api/io6`;

  // ─── SVG icons ────────────────────────────────────────────────────────────
  const ICONS = {
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 12 10 17 19 7" /></svg>',
    warn:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2L12 3.5z" /><line x1="12" y1="10" x2="12" y2="14" /><circle cx="12" cy="17" r="1" fill="currentColor" /></svg>',
    cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>',
    upload:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16v3a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3M16.5 8L12 3.5 7.5 8M12 3.5v13.5" /></svg>',
    video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="14" height="14" /><path d="M17 9.5l4-2.5v10l-4-2.5z" /></svg>',
    wave:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><line x1="3" y1="11" x2="3" y2="13" /><line x1="7" y1="8" x2="7" y2="16" /><line x1="11" y1="5" x2="11" y2="19" /><line x1="15" y1="8" x2="15" y2="16" /><line x1="19" y1="10" x2="19" y2="14" /></svg>',
    box:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" /><line x1="4" y1="9" x2="9" y2="9" /><line x1="9" y1="4" x2="9" y2="9" /></svg>',
    text:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="18" x2="14" y2="18" /></svg>',
    spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 6.4L20 11l-6.4 1.6L12 19l-1.6-6.4L4 11l6.4-1.6L12 3z" /></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="9" /></svg>',
    branch:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="5" r="2" /><circle cx="6" cy="19" r="2" /><circle cx="18" cy="12" r="2" /><path d="M6 7v10M6 12c0-3 4-5 10-5" /></svg>',
  };
  const svgIcon = (k, sz) => `<span class="icon ${sz || 'icon-16'} icon-stroke">${ICONS[k] || ''}</span>`;
  const statusIcon = (v) => {
    const map = { RELIABLE: ['coh','check'], MISLEADING: ['inc','cross'] };
    const [cls, ico] = map[v] || map.MISLEADING;
    return `<div class="status-ico ${cls}">${ICONS[ico]}</div>`;
  };

  // Hydrate existing inline icon placeholders in HTML
  document.querySelectorAll('.icon[data-icon]').forEach(el => {
    const k = el.dataset.icon;
    if (ICONS[k] && !el.firstChild) el.innerHTML = ICONS[k];
  });

  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;',
    }[c]));
  }

  // ─── Init ─────────────────────────────────────────────────────────────────
  function initIo6() {
    pingHealth();
    renderShowcase();
    setupDropZone('drop-io6', 'file-io6');
    document.getElementById('btn-io6').addEventListener('click', analyze);
    restoreDossierCounter();
  }

  // ─── "Verify Index" — cosmetics campaigns already checked (examples) ──────
  const SHOWCASE = [
    {
      brand: 'Aurélys Paris', tone: 'gold', verdict: 'bad', score: 18, featured: true,
      name: 'Absolute Youth Cream',
      tagline: 'Time will just have to behave itself.',
      claim: 'Erases wrinkles in 7 days.',
      summary: 'The ad promises that wrinkles will be guaranteed to disappear in a week. But a cosmetic product acts on the surface: it can smooth the look of the skin, not erase a wrinkle. The stated timeframe is not backed by any solid study — the claim was judged misleading.',
      reasons: [
        'A cosmetic acts on the surface: it can soften the appearance of wrinkles, not "erase" them.',
        'The "7 days" timeframe is presented as a guaranteed result, with no caveat or solid study.',
        'The wording implies an almost medical effect, which is not allowed.',
      ],
      rule: 'An ad cannot attribute to a cosmetic effects it does not have. "Softens the appearance of wrinkles" would be acceptable; "erases wrinkles" is not.',
    },
    {
      brand: 'Maison Lior', tone: 'rose', verdict: 'ok', score: 92,
      name: 'Hydra-Source Serum',
      tagline: 'Hydration that lasts, from morning to night.',
      claim: 'Intensely hydrates for 24 hours.',
      reasons: [
        'The claim is measurable and time-bound: "24 hours".',
        'It is backed by a skin hydration test conducted on a panel of volunteers.',
        'No medical effect or skin "repair" is claimed.',
      ],
      rule: 'A hydration claim is acceptable if it is backed by a test and worded without exaggeration.',
    },
    {
      brand: 'Botaniq', tone: 'green', verdict: 'bad', score: 24,
      name: 'Neroli Body Balm',
      tagline: 'Nature, and nothing else.',
      claim: '100% natural.',
      reasons: [
        'The formula contains preservatives and texturing agents of synthetic origin.',
        'The "100% natural" statement is sweeping and does not reflect the actual composition.',
        'It can mislead the consumer about what they are buying.',
      ],
      rule: '"Natural" or "100% natural" claims must faithfully reflect the composition. A synthetic share, even a small one, makes the statement misleading.',
    },
    {
      brand: 'Solène', tone: 'sky', verdict: 'ok', score: 88,
      name: 'Soothing Care for Sensitive Skin',
      tagline: 'Designed for skin that reacts to everything.',
      claim: 'Fragrance-free — dermatologically tested.',
      reasons: [
        '"Fragrance-free" matches the formula: there is no fragrance in it.',
        'The "dermatologically tested" statement refers to a test that was actually carried out.',
        'No therapeutic effect is promised.',
      ],
      rule: 'A "free of …" claim is acceptable if the ingredient is genuinely absent and if the statement does not mislead about other products.',
    },
    {
      brand: 'Vélare', tone: 'plum', verdict: 'bad', score: 27,
      name: 'Repairing Hair Mask',
      tagline: 'Your hair, like new.',
      claim: 'Deeply repairs the hair fibre.',
      reasons: [
        'A hair product smooths and coats the fibre, but does not "repair" its internal structure.',
        'The word "repairs" suggests an action the product cannot have.',
        '"Deeply" reinforces an undemonstrated claim.',
      ],
      rule: 'The claimed effects must match what a cosmetic can do. "Smooths and strengthens the fibre" would be acceptable; "deeply repairs" is not.',
    },
    {
      brand: 'Pure Éclat', tone: 'amber', verdict: 'ok', score: 90,
      name: 'SPF 50+ Sun Fluid',
      tagline: 'The sun, yes. Its damage, no.',
      claim: 'Protects against UVA and UVB — factor 50+.',
      reasons: [
        'The stated protection matches the measured factor of the product.',
        'The dual UVA / UVB protection is in line with what is expected of a sunscreen.',
        'The conditions of use (generous application, reapplication) are stated.',
      ],
      rule: 'A sun protection claim must reflect the actual factor and be accompanied by usage advice. Well worded, it is compliant.',
    },
    {
      brand: 'Kelvyn Care', tone: 'rose', verdict: 'bad', score: 12,
      name: 'Anti-Cellulite Slimming Gel',
      tagline: 'Goodbye, orange-peel skin.',
      claim: 'Permanently eliminates cellulite.',
      reasons: [
        'No cosmetic gel makes cellulite disappear "permanently".',
        'The word "eliminates" goes well beyond what a product applied to the skin can do.',
        'The absence of any caveat makes the claim misleading.',
      ],
      rule: 'Claims must stay realistic. "Helps smooth the look of orange-peel skin" might pass; "permanently eliminates cellulite" is prohibited.',
    },
    {
      brand: 'Néroli & Co', tone: 'sky', verdict: 'ok', score: 86,
      name: 'Gentle Micellar Water',
      tagline: 'Makeup removal that never stings.',
      claim: 'Removes makeup gently, even around the eyes.',
      reasons: [
        'The claim simply describes how the product is used, without exaggeration.',
        'The "around the eyes" tolerance is backed by an ophthalmological test.',
        'No effect beyond makeup removal is claimed.',
      ],
      rule: 'A claim that faithfully describes the product\'s use and tolerance, backed by a test, is compliant.',
    },
  ];

  // ─── "On the global market" — real international brands ──────────────────
  // Auto-scrolling strip. Verdicts about a TYPE of advertising claim,
  // drawn from public decisions of authorities (ASA · FTC · European Commission).
  // This is not an opinion on product quality.
  const P = 'assets/img/products/';
  const MARKET = [
    // Claims judged misleading
    { brand: 'L’Oréal Paris', name: 'Telescopic Mascara', verdict: 'bad', score: 24, img: P + 'p1.jpg',
      claim: 'Up to 60% longer lashes.',
      why: 'Lash inserts / retouched visuals in mascara ads — a practice already sanctioned by the ASA.' },
    { brand: 'Olay', name: 'Regenerist', verdict: 'bad', score: 29, img: P + 'p4.jpg',
      claim: 'Regenerates the skin — visible lifting effect.',
      why: '"Regenerates / lifts" goes beyond the surface action of a cosmetic; some Olay ads have been challenged.' },
    { brand: 'Pantene Pro-V', name: 'Repair & Protect', verdict: 'bad', score: 23, img: P + 'p15.jpg',
      claim: 'Deeply repairs damaged hair.',
      why: 'A product coats and smooths the fibre; it does not "repair" its internal structure.' },
    { brand: 'Lancôme', name: 'Génifique', verdict: 'bad', score: 21, img: P + 'p12.jpg',
      claim: 'Activates the youth of your skin.',
      why: 'Anti-aging claims using "DNA / genes" wording were challenged by the FTC (L’Oréal / Lancôme).' },
    { brand: 'Maybelline', name: 'Instant Age Rewind', verdict: 'bad', score: 25, img: P + 'p13.jpg',
      claim: 'Erases wrinkles in an instant.',
      why: '"Erases wrinkles" suggests an almost medical effect, prohibited for cosmetics.' },
    { brand: 'Garnier', name: 'Ultra Doux', verdict: 'bad', score: 27, img: P + 'p7.jpg',
      claim: '100% of natural origin.',
      why: 'A sweeping "natural" claim rarely reflects the actual composition faithfully.' },
    { brand: 'Nivea', name: 'Q10 Power', verdict: 'bad', score: 31, img: P + 'p10.jpg',
      claim: 'Firms the skin in 2 weeks.',
      why: '"Firming" effect measurable only at the surface, presented with no caveat.' },
    { brand: 'Rimmel London', name: 'Wonder’Lash', verdict: 'bad', score: 22, img: P + 'p2.jpg',
      claim: 'Dramatic volume, false-lash effect.',
      why: 'False lashes in ads without a clear disclaimer — a type of visual banned by the ASA.' },
    // Compliant claims / genuine effectiveness
    { brand: 'La Roche-Posay', name: 'Anthelios SPF 50+', verdict: 'ok', score: 93, img: P + 'p9.jpg',
      claim: 'Protects against UVA and UVB — factor 50+.',
      why: 'Protection in line with the tested factor, usage advice stated.' },
    { brand: 'CeraVe', name: 'Moisturizing Cream', verdict: 'ok', score: 90, img: P + 'p3.jpg',
      claim: 'Hydrates and helps restore the skin barrier.',
      why: 'Ceramides + hyaluronic acid: measured claim, no medical effect claimed.' },
    { brand: 'The Ordinary', name: 'Niacinamide 10% + Zinc 1%', verdict: 'ok', score: 88, img: P + 'p8.jpg',
      claim: 'Reduces the appearance of blemishes and pores.',
      why: 'Transparent formula, "appearance of" claim realistic and bounded.' },
    { brand: 'Differin', name: 'Adapalene 0.1%', verdict: 'ok', score: 91, img: P + 'p6.jpg',
      claim: 'Treats acne.',
      why: 'A genuinely active retinoid — it is an over-the-counter medicine, not a mere cosmetic: hence the effectiveness.' },
    { brand: 'Avène', name: 'Thermal Spring Water', verdict: 'ok', score: 86, img: P + 'p16.jpg',
      claim: 'Soothes sensitive and irritated skin.',
      why: 'Claim that describes how the product is used, without exaggeration.' },
    { brand: 'Cetaphil', name: 'Gentle Skin Cleanser', verdict: 'ok', score: 87, img: P + 'p14.jpg',
      claim: 'Cleanses gently without drying.',
      why: 'The claim faithfully describes the use and tolerance, backed by a test.' },
    { brand: 'Eucerin', name: 'Aquaphor Repairing Balm', verdict: 'ok', score: 89, img: P + 'p11.jpg',
      claim: 'Protects and helps the skin recover.',
      why: 'A proven occlusive: "helps" + protective barrier, no promise of "healing".' },
  ];

  function marketCard(it) {
    const v = it.verdict === 'ok' ? 'ok' : 'bad';
    const word = v === 'ok' ? 'REAL' : 'FAKE';
    return `
      <div class="mw-card" data-v="${v}">
        <div class="mw-shot">
          <img src="${it.img}" alt="${escapeHtml(it.brand + ' — ' + it.name)}" loading="lazy" />
          <span class="mw-tag ${v}">${word}</span>
          <span class="mw-stamp ${v}" aria-hidden="true">${word}</span>
        </div>
        <div class="mw-body">
          <div class="mw-brand">${escapeHtml(it.brand)}</div>
          <div class="mw-name">${escapeHtml(it.name)}</div>
          <div class="mw-claim">« ${escapeHtml(it.claim)} »</div>
          <div class="mw-foot">
            <span class="mw-why">${escapeHtml(it.why)}</span>
            <span class="mw-score ${v}">${it.score}</span>
          </div>
        </div>
      </div>`;
  }

  const SHOW_TONES = {
    rose:  { a:'#fbe6ef', b:'#f3c9de', ink:'#9d2b62' },
    gold:  { a:'#f7ebca', b:'#ead4a0', ink:'#8a6a1f' },
    green: { a:'#e3f1e3', b:'#c4e2c4', ink:'#2f6b3a' },
    sky:   { a:'#e3edf8', b:'#c5dbf2', ink:'#1f4f8a' },
    plum:  { a:'#ede1f5', b:'#d9c5ef', ink:'#5b3a8a' },
    amber: { a:'#fbecd3', b:'#f0d6ac', ink:'#92580f' },
  };
  function toneVars(tone) {
    const t = SHOW_TONES[tone] || SHOW_TONES.sky;
    return `--th-a:${t.a};--th-b:${t.b};--th-ink:${t.ink};`;
  }
  const verdictColor = (v) => (v === 'ok' ? '#16a34a' : '#dc2626');

  let _showFilter = 'all';

  function adCard(it) {
    const idx = SHOWCASE.indexOf(it);
    const v = it.verdict === 'ok' ? 'ok' : 'bad';
    const ribbon = it.verdict === 'ok' ? 'Reliable' : 'Misleading';
    const revealK = it.verdict === 'ok' ? 'Why it is compliant' : 'What raises a concern';
    return `
      <button type="button" class="ad-card" data-show-idx="${idx}" data-verdict="${v}" style="${toneVars(it.tone)}--m-c:${verdictColor(it.verdict)};">
        <div class="ad-poster">
          <div class="ad-ribbon ${v}"><span>${ribbon}</span></div>
          <div class="ap-brand">${escapeHtml(it.brand)}</div>
          <div class="ap-name">${escapeHtml(it.name)}</div>
          <div class="ap-tag">« ${escapeHtml(it.tagline)} »</div>
          <div class="ad-reveal">
            <div class="ar-k">${revealK}</div>
            <div class="ar-t">${escapeHtml(it.reasons[0])}</div>
          </div>
        </div>
        <div class="ad-foot">
          <span class="meter"><span class="bar"><i data-w="${it.score}"></i></span><span class="pc">${it.score}</span></span>
          <span class="go">See the investigation →</span>
        </div>
      </button>`;
  }

  function renderShowcase() {
    const mount = document.getElementById('io6-showcase');
    if (!mount) return;
    const total = SHOWCASE.length;
    const nBad = SHOWCASE.filter(s => s.verdict === 'bad').length;
    const nOk = total - nBad;
    const featured = SHOWCASE.find(s => s.featured) || SHOWCASE[0];
    const fIdx = SHOWCASE.indexOf(featured);
    const fv = featured.verdict === 'ok' ? 'ok' : 'bad';
    const fvTxt = featured.verdict === 'ok' ? 'Claim judged reliable' : 'Claim judged misleading';

    mount.innerHTML = `
      <div class="vidx">
        <div class="vidx-rv vidx-top">
          <div>
            <div class="vidx-kicker">Verify Index · cosmetics <span class="vidx-live"><span class="ld"></span>live</span></div>
            <h3>The cosmetics ads that Verify has already put under scrutiny.</h3>
          </div>
          <div class="vidx-sub">Each claim is examined one by one, against the EU rules on cosmetic claims.</div>
        </div>

        <div class="vidx-rv vidx-stats" style="transition-delay:.06s;">
          <div class="vidx-stat"><div class="v"><span data-count="248">0</span></div><div class="l">campaigns checked</div></div>
          <div class="vidx-stat bad"><div class="v"><span data-count="37">0</span><span> %</span></div><div class="l">judged misleading</div></div>
          <div class="vidx-stat"><div class="v"><span data-count="30">0</span><span> s</span></div><div class="l">on average, for a verdict</div></div>
        </div>

        <div class="vidx-rv mw" style="transition-delay:.1s;">
          <div class="mw-head">
            <span class="mw-k">On the global market</span>
            <span class="mw-sub">Claims from major international brands, put under scrutiny against EU rules and ASA / FTC decisions.</span>
            <span class="mw-leg"><b class="bad">FAKE</b> misleading advertising claim <span class="sep">·</span> <b class="ok">REAL</b> compliant / proven effectiveness</span>
          </div>
          <div class="marquee mw-marquee" data-speed="38">
            <div class="marquee__track" id="mw-track">${MARKET.map(marketCard).join('')}</div>
          </div>
          <p class="mw-note">Illustrative examples: real brands, verdicts about a <em>type of advertising claim</em> (drawn from public decisions of authorities — ASA, FTC, European Commission). This is not an opinion on product quality.</p>
        </div>
      </div>`;

    // scroll reveal + count-up + meters
    observeReveal(mount);

    // "On the global market" — hydrate the auto-scroll strip (duplicate the
    // track once → seamless translateX(-50%) loop), scale speed to its width.
    const mwq = mount.querySelector('.mw-marquee');
    const mwTrack = mwq && mwq.querySelector('.marquee__track');
    if (mwTrack && mwTrack.dataset.cloned !== 'true') {
      mwTrack.dataset.cloned = 'true';
      mwTrack.innerHTML += mwTrack.innerHTML;
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        requestAnimationFrame(() => {
          const speed = parseFloat(mwq.dataset.speed || '38'); // px / s
          mwTrack.style.animationDuration = Math.max(28, (mwTrack.scrollWidth / 2) / speed) + 's';
        });
      }
    }
  }

  function applyShowFilter() {
    const grid = document.getElementById('vidx-grid');
    if (!grid) return;
    grid.classList.add('filtering');
    setTimeout(() => {
      [...grid.children].forEach(card => {
        const show = _showFilter === 'all' || card.dataset.verdict === _showFilter;
        card.style.display = show ? '' : 'none';
        if (show) { const i = card.querySelector('.bar > i'); if (i) { i.style.width = '0'; } }
      });
      requestAnimationFrame(() => {
        grid.classList.remove('filtering');
        requestAnimationFrame(() => {
          [...grid.children].forEach(card => {
            if (card.style.display !== 'none') { const i = card.querySelector('.bar > i'); if (i) i.style.width = (i.dataset.w || 0) + '%'; }
          });
        });
      });
    }, 260);
  }

  function countUp(el) {
    const target = parseFloat(el.dataset.count || '0');
    const dur = 1300, start = performance.now();
    (function step(now) {
      const t = Math.min(1, (now - start) / dur);
      const e = 1 - Math.pow(1 - t, 3);
      el.textContent = String(Math.round(target * e));
      if (t < 1) requestAnimationFrame(step);
    })(performance.now());
  }

  function observeReveal(root) {
    const els = [...root.querySelectorAll('.vidx-rv')];
    const fire = (el) => {
      el.classList.add('in');
      el.querySelectorAll('[data-count]').forEach(c => { if (!c.dataset.done) { c.dataset.done = '1'; countUp(c); } });
      el.querySelectorAll('[data-w]').forEach(b => { b.style.width = (b.dataset.w || 0) + '%'; });
    };
    if (!('IntersectionObserver' in window)) { els.forEach(fire); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(en => { if (en.isIntersecting) { fire(en.target); io.unobserve(en.target); } });
    }, { threshold: 0.16, rootMargin: '0px 0px -40px 0px' });
    els.forEach(e => io.observe(e));
  }

  function showShowcaseReport(it) {
    if (!it) return;
    const v = it.verdict === 'ok' ? '' : 'bad';
    const vTxt = it.verdict === 'ok' ? 'Claim judged reliable' : 'Claim judged misleading';
    const mark = it.verdict === 'ok' ? '✓' : '✕';
    const box = document.createElement('div');
    box.className = `modal-box deep-modal vrx ${v}`;
    box.style.cssText = toneVars(it.tone);
    box.innerHTML = `
      <button type="button" class="modal-close" aria-label="Close" data-close>×</button>
      <div class="vrx-banner">
        <div class="vb-brand">${escapeHtml(it.brand)} · campaign checked</div>
        <h2 class="vb-name">${escapeHtml(it.name)}</h2>
        <span class="vb-pill">${vTxt}</span>
      </div>
      <div class="vrx-claim">"${escapeHtml(it.claim)}"</div>
      <div class="vrx-meter-row">
        <div>
          <div class="vrx-meter-num">${it.score}<span style="font-size:14px;color:#9ca3af;">/100</span></div>
          <div class="vrx-meter-lbl">Reliability index</div>
        </div>
        <div class="vrx-meter"><i data-w="${it.score}"></i></div>
      </div>
      ${it.summary ? `<p style="font-size:14.5px;line-height:1.65;color:#4b5563;margin:0 0 22px;">${escapeHtml(it.summary)}</p>` : ''}
      <h4>What the newsroom checked</h4>
      <ul class="vrx-checks">
        ${it.reasons.map(r => `<li><span class="ic">${mark}</span><span>${escapeHtml(r)}</span></li>`).join('')}
      </ul>
      <div class="vrx-rule"><strong>What the EU rules say</strong>${escapeHtml(it.rule)}</div>
      <div class="vrx-disc">Illustrative example — summary of a Verify check. The brands cited are fictitious.</div>
    `;
    box.querySelector('[data-close]').addEventListener('click', _closeModal);
    _openModal(box);
    requestAnimationFrame(() => {
      const bar = box.querySelector('.vrx-meter > i');
      if (bar) requestAnimationFrame(() => { bar.style.width = (bar.dataset.w || 0) + '%'; });
    });
  }

  async function pingHealth() {
    const banner = document.getElementById('api-status-io6');
    try {
      const r = await fetch(`${IO6}/health`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const info = data.info || {};
      if (data.status !== 'ok') {
        banner.className = 'api-banner desk';
        banner.innerHTML = `${svgIcon('settings','icon-14')} <span>Service is getting ready…</span>`;
        return;
      }
      banner.className = 'api-banner desk ok';
      banner.innerHTML = `${svgIcon('check','icon-14')} <span>Service available</span>`;
    } catch (e) {
      banner.className = 'api-banner desk err';
      banner.innerHTML = `${svgIcon('warn','icon-14')} <span>Service temporarily unavailable — try again in a moment.</span>`;
    }
  }

  // ─── Dossier counter (persistent across sessions) ─────────────────────────
  function restoreDossierCounter() {
    const el = document.getElementById('desk-dossier');
    if (!el) return;
    let n = parseInt(localStorage.getItem('verify_io6_submissions') || '0', 10) || 0;
    el.textContent = `N° ${String(n + 1).padStart(4, '0')}`;
  }
  function bumpSubmissionCounter() {
    const el = document.getElementById('desk-dossier');
    let n = parseInt(localStorage.getItem('verify_io6_submissions') || '0', 10) || 0;
    n += 1;
    localStorage.setItem('verify_io6_submissions', String(n));
    if (el) el.textContent = `N° ${String(n + 1).padStart(4, '0')}`;
  }

  // ─── Status helper (renamed: setCinemaStatus → setDeskStatus, alias kept) ─
  function setDeskStatus(state, text) {
    const el = document.getElementById('status-io6');
    if (!el) return;
    el.className = `desk-status ${state || ''}`;
    el.innerHTML = `<span class="sc-led"></span><span class="sc-text">${text || ''}</span>`;
  }
  // Keep old name for compatibility within this file
  const setCinemaStatus = setDeskStatus;

  // ─── Drop zone (sibling input pattern) ────────────────────────────────────
  function setupDropZone(zoneId, inputId) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    if (!zone || !input) return;
    const mimeRe = /^video\//;

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
      if (f && mimeRe.test(f.type)) {
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
    zone.classList.add('has-file');
    const sizeMb = (file.size / 1024 / 1024).toFixed(1);
    zone.innerHTML = `
      <div class="desk-filled">
        <div class="file-icon">${svgIcon('video','icon-22')}</div>
        <div class="file-meta">
          <div class="file-name">${escapeHtml(file.name)}</div>
          <div class="file-stats">
            <span>${sizeMb} MB</span>
            <span>${escapeHtml(file.type || 'video')}</span>
            <span>Ready to be checked</span>
          </div>
        </div>
        <button type="button" class="file-change" data-clear>change</button>
      </div>`;
    setDeskStatus('', `Received · ${sizeMb} MB · ready to be checked`);
    const clear = zone.querySelector('[data-clear]');
    if (clear) clear.addEventListener('click', (e) => {
      e.stopPropagation();
      input.value = '';
      restoreDeskDrop(zone);
      setDeskStatus('', 'Ready');
    });
  }

  function restoreDeskDrop(zone) {
    zone.classList.remove('has-file');
    zone.innerHTML = `
      <div class="desk-drop-icon">${svgIcon('video','icon-22')}</div>
      <div class="desk-drop-title">Drag and drop the advertising video</div>
      <div class="desk-drop-sub">or click to browse</div>
      <div class="desk-drop-formats">MP4 · MOV · 200 MB max</div>`;
  }
  // Backwards-compatible alias if anything else still calls it
  const restoreCinemaScreen = restoreDeskDrop;

  // ─── Analyze ──────────────────────────────────────────────────────────────
  async function analyze() {
    const btn = document.getElementById('btn-io6');
    const resultEl = document.getElementById('result-io6');
    const fileInput = document.getElementById('file-io6');
    const file = fileInput.files?.[0];
    if (!file) {
      resultEl.innerHTML = `<div class="coh-error">Please select a video.</div>`;
      setCinemaStatus('error', 'No file · add a video first');
      return;
    }

    btn.disabled = true;
    const t0 = performance.now();
    setDeskStatus('busy', 'Verification in progress…');
    resultEl.innerHTML = '';
    bumpSubmissionCounter();

    const processCtl = startProcessIndicator(document.getElementById('process-io6'));

    try {
      const fd = new FormData();
      fd.append('video', file);
      const resp = await fetch(`${IO6}/analyze/video`, { method: 'POST', body: fd });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`HTTP ${resp.status} — ${txt.slice(0, 300)}`);
      }
      const data = await resp.json();
      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      processCtl.complete(elapsed);
      setDeskStatus('', `Verification completed in ${elapsed} s`);
      renderResult(resultEl, data);
    } catch (e) {
      processCtl.fail();
      resultEl.innerHTML = `<div class="coh-error">An error occurred. Try again in a moment.</div>`;
      setDeskStatus('error', 'Verification failed');
    } finally {
      btn.disabled = false;
    }
  }

  // ─── Process indicator ────────────────────────────────────────────────────
  const STEPS = [
    { ico: 'wave',     lbl: 'Listening to the ad',                          detail: 'Listening to the audio track',           dur: 7000 },
    { ico: 'text',     lbl: 'Reading the on-screen text',                   detail: 'Picking up the displayed wording',       dur: 2500 },
    { ico: 'spark',    lbl: 'Spotting the claims',                          detail: 'Isolating each advertising claim',       dur: 1500 },
    { ico: 'branch',   lbl: 'Checking against the EU rules',                detail: 'Comparing each claim with the rules',    dur: 2000 },
    { ico: 'settings', lbl: 'Preparing the report',                         detail: 'Formatting the results',                 dur: 1000 },
  ];

  function startProcessIndicator(mount) {
    if (!mount) return { complete: () => {}, fail: () => {} };
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
        statusTxt.innerHTML = `${checkMark} ${STEPS.length} / ${STEPS.length} en ${t} s`;
      },
      fail() {
        cancelled = true; timers.forEach(clearTimeout);
        if (activeIdx >= 0) stepEls[activeIdx].dataset.state = 'pending';
        statusTxt.innerHTML = `${svgIcon('cross','icon-14')} error`;
        statusTxt.style.color = 'var(--red)';
      },
    };
  }

  // ─── EU regulatory references (used in the detailed cards) ───────────────
  const EU_ARTICLES = {
    'EU 655/2013 art. 4.2': {
      label: 'An honest ad',
      title: 'An honest ad',
      regulation: 'EU rules on cosmetic claims',
      excerpt: '"Claims made about a cosmetic product must rest on verifiable evidence."',
      explanation: 'Any advertising statement must be capable of being backed by serious data. Percentages, timeframes and numerical comparisons must be documented.',
      examples_violations: [
        'Reduces wrinkles by 50%',
        '3 times more effective',
        '100% natural',
      ],
    },
    'EU 655/2013 art. 4.4': {
      label: 'Substantiated claims',
      title: 'Claims backed by evidence',
      regulation: 'EU rules on cosmetic claims',
      excerpt: '"Claims must be supported by sufficient and verifiable evidence."',
      explanation: 'A claim of a result or a timeframe must rely on recognised studies and tests. Mere user feedback is not enough.',
      examples_violations: [
        'Visible in 24 hours',
        'Results in 7 days',
        'Immediate effect',
      ],
    },
    'EU 655/2013 art. 4.5': {
      label: 'A fair ad',
      title: 'A fair and measured ad',
      regulation: 'EU rules on cosmetic claims',
      excerpt: '"Claims must remain objective, without disparaging competitors or authorised ingredients."',
      explanation: 'No absolute superlative ("the best", "number 1"), no miracle vocabulary, no promise of permanent elimination: a cosmetic acts on the surface.',
      examples_violations: [
        'Miracle cream',
        'The best formula in the world',
        'Permanently eliminates wrinkles',
      ],
    },
    'EU 1223/2009': {
      label: 'Cosmetic, not medicine',
      title: 'A cosmetic is not a medicine',
      regulation: 'EU Cosmetic Products Regulation',
      excerpt: '"A cosmetic product is intended, essentially, to clean, perfume, beautify, protect or keep in good condition the superficial parts of the body."',
      explanation: 'This draws the line between cosmetic and medicine. A cream cannot "cure", "treat" or "heal" a disease: that would be a health claim, which falls under medicines.',
      examples_violations: [
        'Treats eczema',
        'Treats acne',
        'Heals stretch marks',
      ],
    },
  };
  const euLabel = (ref) => (EU_ARTICLES[ref] && EU_ARTICLES[ref].label) || 'Regulatory reference';

  const VERDICT_DESCS = {
    RELIABLE:   'All the claims in the ad can be substantiated. Nothing misleading was found.',
    MISLEADING: 'At least one claim goes against the EU rules on cosmetic claims, or is not substantiated.',
  };

  // ─── Render results — magazine editorial layout ───────────────────────────
  let CURRENT_DATA = null;
  function renderResult(mount, data) {
    CURRENT_DATA = data;
    const verdict = data.global_verdict || 'MISLEADING';
    const trust = +data.trust_score || 0;
    const stats = data.stats || {};
    const claims = data.claims || [];
    const tGood = 70, tSusp = 40;
    const moduleAccent = (getComputedStyle(document.body).getPropertyValue('--mc') || '').trim() || '#9333ea';
    const narrHTML = (window.VerifyXAI && data.narrative)
      ? window.VerifyXAI.narrativeCard(data.narrative, { accent: moduleAccent, verdictHint: data.global_verdict })
      : '';

    mount.className = '';
    mount.innerHTML = `
      <div class="io6-grid">
        <div class="col-12">${buildHero(verdict, trust, stats, data)}</div>
        ${narrHTML ? `<div class="col-12">${narrHTML}</div>` : ''}
        <div class="col-8">${buildClaimRibbon(claims)}</div>
        <div class="col-4">${buildSidebarStats(stats, data, claims)}</div>

        <div class="col-7">${buildAiJustification(verdict, trust, claims, data)}</div>
        <div class="col-5">${buildEuArticlesGrid(data.eu_articles_cited || [])}</div>
        <div class="col-7">${buildSeverityHeatmap(claims)}</div>
        <div class="col-5"></div>
        <div class="col-8">${buildTranscript(data)}</div>
        <div class="col-4">${buildOcrCard(data)}</div>
        <div class="col-12">${buildFilmstrip(data)}</div>
      </div>
    `;

    // Animate bars + gauge after render
    requestAnimationFrame(() => {
      mount.querySelectorAll('[data-target-w]').forEach(el => {
        el.style.width = el.dataset.targetW + '%';
      });
      const arc = mount.querySelector('.gauge-arc');
      if (arc) {
        arc.style.strokeDasharray = `${arc.dataset.arclen} ${arc.dataset.circ}`;
      }
      const counter = mount.querySelector('.gauge-num');
      if (counter) animateNumber(counter, 0, +counter.dataset.count, 1400);
    });

    // Wire claim cards → deep-dive modal
    mount.querySelectorAll('[data-claim-idx]').forEach(card => {
      card.addEventListener('click', () => {
        const idx = +card.dataset.claimIdx;
        showClaimDeepDive(claims[idx], idx, data);
      });
    });

    // Wire EU tiles AND traceability rows → article modal
    mount.querySelectorAll('[data-eu-ref]').forEach(tile => {
      tile.addEventListener('click', () => {
        showEuArticle(tile.dataset.euRef);
      });
      tile.style.cursor = 'pointer';
    });

    mount.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ─── Editorial header ────────────────────────────────────────────────────
  function buildHero(verdict, trust, stats, data) {
    const wordMap = { RELIABLE: 'RELIABLE', MISLEADING: 'MISLEADING' };
    const word = wordMap[verdict] || verdict;
    const flagCount = stats.n_false || 0;
    return `
      <div class="io6-hero" data-v="${verdict}">
        <div class="io6-hero-grid">
          <div>
            <div class="io6-hero-kicker">
              <span class="dot"></span>
              <span>ADVERTISING & COSMETICS</span>
            </div>
            <h1 class="io6-hero-headline">
              This ad is <span class="verdict-word">${escapeHtml(word)}</span>.
            </h1>
            <div class="io6-hero-deck">${escapeHtml(VERDICT_DESCS[verdict] || '')}</div>
            <div class="io6-hero-tags">
              <span class="io6-hero-tag">${stats.total ?? 0} claim${(stats.total ?? 0) > 1 ? 's' : ''} spotted</span>
              ${flagCount > 0 ? `<span class="io6-hero-tag flag">${flagCount} misleading claim${flagCount > 1 ? 's' : ''}</span>` : ''}
              <span class="io6-hero-tag">${data.has_audio ? 'with audio track' : 'no audio'}</span>
            </div>
          </div>
          <div class="io6-hero-gauge">
            ${buildTrustGauge(trust, 70, 40, verdict)}
            <div style="font-size:10px;text-transform:uppercase;letter-spacing:1.4px;color:var(--ink-soft);margin-top:6px;font-weight:700;">Reliability index</div>
          </div>
        </div>
      </div>`;
  }

  // ─── List of spotted claims ──────────────────────────────────────────────
  function buildClaimRibbon(claims) {
    if (!claims.length) {
      return `<div class="ed-card">
        <div class="ed-section-head"><span class="ed-section-num">01.</span><span class="ed-section-title">Spotted claims</span></div>
        <div class="empty-note">No claim could be spotted in this video.</div>
      </div>`;
    }
    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">01.</span>
          <span class="ed-section-title">Spotted claims — click for details</span>
        </div>
        <div class="claim-ribbon">
          ${claims.map((c, i) => buildClaimTape(c, i)).join('')}
        </div>
      </div>`;
  }

  function buildClaimTape(c, idx) {
    const v = c.verdict === 'TRUE' ? 'TRUE' : 'FALSE';
    const sourceLabel = c.source === 'audio' ? 'Audio track' : c.source === 'screen' ? 'On screen' : escapeHtml(c.source || '');
    const verdictWord = { TRUE: 'Accurate', FALSE: 'Misleading' }[v];
    const euCount = (c.eu_articles || []).length;
    return `
      <div class="claim-tape" data-v="${v}" data-claim-idx="${idx}" tabindex="0">
        <div class="ct-num">${String(idx + 1).padStart(2, '0')}</div>
        <div>
          <div class="ct-text">"${escapeHtml(c.claim)}"</div>
          <div class="ct-meta">
            <span class="ct-source-pill">${sourceLabel}</span>
            ${euCount ? `<span>${euCount} regulatory reference${euCount > 1 ? 's' : ''}</span>` : ''}
            <span class="ct-cta">see details ${svgIcon('settings','icon-12')}</span>
          </div>
        </div>
        <div class="ct-verdict-pill">${verdictWord}</div>
      </div>`;
  }

  // ─── Numbers summary ─────────────────────────────────────────────────────
  function buildSidebarStats(stats, data, claims) {
    const totalEu = (data.eu_articles_cited || []).length;
    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">02.</span>
          <span class="ed-section-title">In numbers</span>
        </div>
        <div class="mini-stats">
          <div class="mini-stat"><div><div class="k">Accurate claims</div><div class="v">${stats.n_true || 0}<small>/ ${stats.total || 0}</small></div></div></div>
          <div class="mini-stat"><div><div class="k">Misleading claims</div><div class="v">${stats.n_false || 0}<small>/ ${stats.total || 0}</small></div></div></div>
          <div class="mini-stat"><div><div class="k">Regulatory references</div><div class="v">${totalEu}</div></div></div>
        </div>
      </div>`;
  }

  // ─── Our analysis ────────────────────────────────────────────────────────
  function buildAiJustification(verdict, trust, claims, data) {
    const stats = data.stats || {};

    // Most notable misleading claim
    const sevOrder = { critical: 4, high: 3, medium: 2, info: 1 };
    const falseSorted = claims
      .filter(c => c.verdict === 'FALSE')
      .sort((a, b) => (sevOrder[b.severity] || 0) - (sevOrder[a.severity] || 0));
    const worst = falseSorted[0];

    let body;
    if (verdict === 'RELIABLE') {
      body = `This ad appears <mark class="good">reliable</mark>: its reliability index is <mark>${trust.toFixed(0)}%</mark>. The ${stats.total || 0} claim${(stats.total || 0) > 1 ? 's' : ''} found can be substantiated under the EU rules on cosmetic claims.`;
    } else {
      body = `This ad appears <mark class="bad">misleading</mark>: its reliability index is <mark>${trust.toFixed(0)}%</mark>. ${stats.n_false || 0} claim${(stats.n_false || 0) > 1 ? 's' : ''} out of ${stats.total || 0} ${(stats.n_false || 0) > 1 ? 'do' : 'does'} not comply with the <mark class="bad">EU rules on cosmetic claims</mark>${worst ? `, starting with: <em>"${escapeHtml(worst.claim)}"</em>` : ''}.`;
    }

    return `
      <div class="ed-card" style="padding:0; overflow:hidden;">
        <div class="ed-section-head" style="padding:24px 26px 14px; margin-bottom:0;">
          <span class="ed-section-num">03.</span>
          <span class="ed-section-title">Our analysis</span>
        </div>
        <div class="ai-justify">
          ${body}
          <span class="ai-byline">— Verified by the Verify newsroom · against the EU rules</span>
        </div>
      </div>`;
  }

  // ─── EU regulatory references (clickable) ────────────────────────────────
  function buildEuArticlesGrid(refs) {
    if (!refs.length) {
      return `<div class="ed-card">
        <div class="ed-section-head"><span class="ed-section-num">04.</span><span class="ed-section-title">What the EU rules say</span></div>
        <div class="empty-note">No regulatory reference to report.</div>
      </div>`;
    }
    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">04.</span>
          <span class="ed-section-title">What the EU rules say · click to read</span>
        </div>
        <div class="eu-grid">
          ${refs.map((r, i) => {
            const meta = EU_ARTICLES[r] || {};
            return `
              <div class="eu-tile" data-eu-ref="${escapeHtml(r)}" tabindex="0">
                <div class="eu-tile-num">${String(i + 1).padStart(2, '0')}</div>
                <div class="eu-tile-body">
                  <div class="eu-tile-ref">${escapeHtml(euLabel(r))}</div>
                  <div class="eu-tile-desc">${escapeHtml(meta.title || 'Regulatory reference')}</div>
                </div>
                <div class="eu-tile-arrow">${svgIcon('arrow','icon-16')}</div>
              </div>`;
          }).join('')}
        </div>
      </div>`;
  }

  // ─── Risk level per claim ────────────────────────────────────────────────
  function buildSeverityHeatmap(claims) {
    const sevOrder = { critical: 4, high: 3, medium: 2, info: 1 };
    // 4 columns: from lowest to highest
    const levelCols = [
      { lvl: 1, label: 'Low' },
      { lvl: 2, label: 'Moderate' },
      { lvl: 3, label: 'Significant' },
      { lvl: 4, label: 'High' },
    ];

    if (!claims.length) {
      return `<div class="ed-card">
        <div class="ed-section-head"><span class="ed-section-num">05.</span><span class="ed-section-title">Risk level per claim</span></div>
        <div class="empty-note">No claim to assess.</div>
      </div>`;
    }

    const cells = [];
    cells.push(`<div class="hh-corner">Claim</div>`);
    levelCols.forEach(c => cells.push(`<div class="hh-col">${escapeHtml(c.label)}</div>`));

    claims.forEach((c, i) => {
      const v = c.verdict === 'TRUE' ? 'TRUE' : 'FALSE';
      const lvl = v === 'TRUE' ? 1 : Math.min(4, sevOrder[c.severity] || 2);
      cells.push(`<div class="hh-row">${String(i + 1).padStart(2, '0')}</div>`);
      levelCols.forEach(col => {
        const active = col.lvl === lvl;
        cells.push(`<div class="hh-cell" data-w="${active ? col.lvl : 0}">${active ? '●' : ''}</div>`);
      });
    });

    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">05.</span>
          <span class="ed-section-title">Risk level per claim</span>
        </div>
        <div class="sev-heatmap">${cells.join('')}</div>
        <div style="font-size:11px;color:var(--ink-faint);margin-top:10px;letter-spacing:.3px;">
          Each row is a claim; the dot indicates its risk level. The further a claim strays from the EU rules on cosmetic claims, the higher this level.
        </div>
      </div>`;
  }

  function buildTranscript(data) {
    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">06.</span>
          <span class="ed-section-title">Audio track transcript</span>
        </div>
        ${data.transcript
          ? `<div class="quote-block">${escapeHtml(data.transcript)}</div>`
          : `<div class="empty-note">${data.has_audio ? 'No transcript available.' : 'Video has no audio.'}</div>`}
      </div>`;
  }

  function buildOcrCard(data) {
    const texts = data.ocr_texts || [];
    return `
      <div class="ed-card">
        <div class="ed-section-head">
          <span class="ed-section-num">07.</span>
          <span class="ed-section-title">On-screen text</span>
        </div>
        <div class="detect-chips">
          ${texts.length
            ? texts.map(t => `<span class="chip chip-tag">${escapeHtml(t)}</span>`).join('')
            : '<div class="empty-note">No on-screen text.</div>'}
        </div>
      </div>`;
  }

  function buildFilmstrip(data) {
    const count = data.frames_count || 0;
    if (!count) return '';
    const ocr = data.ocr_texts || [];
    const frames = [];
    for (let i = 0; i < Math.min(count, 12); i++) {
      const ts = i.toFixed(0).padStart(2, '0');
      const overlay = ocr.slice(i, i + 1).join(' · ') || '';
      frames.push({ idx: i, ts, overlay });
    }
    return `
      <div class="ed-card" style="padding:18px 22px;">
        <div class="ed-section-head" style="margin-bottom:14px;">
          <span class="ed-section-num">08.</span>
          <span class="ed-section-title">Frames from the ad</span>
        </div>
        <div class="filmstrip">
          ${frames.map(f => `
            <div class="filmstrip-frame">
              ${f.overlay ? `<div class="filmstrip-overlay">${escapeHtml(f.overlay)}</div>` : ''}
              <div style="opacity:.4;">FRAME ${f.idx + 1}</div>
              <div class="ts">0:${f.ts}</div>
            </div>
          `).join('')}
        </div>
      </div>`;
  }

  function buildTrustGauge(score, tGood, tSusp, verdict) {
    const R = 84, CIRC = 2 * Math.PI * R;
    const clamped = Math.max(0, Math.min(100, score)) / 100;
    const arcLen = clamped * CIRC;
    return `
      <div class="vh-gauge">
        <svg viewBox="0 0 200 200" aria-hidden="true">
          <circle class="gauge-bg" cx="100" cy="100" r="${R}" />
          <circle class="gauge-arc" cx="100" cy="100" r="${R}"
                  data-arclen="${arcLen.toFixed(1)}"
                  data-circ="${CIRC.toFixed(1)}" />
        </svg>
        <div class="gauge-center">
          <div class="gauge-num" data-count="${score}">0</div>
          <div class="gauge-label">Reliability index</div>
        </div>
      </div>`;
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  MODAL INFRASTRUCTURE
  // ═══════════════════════════════════════════════════════════════════════
  let _activeModal = null;
  function _closeModal() {
    if (!_activeModal) return;
    _activeModal.classList.remove('open');
    setTimeout(() => { _activeModal?.remove(); _activeModal = null; }, 250);
  }
  function _openModal(boxEl) {
    _closeModal();
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.appendChild(boxEl);
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) _closeModal(); });
    document.body.appendChild(backdrop);
    _activeModal = backdrop;
    requestAnimationFrame(() => backdrop.classList.add('open'));
  }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') _closeModal(); });

  // ═══════════════════════════════════════════════════════════════════════
  //  DETAILED CARD FOR A CLAIM
  // ═══════════════════════════════════════════════════════════════════════
  function showClaimDeepDive(claim, idx, data) {
    const box = document.createElement('div');
    box.className = 'modal-box deep-modal';

    const v = claim.verdict === 'TRUE' ? 'TRUE' : 'FALSE';
    const verdictWord = { TRUE: 'ACCURATE', FALSE: 'MISLEADING' }[v];

    const highlighted = highlightClaimEvidence(claim);
    const sourceLabel = claim.source === 'audio' ? 'AUDIO TRACK' : claim.source === 'screen' ? 'ON SCREEN' : '';

    box.innerHTML = `
      <button type="button" class="modal-close" aria-label="Close" data-close>×</button>
      <div class="modal-kicker">CLAIM ${String(idx + 1).padStart(2, '0')}${sourceLabel ? ' · ' + sourceLabel : ''}</div>
      <h2 style="margin:0 0 10px;">
        <span class="claim-verdict-pill" data-v="${v}" style="font-size:11px;vertical-align:middle;margin-right:10px;">${verdictWord}</span>
        Claim details
      </h2>

      <div class="deep-claim-text">${highlighted}</div>

      <div class="deep-section-title">What the verification shows</div>
      <ul class="claim-evidence-list" style="margin:0 0 6px;">
        ${(claim.reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join('') || `<li class="empty-note">${v === 'FALSE' ? 'This claim is not sufficiently substantiated.' : 'This claim can be substantiated.'}</li>`}
      </ul>

      ${(claim.eu_articles || []).length ? `
        <div class="deep-section-title">Regulatory references concerned</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          ${claim.eu_articles.map(a => `
            <button type="button" class="eu-pill" data-modal-eu="${escapeHtml(a)}" style="cursor:pointer;background:#fef9c3;border:1px solid #fde68a;color:#713f12;padding:6px 12px;font-size:12px;font-weight:700;">
              ${escapeHtml(euLabel(a))} →
            </button>
          `).join('')}
        </div>
        <div style="font-size:12px;color:var(--ink-faint);margin-top:10px;">
          Click a reference to see what the EU rules on cosmetic claims provide for.
        </div>` : ''}
    `;
    box.querySelector('[data-close]').addEventListener('click', _closeModal);
    // Inner EU pills → open the EU article modal (after closing claim modal)
    box.querySelectorAll('[data-modal-eu]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const ref = btn.dataset.modalEu;
        _closeModal();
        setTimeout(() => showEuArticle(ref), 280);
      });
    });
    _openModal(box);
  }

  function highlightClaimEvidence(claim) {
    let text = claim.claim || '';
    const v = claim.verdict === 'TRUE' ? 'TRUE' : 'FALSE';
    const cls = v === 'FALSE' ? 'danger' : 'safe';

    // Build list of regex patterns to highlight (from FAUX/VRAI patterns embedded in evidence)
    // Since we don't have raw regex from evidence, we approximate: match "evidence-like" tokens (numbers, %, time units)
    const highlights = [
      /\b\d+\s*%\s*(?:[a-zéèçà]+)?/gi,
      /\b\d+\s*(?:days?|jours?|hours?|heures?|weeks?|semaines?|months?|mois|times?|fois)\b/gi,
      /\b(miracle|miraculeu\w*|magique|magical|magic|wonder|merveille\w*)\b/gi,
      /\b(meilleur|best|number\s*one|n[°o]\s*1|le\s*plus|the\s*most)\b/gi,
      /\b(instantan\w*|immédiat\w*|immediate|instant\w*)\b/gi,
      /\b(double|triple|quadruple)s?\b/gi,
      /\b\d+\s*x?\s*(?:more|times|fois|plus)\b/gi,
      /\b(?:cure|guéri|heal|treat|soigne)\w*/gi,
      /\b(?:remove|elimin|effac|erase|eradicat)\w*/gi,
      /\b(?:hyaluronic|retinol|niacinamide|peptide|ceramide|vitamin|q10|coenzyme|salicylic|glycolic)\b/gi,
      /\b(?:ecocert|cosmos|cruelty.free|vegan|paraben.free|sulfate.free)\b/gi,
    ];
    const escaped = escapeHtml(text);
    let out = escaped;
    highlights.forEach(re => {
      out = out.replace(re, (m) => `<mark class="${cls}">${m}</mark>`);
    });
    return out;
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  EU ARTICLE MODAL
  // ═══════════════════════════════════════════════════════════════════════
  function showEuArticle(ref) {
    const meta = EU_ARTICLES[ref];
    const box = document.createElement('div');
    box.className = 'modal-box deep-modal';

    if (!meta) {
      box.innerHTML = `
        <button type="button" class="modal-close" data-close>×</button>
        <div class="modal-kicker">EU RULES</div>
        <h2>${escapeHtml(euLabel(ref))}</h2>
        <p>Details for this reference are not available at the moment.</p>`;
    } else {
      box.innerHTML = `
        <button type="button" class="modal-close" data-close>×</button>
        <div class="modal-kicker">${escapeHtml(meta.regulation)}</div>
        <h2>${escapeHtml(meta.title)}</h2>

        <div class="eu-article-quote">${escapeHtml(meta.excerpt)}</div>

        <p>${escapeHtml(meta.explanation)}</p>

        <div class="deep-section-title">Examples of wording to avoid</div>
        <ul style="font-family:'Playfair Display',serif;font-style:italic;font-size:15px;line-height:1.7;color:var(--ink);padding-left:22px;">
          ${meta.examples_violations.map(e => `<li>"${escapeHtml(e)}"</li>`).join('')}
        </ul>

        <div class="modal-tip">
          <strong>Our verification</strong> — each claim in the ad is compared against this reference. When a claim strays from it, it is flagged as misleading.
        </div>`;
    }
    box.querySelector('[data-close]').addEventListener('click', _closeModal);
    _openModal(box);
  }

  function animateNumber(el, from, to, duration) {
    const start = performance.now();
    function step(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const val = from + (to - from) * eased;
      el.textContent = Number.isInteger(to) ? Math.round(val) : val.toFixed(1);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
})();
