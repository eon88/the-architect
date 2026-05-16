/* ===== THE ARCHITECT — FRONTEND ENGINE ===== */

'use strict';

// ===== STATE =====
const State = {
  userId: null,
  userEmail: null,
  currentSection: null,
  dailyProgress: { morning: false, midday: false, evening: false },
  retryCallbacks: {},
};

// ===== DOM REFS =====
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ===== ERROR CATEGORIZATION =====
function categorizeError(err, response) {
  if (!navigator.onLine) {
    return {
      type: 'network',
      title: 'Network Error',
      message: 'Network connection lost. Please check your internet connection.',
      recoverable: true,
      icon: '⚡',
    };
  }
  if (!response) {
    return {
      type: 'network',
      title: 'Connection Failed',
      message: 'Could not reach the server. Try again in a moment.',
      recoverable: true,
      icon: '⚡',
    };
  }
  if (response.status === 401 || response.status === 403) {
    return {
      type: 'auth',
      title: 'Session Expired',
      message: 'Your session has expired. Please log in again.',
      recoverable: false,
      icon: '🔒',
    };
  }
  if (response.status === 400) {
    return {
      type: 'validation',
      title: 'Invalid Input',
      message: 'Invalid input. Check your entry and try again.',
      recoverable: false,
      icon: '⚠',
    };
  }
  if (response.status === 429) {
    return {
      type: 'ratelimit',
      title: 'Rate Limited',
      message: 'Too many requests. Wait a moment before trying again.',
      recoverable: true,
      icon: '⏳',
    };
  }
  if (response.status >= 500) {
    return {
      type: 'server',
      title: 'Server Error',
      message: 'Server temporarily unavailable. Try again in a moment.',
      recoverable: true,
      icon: '⚠',
    };
  }
  return {
    type: 'unknown',
    title: 'Error',
    message: err?.message || 'An unexpected error occurred.',
    recoverable: true,
    icon: '⚠',
  };
}

// ===== FETCH WRAPPER =====
async function apiFetch(url, options = {}, retryCallback = null) {
  let response = null;
  try {
    response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!response.ok) {
      const errInfo = categorizeError(null, response);
      if (errInfo.type === 'auth') {
        showToast(errInfo.type, errInfo.title, errInfo.message, false, null);
        setTimeout(() => showLogin(), 1500);
        throw new Error(errInfo.message);
      }
      showToast('error', errInfo.title, errInfo.message, errInfo.recoverable, retryCallback);
      throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (err.message?.startsWith('HTTP ')) throw err;
    const errInfo = categorizeError(err, response);
    showToast('error', errInfo.title, errInfo.message, errInfo.recoverable, retryCallback);
    console.error('[Architect API Error]', url, err);
    throw err;
  }
}

// ===== LOADING STATE =====
let loadingTimer = null;

function showLoading(message = 'Initializing') {
  const overlay = $('loading-overlay');
  const textEl = $('loading-message');
  const timeoutEl = $('loading-timeout');
  if (textEl) textEl.textContent = message;
  if (timeoutEl) timeoutEl.style.display = 'none';
  overlay.classList.add('visible');

  loadingTimer = setTimeout(() => {
    if (timeoutEl) timeoutEl.style.display = 'block';
  }, 5000);
}

function hideLoading() {
  $('loading-overlay').classList.remove('visible');
  if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null; }
}

// ===== TOAST SYSTEM =====
let toastCounter = 0;

