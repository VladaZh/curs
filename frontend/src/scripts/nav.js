import { identity } from './api.js';
import { isLoggedIn } from './session.js';

const NEXT_RE = /^[a-z0-9_-]+\.html(\?[\w=&%.-]*)?$/i;

export const safeNext = (raw, fallback = 'index.html') => (NEXT_RE.test(raw ?? '') ? raw : fallback);

const currentPage = () => location.pathname.split('/').pop() + location.search;

export const loginUrl = (hash = 'login') => `auth.html?next=${encodeURIComponent(currentPage())}#${hash}`;

export const redirectToLogin = () => location.assign(loginUrl());

export function renderAccountBar(container = document.querySelector('[data-account-bar]')) {
  if (!container) return;
  container.replaceChildren();

  const link = (href, text) => {
    const a = document.createElement('a');
    a.href = href;
    a.textContent = text;
    return a;
  };

  if (isLoggedIn()) {
    const out = document.createElement('button');
    out.type = 'button';
    out.textContent = 'выйти';
    out.addEventListener('click', async () => {
      await identity.logout();
      location.assign('index.html');
    });
    container.append(link('bookings.html', 'мои брони'), out);
  } else {
    container.append(link(loginUrl(), 'войти'));
  }
}