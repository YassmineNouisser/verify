/* Shared header/footer/FAB components — single source of truth, injected on every page. */

/* ---- Inline SVG icon system (replaces emoji) ---- */
const Icon = {
  io1: '<svg class="icon-svg" viewBox="0 0 24 24"><circle cx="12" cy="9" r="4"/><path d="M5 21c0-3.866 3.134-7 7-7s7 3.134 7 7"/><path d="M9 9h.01M15 9h.01" stroke-width="2.5"/></svg>',
  io2: '<svg class="icon-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>',
  io3: '<svg class="icon-svg" viewBox="0 0 24 24"><path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9z"/><path d="M19 14l.7 1.7L21.4 16.4l-1.7.7L19 19l-.7-1.7L16.6 16.4l1.7-.7z"/></svg>',
  io4: '<svg class="icon-svg" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/><path d="M11 8v6M8 11h6" stroke-width="1.5"/></svg>',
  io5: '<svg class="icon-svg" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9h10M7 13h6M7 17h4"/><circle cx="16.5" cy="14.5" r="2.5" fill="none"/></svg>',
  io6: '<svg class="icon-svg" viewBox="0 0 24 24"><path d="M3 10v4a1 1 0 001 1h3l5 4V5L7 9H4a1 1 0 00-1 1z"/><path d="M16 8a5 5 0 010 8M19 5a8 8 0 010 14"/></svg>',
  search: '<svg class="icon-svg" viewBox="0 0 24 24" style="width:16px;height:16px;"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
  bolt: '<svg class="icon-svg" viewBox="0 0 24 24" style="width:14px;height:14px;"><path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" fill="currentColor" stroke="none"/></svg>',
  arrow: '<svg class="icon-svg" viewBox="0 0 24 24" style="width:14px;height:14px;"><path d="M5 12h14M13 5l7 7-7 7"/></svg>',
  shield: '<svg class="icon-svg" viewBox="0 0 24 24" style="width:14px;height:14px;"><path d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6z"/><path d="M9 12l2 2 4-4"/></svg>',
};

/* Internal slugs (io1..io6) kept stable for URL backward compatibility,
   but user-facing UI only shows the descriptive `name`. No IO codes shown. */
const MODULES = [
  { id: 'io1', name: 'AI-Generated Media',          short: 'AI Detection',         icon: Icon.io3, bg: '#ede9fe', fg: '#5b21b6',
    tagline: 'Catches images and videos produced by generative models.',
    desc:    'Detects content created by GANs and diffusion models. Looks at visual artifacts, spectral signatures and inconsistencies the eye cannot see.' },
  { id: 'io2', name: 'Manipulation & Persuasion',   short: 'Persuasion',           icon: Icon.io2, bg: '#fef3c7', fg: '#78350f',
    tagline: 'Spots the emotional triggers hidden in ads and propaganda.',
    desc:    'Identifies persuasion and visual-manipulation techniques used in advertising and propaganda video — biased framing, color grading, emotional zoom.' },
  { id: 'io4', name: 'Photoshop Forensics',         short: 'Forensics',            icon: Icon.io4, bg: '#dcfce7', fg: '#14532d',
    tagline: 'Detects local edits on otherwise authentic photos.',
    desc:    'Spots local modifications: object insertion or removal, cloning, splicing, inpainting. Powered by ELA, double-JPEG analysis and quantization-table reconstruction.' },
  { id: 'io5', name: 'Caption Fidelity',            short: 'Fidelity',             icon: Icon.io1, bg: '#dbeafe', fg: '#1e3a8a',
    tagline: 'Measures how faithfully a caption describes the post.',
    desc:    'Evaluates how faithfully a caption describes its visual content. Surfaces exaggerations, omissions and editorial framing.' },
  { id: 'io6', name: 'Cosmetic Ads Fact-Check',     short: 'Cosmetics',            icon: Icon.io6, bg: '#ffedd5', fg: '#9a3412',
    tagline: 'Verifies the visual claims of cosmetics advertising.',
    desc:    'Verifies the visual claims of cosmetic advertising: retouched before/after photos, deepfaked testimonials, misleading claims.' },
];

const ModuleDropdown = () => `
  <div class="dropdown-panel" role="menu">
    <div class="dd-rail">
      <span class="dd-rail-kicker">The Verify Toolkit</span>
      <p class="dd-rail-pitch">Five specialised modules — from the raw pixel up to the words around it.</p>
      <a href="verifier.html" class="dd-rail-cta">Open the full toolkit <span>→</span></a>
      <div class="dd-rail-links">
        <a href="methodologie.html">How it works</a>
        <a href="archive.html">Browse the archive ›</a>
      </div>
    </div>
    <div class="dd-modules">
      ${MODULES.map((m, i) => `
        <a href="verifier-module.html?v=12&m=${m.id}" role="menuitem" style="--m-bg:${m.bg};--m-fg:${m.fg};">
          <span class="icon-tile sm" style="background:${m.bg};color:${m.fg};">${m.icon}</span>
          <span class="dd-text">
            <span class="dd-title">${m.name}${i === 0 ? '<em class="dd-tag">Most used</em>' : ''}</span>
            <span class="dd-sub">${m.tagline}</span>
          </span>
          <span class="dd-arrow">${Icon.arrow}</span>
        </a>
      `).join('')}
    </div>
  </div>
`;

