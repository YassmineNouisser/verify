/* Partner fact-checks (Tunifact / iCheck) — front-end aggregator.
   Mock data for now. To plug a backend, replace fetchPartnerFactChecks()
   with a real fetch() to your endpoint that returns the same shape.
*/

const PARTNER_FACT_CHECKS_MOCK = [
  {
    source: 'Tunifact',
    sourceUrl: 'https://tunifact.org',
    verdict: 'fake',
    title: 'No, this photo does not show a recent earthquake in Kasserine',
    excerpt:
      'The image has been circulating since yesterday on Facebook with the caption "earthquake morning of May 8." Reverse image search: the photo is from Hatay, Turkey, February 2023.',
    date: '2026-05-09',
    url: 'https://tunifact.org/article/kasserine-earthquake-fake',
    image: 'https://images.unsplash.com/photo-1635322966219-b75ed372eb01?auto=format&fit=crop&w=600&q=80',
  },
  {
    source: 'iCheck',
    sourceUrl: 'https://icheck.tn',
    verdict: 'misleading',
    title: 'Is this video of a protest in Tunis really from today?',
    excerpt:
      "The viral video (320k views) actually dates from the January 2024 mobilization — reposted out of context on X.",
    date: '2026-05-08',
    url: 'https://icheck.tn/tunis-protest-may-2026',
    image: 'https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=600&q=80',
  },
  {
    source: 'Tunifact',
    sourceUrl: 'https://tunifact.org',
    verdict: 'fake',
    title: 'No official curfew decision in Sfax this weekend',
    excerpt:
      'A "Sfax governorate" notice is circulating on WhatsApp. Verification: fake logo, spelling errors, no official reference number.',
    date: '2026-05-07',
    url: 'https://tunifact.org/article/sfax-curfew-fake',
    image: 'https://images.unsplash.com/photo-1488521787991-ed7bbaae773c?auto=format&fit=crop&w=600&q=80',
  },
  {
    source: 'iCheck',
    sourceUrl: 'https://icheck.tn',
    verdict: 'real',
    title: 'Yes, the Ministry of Health has launched the 2026 vaccination campaign',
    excerpt:
      "The decree was published in the JORT on May 5. Cross-confirmed with two hospital sources and the official website.",
    date: '2026-05-06',
    url: 'https://icheck.tn/vaccination-2026-confirmed',
    image: 'https://images.unsplash.com/photo-1581094794329-c8112a89af12?auto=format&fit=crop&w=600&q=80',
  },
  {
    source: 'Tunifact',
    sourceUrl: 'https://tunifact.org',
    verdict: 'out-of-context',
    title: "This image of a border checkpoint was not taken this week",
    excerpt:
      'Authentic image but dated July 2022, during the temporary closure of the Ras Jedir crossing.',
    date: '2026-05-05',
    url: 'https://tunifact.org/article/border-out-of-context',
    image: 'https://images.unsplash.com/photo-1605792657660-596af9009e82?auto=format&fit=crop&w=600&q=80',
  },
  {
    source: 'iCheck',
    sourceUrl: 'https://icheck.tn',
    verdict: 'misleading',
    title: 'The "IMF report" circulating in Arabic contains altered figures',
    excerpt:
      'The shared PDF reuses the official layout but pages 4 and 7 have been edited: growth rate changed from 2.1% to 0.3%.',
    date: '2026-05-04',
    url: 'https://icheck.tn/imf-report-altered',
    image: 'https://images.unsplash.com/photo-1554224155-1696413565d3?auto=format&fit=crop&w=600&q=80',
  },
];

const VERDICT_STYLES = {
  real:             { label: 'Real',           cls: 'pv-ok'      },
  fake:             { label: 'Fake',           cls: 'pv-fake'    },
  misleading:       { label: 'Misleading',     cls: 'pv-suspect' },
  'out-of-context': { label: 'Out of context', cls: 'pv-suspect' },
};

const SOURCE_STYLES = {
  Tunifact: { color: '#dc2626', bg: '#fee2e2' },
  iCheck:   { color: '#1e3a8a', bg: '#dbeafe' },
};

async function fetchPartnerFactChecks() {
  // Backend hook — when ready, replace the mock with:
  // const r = await fetch('/api/partners/fact-checks?limit=6');
  // return r.json();
  return new Promise((resolve) => setTimeout(() => resolve(PARTNER_FACT_CHECKS_MOCK), 250));
}

function formatDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
}

function renderPartnerCard(item) {
  const v = VERDICT_STYLES[item.verdict] || VERDICT_STYLES.misleading;
  const s = SOURCE_STYLES[item.source] || { color: '#052962', bg: '#eef1f7' };
  return `
    <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="pn-card">
      <div class="pn-thumb">
        <img src="${item.image}" alt="" loading="lazy" />
        <span class="pn-verdict ${v.cls}">${v.label}</span>
      </div>
      <div class="pn-body">
        <span class="pn-source" style="background:${s.bg};color:${s.color};">${item.source}</span>
        <h3>${item.title}</h3>
        <p>${item.excerpt}</p>
        <div class="pn-meta">
          <span>${formatDate(item.date)}</span>
          <span class="pn-link">Read on ${item.source} →</span>
        </div>
      </div>
    </a>
  `;
}

document.addEventListener('DOMContentLoaded', async () => {
  const mount = document.getElementById('partner-news-mount');
  if (!mount) return;

  mount.innerHTML = `
    <div class="pn-skeleton" aria-hidden="true">
      ${Array.from({ length: 3 }).map(() => '<div class="pn-skel-card"></div>').join('')}
    </div>
  `;

  try {
    const items = await fetchPartnerFactChecks();
    mount.innerHTML = items.map(renderPartnerCard).join('');
  } catch (e) {
    mount.innerHTML = `<div class="pn-empty">Could not load partner fact-checks right now.</div>`;
  }
});
