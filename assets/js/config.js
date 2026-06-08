/*
 * Verify — frontend → backend URL resolver.
 *
 * Loaded BEFORE all other module JS files (synthesis.js, coherence.js, etc.).
 * Each module reads window.VERIFY_API_URL to know where to send /api/* requests.
 *
 * Auto-detection rules:
 *   • file:// or localhost:5500       → backend assumed on http://localhost:8000 (Live Server dev)
 *   • everything else (HF Space, GitHub Pages mirror, prod domain) → empty string = same-domain
 *
 * Override (e.g. when developing the frontend against a remote backend):
 *   window.VERIFY_API_URL = 'https://your-username-verify.hf.space';
 *   <script src="assets/js/config.js"></script>      ← include this AFTER the override
 *
 * The empty-string default makes every fetch a relative URL like `/api/io1/analyze/image`,
 * which works when FastAPI serves both the static frontend and the API on the same port
 * (this is the HuggingFace Space / single-container deployment).
 */
(function () {
  // Respect any value already set by a previous inline <script>
  if (typeof window.VERIFY_API_URL === 'string') return;

  var host = (window.location.hostname || '').toLowerCase();
  var port = window.location.port || '';
  var protocol = window.location.protocol || '';

  var isLocalLiveServer =
    (host === 'localhost' || host === '127.0.0.1') && (port === '5500' || port === '5501' || port === '5502');
  var isFileProtocol = protocol === 'file:';

  if (isLocalLiveServer || isFileProtocol) {
    // Live Server / opened-as-file workflow → talk to the dev backend.
    window.VERIFY_API_URL = 'http://localhost:8000';
  } else {
    // HF Space, GitHub Pages with same-domain backend, or any deployed environment.
    // Use window.location.origin (NOT empty string) — because modules use the pattern
    //   `(window.VERIFY_API_URL || 'http://localhost:8000')`
    // and '' is falsy in JavaScript, so the fallback to localhost would kick in. With the
    // explicit origin (e.g. "https://yassmine1211-verify.hf.space") the OR keeps it intact.
    window.VERIFY_API_URL = window.location.origin;
  }
})();