function showToast(variant, title, message, recoverable = false, retryFn = null, duration = 6000) {
  const container = $('toast-container');
  const id = `toast-${toastCounter++}`;

  const icons = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ', network: '⚡', auth: '🔒', ratelimit: '⏳' };
  const icon = icons[variant] || icons.info;

  const toast = document.createElement('div');
  toast.className = `toast ${variant === 'network' ? 'error' : (variant === 'auth' || variant === 'ratelimit' ? 'warning' : variant)}`;
  toast.id = id;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'assertive');

  toast.innerHTML = `
    <span class="toast-icon" aria-hidden="true">${icon}</span>
    <div class="toast-body">
      <div class="toast-title">${escHtml(title)}</div>
      <div class="toast-message">${escHtml(message)}</div>
      ${recoverable && retryFn ? `<button class="toast-retry" aria-label="Retry action">[ RETRY ]</button>` : ''}
    </div>
    <button class="toast-close" aria-label="Dismiss notification">×</button>
  `;

  container.appendChild(toast);

  const dismiss = () => {
    toast.classList.add('leaving');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };

  toast.querySelector('.toast-close').addEventListener('click', dismiss);

  if (recoverable && retryFn) {
    toast.querySelector('.toast-retry')?.addEventListener('click', () => {
      dismiss();
      retryFn();
    });
  }

  if (duration > 0) {
    // Drive the CSS animation duration to match
    const afterEl = toast;
    afterEl.style.setProperty('--toast-duration', `${duration}ms`);
    setTimeout(dismiss, duration);
  }

  return id;
}

// ===== BREADCRUMB & PROGRESS =====
function setBreadcrumb(parts) {
  const el = $('breadcrumb');
  if (!el) return;
  el.innerHTML = parts.map((p, i) => {
    const cls = i === parts.length - 1 ? 'breadcrumb-item active' : 'breadcrumb-item';
    return (i > 0 ? '<span class="breadcrumb-sep">/</span>' : '') + `<span class="${cls}">${escHtml(p)}</span>`;
  }).join('');
}

function updateDailyProgress() {
  const steps = [
    { id: 'dp-morning', key: 'morning', label: 'Morning' },
    { id: 'dp-midday', key: 'midday', label: 'Midday' },
    { id: 'dp-evening', key: 'evening', label: 'Evening' },
  ];

  const activeKey = State.currentSection;
  steps.forEach(step => {
    const el = $(step.id);
    if (!el) return;
    el.className = 'progress-step';
    if (State.dailyProgress[step.key]) {
      el.classList.add('done');
    } else if (step.key === activeKey || (activeKey === step.key)) {
      el.classList.add('active');
    }
  });
}

// ===== NAVIGATION =====
function setActiveNav(sectionKey) {
  $$('.nav-btn').forEach(btn => btn.classList.remove('active'));
  const active = document.querySelector(`.nav-btn[data-section="${sectionKey}"]`);
  if (active) active.classList.add('active');
  State.currentSection = sectionKey;
  updateDailyProgress();
}

function showSection(key) {
  $$('.section').forEach(s => s.classList.remove('active'));
  const section = $(`section-${key}`);
  if (section) section.classList.add('active');
  setActiveNav(key);
  // Close mobile menu
  closeMobileMenu();
}

function closeMobileMenu() {
  const menu = $('nav-menu');
  const btn = $('hamburger');
  if (menu) menu.classList.remove('open');
  if (btn) btn.classList.remove('open');
  if (btn) btn.setAttribute('aria-expanded', 'false');
}

function toggleMobileMenu() {
  const menu = $('nav-menu');
  const btn = $('hamburger');
  const isOpen = menu.classList.toggle('open');
  btn.classList.toggle('open', isOpen);
  btn.setAttribute('aria-expanded', String(isOpen));
}

// ===== LOGIN =====
function showLogin() {
  $('app-shell').classList.add('hidden');
  $('screen-login').classList.remove('hidden');
}

function showAppShell() {
  $('screen-login').classList.add('hidden');
  $('app-shell').classList.remove('hidden');
}

async function handleLogin() {
  const emailInput = $('login-email');
  const email = emailInput ? emailInput.value.trim() : 'user@architect.app';

  if (!email || !email.includes('@')) {
    showToast('warning', 'Invalid Email', 'Please enter a valid email address.', false, null, 4000);
    emailInput?.focus();
    return;
  }

  const btn = $('login-btn');
  btn.disabled = true;
  showLoading('Authenticating');

  try {
    const data = await apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, name: email.split('@')[0] }),
    }, () => handleLogin());

    State.userId = data.user_id;
    State.userEmail = data.email;

    const userEl = $('topbar-user');
    if (userEl) userEl.textContent = data.email;

    hideLoading();
    showAppShell();
    await loadMorning();
  } catch {
    hideLoading();
    btn.disabled = false;
  }
}

