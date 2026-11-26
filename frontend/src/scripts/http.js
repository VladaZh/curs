import { API, TIMEOUT_MS } from './config.js';
import { clearSession, getSession, isAccessFresh, saveTokens } from './session.js';

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

const parseDetail = (data, fallback) => {
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((e) => e.msg).join('; ');
  return fallback || 'Ошибка';
};

export async function request(url, { method = 'GET', body, headers = {}, token } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    let res;
    try {
      res = await fetch(url, {
        method,
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          ...(body !== undefined && { 'Content-Type': 'application/json' }),
          ...(token && { Authorization: `Bearer ${token}` }),
          ...headers,
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new ApiError(0, e.name === 'AbortError' ? 'Превышено время ожидания ответа сервера' : 'Не удалось соединиться с сервером');
    }
    if (res.status === 204) return null;
    let data = null;
    try {
      data = await res.json();
    } catch {

    }
    if (!res.ok) throw new ApiError(res.status, parseDetail(data, res.statusText));
    return data;
  } finally {
    clearTimeout(timer);
  }
}

let inFlight = null;

async function runRefresh(usedToken) {
  const session = getSession();
  if (!session?.refreshToken) throw new ApiError(401, 'Требуется вход');

  const alreadyRenewed = usedToken ? session.accessToken !== usedToken : isAccessFresh(session);
  if (alreadyRenewed) return session.accessToken;

  const pair = await request(`${API.identity}/v1/auth/refresh`, {
    method: 'POST',
    body: { refresh_token: session.refreshToken },
  });
  return saveTokens(pair).accessToken;
}

export function refreshAccessToken(usedToken) {
  if (!inFlight) {
    const run = () => runRefresh(usedToken);
    const task = globalThis.navigator?.locks ? navigator.locks.request('restaurants-refresh', run) : run();
    inFlight = task.finally(() => {
      inFlight = null;
    });
  }
  return inFlight;
}

async function refreshOrLogout(usedToken) {
  try {
    return await refreshAccessToken(usedToken);
  } catch (e) {
    if (e.status === 401) clearSession();
    throw e;
  }
}

export async function authRequest(url, options = {}) {
  const session = getSession();
  if (!session) throw new ApiError(401, 'Требуется вход');

  let token = session.accessToken;
  if (!isAccessFresh(session)) token = await refreshOrLogout();

  try {
    return await request(url, { ...options, token });
  } catch (e) {
    if (e.status !== 401) throw e;
    token = await refreshOrLogout(token);
    return request(url, { ...options, token });
  }
}