const VerifyHeader = ({ slim = false } = {}) => `
  <!-- Navy nav with brand -->
  <div class="navy-nav">
    <div class="container-x">
      <div class="nav-inner">
        <button class="burger" aria-label="Menu">☰</button>
        <nav class="nav-links">
          <a href="index.html">Home</a>
          <a href="real-or-fake.html">Fact-Checks</a>
          <span class="has-dropdown">
            <a href="verifier.html">Verify a File</a>
            ${ModuleDropdown()}
          </span>
          <a href="dashboard.html">Statistics</a>
          <a href="packs.html">Pricing</a>
          <a href="mission.html">About</a>
        </nav>

        <div class="hidden md:flex items-center gap-3">
          <form class="header-search" onsubmit="event.preventDefault(); window.location.href='real-or-fake.html?q='+encodeURIComponent(this.querySelector('input').value);">
            <span style="color:rgba(255,255,255,0.7);">${Icon.search}</span>
            <input type="text" placeholder="Search a fact-check, a topic…" />
            <button type="submit">Search</button>
          </form>
        </div>

        <a href="index.html" class="brand" aria-label="Verify — home">
          <img src="assets/img/logo-verify-white.png" alt="Verify" class="brand-logo" />
        </a>
      </div>
      ${slim ? '' : `
      <div class="subnav">
        <a href="real-or-fake.html?v=fake"   class="chip">Fake</a>
        <a href="real-or-fake.html?v=real"   class="chip">Real</a>
        <a href="real-or-fake.html?v=unverified" class="chip">Not Verified</a>
        <a href="categorie.html" class="chip">Politics</a>
        <a href="categorie.html" class="chip">Economy</a>
        <a href="categorie.html" class="chip">Health</a>
        <a href="categorie.html" class="chip">Tech</a>
        <a href="categorie.html" class="chip">Climate</a>
        <a href="categorie.html" class="chip">International</a>
      </div>
      `}
    </div>
  </div>
`;

const VerifyFooter = () => `
  <footer class="site-footer">
    <div class="footer-grid">
      <div>
        <img src="assets/img/logo-verify-white.png" alt="Verify" class="footer-logo" />
        <p style="font-size:14px;opacity:0.8;line-height:1.55;margin:0 0 16px;">
          A Tunisian platform fighting visual disinformation with AI-powered analysis and independent journalism.
        </p>
        <div style="display:flex;gap:8px;">
          <a href="#" aria-label="Twitter" style="width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,0.10);display:inline-flex;align-items:center;justify-content:center;text-decoration:none;color:#fff;">𝕏</a>
          <a href="#" aria-label="Facebook" style="width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,0.10);display:inline-flex;align-items:center;justify-content:center;text-decoration:none;color:#fff;font-weight:700;">f</a>
          <a href="#" aria-label="Instagram" style="width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,0.10);display:inline-flex;align-items:center;justify-content:center;text-decoration:none;color:#fff;font-weight:700;">◉</a>
          <a href="#" aria-label="LinkedIn" style="width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,0.10);display:inline-flex;align-items:center;justify-content:center;text-decoration:none;color:#fff;font-weight:700;font-size:13px;">in</a>
        </div>
      </div>
      <div>
        <h4>Fact-Checks</h4>
        <ul>
          <li><a href="real-or-fake.html">All fact-checks</a></li>
          <li><a href="real-or-fake.html?v=fake">Fake claims</a></li>
          <li><a href="real-or-fake.html?v=real">Real claims</a></li>
          <li><a href="real-or-fake.html?v=unverified">Not verified</a></li>
          <li><a href="archive.html">Archive</a></li>
        </ul>
      </div>
      <div>
        <h4>Analysis modules</h4>
        <ul>
          ${MODULES.map((m) => `<li><a href="verifier-module.html?v=12&m=${m.id}">${m.name}</a></li>`).join('')}
        </ul>
      </div>
      <div>
        <h4>About</h4>
        <ul>
          <li><a href="mission.html">Our mission</a></li>
          <li><a href="equipe.html">The team</a></li>
          <li><a href="methodologie.html">Methodology</a></li>
          <li><a href="dashboard.html">Statistics</a></li>
          <li><a href="packs.html">Plans &amp; pricing</a></li>
          <li><a href="#">Press contact</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <span>© 2026 Verify Tunisia. All rights reserved.</span>
      <span>Tunis · Sfax · Sousse</span>
    </div>
  </footer>
`;

