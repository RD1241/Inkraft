/**
 * auth.js — Inkraft localStorage-backed authentication store.
 * JWT token lives in-memory and is synchronized with localStorage so it
 * survives page redirects/reloads, tab suspensions, and browser restarts.
 */

let initialToken = null;
let initialUser = null;
let initialCredits = null;

try {
  initialToken = localStorage.getItem('ntc_token') || null;
  const rawUser = localStorage.getItem('ntc_user');
  initialUser = rawUser ? JSON.parse(rawUser) : null;
  const rawCredits = localStorage.getItem('ntc_credits');
  initialCredits = rawCredits ? parseInt(rawCredits, 10) : null;
} catch (e) {
  console.warn('[authStore] Failed to load local storage:', e);
}

const _state = {
  token: initialToken,
  user: initialUser,
  credits: initialCredits,
  listeners: [],
};

function _notify() {
  _state.listeners.forEach(fn => fn({ ..._state }));
}

export const authStore = {
  /** Subscribe to auth state changes. Returns an unsubscribe function. */
  subscribe(fn) {
    _state.listeners.push(fn);
    // Immediately call with current state
    fn({ ..._state });
    return () => {
      _state.listeners = _state.listeners.filter(l => l !== fn);
    };
  },

  getToken() { return _state.token; },
  getUser()  { return _state.user; },
  isLoggedIn() { return !!_state.token; },

  /** Called after successful login or register */
  setAuth(token, user) {
    _state.token = token;
    _state.user = user;
    try {
      if (token) {
        localStorage.setItem('ntc_token', token);
      } else {
        localStorage.removeItem('ntc_token');
      }
      if (user) {
        localStorage.setItem('ntc_user', JSON.stringify(user));
      } else {
        localStorage.removeItem('ntc_user');
      }
    } catch (e) {
      console.warn('[authStore] Failed to write to localStorage:', e);
    }
    _notify();
  },

  setCredits(credits) {
    _state.credits = credits;
    try {
      if (credits !== null && credits !== undefined) {
        localStorage.setItem('ntc_credits', credits.toString());
      } else {
        localStorage.removeItem('ntc_credits');
      }
    } catch (e) {
      console.warn('[authStore] Failed to write credits to localStorage:', e);
    }
    _notify();
  },

  logout() {
    if (_state.token) {
      // Fire-and-forget logout call
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${_state.token}` }
      }).catch(() => {});
    }
    _state.token = null;
    _state.user = null;
    _state.credits = null;
    try {
      localStorage.removeItem('ntc_token');
      localStorage.removeItem('ntc_user');
      localStorage.removeItem('ntc_credits');
    } catch (e) {
      console.warn('[authStore] Failed to clear localStorage:', e);
    }
    _notify();
    window.location.href = '/login.html';
  },
};

/** Authenticated fetch wrapper — injects Bearer token automatically */
export async function apiFetch(url, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (_state.token) {
    headers['Authorization'] = `Bearer ${_state.token}`;
    headers['X-User-ID'] = _state.user?.id || '';
  }
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    authStore.logout();
    throw new Error('Session expired. Please log in again.');
  }
  return res;
}

/** Redirect to dashboard if already logged in, used on login/register pages */
export function redirectIfLoggedIn(dest = '/dashboard.html') {
  if (_state.token) window.location.href = dest;
}

/** Redirect to login if NOT logged in, used on protected pages */
export function requireAuth(loginDest = '/login.html') {
  if (!_state.token) {
    window.location.href = loginDest;
    return false;
  }
  return true;
}

/**
 * Poll credits balance every 30s while user is logged in.
 * Stores result in _state.credits and notifies subscribers.
 */
export function startCreditPolling(intervalMs = 30000) {
  async function fetchCredits() {
    if (!_state.token) return;
    try {
      const res = await apiFetch('/api/credits/balance');
      if (res.ok) {
        const data = await res.json();
        if (data.balance !== undefined) authStore.setCredits(data.balance);
      }
    } catch (_) {}
  }
  fetchCredits();
  return setInterval(fetchCredits, intervalMs);
}