// ===== MORNING RITUAL =====
async function loadMorning() {
  showSection('morning');
  setBreadcrumb(['RITUAL', 'MORNING PROTOCOL']);

  const contentEl = $('morning-content');
  if (contentEl) {
    contentEl.innerHTML = `
      <div class="ritual-quote">
        <div class="skeleton-line w-full skeleton" style="height:1.2em;margin-bottom:0.5rem"></div>
        <div class="skeleton-line w-3q skeleton" style="height:1.2em;margin-bottom:0.5rem"></div>
        <div class="skeleton-line w-half skeleton" style="height:1.2em"></div>
      </div>
    `;
  }

  showLoading('Loading morning protocol');

  const retry = () => loadMorning();
  try {
    const data = await apiFetch(`/ritual/morning/${State.userId}`, {}, retry);
    hideLoading();
    if (contentEl) {
      contentEl.innerHTML = `
        <div class="ritual-quote">
          <p class="quote-text">${escHtml(data.message)}</p>
        </div>
      `;
    }
    State.dailyProgress.morning = true;
    updateDailyProgress();
    showToast('success', 'Morning Protocol', 'Your morning brief is ready.', false, null, 3000);
  } catch {
    hideLoading();
    if (contentEl) {
      contentEl.innerHTML = `<p class="text-dim">Could not load morning protocol. <button class="btn btn-ghost mt-1" onclick="loadMorning()">Retry</button></p>`;
    }
  }
}

// ===== MIDDAY RITUAL =====
function loadMidday() {
  showSection('midday');
  setBreadcrumb(['RITUAL', 'MIDDAY ALIGNMENT']);
}

// ===== EVENING RITUAL =====
const MAX_CHARS = 2000;
const SEED_QUESTIONS = [
  'Who in your life actually pushes you to be better, and who is just taking up space?',
  'If your income vanished tomorrow, how many days could you survive?',
  'When was the last time you felt peace without a screen or distraction?',
  'What is one skill you\'d spend 10,000 hours mastering just for the pride of mastering it?',
  'Do the people closest to you feel truly seen and heard by you?',
  'What belief did you hold for years that you now know is wrong?',
  'If you disappeared tomorrow, what would the world actually miss?',
  'What did you avoid today that you know you should have done?',
  'What is the most honest sentence you could write about how you spent your energy this week?',
];

function loadEvening() {
  showSection('evening');
  setBreadcrumb(['RITUAL', 'EVENING REFLECTION']);

  const q = SEED_QUESTIONS[Math.floor(Math.random() * SEED_QUESTIONS.length)];
  const qEl = $('seed-question');
  if (qEl) qEl.textContent = q;

  const textarea = $('journal-textarea');
  if (textarea) {
    textarea.value = '';
    updateCharCounter(textarea);
  }
}

function updateCharCounter(textarea) {
  const count = textarea.value.length;
  const pct = count / MAX_CHARS;

  const fillEl = $('char-fill');
  const textEl = $('char-text');

  if (fillEl) {
    fillEl.style.width = `${Math.min(pct * 100, 100)}%`;
    fillEl.className = 'char-counter-fill';
    if (pct < 0.5) fillEl.classList.add('low');
    else if (pct < 0.8) fillEl.classList.add('mid');
    else if (pct < 0.95) fillEl.classList.add('warn');
    else fillEl.classList.add('danger');
  }

  if (textEl) {
    textEl.className = 'char-counter-text';
    if (pct >= 0.95) textEl.classList.add('danger');
    else if (pct >= 0.8) textEl.classList.add('warn');

    const remaining = MAX_CHARS - count;
    if (pct === 0) {
      textEl.textContent = `0 of ${MAX_CHARS.toLocaleString()} characters`;
    } else if (remaining < 100) {
      textEl.textContent = `${remaining} characters remaining`;
    } else {
      textEl.textContent = `${count.toLocaleString()} of ${MAX_CHARS.toLocaleString()} characters`;
    }
  }
}

