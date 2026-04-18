"""
Хендлеры расписания
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..vk_api.client import VkMessage
from ..keyboards.schedule import get_schedule_menu_keyboard, get_schedule_day_keyboard
from ..keyboards.base import create_back_keyboard
from ..handlers import router
from models.user import User
from services.schedule.factory import ParserFactory
from ..utils.vk_utils import format_message, chunk_text
import bot.utils.dates as dates

logger = logging.getLogger(__name__)

_parsers_cache = {}


def get_parser(institution_name: str, is_teacher: bool = False):
    """Получает парсер для учебного заведения"""
    college_id = "magpk"
    cache_key = f"{college_id}_{'teacher' if is_teacher else 'student'}"

    if cache_key not in _parsers_cache:
        _parsers_cache[cache_key] = ParserFactory.get_parser(college_id, teacher_mode=is_teacher)

    return _parsers_cache[cache_key]


def format_day_schedule(schedule: dict, title: str = "", is_teacher: bool = False) -> str:
    """Форматирует расписание на день"""
    lines = []

    if title:
        lines.append(f"📅 {title}\n")

    if not schedule:
        return "❌ Пар нет или расписание не найдено"

    for day_name, lessons in schedule.items():
        lines.append(f"\n📌 {day_name}")

        if not lessons:
            lines.append("   Пар нет")
        else:
            for lesson in lessons:
                time_str = f"{lesson.time_start}–{lesson.time_end}"
                lines.append(f"   {lesson.number} пара: {time_str}")

                if lesson.room:
                    lines.append(f"   {lesson.name} / {lesson.room}")
                else:
                    lines.append(f"   {lesson.name}")

                if is_teacher:
                    if lesson.teacher and lesson.teacher != "Самостоятельная работа":
                        lines.append(f"   👥 Группа: {lesson.teacher}")
                else:
                    if lesson.teacher and lesson.teacher != "Самостоятельная работа":
                        lines.append(f"   👨‍🏫 {lesson.teacher}")

                lines.append("")

    return "\n".join(lines)


def format_week_schedule(schedule: dict, title: str = "", is_teacher: bool = False) -> str:
    """Форматирует расписание на неделю"""
    lines = []

    if title:
        lines.append(f"📅 {title}\n")

    if not schedule:
        return "❌ Пар нет или расписание не найдено"

    days = list(schedule.items())

    for i, (day_name, lessons) in enumerate(days):
        lines.append(f"\n📌 {day_name}")

        if not lessons:
            lines.append("   Пар нет")
        else:
            for lesson in lessons:
                time_str = f"{lesson.time_start}–{lesson.time_end}"
                lines.append(f"   {lesson.number} пара: {time_str}")

                if lesson.room:
                    lines.append(f"   {lesson.name} / {lesson.room}")
                else:
                    lines.append(f"   {lesson.name}")

                if is_teacher:
                    if lesson.teacher and lesson.teacher != "Самостоятельная работа":
                        lines.append(f"   👥 Группа: {lesson.teacher}")
                else:
                    if lesson.teacher and lesson.teacher != "Самостоятельная работа":
                        lines.append(f"   👨‍🏫 {lesson.teacher}")

                lines.append("")

        if i < len(days) - 1:
            lines.append("   " + "─" * 30)

    return "\n".join(lines)


@router.command("schedule")
@router.callback("menu_schedule")
async def show_schedule_menu(message: VkMessage, state: Optional[str], data: dict):
    """Показывает меню расписания"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.clear(user_id)

    user = await User.get_or_none(vk_id=user_id).select_related('institution')

    if not user:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Профиль не найден! Используйте /start для регистрации.",
            keyboard=create_back_keyboard("back_to_menu")
        )
        return

    if user.role == "teacher":
        if not user.full_name:
            await vk.send_message(
                peer_id=user_id,
                text="❌ У вас не указано ФИО. Настройте профиль.",
                keyboard=create_back_keyboard("back_to_menu")
            )
            return
        role_text = "преподавателя"
    else:
        if not user.group:
            await vk.send_message(
                peer_id=user_id,
                text="❌ У вас не выбрана группа. Настройте профиль.",
                keyboard=create_back_keyboard("back_to_menu")
            )
            return
        role_text = "студента"

    text = (
        f"📚 **Расписание занятий**\n"
        f"👤 Роль: **{role_text}**\n"
        f"🏫 Уч. заведение: **{user.institution.name if user.institution else 'Не указано'}**\n\n"
        f"Выберите период:"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_schedule_menu_keyboard()
    )


@router.callback("schedule:today")
async def show_today_schedule(message: VkMessage, state: Optional[str], data: dict):
    """Показывает расписание на сегодня"""
    await show_day_schedule(message, state, data, dates.now())


