"""
Хендлеры для работы с ежедневными планами
"""
import logging
from datetime import timedelta
from typing import Optional

from ..vk_api.client import VkMessage
from ..keyboards.base import create_back_keyboard
from ..handlers import router
from models.user import User
from models.daily_plan import DailyPlan
from ..utils.vk_utils import format_message, chunk_text, create_keyboard, create_text_button
import bot.utils.dates as dates

logger = logging.getLogger(__name__)


def get_plan_actions_keyboard(target_date, from_cache: bool = False):
    """Клавиатура с действиями для плана"""
    today = dates.today()
    tomorrow = today + timedelta(days=1)

    buttons = []

    # Кнопки оценки
    rating_row = []
    for i in range(1, 6):
        rating_row.append(create_text_button(
            f"{'⭐' * i}",
            {"callback": f"plan_rate_{i}"},
            "secondary"
        ))
    buttons.append(rating_row)

    # Кнопки обновления
    if target_date == today:
        buttons.append([create_text_button(
            "🔄 Обновить сегодня",
            {"callback": "plan_refresh_today"},
            "primary"
        )])
    elif target_date == tomorrow:
        buttons.append([create_text_button(
            "🔄 Обновить завтра",
            {"callback": "plan_refresh_tomorrow"},
            "primary"
        )])

    # Кнопки навигации
    nav_row = []
    if target_date != today:
        nav_row.append(create_text_button("📅 Сегодня", {"callback": "menu_plan_today"}, "secondary"))
    if target_date != tomorrow:
        nav_row.append(create_text_button("📅 Завтра", {"callback": "menu_plan_tomorrow"}, "secondary"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([create_text_button("🏠 Главное меню", {"callback": "back_to_menu"}, "secondary")])

    return create_keyboard(buttons)


@router.command("plan")
@router.callback("menu_plan_today")
async def show_today_plan(message: VkMessage, state: Optional[str], data: dict):
    """Показывает план на сегодня"""
    await show_plan(message, state, data, dates.today())


@router.command("plan_tomorrow")
@router.callback("menu_plan_tomorrow")
async def show_tomorrow_plan(message: VkMessage, state: Optional[str], data: dict):
    """Показывает план на завтра"""
    await show_plan(message, state, data, dates.today() + timedelta(days=1))


async def show_plan(message: VkMessage, state: Optional[str], data: dict, target_date):
    """Показывает план на указанную дату"""
    vk = data['vk']
    day_planner = data['day_planner']
    user_id = message.from_id

    user = await User.get_or_none(vk_id=user_id)

    if not user:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Сначала настройте профиль! Используйте /start.",
            keyboard=create_back_keyboard("back_to_menu")
        )
        return

    if not user.group and user.role != "teacher":
        await vk.send_message(
            peer_id=user_id,
            text="❌ Укажите вашу группу в настройках профиля.",
            keyboard=create_back_keyboard("back_to_menu")
        )
        return

    # Отправляем сообщение о загрузке
    await vk.send_message(
        peer_id=user_id,
        text="🧠 **Думаю над вашим планом...**\nЭто может занять до 10 секунд."
    )

    try:
        result = await day_planner.get_or_generate_plan(
            user=user,
            target_date=target_date
        )

        if result.success:
            today = dates.today()
            if target_date == today:
                title = "🌅 **Ваш план на сегодня:**\n\n"
            elif target_date == today + timedelta(days=1):
                title = "🌄 **План на завтра:**\n\n"
            else:
                title = f"📅 **План на {target_date.strftime('%d.%m.%Y')}:**\n\n"

            if result.from_cache:
                title = "📋 (из кэша) " + title

            full_text = title + result.plan

            # Разбиваем длинный текст на части
            chunks = chunk_text(full_text, 3800)

            for i, chunk in enumerate(chunks):
                # Клавиатуру добавляем только к последнему сообщению
                keyboard = get_plan_actions_keyboard(target_date, result.from_cache) if i == len(chunks) - 1 else None
                await vk.send_message(
                    peer_id=user_id,
                    text=chunk,
                    keyboard=keyboard
                )
        else:
            await vk.send_message(
                peer_id=user_id,
                text=f"❌ **Не удалось сгенерировать план**\n\nПричина: {result.error}",
                keyboard=create_back_keyboard("back_to_menu")
            )

    except Exception as e:
        logger.error(f"Error generating plan: {e}", exc_info=True)
        await vk.send_message(
            peer_id=user_id,
            text="❌ Произошла ошибка при генерации плана.",
            keyboard=create_back_keyboard("back_to_menu")
        )


@router.callback("plan_refresh_today")
async def refresh_today_plan(message: VkMessage, state: Optional[str], data: dict):
    """Принудительно обновляет план на сегодня"""
    await refresh_plan(message, state, data, dates.today(), "сегодня")


@router.callback("plan_refresh_tomorrow")
async def refresh_tomorrow_plan(message: VkMessage, state: Optional[str], data: dict):
    """Принудительно обновляет план на завтра"""
    tomorrow = dates.today() + timedelta(days=1)
    await refresh_plan(message, state, data, tomorrow, "завтра")


async def refresh_plan(message: VkMessage, state: Optional[str], data: dict, target_date, date_name: str):
    """Обновляет план на указанную дату"""
    vk = data['vk']
    day_planner = data['day_planner']
    user_id = message.from_id

    user = await User.get_or_none(vk_id=user_id)

    if not user:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Пользователь не найден.",
            keyboard=create_back_keyboard("back_to_menu")
        )
        return

    await vk.send_message(
        peer_id=user_id,
        text=f"🔄 **Генерирую новый план на {date_name}...**"
    )

    result = await day_planner.get_or_generate_plan(
        user=user,
        target_date=target_date,
        force_refresh=True
    )

    if result.success:
        if target_date == dates.today():
            title = "🌅 **Ваш обновленный план на сегодня:**\n\n"
        elif target_date == dates.today() + timedelta(days=1):
            title = "🌄 **Обновленный план на завтра:**\n\n"
        else:
            title = f"📅 **Обновленный план на {target_date.strftime('%d.%m.%Y')}:**\n\n"

        full_text = title + result.plan

        chunks = chunk_text(full_text, 3800)

        for i, chunk in enumerate(chunks):
            keyboard = get_plan_actions_keyboard(target_date) if i == len(chunks) - 1 else None
            await vk.send_message(
                peer_id=user_id,
                text=chunk,
                keyboard=keyboard
            )
    else:
        await vk.send_message(
            peer_id=user_id,
            text=f"❌ Ошибка при генерации плана:\n{result.error}",
            keyboard=create_back_keyboard("back_to_menu")
        )


@router.callback("plan_rate_")
async def rate_plan(message: VkMessage, state: Optional[str], data: dict):
    """Оценивает план"""
    vk = data['vk']
    user_id = message.from_id

    callback = message.payload.get("callback")
    rating = int(callback.replace("plan_rate_", ""))

    user = await User.get_or_none(vk_id=user_id)

    if not user:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Пользователь не найден."
        )
        return

    today = dates.today()
    plan = await DailyPlan.filter(user=user, plan_date=today).first()

    if plan:
        plan.rating = rating
        await plan.save()

        await vk.send_message(
            peer_id=user_id,
            text=f"Спасибо за оценку {'⭐' * rating}!"
        )

        if rating <= 3:
            await vk.send_message(
                peer_id=user_id,
                text="💡 Хотите, чтобы планы были лучше? Попробуйте добавить больше задач или обновить расписание.",
                keyboard=create_back_keyboard("back_to_menu")
            )