const FullscreenMenu = () => `
  <div class="menu-overlay" id="menu-overlay" role="dialog" aria-modal="true" aria-label="Main menu" hidden>
    <div class="mo-top">
      <a href="index.html" class="mo-brand" aria-label="Verify — home">
        <img src="assets/img/logo-verify-white.png" alt="Verify" class="mo-brand-logo" />
      </a>
      <button type="button" class="mo-close" id="menu-close" aria-label="Close menu">✕</button>
    </div>

    <div class="mo-body">
      <span class="mo-tagline">Tunisia · Fact-checking platform</span>
      <nav class="mo-links">
        <a href="index.html">Home</a>
        <a href="real-or-fake.html">Fact-Checks</a>
        <a href="verifier.html">Verify a File</a>
        <a href="dashboard.html">Statistics</a>
        <a href="packs.html">Pricing</a>
        <a href="mission.html">About</a>
        <a href="equipe.html">The Team</a>
        <a href="methodologie.html">Methodology</a>
      </nav>

      <div class="mo-secondary">
        <a href="archive.html">Archive</a>
        <a href="connexion.html">Sign in</a>
        <a href="inscription.html">Create account</a>
        <a href="#">Press contact</a>
      </div>
    </div>

    <div class="mo-foot">
      <span>© 2026 Verify Tunisia</span>
      <span>Tunis · Sfax · Sousse</span>
    </div>
  </div>
`;

/* ── Verify Assistant — topic-restricted chatbot widget ──
   Auto-mounted next to the FAB. Talks to POST /api/chat/ask.
   Also accepts images/videos and routes them to /api/io1/analyze/* for an
   AI-generated / deepfake verdict, rendered inline. */
const VerifyChatWidget = () => `
  <div class="vchat" id="verify-chat" data-state="closed">
    <div class="vchat__panel" role="dialog" aria-labelledby="vchat-title" aria-hidden="true">
      <header class="vchat__head">
        <span class="vchat__kicker">${Icon.shield} Verify Assistant</span>
        <h3 id="vchat-title">Ask Verify</h3>
        <p>Ask about deepfakes, edits, fact-checking — or drop a photo / video to check if it's AI-generated.</p>
        <div class="vchat__head-actions">
          <button class="vchat__reset" id="vchat-reset" aria-label="New conversation" title="New conversation">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>
          </button>
          <button class="vchat__close" id="vchat-close" aria-label="Close">×</button>
        </div>
      </header>
      <div class="vchat__body" id="vchat-body" aria-live="polite"></div>
      <div class="vchat__foot">
        <div class="vchat__preview" id="vchat-preview" hidden></div>
        <form class="vchat__inputrow" id="vchat-form" autocomplete="off">
          <button type="button" class="vchat__attach" id="vchat-attach" aria-label="Attach an image or a video" title="Attach an image or a video">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
          </button>
          <input type="file" id="vchat-file" accept="image/*,video/*" hidden />
          <textarea class="vchat__input" id="vchat-input" rows="1"
            placeholder="Ask a question — or drop an image / video to check it…"
            maxlength="1500" aria-label="Your question"></textarea>
          <button class="vchat__send" id="vchat-send" type="submit" aria-label="Send">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg>
          </button>
        </form>
        <div class="vchat__hint">Verify Assistant handles <strong>media-verification</strong> topics only.</div>
      </div>
    </div>
    <button class="vchat__launcher" id="vchat-launcher" aria-label="Open Verify Assistant" aria-expanded="false">
      <span class="vchat__avatar" aria-hidden="true">V</span>
      <span class="vchat__label">Ask Verify</span>
      <span class="vchat__chev" aria-hidden="true">▲</span>
    </button>
  </div>
`;

const VerifyFAB = () => `
  <div class="fab" id="verify-fab">
    <div class="fab-menu" id="fab-menu">
      <h4>Verify now</h4>
      <div class="fab-list">
        ${MODULES.map((m) => `
          <a href="verifier-module.html?v=12&m=${m.id}">
            <span class="icon-tile sm" style="background:${m.bg};color:${m.fg};">${m.icon}</span>
            <span><strong>${m.short}</strong> · ${m.name}</span>
          </a>
        `).join('')}
        <a href="verifier.html" style="border-top:1px solid var(--line);margin-top:6px;padding-top:10px;font-weight:700;color:var(--navy);">
          → View all modules
        </a>
      </div>
    </div>
    <button class="fab-btn" id="fab-toggle">
      <span class="pulse"></span>
      ${Icon.shield}
      Verify
    </button>
  </div>
`;

