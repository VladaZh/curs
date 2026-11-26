const env = import.meta.env ?? {};

export const API = {
  identity: env.VITE_IDENTITY_URL ?? '/api/identity',
  catalog: env.VITE_CATALOG_URL ?? '/api/catalog',
  booking: env.VITE_BOOKING_URL ?? '/api/booking',
};

export const TIMEOUT_MS = 10000;
export const MAX_GUESTS = 10;