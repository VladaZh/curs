import { catalog } from './api.js';
import { loadDishes } from './dishes.js';
import { renderAccountBar } from './nav.js';
import { initReservation } from './reservation.js';
import { sortRestaurants, themeAt } from './theme.js';
import { WEEKDAYS, nowInZoneLocal, shortTime, weekdayOfLocal } from './time.js';

const $ = (id) => document.getElementById(id);

function renderHours(restaurant) {
  const list = $('hours-list');
  if (!restaurant.hours.length) return list.remove();
  const today = weekdayOfLocal(nowInZoneLocal(restaurant.timezone));
  const rows = WEEKDAYS.map((name, day) => {
    const h = restaurant.hours.find((x) => x.weekday === day);
    const li = document.createElement('li');
    if (day === today) li.className = 'is-today';
    const label = document.createElement('span');
    label.textContent = name;
    const value = document.createElement('span');
    value.textContent = h ? `${shortTime(h.opens)} – ${shortTime(h.closes)}` : 'выходной';
    li.append(label, value);
    return li;
  });
  list.replaceChildren(...rows);
}

function render(restaurant, index) {
  document.body.classList.add(themeAt(index));
  document.title = restaurant.name;
  $('restaurant-name').textContent = restaurant.name;
  $('about-name').textContent = restaurant.name;
  $('about-description').textContent =
    `Ждём вас в ресторане ${restaurant.name}: ${restaurant.city}, ${restaurant.address}. ` +
    'Забронируйте столик онлайн, подтверждение придёт на вашу почту.';
  $('contact-address').textContent = `Адрес: ${restaurant.city}, ${restaurant.address}`;
  renderHours(restaurant);
  loadDishes($('dishes-list'));
  initReservation(restaurant);
}

async function init() {
  renderAccountBar();
  const state = $('state');
  const id = new URLSearchParams(location.search).get('id');
  try {
    const restaurants = sortRestaurants(await catalog.listRestaurants());
    const index = restaurants.findIndex((r) => r.id === id);
    if (index === -1) {
      state.textContent = 'Ресторан не найден или временно недоступен.';
      state.append(Object.assign(document.createElement('a'), { href: 'index.html', className: 'reserve-button', textContent: 'ко всем ресторанам' }));
      return;
    }
    state.hidden = true;
    $('restaurant').hidden = false;
    render(restaurants[index], index);
  } catch (err) {
    state.textContent = err.detail ?? 'Не удалось загрузить ресторан';
    const retry = Object.assign(document.createElement('button'), { className: 'reserve-button', textContent: 'повторить' });
    retry.addEventListener('click', () => location.reload());
    state.append(retry);
  }
}

init();