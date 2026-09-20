from typing import Any

import aiohttp


MEALDB_SEARCH_URL = "https://www.themealdb.com/api/json/v1/1/search.php"
MEALDB_LOOKUP_URL = "https://www.themealdb.com/api/json/v1/1/lookup.php"


class MealDBError(Exception):
    """Ошибка при обращении к TheMealDB."""


async def search_meals(query: str) -> list[dict[str, Any]]:
    data = await _request_mealdb(MEALDB_SEARCH_URL, {"s": query})
    meals = data.get("meals")
    return meals if isinstance(meals, list) else []


async def lookup_meal(recipe_id: str) -> dict[str, Any] | None:
    data = await _request_mealdb(MEALDB_LOOKUP_URL, {"i": recipe_id})
    meals = data.get("meals")
    if not isinstance(meals, list) or not meals:
        return None
    return meals[0]


async def _request_mealdb(url: str, params: dict[str, str]) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as error:
        raise MealDBError("Не удалось получить данные от TheMealDB") from error

    return data


def extract_ingredients(meal: dict[str, Any]) -> list[tuple[str, str]]:
    ingredients: list[tuple[str, str]] = []

    for number in range(1, 21):
        ingredient = str(meal.get(f"strIngredient{number}") or "").strip()
        measure = str(meal.get(f"strMeasure{number}") or "").strip()
        if ingredient:
            ingredients.append((ingredient, measure))

    return ingredients


def format_recipe(meal: dict[str, Any]) -> str:
    ingredients = [
        f"• {ingredient} — {measure}" if measure else f"• {ingredient}"
        for ingredient, measure in extract_ingredients(meal)
    ]

    name = str(meal.get("strMeal") or "Без названия").strip()
    category = str(meal.get("strCategory") or "Не указана").strip()
    area = str(meal.get("strArea") or "Не указана").strip()
    instructions = str(meal.get("strInstructions") or "Инструкция отсутствует").strip()
    youtube_url = str(meal.get("strYoutube") or "").strip()
    ingredients_text = "\n".join(ingredients) or "Ингредиенты не указаны"

    recipe_text = (
        f"{name}\n\n"
        f"Категория: {category}\n"
        f"Кухня/страна: {area}\n\n"
        f"Ингредиенты:\n{ingredients_text}\n\n"
        f"Инструкция приготовления:\n{instructions}"
    )

    if youtube_url:
        recipe_text += f"\n\n🎬 Видеорецепт:\n{youtube_url}"

    return recipe_text
