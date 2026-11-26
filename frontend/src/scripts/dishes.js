const URL = 'https://www.themealdb.com/api/json/v1/1/filter.php?a=Italian';

const shuffle = (items) => {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

const message = (className, text) => {
  const li = document.createElement('li');
  li.className = className;
  li.textContent = text;
  return li;
};

export async function loadDishes(container, count = 6) {
  if (!container) return;
  container.replaceChildren(message('loading-text', 'Загрузка фирменных блюд...'));
  try {
    const res = await fetch(URL);
    const data = await res.json();
    if (!data.meals?.length) throw new Error('Блюда не найдены');

    const cards = shuffle(data.meals)
      .slice(0, count)
      .map((meal) => {
        const li = document.createElement('li');
        li.className = 'dish-card';
        const img = document.createElement('img');
        img.src = meal.strMealThumb;
        img.alt = meal.strMeal;
        img.loading = 'lazy';
        const title = document.createElement('h4');
        title.textContent = meal.strMeal;
        li.append(img, title);
        return li;
      });
    container.replaceChildren(...cards);
  } catch (err) {
    console.error(err);
    container.replaceChildren(message('error-text', 'Не удалось загрузить меню. Обновите страницу.'));
  }
}