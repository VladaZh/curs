import { identity } from './api.js';
import { safeNext } from './nav.js';
import { isLoggedIn } from './session.js';
import { attachValidation, normalizePhone, phoneValidator } from './validate.js';

const next = safeNext(new URLSearchParams(location.search).get('next'));
if (isLoggedIn()) location.replace(next);

const title = document.getElementById('auth-title');
const tabs = [...document.querySelectorAll('[role="tab"]')];
const forms = {
  login: document.querySelector('[data-form="login"]'),
  register: document.querySelector('[data-form="register"]'),
};
const TITLES = { login: 'Вход', register: 'Регистрация' };

function select(name) {
  tabs.forEach((t) => t.setAttribute('aria-selected', String(t.dataset.tab === name)));
  Object.entries(forms).forEach(([key, el]) => (el.hidden = key !== name));
  title.textContent = TITLES[name];
  history.replaceState(null, '', `${location.search}#${name}`);
}

tabs.forEach((t) => t.addEventListener('click', () => select(t.dataset.tab)));
select(location.hash === '#register' ? 'register' : 'login');

const setStatus = (form, text) => {
  const el = form.querySelector('[data-role="status"]');
  el.hidden = !text;
  el.textContent = text ?? '';
};

function bind(form, validation, action) {
  const btn = form.querySelector('.form-button');
  form.addEventListener('submit', async (evt) => {
    evt.preventDefault();
    if (!validation.validateAll()) return;
    setStatus(form, '');
    btn.disabled = true;
    try {
      await action();
      location.assign(next);
    } catch (err) {
      setStatus(form, err.detail ?? 'Ошибка');
      btn.disabled = false;
    }
  });
}

const val = (form, id) => form.querySelector(`#${id}`).value.trim();

const loginForm = forms.login;
bind(loginForm, attachValidation(loginForm), () =>
  identity.login(val(loginForm, 'login-email'), loginForm.querySelector('#login-password').value),
);

const regForm = forms.register;
bind(regForm, attachValidation(regForm, { customValidators: { 'reg-phone': phoneValidator } }), async () => {
  const phone = normalizePhone(val(regForm, 'reg-phone'));
  const password = regForm.querySelector('#reg-password').value;
  const email = val(regForm, 'reg-email');
  await identity.register({ email, password, full_name: val(regForm, 'reg-name'), ...(phone && { phone }) });
  await identity.login(email, password);
});