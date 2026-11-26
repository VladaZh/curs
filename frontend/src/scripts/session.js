const KEY = 'restaurants.session';

export const getSession = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY));
  } catch {
    return null;
  }
};

export const saveTokens = ({ access_token, refresh_token, expires_in }) => {
  const session = {
    accessToken: access_token,
    refreshToken: refresh_token,
    expiresAt: Date.now() + expires_in * 1000,
  };
  try {
    localStorage.setItem(KEY, JSON.stringify(session));
  } catch {

  }
  return session;
};

export const clearSession = () => {
  try {
    localStorage.removeItem(KEY);
  } catch {

  }
};

export const isLoggedIn = () => Boolean(getSession()?.refreshToken);

export const isAccessFresh = (session = getSession(), skewMs = 10_000) =>
  Boolean(session) && session.expiresAt - skewMs > Date.now();