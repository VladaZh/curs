export function attachValidation(form, { customValidators = {}, debounceMs = 300, buttonSelector = '.form-button' } = {}) {
  const errorClass = 'form_input--error';
  const inputs = Array.from(form.querySelectorAll('input'));
  const submitBtn = form.querySelector(buttonSelector);
  const touched = new Set();
  const timers = new Map();

  const errorEl = (input) => document.getElementById(`${input.id}-error`);

  const showError = (input, message) => {
    const el = errorEl(input);
    input.classList.add(errorClass);
    input.setAttribute('aria-invalid', 'true');
    if (el) {
      el.textContent = message;
      el.style.display = 'block';
    }
  };

  const clearError = (input) => {
    const el = errorEl(input);
    input.classList.remove(errorClass);
    input.removeAttribute('aria-invalid');
    if (el) {
      el.textContent = '';
      el.style.display = 'none';
    }
  };

  const isRelevant = (input) => input.required || input.value !== '';

  const check = (input, render = true) => {
    input.setCustomValidity(customValidators[input.id]?.(input.value) ?? '');
    const valid = !isRelevant(input) || input.checkValidity();
    if (render) {
      if (valid) clearError(input);
      else showError(input, customValidators[input.id]?.(input.value) || input.dataset.errorMessage || input.validationMessage);
    }
    return valid;
  };

  const isValid = () => inputs.every((i) => check(i, false));
  const updateButton = () => {
    if (submitBtn) submitBtn.disabled = !isValid();
  };

  inputs.forEach((input) => {
    const onChange = () => {
      clearTimeout(timers.get(input));
      timers.set(
        input,
        setTimeout(() => {
          if (touched.has(input)) check(input);
          updateButton();
        }, debounceMs),
      );
      updateButton();
    };
    input.addEventListener('input', onChange);
    input.addEventListener('change', onChange);
    input.addEventListener('blur', () => {
      touched.add(input);
      check(input);
      updateButton();
    });
    input.addEventListener('focus', () => clearError(input));
  });

  form.addEventListener('reset', () => {
    inputs.forEach(clearError);
    touched.clear();
    queueMicrotask(updateButton);
  });

  updateButton();

  return {
    validateAll() {
      inputs.forEach((i) => touched.add(i));
      const results = inputs.map((i) => check(i));
      updateButton();
      return results.every(Boolean);
    },
    isValid,
    refresh: updateButton,
  };
}

const PHONE_RE = /^\+[1-9]\d{6,14}$/;

export const normalizePhone = (value) => value.replace(/[\s()-]/g, '');

export const phoneValidator = (value) => {
  if (value === '') return '';
  return PHONE_RE.test(normalizePhone(value)) ? '' : 'Укажите номер в международном формате, например +7 912 345 67 99';
};