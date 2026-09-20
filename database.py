import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from mealdb import extract_ingredients


DATABASE_PATH = Path(__file__).with_name("recipes.db")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _initialize_database() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS favorite_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recipe_id TEXT NOT NULL,
                title TEXT NOT NULL,
                photo_url TEXT,
                category TEXT,
                area TEXT,
                ingredients TEXT NOT NULL,
                instructions TEXT NOT NULL,
                youtube_url TEXT,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, recipe_id)
            )
            """
        )


async def initialize_database() -> None:
    await asyncio.to_thread(_initialize_database)


def _save_favorite(user_id: int, meal: dict[str, Any], rating: int) -> None:
    ingredients = [
        {"name": ingredient, "measure": measure}
        for ingredient, measure in extract_ingredients(meal)
    ]

    values = (
        user_id,
        str(meal.get("idMeal") or ""),
        str(meal.get("strMeal") or "Без названия").strip(),
        str(meal.get("strMealThumb") or "").strip(),
        str(meal.get("strCategory") or "Не указана").strip(),
        str(meal.get("strArea") or "Не указана").strip(),
        json.dumps(ingredients, ensure_ascii=False),
        str(meal.get("strInstructions") or "Инструкция отсутствует").strip(),
        str(meal.get("strYoutube") or "").strip(),
        rating,
    )

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO favorite_recipes (
                user_id,
                recipe_id,
                title,
                photo_url,
                category,
                area,
                ingredients,
                instructions,
                youtube_url,
                rating
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, recipe_id) DO UPDATE SET
                title = excluded.title,
                photo_url = excluded.photo_url,
                category = excluded.category,
                area = excluded.area,
                ingredients = excluded.ingredients,
                instructions = excluded.instructions,
                youtube_url = excluded.youtube_url,
                rating = excluded.rating,
                updated_at = CURRENT_TIMESTAMP
            """,
            values,
        )


async def save_favorite(user_id: int, meal: dict[str, Any], rating: int) -> None:
    await asyncio.to_thread(_save_favorite, user_id, meal, rating)


def _get_favorites(user_id: int) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT recipe_id, title, category, area, rating
            FROM favorite_recipes
            WHERE user_id = ?
            ORDER BY rating DESC, updated_at DESC, title COLLATE NOCASE
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


async def get_favorites(user_id: int) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_get_favorites, user_id)
