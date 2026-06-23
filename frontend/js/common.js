/* ── Auth helpers ── */
const auth = {
  token:      ()  => localStorage.getItem('persona_token'),
  setToken:   (t) => localStorage.setItem('persona_token', t),
  clearToken: ()  => localStorage.removeItem('persona_token'),
  isLoggedIn: ()  => !!localStorage.getItem('persona_token'),

  guard() {
    if (!this.isLoggedIn()) {
      window.location.href = '/login.html';
      throw new Error('not authenticated'); // stop further JS execution
    }
  },

  async logout() {
    try { await fetch('/api/auth/logout', { method: 'POST' }); } catch (_) {}
    this.clearToken();
    window.location.href = '/login.html';
  },
};

/* ── API Client ── */
const API_BASE = window.API_BASE || '/api';

const api = {
  async request(method, path, body) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    const token = auth.token();
    if (token) opts.headers['Authorization'] = `Bearer ${token}`;
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    if (res.status === 401) {
      auth.clearToken();
      window.location.href = '/login.html';
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return res.json();
  },
  get:    (path)        => api.request('GET', path),
  post:   (path, body)  => api.request('POST', path, body),
  put:    (path, body)  => api.request('PUT', path, body),
  delete: (path)        => api.request('DELETE', path),
};

/* ── Toast notifications ── */
const toast = (() => {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  function show(type, title, msg = '', duration = 4000) {
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'i' };
    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.innerHTML = `
      <span class="toast__icon">${icons[type] || 'i'}</span>
      <div class="toast__content">
        <div class="toast__title">${title}</div>
        ${msg ? `<div class="toast__msg">${msg}</div>` : ''}
      </div>
    `;
    container.appendChild(el);
    setTimeout(() => {
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 250);
    }, duration);
  }

  return {
    success: (t, m) => show('success', t, m),
    error:   (t, m) => show('error',   t, m),
    warning: (t, m) => show('warning', t, m),
    info:    (t, m) => show('info',    t, m),
  };
})();

/* ── Modal helpers ── */
function openModal(id) {
  const overlay = document.getElementById(id);
  if (overlay) { overlay.classList.add('open'); trapFocus(overlay); }
}
function closeModal(id) {
  const overlay = document.getElementById(id);
  if (overlay) overlay.classList.remove('open');
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
  if (e.target.closest('.modal__close')) {
    e.target.closest('.modal-overlay')?.classList.remove('open');
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
});
function trapFocus(el) {
  const focusable = el.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (focusable.length) focusable[0].focus();
}

/* ── Active nav link ── */
(function markActiveNav() {
  const current = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-item[href]').forEach(a => {
    const href = a.getAttribute('href').split('/').pop();
    if (href === current || (current === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });
})();

/* ── Format helpers ── */
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}
function fmtNum(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString();
}
function fmtPct(n) {
  return (n || 0).toFixed(1) + '%';
}
function statusBadge(status) {
  const s = (status || '').toLowerCase();
  return `<span class="badge badge--${s}">${status || '—'}</span>`;
}
function progressBar(pct) {
  const clamped = Math.min(100, Math.max(0, pct || 0));
  const cls = clamped >= 100 ? 'progress-bar__fill--success' : '';
  return `<div class="progress-bar"><div class="progress-bar__fill ${cls}" style="width:${clamped}%"></div></div>`;
}

/* ── Confirm dialog ── */
function confirmAction(msg, fn) {
  if (window.confirm(msg)) fn();
}

/* ── Responsive sidebar toggle ── */
(function () {
  const burger = document.querySelector('.btn--menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (!burger || !sidebar) return;
  burger.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (window.innerWidth < 769 && sidebar.classList.contains('open')) {
      if (!sidebar.contains(e.target) && !burger.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    }
  });
})();