document.addEventListener('DOMContentLoaded', () => {
  // Header
  const headerMount = document.getElementById('site-header');
  if (headerMount) {
    const slim = headerMount.dataset.slim === 'true';
    headerMount.innerHTML = VerifyHeader({ slim });

    // Sticky navbar — pin shadow on scroll
    const navyNav = headerMount.querySelector('.navy-nav');
    if (navyNav) {
      const onScroll = () => {
        navyNav.classList.toggle('is-pinned', window.scrollY > 40);
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }
  }

  // Footer
  const footerMount = document.getElementById('site-footer');
  if (footerMount) footerMount.innerHTML = VerifyFooter();

  // Fullscreen menu overlay (mounted once, shared across all pages)
  document.body.insertAdjacentHTML('beforeend', FullscreenMenu());
  const overlay = document.getElementById('menu-overlay');
  const burger  = document.querySelector('.navy-nav .burger');
  const closeBtn = document.getElementById('menu-close');

  function openMenu() {
    if (!overlay) return;
    overlay.hidden = false;
    requestAnimationFrame(() => overlay.classList.add('is-open'));
    document.body.classList.add('menu-open');
    if (closeBtn) closeBtn.focus();
  }
  function closeMenu() {
    if (!overlay) return;
    overlay.classList.remove('is-open');
    document.body.classList.remove('menu-open');
    setTimeout(() => { overlay.hidden = true; }, 350);
    if (burger) burger.focus();
  }

  if (burger) burger.addEventListener('click', openMenu);
  if (closeBtn) closeBtn.addEventListener('click', closeMenu);
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeMenu();
    });
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay && !overlay.hidden) closeMenu();
  });

  // FAB — auto-injected on every page (unless explicitly disabled)
  if (document.body.dataset.fab !== 'off') {
    document.body.insertAdjacentHTML('beforeend', VerifyFAB());
    const toggle = document.getElementById('fab-toggle');
    const menu   = document.getElementById('fab-menu');
    if (toggle && menu) {
      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.toggle('open');
      });
      document.addEventListener('click', (e) => {
        if (!document.getElementById('verify-fab').contains(e.target)) {
          menu.classList.remove('open');
        }
      });
    }
  }

  // Verify Assistant (chatbot) — auto-injected unless data-chatbot="off"
  if (document.body.dataset.chatbot !== 'off') {
    document.body.insertAdjacentHTML('beforeend', VerifyChatWidget());
    if (window.VerifyChat && typeof window.VerifyChat.mount === 'function') {
      window.VerifyChat.mount();
    }
  }

  // Scroll reveal — IntersectionObserver-based
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('in');
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );
    document
      .querySelectorAll('[data-reveal], [data-reveal-stagger]')
      .forEach((el) => io.observe(el));
  } else {
    document
      .querySelectorAll('[data-reveal], [data-reveal-stagger]')
      .forEach((el) => el.classList.add('in'));
  }

  // Animate stats counters when they enter the viewport
  const counters = document.querySelectorAll('.stats-band .num[data-count-to]');
  if (counters.length && 'IntersectionObserver' in window) {
    const cio = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        const el = e.target;
        const target = parseFloat(el.dataset.countTo);
        const suffix = el.dataset.countSuffix || '';
        const decimals = parseInt(el.dataset.countDecimals || '0', 10);
        let current = 0;
        const start = performance.now();
        const dur = 1200;
        const step = (now) => {
          const t = Math.min(1, (now - start) / dur);
          const eased = 1 - Math.pow(1 - t, 3);
          current = target * eased;
          el.textContent = current.toFixed(decimals) + suffix;
          if (t < 1) requestAnimationFrame(step);
          else el.textContent = target.toFixed(decimals) + suffix;
        };
        requestAnimationFrame(step);
        cio.unobserve(el);
      });
    }, { threshold: 0.5 });
    counters.forEach((el) => cio.observe(el));
  }

  // Auto-scrolling marquees — duplicate the track content once so the
  // CSS translateX(-50%) loop is seamless. Honour reduced-motion.
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('.marquee').forEach((mq) => {
    const track = mq.querySelector('.marquee__track');
    if (!track || track.dataset.cloned === 'true') return;
    track.dataset.cloned = 'true';
    track.innerHTML += track.innerHTML;
    // Scale duration to content width so speed stays consistent across strips
    if (!reduceMotion) {
      requestAnimationFrame(() => {
        const px = track.scrollWidth / 2;
        const speed = parseFloat(mq.dataset.speed || '70'); // px per second
        track.style.animationDuration = Math.max(14, px / speed) + 's';
      });
    }
  });
});

window.VERIFY_MODULES = MODULES;

