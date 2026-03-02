"""
Хендлеры для работы с ежедневными планами
"""
import logging
from datetime import datetime, timedelta, date
from typing import Union, Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from bot.handlers.menu.keyboards.common import back_button_kb
from bot.utils import dates
from models.user import User
from models.daily_plan import DailyPlan
from bot_integration.integration import get_integration

logger = logging.getLogger(__name__)

router = Router()


# ==================== КОМАНДЫ ====================

@router.message(Command("plan"))
@router.message(F.text == "📅 План на сегодня")
async def cmd_show_today_plan(message: Message):
    """Показать план на сегодня"""
    user_id = message.from_user.id
    logger.info(f"Plan today command from user {user_id}")
    await show_plan(user_id, message, dates.today())


@router.message(Command("plan_tomorrow"))
async def cmd_show_tomorrow_plan(message: Message):
    """Показать план на завтра"""
    user_id = message.from_user.id
    logger.info(f"Plan tomorrow command from user {user_id}")
    await show_plan(user_id, message, dates.today() + timedelta(days=1))


@router.callback_query(F.data == "menu_plan_today")
async def callback_show_today_plan(callback: CallbackQuery):
    """Показать план на сегодня (из меню)"""
    user_id = callback.from_user.id
    logger.info(f"Plan today callback from user {user_id}")
    await callback.answer()
    await show_plan(user_id, callback.message, dates.today())


@router.callback_query(F.data == "menu_plan_tomorrow")
async def callback_show_tomorrow_plan(callback: CallbackQuery):
    """Показать план на завтра (из меню)"""
    user_id = callback.from_user.id
    logger.info(f"Plan tomorrow callback from user {user_id}")
    await callback.answer()
    await show_plan(user_id, callback.message, dates.today() + timedelta(days=1))


@router.callback_query(F.data == "menu_plan_refresh_today")
async def callback_refresh_today_plan(callback: CallbackQuery):
    """Принудительно обновить план на сегодня"""
    user_id = callback.from_user.id
    logger.info(f"Refresh today plan callback from user {user_id}")

    await callback.answer()
    await refresh_plan(callback, dates.today(), "сегодня")


@router.callback_query(F.data == "menu_plan_refresh_tomorrow")
async def callback_refresh_tomorrow_plan(callback: CallbackQuery):
    """Принудительно обновить план на завтра"""
    user_id = callback.from_user.id
    tomorrow = dates.today() + timedelta(days=1)
    logger.info(f"Refresh tomorrow plan callback from user {user_id}")

    await callback.answer()
    await refresh_plan(callback, tomorrow, "завтра")


async def refresh_plan(callback: CallbackQuery, target_date: date, date_name: str):
    """
    Обновляет план на указанную дату

    Args:
        callback: CallbackQuery
        target_date: Дата для обновления
        date_name: Название даты для сообщения (сегодня/завтра)
    """
    integration = await get_integration()
    user_id = callback.from_user.id

    # Получаем пользователя по telegram_id из callback
    user = await User.get_or_none(telegram_id=user_id)

    if not user:
        await callback.message.edit_text(
            "❌ **Пользователь не найден!**\n"
            "Пожалуйста, используйте /start для регистрации.",
            reply_markup=back_button_kb()
        )
        return

    await callback.message.edit_text(
        f"🔄 **Генерирую новый план на {date_name}...**\n"
        "Это может занять несколько секунд.",
        parse_mode="Markdown"
    )

    # Принудительно генерируем новый план
    result = await integration.day_planner.get_or_generate_plan(
        user=user,
        target_date=target_date,
        force_refresh=True
    )

    if result.success:
        # Определяем заголовок
        if target_date == dates.today():
            title = "🌅 **Ваш обновленный план на сегодня:**\n\n"
        elif target_date == dates.today() + timedelta(days=1):
            title = "🌄 **Обновленный план на завтра:**\n\n"
        else:
            title = f"📅 **Обновленный план на {target_date.strftime('%d.%m.%Y')}:**\n\n"

        await callback.message.edit_text(
            title + result.plan,
            parse_mode="Markdown",
            reply_markup=get_plan_actions_keyboard(target_date)
        )
    else:
        await callback.message.edit_text(
            f"❌ **Ошибка при генерации плана:**\n{result.error}",
            reply_markup=back_button_kb()
        )


