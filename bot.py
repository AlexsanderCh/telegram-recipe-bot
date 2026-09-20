import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dotenv import load_dotenv

from database import get_favorites, initialize_database, save_favorite
from keyboards import main_menu, rating_keyboard
from mealdb import MealDBError, format_recipe, lookup_meal, search_meals


load_dotenv()

dp = Dispatcher()


class RecipeSearch(StatesGroup):
    waiting_for_query = State()


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Я помогу найти рецепты и сохранить понравившиеся.\n\n"
        "Выберите действие:",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "🔎 Поиск рецептов")
async def search_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(RecipeSearch.waiting_for_query)
    await message.answer(
        "Введите название блюда:",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "⭐ Мои рецепты")
async def favorites_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    favorites = await get_favorites(message.from_user.id)

    if not favorites:
        await message.answer(
            "У вас пока нет сохранённых рецептов.",
            reply_markup=main_menu(),
        )
        return

    entries = []
    for favorite in favorites:
        entries.append(
            f"{favorite['title']}\n"
            f"Рейтинг: {'⭐' * favorite['rating']}\n"
            f"Категория: {favorite['category']}\n"
            f"Кухня/страна: {favorite['area']}"
        )

    await send_text_chunks(
        message,
        "⭐ Мои рецепты\n\n" + "\n\n".join(entries),
        reply_markup=main_menu(),
    )


@dp.message(RecipeSearch.waiting_for_query, F.text)
async def recipe_query_handler(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите название блюда:", reply_markup=main_menu())
        return

    await state.clear()

    try:
        meals = await search_meals(query)
    except MealDBError:
        logging.exception("Ошибка запроса к TheMealDB")
        await message.answer(
            "Не удалось выполнить поиск. Попробуйте немного позже.",
            reply_markup=main_menu(),
        )
        return

    if not meals:
        await message.answer(
            "Рецепт не найден. Попробуйте другое название.",
            reply_markup=main_menu(),
        )
        return

    recipe = meals[0]
    recipe_id = str(recipe.get("idMeal") or "").strip()
    photo_url = str(recipe.get("strMealThumb") or "").strip()
    recipe_name = str(recipe.get("strMeal") or "Рецепт").strip()

    if photo_url:
        try:
            await message.answer_photo(photo=photo_url, caption=recipe_name)
        except Exception:
            logging.exception("Не удалось отправить фотографию рецепта")

    await send_text_chunks(
        message,
        format_recipe(recipe),
        reply_markup=rating_keyboard(recipe_id),
    )


@dp.callback_query(F.data.startswith("rate:"))
async def rating_handler(callback: CallbackQuery) -> None:
    try:
        _, recipe_id, rating_text = (callback.data or "").split(":", maxsplit=2)
        rating = int(rating_text)
        if not recipe_id or rating not in range(1, 6):
            raise ValueError
    except ValueError:
        await callback.answer("Некорректная оценка.", show_alert=True)
        return

    try:
        recipe = await lookup_meal(recipe_id)
    except MealDBError:
        logging.exception("Ошибка получения рецепта для сохранения")
        await callback.answer(
            "Не удалось сохранить рецепт. Попробуйте позже.",
            show_alert=True,
        )
        return

    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return

    await save_favorite(callback.from_user.id, recipe, rating)
    await callback.answer("Оценка сохранена")

    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Рецепт сохранён. Ваша оценка: {'⭐' * rating}",
            reply_markup=main_menu(),
        )


@dp.message(RecipeSearch.waiting_for_query)
async def non_text_query_handler(message: Message) -> None:
    await message.answer(
        "Введите название блюда текстом:",
        reply_markup=main_menu(),
    )


@dp.message()
async def unknown_message_handler(message: Message) -> None:
    await message.answer(
        "Пожалуйста, выберите действие с помощью кнопок ниже.",
        reply_markup=main_menu(),
    )


async def send_text_chunks(message: Message, text: str, reply_markup=None) -> None:
    chunks = [text[start : start + 4000] for start in range(0, len(text), 4000)] or [""]
    for index, chunk in enumerate(chunks):
        await message.answer(
            chunk,
            reply_markup=reply_markup if index == len(chunks) - 1 else None,
        )


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Переменная окружения BOT_TOKEN не задана")

    logging.basicConfig(level=logging.INFO)
    await initialize_database()
    bot = Bot(token=token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
