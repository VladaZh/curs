import { booking } from './api.js';
import { MAX_GUESTS } from './config.js';
import { guestsText, uuid } from './format.js';
import { loginUrl, redirectToLogin } from './nav.js';
import { isLoggedIn } from './session.js';
import {
  addMinutesLocal,
  checkOpeningHours,
  formatInZone,
  nowInZoneLocal,
  roundUpLocal,
  timeInZone,
  zonedLocalToUtcIso,
} from './time.js';
import { attachValidation } from './validate.js';

const MIN_LEAD_MINUTES = 60;
const ALT_OFFSETS = [-60, -30, 30, 60];

export function initReservation(restaurant) {
  const tz = restaurant.timezone;
  const card = document.getElementById('reserve-card');
  const panels = Object.fromEntries([...card.querySelectorAll('[data-step]')].map((el) => [el.dataset.step, el]));
  const show = (name) => Object.entries(panels).forEach(([key, el]) => (el.hidden = key !== name));

  if (!isLoggedIn()) {
    card.querySelectorAll('[data-keep-next]').forEach((a) => {
      a.href = loginUrl(a.dataset.keepNext);
    });
    show('login');
    return;
  }
  show('form');

  const form = panels.form;
  const dt = form.querySelector('#user-datetime');
  const guests = form.querySelector('#guests');
  const submitBtn = form.querySelector('.form-button');
  const statusEl = form.querySelector('[data-role="status"]');
  const altsEl = form.querySelector('[data-role="alternatives"]');

  const minLocal = () => roundUpLocal(addMinutesLocal(nowInZoneLocal(tz), MIN_LEAD_MINUTES));
  const maxLocal = () => addMinutesLocal(nowInZoneLocal(tz), restaurant.booking_horizon_days * 1440);

  const applyBounds = () => {
    dt.min = minLocal();
    dt.max = maxLocal();
  };
  applyBounds();
  dt.step = 900;
  guests.max = MAX_GUESTS;
  form.querySelector('[data-role="tz"]').textContent =
    `Время указывается по местному времени ресторана (${tz}). Бронь длится ${restaurant.slot_minutes} мин.`;

  dt.value = `${addMinutesLocal(nowInZoneLocal(tz), 1440).slice(0, 10)}T19:00`;
  dt.classList.add('default-value');
  dt.addEventListener('input', () => dt.classList.remove('default-value'), { once: true });
  dt.addEventListener('focus', applyBounds);

  const validation = attachValidation(form, {
    customValidators: {
      'user-datetime': (value) => {
        if (!value) return 'Введите корректную дату и время';
        if (value < minLocal()) return 'Бронь возможна не раньше чем через час';
        if (value > maxLocal()) return `Бронь доступна не более чем на ${restaurant.booking_horizon_days} дн. вперёд`;
        return checkOpeningHours(value, restaurant.hours, restaurant.slot_minutes).message ?? '';
      },
    },
  });

  const setStatus = (type, text) => {
    statusEl.hidden = !text;
    statusEl.className = `form-status form-status--${type}`;
    statusEl.textContent = text ?? '';
  };
  const clearAlternatives = () => altsEl.replaceChildren();
  const setBusy = (busy) => {
    submitBtn.disabled = busy || !validation.isValid();
  };

  const backToForm = (type, text) => {
    stopTimer();
    show('form');
    setStatus(type, text);
    clearAlternatives();
    validation.refresh();
  };

  let attempt = null;

  form.addEventListener('submit', async (evt) => {
    evt.preventDefault();
    if (!validation.validateAll()) return;

    const startsAt = zonedLocalToUtcIso(dt.value, tz);
    const partySize = Number(guests.value);
    const fingerprint = `${restaurant.id}|${startsAt}|${partySize}`;
    if (attempt?.fingerprint !== fingerprint) attempt = { fingerprint, key: uuid() };

    setStatus('info', 'Подбираем столик...');
    clearAlternatives();
    setBusy(true);
    try {
      const created = await booking.create({ restaurantId: restaurant.id, startsAt, partySize }, attempt.key);
      attempt = null;
      showHold(created);
    } catch (err) {
      await onCreateError(err, partySize);
    } finally {
      setBusy(false);
    }
  });

  async function onCreateError(err, partySize) {
    if (err.status === 401) return redirectToLogin();
    if (err.status === 409) {
      setStatus('error', 'На это время нет свободных столов.');
      return suggestAlternatives(partySize);
    }
    setStatus('error', err.detail ?? 'Не удалось создать бронь');
  }

  async function suggestAlternatives(partySize) {
    const candidates = ALT_OFFSETS.map((m) => addMinutesLocal(dt.value, m)).filter(
      (c) => c >= minLocal() && c <= maxLocal() && checkOpeningHours(c, restaurant.hours, restaurant.slot_minutes).ok,
    );
    const results = await Promise.allSettled(
      candidates.map((c) =>
        booking.availability({ restaurantId: restaurant.id, startsAt: zonedLocalToUtcIso(c, tz), partySize }),
      ),
    );
    const free = candidates.filter((_, i) => results[i].status === 'fulfilled' && results[i].value.length > 0);
    if (!free.length) return;

    setStatus('error', 'На это время нет свободных столов. Свободно в другое время:');
    altsEl.replaceChildren(
      ...free.map((c) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'reserve-button slot-button';
        btn.textContent = c.slice(11);
        btn.addEventListener('click', () => {
          dt.value = c;
          dt.dispatchEvent(new Event('input'));
          form.requestSubmit();
        });
        return btn;
      }),
    );
  }

  const hold = panels.hold;
  const timerEl = hold.querySelector('[data-role="timer"]');
  const holdStatus = hold.querySelector('[data-role="hold-status"]');
  const confirmBtn = hold.querySelector('[data-action="confirm"]');
  const cancelBtn = hold.querySelector('[data-action="cancel"]');
  let current = null;
  let timerId = null;

  const detailsText = (b) => `${formatInZone(b.starts_at, tz)}, ${guestsText(b.party_size)}`;

  function stopTimer() {
    clearInterval(timerId);
    timerId = null;
  }

  function showHold(b) {
    current = b;
    show('hold');
    holdStatus.hidden = true;
    hold.querySelector('[data-role="hold-details"]').textContent = detailsText(b);
    hold.querySelector('[data-role="hold-until"]').textContent =
      `${restaurant.name}, до ${timeInZone(b.ends_at, tz)}`;

    const tick = () => {
      const left = Math.max(0, Date.parse(b.expires_at) - Date.now());
      const sec = Math.ceil(left / 1000);
      timerEl.textContent = `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`;
      timerEl.classList.toggle('hold-timer--low', sec <= 60);
      if (left === 0) backToForm('error', 'Время удержания столика истекло. Выберите время ещё раз.');
    };
    stopTimer();
    tick();
    timerId = setInterval(tick, 1000);
  }

  const holdBusy = (busy) => {
    confirmBtn.disabled = busy;
    cancelBtn.disabled = busy;
  };

  confirmBtn.addEventListener('click', async () => {
    holdBusy(true);
    try {
      const confirmed = await booking.confirm(current.id);
      stopTimer();
      showDone(confirmed);
    } catch (err) {
      if (err.status === 401) return redirectToLogin();
      if (err.status === 410) return backToForm('error', 'Время удержания столика истекло. Выберите время ещё раз.');
      holdStatus.hidden = false;
      holdStatus.className = 'form-status form-status--error';
      holdStatus.textContent = err.detail ?? 'Не удалось подтвердить бронь';
    } finally {
      holdBusy(false);
    }
  });

  cancelBtn.addEventListener('click', async () => {
    holdBusy(true);
    try {
      await booking.cancel(current.id);
      backToForm('info', 'Удержание столика отменено.');
    } catch (err) {
      if (err.status === 401) return redirectToLogin();
      holdStatus.hidden = false;
      holdStatus.className = 'form-status form-status--error';
      holdStatus.textContent = err.detail ?? 'Не удалось отменить';
    } finally {
      holdBusy(false);
    }
  });

  const done = panels.done;
  function showDone(b) {
    show('done');
    done.querySelector('[data-role="done-details"]').textContent = `${restaurant.name}: ${detailsText(b)}`;
  }
  done.querySelector('[data-action="again"]').addEventListener('click', () => backToForm('info', ''));
}