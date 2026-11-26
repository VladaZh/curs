const THEMES = ['roma', 'firenze'];

export const sortRestaurants = (list) => [...list].sort((a, b) => a.id.localeCompare(b.id));

export const themeAt = (index) => `theme-${THEMES[index % THEMES.length]}`;