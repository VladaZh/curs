import { API } from './config.js';
import { authRequest, request } from './http.js';
import { clearSession, getSession, saveTokens } from './session.js';

export const catalog = {
  listRestaurants: () => request(`${API.catalog}/v1/restaurants`),
};

export const identity = {
  register: (data) => request(`${API.identity}/v1/auth/register`, { method: 'POST', body: data }),

  async login(email, password) {
    const pair = await request(`${API.identity}/v1/auth/login`, {
      method: 'POST',
      body: { email, password },
    });
    saveTokens(pair);
  },

  async logout() {
    const session = getSession();
    clearSession();
    if (session?.refreshToken) {
      await request(`${API.identity}/v1/auth/logout`, {
        method: 'POST',
        body: { refresh_token: session.refreshToken },
      }).catch(() => {});
    }
  },
};

export const booking = {
  availability: ({ restaurantId, startsAt, partySize }) =>
    authRequest(
      `${API.booking}/v1/availability?` +
        new URLSearchParams({ restaurant_id: restaurantId, starts_at: startsAt, party_size: partySize }),
    ),

  create: ({ restaurantId, startsAt, partySize }, idempotencyKey) =>
    authRequest(`${API.booking}/v1/bookings`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: { restaurant_id: restaurantId, starts_at: startsAt, party_size: partySize },
    }),

  confirm: (id) => authRequest(`${API.booking}/v1/bookings/${id}/confirm`, { method: 'POST' }),
  cancel: (id) => authRequest(`${API.booking}/v1/bookings/${id}/cancel`, { method: 'POST' }),
  my: () => authRequest(`${API.booking}/v1/bookings/my`),
};