@router.callback("schedule:tomorrow")
async def show_tomorrow_schedule(message: VkMessage, state: Optional[str], data: dict):
    """Показывает расписание на завтра"""
    tomorrow = dates.now() + timedelta(days=1)
    await show_day_schedule(message, state, data, tomorrow)


async def show_day_schedule(message: VkMessage, state: Optional[str], data: dict, target_date: datetime):
    """Показывает расписание на конкретный день"""
    vk = data['vk']
    user_id = message.from_id

    user = await User.get_or_none(vk_id=user_id).select_related('institution')

    if not user:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Профиль не найден.",
            keyboard=create_back_keyboard("back_to_menu")
        )
        return

    is_teacher = user.role == "teacher"
    search_param = user.full_name if is_teacher else user.group

    # Отправляем сообщение о загрузке
    loading_msg = await vk.send_message(
        peer_id=user_id,
        text="⏳ Загружаю расписание..."
    )

    try:
        parser = get_parser(
            user.institution.name if user.institution else None,
            is_teacher=is_teacher
        )

        schedule = await parser.get_day_schedule(search_param, target_date)

        today = dates.now().date()
        if target_date.date() == today:
            title = f"Расписание на СЕГОДНЯ ({target_date.strftime('%d.%m.%Y')})"
        elif target_date.date() == today + timedelta(days=1):
            title = f"Расписание на ЗАВТРА ({target_date.strftime('%d.%m.%Y')})"
        else:
            title = f"Расписание на {target_date.strftime('%d.%m.%Y')}"

        formatted = format_day_schedule(schedule, title, is_teacher)

        show_today_btn = target_date.date() != today

        for chunk in chunk_text(formatted, 3800):
            await vk.send_message(
                peer_id=user_id,
                text=chunk,
                keyboard=get_schedule_day_keyboard(
                    target_date.strftime('%Y-%m-%d'),
                    show_today=show_today_btn
                ) if chunk == chunk_text(formatted, 3800)[-1] else None
            )

    except Exception as e:
        logger.error(f"Error getting schedule: {e}", exc_info=True)
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при загрузке расписания.",
            keyboard=create_back_keyboard("schedule:main")
        )


@router.callback("schedule:week_current")
async def show_current_week_schedule(message: VkMessage, state: Optional[str], data: dict):
    """Показывает расписание на текущую неделю"""
    await show_week_schedule(message, state, data, "current")


@router.callback("schedule:week_next")
async def show_next_week_schedule(message: VkMessage, state: Optional[str], data: dict):
    """Показывает расписание на следующую неделю"""
    await show_week_schedule(message, state, data, "next")


async def show_week_schedule(message: VkMessage, state: Optional[str], data: dict, week_type: str):
    """Показывает расписание на неделю"""
    vk = data['vk']
    user_id = message.from_id

    user = await User.get_or_none(vk_id=user_id).select_related('institution')

    if not user:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Профиль не найден.",
            keyboard=create_back_keyboard("back_to_menu")
        )
        return

    is_teacher = user.role == "teacher"
    search_param = user.full_name if is_teacher else user.group

    loading_msg = await vk.send_message(
        peer_id=user_id,
        text="⏳ Загружаю расписание на неделю..."
    )

    try:
        parser = get_parser(
            user.institution.name if user.institution else None,
            is_teacher=is_teacher
        )

        if week_type == "current":
            schedule = await parser.get_week_schedule(search_param)
            title = "Расписание на ТЕКУЩУЮ НЕДЕЛЮ"
        else:
            schedule = await parser.get_next_week_schedule(search_param)
            title = "Расписание на СЛЕДУЮЩУЮ НЕДЕЛЮ"

        formatted = format_week_schedule(schedule, title, is_teacher)

        for chunk in chunk_text(formatted, 3800):
            await vk.send_message(
                peer_id=user_id,
                text=chunk,
                keyboard=create_back_keyboard("schedule:main") if chunk == chunk_text(formatted, 3800)[-1] else None
            )

    except Exception as e:
        logger.error(f"Error getting week schedule: {e}", exc_info=True)
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при загрузке расписания.",
            keyboard=create_back_keyboard("schedule:main")
        )


@router.callback("schedule:date:")
async def show_schedule_by_date(message: VkMessage, state: Optional[str], data: dict):
    """Показывает расписание на выбранную дату"""
    callback = message.payload.get("callback")
    date_str = callback.replace("schedule:date:", "")

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        await show_day_schedule(message, state, data, target_date)
    except ValueError:
        vk = data['vk']
        await vk.send_message(
            peer_id=message.from_id,
            text="❌ Неверная дата.",
            keyboard=create_back_keyboard("schedule:main")
        )


@router.callback("schedule:main")
async def back_to_schedule_menu(message: VkMessage, state: Optional[str], data: dict):
    """Возврат в меню расписания"""
    await show_schedule_menu(message, state, data)
