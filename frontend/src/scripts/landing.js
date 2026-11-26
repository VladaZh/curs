import { catalog } from './api.js';
import { renderAccountBar } from './nav.js';
import { sortRestaurants, themeAt } from './theme.js';

const list = document.getElementById('restaurants-list');
const state = document.getElementById('state');

const showState = (text, withRetry = false) => {
  state.hidden = false;
  state.replaceChildren(text);
  if (withRetry) {
    const btn = Object.assign(document.createElement('button'), { className: 'reserve-button', textContent: 'повторить' });
    btn.addEventListener('click', load);
    state.append(btn);
  }
};

function render(restaurants) {
  list.toggleAttribute('data-many', restaurants.length > 4);
  list.replaceChildren(
    ...restaurants.map((r, i) => {
      const li = document.createElement('li');
      li.className = 'menu_main-item';

      const a = document.createElement('a');
      a.className = `menu_main-button ${themeAt(i)}`;
      a.href = `restaurant.html?id=${encodeURIComponent(r.id)}`;
      a.textContent = r.name;

      const sub = document.createElement('span');
      sub.className = 'menu_main-sub';
      sub.textContent = r.city;
      a.append(sub);

      li.append(a);
      return li;
    }),
  );
}

async function load() {
  showState('Загрузка...');
  list.replaceChildren();
  try {
    const restaurants = sortRestaurants(await catalog.listRestaurants());
    if (!restaurants.length) return showState('Пока нет доступных ресторанов');
    state.hidden = true;
    render(restaurants);
  } catch (err) {
    showState(err.detail ?? 'Не удалось загрузить рестораны', true);
  }
}

renderAccountBar();
load();