/* ─────────────────────────────────────────────────────────────────────────
   XAI — "Reading the result"
   Shared, jargon-free card that presents the AI-written explanation attached
   by the backend to `data.narrative` ({headline, confidence_label, summary,
   signals[], checked[], caveat}). Used by the result renderers of all 5
   modules: window.VerifyXAI.narrativeCard(narrative, opts).
   ───────────────────────────────────────────────────────────────────────── */
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const CONF = {
    'almost certain': { pct: 96, tone: 'hi' },
    'very likely': { pct: 86, tone: 'hi' },
    'likely': { pct: 72, tone: 'mid' },
    'plausible — to confirm': { pct: 55, tone: 'lo' },
    'plausible - to confirm': { pct: 55, tone: 'lo' },
    'plausible': { pct: 55, tone: 'lo' },
    'uncertain': { pct: 38, tone: 'lo' },
  };
  function confMeta(label) {
    return CONF[String(label || '').toLowerCase().trim()] || { pct: 70, tone: 'mid' };
  }

  // verdict colour family, inferred from a free-text string
  function familyFor(hint) {
    const v = String(hint || '').toLowerCase();
    if (/suspect|suspici|to confirm|unconfirmed|uncertain|nuance|caution|doubt|needs review|to verify|to examine|inconclusive/.test(v)) return 'warn';
    if (/\b(fake|deepfake)\b|swapp|incoher|mislead|deceptiv|alter|tamper|manipul|generat|fabricat|retouch|edited|exagger|overstat|false\b|unproven|not proven/.test(v)) return 'alert';
    if (/authent|reliable|coheren|faithful|genuine|compliant|\breal\b|\bok\b|honest|credible|proven|trustworth/.test(v)) return 'ok';
    return 'neutral';
  }

  const ICO = {
    ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m18 6-12 12M6 6l12 12"/></svg>',
    warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
    neutral: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7h.01M11 11h1v5h1"/></svg>',
    sig: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6 7.8 7.8M16.2 16.2l2.2 2.2M18.4 5.6l-2.2 2.2M7.8 16.2l-2.2 2.2"/><circle cx="12" cy="12" r="3.2"/></svg>',
    chk: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  };

  /**
   * narrative : { headline, confidence_label, summary, signals[], checked[], caveat }
   * opts : { accent:'#hex' (module colour), verdictHint:string }
   * → returns the card HTML, or '' if there's nothing usable.
   */
  function narrativeCard(narrative, opts) {
    const n = narrative || {};
    if (!n.summary && !(Array.isArray(n.signals) && n.signals.length)) return '';
    opts = opts || {};
    const fam = familyFor(opts.verdictHint || n.headline || '');
    const cm = confMeta(n.confidence_label);
    const accent = opts.accent || '#052962';
    const sig = (n.signals || []).filter(Boolean).slice(0, 4);
    const chk = (n.checked || []).filter(Boolean).slice(0, 4);
    return `
      <section class="xai-read xai-read--${fam} xai-read--c${cm.tone}" style="--xai-accent:${esc(accent)};">
        <div class="xai-read__rail" aria-hidden="true"></div>
        <header class="xai-read__head">
          <span class="xai-read__kicker">Reading the result — in plain words</span>
          <div class="xai-read__verdict">
            <span class="xai-read__ico">${ICO[fam] || ICO.neutral}</span>
            <h3>${esc(n.headline || "Analysis result")}</h3>
          </div>
          ${n.confidence_label ? `
          <div class="xai-read__conf" title="How certain the analysis is">
            <div class="xai-read__conf-bar"><i style="width:${cm.pct}%"></i></div>
            <span class="xai-read__conf-lbl">${esc(n.confidence_label)}</span>
          </div>` : ''}
        </header>
        ${n.summary ? `<p class="xai-read__lede">${esc(n.summary)}</p>` : ''}
        ${(sig.length || chk.length) ? `
        <div class="xai-read__cols">
          ${sig.length ? `
          <div class="xai-read__col">
            <div class="xai-read__col-h">${ICO.sig}<span>What led us to this verdict</span></div>
            <ul>${sig.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>
          </div>` : ''}
          ${chk.length ? `
          <div class="xai-read__col xai-read__col--checked">
            <div class="xai-read__col-h">${ICO.chk}<span>What the analysis reviewed</span></div>
            <ul>${chk.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>
          </div>` : ''}
        </div>` : ''}
        ${n.caveat ? `<p class="xai-read__note">${esc(n.caveat)}</p>` : ''}
        <div class="xai-read__sign" aria-hidden="true">Reading written by Verify · AI — assisted verification</div>
      </section>`;
  }

  window.VerifyXAI = { narrativeCard, confMeta, familyFor, escapeHtml: esc };
})();

