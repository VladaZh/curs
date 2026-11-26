import { booking, catalog } from './api.js';
import { guestsText } from './format.js';
import { redirectToLogin, renderAccountBar } from './nav.js';
import { isLoggedIn } from './session.js';
import { formatInZone, timeInZone } from './time.js';
import { toast } from './toast.js';

const LABELS = {
  PENDING: 'Ожидает подтверждения',
  CONFIRMED: 'Подтверждена',
  SEATED: 'Гости за столом',
  COMPLETED: 'Завершена',
  CANCELLED: 'Отменена',
  EXPIRED: 'Истекла',
  NO_SHOW: 'Не пришли',
};

const upcomingEl = document.getElementById('upcoming');
const historyEl = document.getElementById('history');
const historyHeading = document.getElementById('history-heading');
const emptyEl = document.getElementById('empty');
const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

let restaurants = new Map();

const effectiveStatus = (b) => (b.status === 'PENDING' && Date.parse(b.expires_at) <= Date.now() ? 'EXPIRED' : b.status);

const isUpcoming = (b) => ['PENDING', 'CONFIRMED', 'SEATED'].includes(effectiveStatus(b)) && Date.parse(b.ends_at) > Date.now();

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

function card(b) {
  const status = effectiveStatus(b);
  const r = restaurants.get(b.restaurant_id);
  const tz = r?.timezone ?? browserTz;

  const li = el('li', 'booking-card');
  const info = el('div');
  info.append(
    el('h4', '', r?.name ?? 'Ресторан'),
    el('p', 'booking-meta', `${formatInZone(b.starts_at, tz)}, ${guestsText(b.party_size)}`),
  );
  if (status === 'PENDING') {
    info.append(el('p', 'booking-meta', `Столик удерживается до ${timeInZone(b.expires_at, tz)}. Подтвердите бронь.`));
  }
  li.append(info, el('span', `status-badge status-badge--${status.toLowerCase()}`, LABELS[status]));

  const actions = el('div', 'booking-actions');
  const action = (name, text) => {
    const btn = el('button', 'reserve-button', text);
    btn.type = 'button';
    btn.dataset.action = name;
    btn.dataset.id = b.id;
    return btn;
  };
  if (status === 'PENDING') actions.append(action('confirm', 'подтвердить'));
  if (['PENDING', 'CONFIRMED'].includes(status) && Date.parse(b.starts_at) > Date.now()) {
    actions.append(action('cancel', 'отменить'));
  }
  if (actions.childElementCount) li.append(actions);
  return li;
}

function render(bookings) {
  const upcoming = bookings.filter(isUpcoming).sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at));
  const past = bookings.filter((b) => !isUpcoming(b)).sort((a, b) => Date.parse(b.starts_at) - Date.parse(a.starts_at));
  upcomingEl.replaceChildren(...upcoming.map(card));
  historyEl.replaceChildren(...past.map(card));
  historyHeading.hidden = past.length === 0;
  emptyEl.hidden = bookings.length > 0;
}

async function load() {
  try {
    const [bookings, list] = await Promise.all([booking.my(), catalog.listRestaurants().catch(() => [])]);
    restaurants = new Map(list.map((r) => [r.id, r]));
    render(bookings);
  } catch (err) {
    if (err.status === 401) return redirectToLogin();
    toast(err.detail ?? 'Не удалось загрузить брони', 'error');
  }
}

document.addEventListener('click', async (evt) => {
  const btn = evt.target.closest('[data-action]');
  if (!btn) return;
  btn.disabled = true;
  try {
    if (btn.dataset.action === 'confirm') {
      await booking.confirm(btn.dataset.id);
      toast('Бронь подтверждена', 'success');
    } else {
      await booking.cancel(btn.dataset.id);
      toast('Бронь отменена', 'success');
    }
  } catch (err) {
    if (err.status === 401) return redirectToLogin();
    toast(err.status === 410 ? 'Время удержания столика истекло' : (err.detail ?? 'Ошибка'), 'error');
  }
  await load();
});

if (!isLoggedIn()) {
  redirectToLogin();
} else {
  renderAccountBar();
  load();
}