async function submitJournal() {
  const textarea = $('journal-textarea');
  const content = textarea?.value?.trim();

  if (!content || content.length < 10) {
    showToast('warning', 'Too Brief', 'Write at least a few sentences before submitting.', false, null, 4000);
    textarea?.focus();
    return;
  }

  const submitBtn = $('evening-submit');
  if (submitBtn) submitBtn.disabled = true;
  showLoading('Processing reflection');

  const retry = () => submitJournal();
  try {
    await apiFetch('/ritual/evening', {
      method: 'POST',
      body: JSON.stringify({ user_id: State.userId, content }),
    }, retry);

    hideLoading();
    State.dailyProgress.evening = true;
    updateDailyProgress();
    showToast('success', 'Reflection Saved', 'Your entry has been recorded. See you in the morning.', false, null, 5000);
    textarea.value = '';
    updateCharCounter(textarea);

    setTimeout(() => showSection('morning'), 1000);
  } catch {
    hideLoading();
    if (submitBtn) submitBtn.disabled = false;
  }
}

// ===== PILLAR MAP =====
async function loadPillarMap() {
  showSection('pillars');
  setBreadcrumb(['INSIGHTS', 'PILLAR MAP']);

  const grid = $('pillars-grid');
  if (grid) {
    grid.innerHTML = Array(7).fill(0).map(() => `
      <div class="pillar-card">
        <div class="skeleton-line w-3q skeleton" style="height:0.9em;margin-bottom:0.5rem;margin-left:0.75rem"></div>
        <div class="skeleton-line w-half skeleton" style="height:0.65em;margin-left:0.75rem"></div>
      </div>
    `).join('');
  }

  showLoading('Mapping pillars');
  const retry = () => loadPillarMap();
  try {
    const pillars = await apiFetch(`/user/pillars/${State.userId}`, {}, retry);
    hideLoading();
    if (grid) {
      grid.innerHTML = pillars.map(p => {
        const isMoving = p.status === 'Moving';
        return `
          <div class="pillar-card ${isMoving ? 'moving' : ''}" role="article" aria-label="${escHtml(p.name)}: ${escHtml(p.status)}">
            <div class="pillar-name">${escHtml(p.name)}</div>
            <div class="pillar-status">${escHtml(p.status)}</div>
          </div>
        `;
      }).join('');
    }
  } catch {
    hideLoading();
    if (grid) {
      grid.innerHTML = `<p class="text-dim">Could not load pillar map. <button class="btn btn-ghost" onclick="loadPillarMap()">Retry</button></p>`;
    }
  }
}

// ===== KEYBOARD NAVIGATION =====
function initKeyboard() {
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;

    if (e.key === 'Escape') {
      closeMobileMenu();
    }
    if (e.key === 'm' && !e.ctrlKey && !e.metaKey) {
      loadMorning();
    }
    if (e.key === 'e' && !e.ctrlKey && !e.metaKey) {
      loadEvening();
    }
    if (e.key === 'p' && !e.ctrlKey && !e.metaKey) {
      loadPillarMap();
    }
  });
}

// ===== HELPER =====
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
  initKeyboard();

  // Login form submit on Enter
  $('login-email')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') handleLogin();
  });

  // Textarea character counter
  $('journal-textarea')?.addEventListener('input', function() {
    updateCharCounter(this);
    // Enforce max
    if (this.value.length > MAX_CHARS) {
      this.value = this.value.slice(0, MAX_CHARS);
      updateCharCounter(this);
      showToast('warning', 'Character Limit', `Maximum ${MAX_CHARS} characters reached.`, false, null, 3000);
    }
  });

  // Hamburger
  $('hamburger')?.addEventListener('click', toggleMobileMenu);

  // Close menu on outside click
  document.addEventListener('click', e => {
    const nav = $('nav-wrapper');
    if (nav && !nav.contains(e.target)) {
      closeMobileMenu();
    }
  });

  // Wire nav buttons
  $$('.nav-btn[data-section]').forEach(btn => {
    btn.addEventListener('click', () => {
      const section = btn.dataset.section;
      switch(section) {
        case 'morning': loadMorning(); break;
        case 'midday': loadMidday(); break;
        case 'evening': loadEvening(); break;
        case 'pillars': loadPillarMap(); break;
        default: showSection(section); setBreadcrumb(['SYSTEM', section.toUpperCase()]);
      }
    });
  });
});