/* ─────────────────────────────────────────────────────────────
   Verify Assistant — runtime
   Renders messages, talks to POST /api/chat/ask, and persists the
   conversation per-tab in sessionStorage so it survives navigation.
───────────────────────────────────────────────────────────── */
(function () {
  const STORAGE_KEY = 'verify-chat-history-v1';
  const API_BASE = () => (window.VERIFY_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  // Minimal safe markdown: **bold**, *italic*, `code`, and line breaks.
  function lightFormat(text) {
    let s = esc(text);
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|\s)\*([^*\s][^*]*[^*\s])\*(?=\s|$)/g, '$1<em>$2</em>');
    s = s.replace(/\n/g, '<br>');
    return s;
  }

  const SUGGESTIONS = [
    'How can I spot an AI-generated photo?',
    'What does the Photoshop Forensics module check?',
    'Why is this caption misleading?',
    'How does Verify rate a cosmetic ad?',
  ];

  const WELCOME = "Hi — I'm the Verify Assistant. Ask me about deepfakes, AI-generated images, edited photos, misleading captions, or how to use the Verify platform. I only answer questions on these topics.";

  function loadHistory() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr.slice(-24) : [];
    } catch { return []; }
  }
  function saveHistory(arr) {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(arr.slice(-24))); } catch {}
  }

  function bubbleHTML(msg) {
    const isUser = msg.role === 'user';
    const side = isUser ? 'user' : 'assistant';
    const mini = isUser ? '' : '<span class="vchat__mini" aria-hidden="true">V</span>';

    // Media attachment bubble (user-uploaded image / video)
    if (msg.kind === 'media') {
      const inner = msg.media_type === 'video'
        ? `<div class="vchat__media vchat__media--video"><span class="vchat__media-ico">🎬</span><span class="vchat__media-name">${esc(msg.name || 'video')}</span></div>`
        : `<div class="vchat__media"><img src="${esc(msg.thumb || '')}" alt="" /></div>`;
      return `
        <div class="vchat__msg vchat__msg--${side}">
          ${mini}
          <div class="vchat__bubble vchat__bubble--media">
            ${inner}
            ${msg.content ? `<div class="vchat__media-cap">${esc(msg.content)}</div>` : ''}
          </div>
        </div>`;
    }

    // Verdict bubble (assistant — result of an io1 analysis)
    if (msg.kind === 'verdict') {
      const v = msg.verdict || {};
      const tone = v.tone || 'neutral';
      const ico = tone === 'alert'
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>'
        : tone === 'ok'
          ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
          : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 17h.01"/></svg>';
      const sigList = (v.signals && v.signals.length)
        ? `<ul class="vchat__verdict-sig">${v.signals.slice(0,3).map((s) => `<li>${esc(s)}</li>`).join('')}</ul>`
        : '';
      return `
        <div class="vchat__msg vchat__msg--assistant">
          ${mini}
          <div class="vchat__bubble vchat__bubble--verdict vchat__verdict--${tone}">
            <div class="vchat__verdict-head">
              <span class="vchat__verdict-ico">${ico}</span>
              <div>
                <div class="vchat__verdict-title">${esc(v.headline || 'Analysis verdict')}</div>
                ${v.confidence ? `<div class="vchat__verdict-conf">${esc(v.confidence)}</div>` : ''}
              </div>
            </div>
            ${v.summary ? `<p class="vchat__verdict-sum">${esc(v.summary)}</p>` : ''}
            ${sigList}
            ${v.caveat ? `<p class="vchat__verdict-note">${esc(v.caveat)}</p>` : ''}
          </div>
        </div>`;
    }

    return `
      <div class="vchat__msg vchat__msg--${side}">
        ${mini}
        <div class="vchat__bubble">${lightFormat(msg.content)}</div>
      </div>`;
  }

  function suggestionsHTML() {
    return `
      <div class="vchat__suggest" id="vchat-suggest">
        ${SUGGESTIONS.map((s) => `<button class="vchat__chip" type="button" data-q="${esc(s)}">${esc(s)}</button>`).join('')}
      </div>`;
  }

  function typingHTML() {
    return `
      <div class="vchat__msg vchat__msg--assistant" id="vchat-typing">
        <span class="vchat__mini" aria-hidden="true">V</span>
        <div class="vchat__bubble vchat__typing"><span></span><span></span><span></span></div>
      </div>`;
  }

  function render(state) {
    const body = document.getElementById('vchat-body');
    if (!body) return;
    let html = '';
    if (!state.history.length) {
      html += bubbleHTML({ role: 'assistant', content: WELCOME });
      html += suggestionsHTML();
    } else {
      state.history.forEach((m) => { html += bubbleHTML(m); });
    }
    if (state.pending) html += typingHTML();
    body.innerHTML = html;
    requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
  }

  async function callBackend(history) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 35000);
    try {
      const r = await fetch(`${API_BASE()}/api/chat/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history }),
        signal: ctrl.signal,
      });
      clearTimeout(t);
      if (!r.ok) throw new Error('http ' + r.status);
      const json = await r.json();
      return (json && typeof json.reply === 'string' && json.reply.trim())
        ? json.reply.trim()
        : null;
    } catch (e) {
      clearTimeout(t);
      return null;
    }
  }

  function offlineReply() {
    return "I can't reach the Verify backend right now. Make sure the API is running (uvicorn backend.main:app --port 8000) and try again.";
  }

  function formatBytes(n) {
    if (!Number.isFinite(n)) return '';
    const u = ['B','KB','MB','GB'];
    let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return n.toFixed(n >= 10 || i === 0 ? 0 : 1) + ' ' + u[i];
  }

  function fileToDataURL(f) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result || ''));
      r.onerror = () => reject(r.error);
      r.readAsDataURL(f);
    });
  }

  // Upload to io1 — returns a normalised verdict object or null on failure.
  async function callIO1(file, isVideo) {
    const endpoint = isVideo ? '/api/io1/analyze/video' : '/api/io1/analyze/image';
    const fd = new FormData();
    fd.append(isVideo ? 'video' : 'image', file, file.name || (isVideo ? 'clip.mp4' : 'image.jpg'));
    if (!isVideo) fd.append('mode', 'auto');

    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 120000); // image/video analysis is slower than chat
    try {
      const r = await fetch(`${API_BASE()}${endpoint}`, { method: 'POST', body: fd, signal: ctrl.signal });
      clearTimeout(t);
      if (!r.ok) return null;
      const data = await r.json();
      return normaliseVerdict(data, isVideo);
    } catch {
      clearTimeout(t);
      return null;
    }
  }

  function normaliseVerdict(data, isVideo) {
    if (!data || typeof data !== 'object') return null;
    const n = data.narrative || {};
    const cls = String(data.verdict_class || data.verdict || '').toLowerCase();
    const isAi = String(data.verdict_kind || data.kind || '').toLowerCase() === 'ai';
    const isFake = cls === 'fake' || cls === 'ai-generated' || cls === 'ai_generated' || isAi;
    const label = n.headline
      || data.verdict_label
      || (isFake
        ? (isAi ? 'AI-generated media' : (isVideo ? 'Faked face (deepfake)' : 'Likely manipulated'))
        : (isVideo ? 'Authentic video' : 'Authentic image'));
    const tone = isFake ? 'alert' : (cls === 'real' || cls === 'authentic' ? 'ok' : 'neutral');
    return {
      tone,
      headline: label,
      confidence: n.confidence_label || '',
      summary: n.summary || data.verdict_explanation || '',
      signals: Array.isArray(n.signals) ? n.signals : [],
      caveat: n.caveat || '',
    };
  }

  function mount() {
    const root = document.getElementById('verify-chat');
    if (!root) return;

    const launcher = document.getElementById('vchat-launcher');
    const closeBtn = document.getElementById('vchat-close');
    const resetBtn = document.getElementById('vchat-reset');
    const form = document.getElementById('vchat-form');
    const input = document.getElementById('vchat-input');
    const sendBtn = document.getElementById('vchat-send');
    const attachBtn = document.getElementById('vchat-attach');
    const fileInput = document.getElementById('vchat-file');
    const previewBox = document.getElementById('vchat-preview');
    const panel = root.querySelector('.vchat__panel');

    const state = { history: loadHistory(), pending: false, pendingFile: null, pendingFileURL: null };
    render(state);

    function open() {
      root.classList.add('is-open');
      root.dataset.state = 'open';
      launcher.setAttribute('aria-expanded', 'true');
      if (panel) panel.setAttribute('aria-hidden', 'false');
      setTimeout(() => input && input.focus(), 50);
    }
    function close() {
      root.classList.remove('is-open');
      root.dataset.state = 'closed';
      launcher.setAttribute('aria-expanded', 'false');
      if (panel) panel.setAttribute('aria-hidden', 'true');
    }
    function toggle() { root.classList.contains('is-open') ? close() : open(); }

    launcher.addEventListener('click', toggle);
    if (closeBtn) closeBtn.addEventListener('click', close);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && root.classList.contains('is-open')) close();
    });

    // Suggestion chips (event-delegation, since they may re-render)
    root.addEventListener('click', (e) => {
      const chip = e.target.closest && e.target.closest('.vchat__chip');
      if (!chip) return;
      const q = chip.dataset.q || chip.textContent || '';
      if (q.trim()) ask(q.trim());
    });

    // Auto-grow textarea
    function grow() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 110) + 'px';
    }
    input.addEventListener('input', grow);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
      }
    });

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      if (state.pending) return;
      const q = (input.value || '').trim();
      const f = state.pendingFile;
      if (!q && !f) return;
      input.value = '';
      grow();
      if (f) {
        clearPreview();
        analyzeFile(f, q);
      } else {
        ask(q);
      }
    });

    // ── Attachments ──
    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      const f = fileInput.files && fileInput.files[0];
      fileInput.value = ''; // allow re-picking the same file
      if (!f) return;
      acceptFile(f);
    });

    // Drag & drop on the panel
    panel.addEventListener('dragover', (e) => {
      if (e.dataTransfer && [...e.dataTransfer.items].some((it) => it.kind === 'file')) {
        e.preventDefault();
        panel.classList.add('is-drop');
      }
    });
    panel.addEventListener('dragleave', () => panel.classList.remove('is-drop'));
    panel.addEventListener('drop', (e) => {
      panel.classList.remove('is-drop');
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f) return;
      e.preventDefault();
      acceptFile(f);
    });

    function acceptFile(f) {
      const kind = f.type.startsWith('video/') ? 'video' : f.type.startsWith('image/') ? 'image' : null;
      if (!kind) {
        state.history.push({ role: 'assistant', content: 'Sorry — I can only check images and videos.' });
        saveHistory(state.history); render(state);
        return;
      }
      const MAX = 50 * 1024 * 1024; // 50 MB
      if (f.size > MAX) {
        state.history.push({ role: 'assistant', content: 'That file is over 50 MB — try a smaller version, please.' });
        saveHistory(state.history); render(state);
        return;
      }
      if (state.pendingFileURL) { URL.revokeObjectURL(state.pendingFileURL); }
      state.pendingFile = f;
      state.pendingFileURL = URL.createObjectURL(f);
      showPreview(f, kind);
    }

    function showPreview(f, kind) {
      const isImg = kind === 'image';
      previewBox.hidden = false;
      previewBox.innerHTML = `
        <div class="vchat__prev-card">
          ${isImg
            ? `<img src="${state.pendingFileURL}" alt="" />`
            : `<span class="vchat__prev-vid">🎬</span>`}
          <div class="vchat__prev-meta">
            <div class="vchat__prev-name">${esc(f.name || (isImg ? 'image' : 'video'))}</div>
            <div class="vchat__prev-sub">${isImg ? 'Image' : 'Video'} · ${formatBytes(f.size)} — ready to verify</div>
          </div>
          <button type="button" class="vchat__prev-x" id="vchat-prev-x" aria-label="Remove">×</button>
        </div>`;
      const xBtn = document.getElementById('vchat-prev-x');
      if (xBtn) xBtn.addEventListener('click', clearPreview);
    }

    function clearPreview() {
      if (state.pendingFileURL) { URL.revokeObjectURL(state.pendingFileURL); state.pendingFileURL = null; }
      state.pendingFile = null;
      previewBox.hidden = true;
      previewBox.innerHTML = '';
    }

    async function ask(q) {
      state.history.push({ role: 'user', content: q });
      state.pending = true;
      sendBtn.disabled = true;
      render(state);

      const reply = await callBackend(state.history);
      state.pending = false;
      sendBtn.disabled = false;
      state.history.push({ role: 'assistant', content: reply || offlineReply() });
      saveHistory(state.history);
      render(state);
    }

    async function analyzeFile(f, caption) {
      const isVideo = f.type.startsWith('video/');
      // Thumbnail data URL for images so it survives storage / re-render
      let thumb = null;
      if (!isVideo) {
        try { thumb = await fileToDataURL(f); } catch {}
      }
      state.history.push({
        role: 'user',
        kind: 'media',
        media_type: isVideo ? 'video' : 'image',
        name: f.name,
        thumb,
        content: caption || '',
      });
      state.pending = true;
      sendBtn.disabled = true;
      render(state);

      const verdict = await callIO1(f, isVideo);
      state.pending = false;
      sendBtn.disabled = false;

      if (verdict) {
        state.history.push({ role: 'assistant', kind: 'verdict', verdict });
      } else {
        state.history.push({
          role: 'assistant',
          content: "I couldn't analyse that file. Make sure the Verify backend is running and try again — or use the dedicated AI-Generated Media module for a full report.",
        });
      }
      saveHistory(state.history);
      render(state);
    }

    // Public API: programmatic open + reset
    window.VerifyChat.open = open;
    window.VerifyChat.close = close;
    window.VerifyChat.reset = () => {
      clearPreview();
      state.history = [];
      saveHistory([]);
      render(state);
    };

    if (resetBtn) resetBtn.addEventListener('click', () => window.VerifyChat.reset());
  }

  window.VerifyChat = { mount };
})();
