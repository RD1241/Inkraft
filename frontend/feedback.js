/* feedback.js — self-contained private beta-feedback widget.
   Injects a floating "Feedback" button + modal; POSTs to /api/feedback.
   No external CSS/JS deps. Include with <script src="feedback.js" defer></script>. */
(function () {
  if (window.__inkraftFeedbackLoaded) return;
  window.__inkraftFeedbackLoaded = true;

  var ACCENT = '#e8324a';
  var state = { rating: 0, wouldUse: '' };

  function el(tag, css, html) {
    var e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (html != null) e.innerHTML = html;
    return e;
  }

  // Floating button
  var btn = el('button', [
    'position:fixed', 'right:18px', 'bottom:18px', 'z-index:9998',
    'background:' + ACCENT, 'color:#fff', 'border:3px solid #000',
    'box-shadow:4px 4px 0 #000', 'border-radius:0', 'padding:0.6rem 0.9rem',
    'font-weight:800', 'font-family:inherit', 'cursor:pointer', 'font-size:0.9rem'
  ].join(';'), '💬 Feedback');
  btn.setAttribute('aria-label', 'Leave feedback');

  // Overlay + modal
  var overlay = el('div', [
    'position:fixed', 'inset:0', 'background:rgba(0,0,0,0.85)', 'z-index:10000',
    'display:none', 'align-items:center', 'justify-content:center', 'padding:1rem'
  ].join(';'));

  var card = el('div', [
    'width:100%', 'max-width:460px', 'background:#111', 'border:3px solid #000',
    'box-shadow:6px 6px 0 #000', 'padding:1.5rem', 'color:#e0e0e0',
    'font-family:inherit', 'position:relative', 'max-height:90vh', 'overflow:auto'
  ].join(';'));

  card.appendChild(el('h3', 'margin:0 0 0.25rem;color:' + ACCENT + ';font-size:1.3rem;text-transform:uppercase;letter-spacing:0.5px;', 'Tell us what you think'));
  card.appendChild(el('p', 'margin:0 0 1rem;font-size:0.85rem;opacity:0.8;', "You're using an early beta. Your honest feedback shapes what we build next — it's private."));

  // Rating
  card.appendChild(el('div', 'font-size:0.8rem;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:0.3rem;opacity:0.9;', 'Rating'));
  var stars = el('div', 'font-size:1.8rem;letter-spacing:0.2rem;margin-bottom:1rem;cursor:pointer;user-select:none;');
  function renderStars() {
    stars.innerHTML = '';
    for (var i = 1; i <= 5; i++) {
      (function (n) {
        var s = el('span', 'color:' + (n <= state.rating ? '#f5c518' : '#555') + ';', '★');
        s.onclick = function () { state.rating = n; renderStars(); };
        stars.appendChild(s);
      })(i);
    }
  }
  renderStars();
  card.appendChild(stars);

  // Would use?
  card.appendChild(el('div', 'font-size:0.8rem;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:0.3rem;opacity:0.9;', 'Would you use Inkraft?'));
  var useWrap = el('div', 'display:flex;gap:0.5rem;margin-bottom:1rem;flex-wrap:wrap;');
  var useBtns = {};
  ['yes', 'maybe', 'no'].forEach(function (v) {
    var b = el('button', [
      'flex:1', 'min-width:80px', 'padding:0.5rem', 'border:2px solid #000',
      'box-shadow:2px 2px 0 #000', 'background:#222', 'color:#ddd', 'cursor:pointer',
      'font-weight:700', 'text-transform:capitalize', 'font-family:inherit'
    ].join(';'), v);
    b.onclick = function () {
      state.wouldUse = v;
      Object.keys(useBtns).forEach(function (k) {
        useBtns[k].style.background = '#222'; useBtns[k].style.color = '#ddd';
      });
      b.style.background = ACCENT; b.style.color = '#fff';
    };
    useBtns[v] = b; useWrap.appendChild(b);
  });
  card.appendChild(useWrap);

  // Message
  card.appendChild(el('div', 'font-size:0.8rem;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:0.3rem;opacity:0.9;', 'How do you feel about it?'));
  var ta = el('textarea', [
    'width:100%', 'min-height:90px', 'background:#000', 'color:#fff',
    'border:2px solid #000', 'box-shadow:2px 2px 0 #000', 'padding:0.6rem',
    'font-family:inherit', 'font-size:0.9rem', 'box-sizing:border-box', 'resize:vertical'
  ].join(';'));
  ta.placeholder = 'What did you like? What felt off? Would you tell a friend? (max 2000 chars)';
  ta.maxLength = 2000;
  card.appendChild(ta);

  var msg = el('div', 'font-size:0.85rem;margin:0.6rem 0 0;min-height:1em;');

  var actions = el('div', 'display:flex;gap:0.6rem;margin-top:1rem;');
  var submit = el('button', [
    'flex:2', 'padding:0.7rem', 'background:' + ACCENT, 'color:#fff',
    'border:3px solid #000', 'box-shadow:3px 3px 0 #000', 'font-weight:800',
    'cursor:pointer', 'font-family:inherit', 'text-transform:uppercase'
  ].join(';'), 'Send feedback');
  var cancel = el('button', [
    'flex:1', 'padding:0.7rem', 'background:#222', 'color:#ccc',
    'border:2px solid #000', 'box-shadow:2px 2px 0 #000', 'cursor:pointer',
    'font-family:inherit'
  ].join(';'), 'Close');
  actions.appendChild(submit); actions.appendChild(cancel);
  card.appendChild(actions);
  card.appendChild(msg);

  overlay.appendChild(card);

  function open() { overlay.style.display = 'flex'; }
  function close() { overlay.style.display = 'none'; }
  btn.onclick = open;
  cancel.onclick = close;
  overlay.onclick = function (e) { if (e.target === overlay) close(); };

  submit.onclick = function () {
    if (!state.rating && !ta.value.trim() && !state.wouldUse) {
      msg.style.color = '#f5c518'; msg.textContent = 'Add a rating, a note, or pick an option first.';
      return;
    }
    submit.disabled = true; submit.textContent = 'Sending…';
    var headers = { 'Content-Type': 'application/json' };
    try {
      var tok = localStorage.getItem('ntc_token');
      if (tok) headers['Authorization'] = 'Bearer ' + tok;
    } catch (e) {}
    fetch('/api/feedback', {
      method: 'POST', headers: headers,
      body: JSON.stringify({
        rating: state.rating || null,
        would_use: state.wouldUse || null,
        message: ta.value.trim(),
        page: location.pathname
      })
    }).then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function () {
        msg.style.color = '#2ecc71';
        card.innerHTML = '<h3 style="color:' + ACCENT + ';margin:0 0 0.5rem;">Thank you! 🙏</h3>'
          + '<p style="opacity:0.85;">Your feedback went straight to the team. It genuinely helps.</p>';
        setTimeout(close, 1600);
      })
      .catch(function () {
        submit.disabled = false; submit.textContent = 'Send feedback';
        msg.style.color = '#e8324a'; msg.textContent = 'Could not send — please try again.';
      });
  };

  function mount() {
    document.body.appendChild(btn);
    document.body.appendChild(overlay);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