@router.callback_query(F.data.startswith("plan_rate_"))
async def rate_plan(callback: CallbackQuery):
    """Оценить план"""
    rating = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    logger.info(f"Rate plan {rating} from user {user_id}")

    # Получаем пользователя по telegram_id из callback
    user = await User.get_or_none(telegram_id=user_id)

    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    today = dates.today()
    plan = await DailyPlan.filter(user=user, plan_date=today).first()

    if plan:
        plan.rating = rating
        await plan.save()

        await callback.answer(f"Спасибо за оценку {rating}⭐!")

        # Если оценка низкая, предлагаем улучшить
        if rating <= 3:
            await callback.message.answer(
                "💡 Хотите, чтобы планы были лучше? "
                "Попробуйте добавить больше задач или обновить расписание.",
                reply_markup=back_button_kb()
            )
    else:
        await callback.answer("План не найден", show_alert=True)


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

async def show_plan(
    user_id: int,
    message: Message,
    target_date: date
):
    """
    Показывает план на указанную дату

    Args:
        user_id: ID пользователя Telegram
        message: Сообщение для ответа
        target_date: Дата, на которую нужен план
    """
    logger.info(f"Showing plan for user {user_id} on date {target_date}")

    integration = await get_integration()

    # Получаем пользователя из БД по telegram_id
    user = await User.get_or_none(telegram_id=user_id)

    if not user:
        await message.answer(
            "❌ **Сначала запустите бота!**\n"
            "Используйте команду /start для регистрации.",
            reply_markup=back_button_kb()
        )
        return

    if not user.group:
        await message.answer(
            "❌ **Сначала настройте профиль!**\n"
            "Укажите вашу группу в настройках (/profile).",
            reply_markup=back_button_kb()
        )
        return

    # Показываем загрузку
    loading_msg = await message.answer(
        "🧠 **Думаю над вашим планом...**\n"
        "Это может занять до 10 секунд.",
        parse_mode="Markdown"
    )

    # Получаем план
    try:
        result = await integration.day_planner.get_or_generate_plan(
            user=user,
            target_date=target_date
        )

        if result.success:
            # Определяем заголовок
            today = dates.today()
            if target_date == today:
                title = "🌅 **Ваш план на сегодня:**\n\n"
            elif target_date == today + timedelta(days=1):
                title = "🌄 **План на завтра:**\n\n"
            else:
                title = f"📅 **План на {target_date.strftime('%d.%m.%Y')}:**\n\n"

            # Если план из кэша, добавляем пометку
            if result.from_cache:
                title = "📋 (из кэша) " + title

            await loading_msg.edit_text(
                title + result.plan,
                parse_mode="Markdown",
                reply_markup=get_plan_actions_keyboard(target_date)
            )
        else:
            await loading_msg.edit_text(
                f"❌ **Не удалось сгенерировать план**\n\n"
                f"Причина: {result.error}\n\n"
                f"Попробуйте позже или обратитесь к администратору.",
                reply_markup=back_button_kb()
            )
    except Exception as e:
        logger.error(f"Error generating plan for user {user_id}: {e}", exc_info=True)
        await loading_msg.edit_text(
            f"❌ **Произошла ошибка**\n\n"
            f"{str(e)}",
            reply_markup=back_button_kb()
        )


def get_plan_actions_keyboard(target_date: date):
    """
    Клавиатура с действиями для плана

    Args:
        target_date: Дата, для которой показывается план
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    today = dates.today()
    tomorrow = today + timedelta(days=1)

    # Кнопки оценки
    builder.row(
        InlineKeyboardButton(text="⭐ 1", callback_data="plan_rate_1"),
        InlineKeyboardButton(text="⭐ 2", callback_data="plan_rate_2"),
        InlineKeyboardButton(text="⭐ 3", callback_data="plan_rate_3"),
        InlineKeyboardButton(text="⭐ 4", callback_data="plan_rate_4"),
        InlineKeyboardButton(text="⭐ 5", callback_data="plan_rate_5"),
        width=5
    )

    # Кнопки обновления в зависимости от даты
    if target_date == today:
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить сегодня", callback_data="menu_plan_refresh_today"),
            width=1
        )
    elif target_date == tomorrow:
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить завтра", callback_data="menu_plan_refresh_tomorrow"),
            width=1
        )
    else:
        # Для других дат пока просто заглушка
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"menu_plan_refresh_{target_date.isoformat()}"),
            width=1
        )

    # Кнопки навигации
    nav_buttons = []
    if target_date != today:
        nav_buttons.append(
            InlineKeyboardButton(text="📅 Сегодня", callback_data="menu_plan_today")
        )
    if target_date != tomorrow:
        nav_buttons.append(
            InlineKeyboardButton(text="📅 Завтра", callback_data="menu_plan_tomorrow")
        )

    if nav_buttons:
        builder.row(*nav_buttons, width=len(nav_buttons))

    builder.row(
        InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu"),
        width=1
    )

    return builder.as_markup()
