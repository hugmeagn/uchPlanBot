# app/bot/handlers/schedule/schedule.py - исправленная версия с поддержкой преподавателей

"""
Обработчики расписания
"""
import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from services.schedule.factory import ParserFactory
from models.user import User

import bot.utils.dates as dates

from bot.handlers.menu.menu import show_main_menu

from .keyboards.main import get_schedule_main_keyboard, get_error_keyboard
from .keyboards.day_navigation import get_day_navigation_keyboard, get_week_navigation_keyboard

# Настраиваем логирование
logger = logging.getLogger(__name__)

# Создаем роутер
router = Router()

# Словарь для кэширования парсеров (чтобы не создавать каждый раз)
_parsers_cache = {}


def get_parser(institution_name: str, is_teacher: bool = False):
    """
    Получает парсер для учебного заведения.

    Args:
        institution_name: Название учебного заведения
        is_teacher: True для преподавателя, False для студента
    """
    # TODO: Сделать маппинг institution_name -> college_id
    # Пока для всех используем magpk
    college_id = "magpk"

    cache_key = f"{college_id}_{'teacher' if is_teacher else 'student'}"

    if cache_key not in _parsers_cache:
        _parsers_cache[cache_key] = ParserFactory.get_parser(college_id, teacher_mode=is_teacher)
        logger.info(f"Created new parser for {cache_key}")

    return _parsers_cache[cache_key]


def format_day_schedule(schedule: dict, title: str = "", is_teacher: bool = False) -> str:
    """
    Форматирует расписание для вывода в Telegram в компактном виде.

    Формат:
    день (с эмодзи)
    1 пара: время
    название пары / аудитория
    группа (для преподавателя) или преподаватель (для студента)
    """
    if title:
        output = [f"📅 *{title}*\n"]
    else:
        output = []

    if not schedule:
        return "❌ *Пар нет или расписание не найдено*"

    for day_name, lessons in schedule.items():
        # Эмодзи перед названием дня оставляем
        output.append(f"\n📌 *{day_name}*")

        if not lessons:
            output.append("   Пар нет")
        else:
            for lesson in lessons:
                # Номер и время пары
                time_str = f"{lesson.time_start}–{lesson.time_end}"
                output.append(f"   {lesson.number} пара: {time_str}")

                # Название пары и аудитория
                if lesson.room:
                    output.append(f"   {lesson.name} / {lesson.room}")
                else:
                    output.append(f"   {lesson.name}")

                # Для преподавателя показываем группу, для студента - преподавателя
                if is_teacher:
                    if lesson.teacher and lesson.teacher != "Самостоятельная работа":
                        output.append(f"   👥 Группа: {lesson.teacher}")
                else:
                    if lesson.teacher and lesson.teacher != "Самостоятельная работа":
                        output.append(f"   👨‍🏫 {lesson.teacher}")
                    elif lesson.teacher == "Самостоятельная работа":
                        output.append(f"   Самостоятельная работа")

                # Пустая строка между парами для читаемости
                output.append("")

    return "\n".join(output)


def format_week_schedule(schedule: dict, title: str = "", is_teacher: bool = False) -> str:
    """
    Форматирует расписание на неделю с разделителями между днями.
    """
    if title:
        output = [f"📅 *{title}*\n"]
    else:
        output = []

    if not schedule:
        return "❌ *Пар нет или расписание не найдено*"

    days = list(schedule.items())

    for i, (day_name, lessons) in enumerate(days):
        # Эмодзи перед названием дня оставляем
        output.append(f"\n📌 *{day_name}*")

        if not lessons:
            output.append("   Пар нет")
        else:
            for lesson in lessons:
                # Номер и время пары
                time_str = f"{lesson.time_start}–{lesson.time_end}"
                output.append(f"   {lesson.number} пара: {time_str}")

                # Название пары и аудитория
                if lesson.room:
                    output.append(f"   {lesson.name} / {lesson.room}")
                else:
                    output.append(f"   {lesson.name}")

                # Для преподавателя показываем группу, для студента - преподавателя
                if is_teacher:
                    if lesson.teacher and lesson.teacher != "Самостоятельная работа":
                        output.append(f"   👥 Группа: {lesson.teacher}")
                else:
                    if lesson.teacher and lesson.teacher != "Самостоятельная работа":
                        output.append(f"   👨‍🏫 {lesson.teacher}")
                    elif lesson.teacher == "Самостоятельная работа":
                        output.append(f"   Самостоятельная работа")

                # Пустая строка между парами
                output.append("")

        # Добавляем разделитель между днями (кроме последнего)
        if i < len(days) - 1:
            output.append("   " + "─" * 35)

    return "\n".join(output)


def get_weekday_name_russian(date: datetime) -> str:
    """Возвращает название дня недели по-русски в родительном падеже."""
    weekdays = {
        0: "понедельник",
        1: "вторник",
        2: "среду",
        3: "четверг",
        4: "пятницу",
        5: "субботу",
        6: "воскресенье"
    }
    return weekdays[date.weekday()]


@router.callback_query(F.data == "menu_schedule")
async def show_schedule_menu(callback: CallbackQuery):
    """
    Показывает главное меню расписания с выбором периода.
    """
    user = await User.get_or_none(telegram_id=callback.from_user.id).select_related('institution')

    if not user:
        await callback.message.edit_text(
            "❌ *Профиль не найден!*\n\n"
            "Пожалуйста, сначала используйте /start для регистрации.",
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    # Проверяем наличие необходимых данных в зависимости от роли
    if user.role == "teacher":
        if not user.full_name:
            await callback.message.edit_text(
                "❌ *У вас не указано ФИО*\n\n"
                "Пожалуйста, укажите ваше ФИО в настройках профиля.",
                parse_mode="Markdown"
            )
            await callback.answer()
            return
        search_param = user.full_name
        role_text = "преподавателя"
    else:
        if not user.group:
            await callback.message.edit_text(
                "❌ *У вас не выбрана группа*\n\n"
                "Пожалуйста, сначала укажите вашу группу в настройках профиля.",
                parse_mode="Markdown"
            )
            await callback.answer()
            return
        search_param = user.group
        role_text = "студента"

    await callback.message.edit_text(
        f"📚 *Расписание занятий*\n"
        f"👤 Роль: *{role_text}*\n"
        f"🏫 Уч. заведение: *{user.institution.name if user.institution else 'Не указано'}*\n\n"
        f"Выберите период:",
        parse_mode="Markdown",
        reply_markup=get_schedule_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("schedule:"))
async def process_schedule_callback(callback: CallbackQuery):
    """
    Обрабатывает все callback'и связанные с расписанием.
    """
    # Получаем пользователя
    user = await User.get_or_none(telegram_id=callback.from_user.id).select_related('institution')
    if not user:
        await callback.message.edit_text(
            "❌ *Профиль не найден!*\n\n"
            "Пожалуйста, сначала используйте /start для регистрации.",
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    # Определяем параметр поиска в зависимости от роли
    if user.role == "teacher":
        if not user.full_name:
            await callback.message.edit_text(
                "❌ *У вас не указано ФИО*\n\n"
                "Пожалуйста, укажите ваше ФИО в настройках профиля.",
                parse_mode="Markdown"
            )
            await callback.answer()
            return
        search_param = user.full_name
        is_teacher = True
    else:
        if not user.group:
            await callback.message.edit_text(
                "❌ *У вас не выбрана группа*\n\n"
                "Пожалуйста, сначала укажите вашу группу в настройках профиля.",
                parse_mode="Markdown"
            )
            await callback.answer()
            return
        search_param = user.group
        is_teacher = False

    action = callback.data.split(":")[1]

    # Показываем сообщение загрузки
    loading_msg = await callback.message.edit_text(
        "⏳ *Загружаю расписание...*",
        parse_mode="Markdown"
    )

    try:
        # Получаем парсер
        parser = get_parser(
            user.institution.name if user.institution else None,
            is_teacher=is_teacher
        )

        # Обрабатываем разные действия
        if action == "main":
            await loading_msg.edit_text(
                f"📚 *Расписание занятий*\n"
                f"👤 Роль: *{'преподаватель' if is_teacher else 'студент'}*\n\n"
                f"Выберите период:",
                parse_mode="Markdown",
                reply_markup=get_schedule_main_keyboard()
            )

        elif action == "today":
            await show_day_schedule(loading_msg, search_param, dates.now(), is_teacher)

        elif action == "tomorrow":
            tomorrow = dates.now() + timedelta(days=1)
            await show_day_schedule(loading_msg, search_param, tomorrow, is_teacher)

        elif action == "week_current":
            await show_week_schedule(loading_msg, search_param, "current", is_teacher)

        elif action == "week_next":
            await show_week_schedule(loading_msg, search_param, "next", is_teacher)

        elif action == "date":
            date_str = callback.data.split(":")[2]
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            await show_day_schedule(loading_msg, search_param, target_date, is_teacher)

    except Exception as e:
        logger.error(f"Ошибка при получении расписания: {e}", exc_info=True)
        await loading_msg.edit_text(
            "❌ *Произошла ошибка при загрузке расписания*\n"
            "Попробуйте позже или выберите другой период.",
            parse_mode="Markdown",
            reply_markup=get_error_keyboard()
        )
    finally:
        await callback.answer()


async def show_day_schedule(message: Message, search_param: str, target_date: datetime, is_teacher: bool):
    """
    Показывает расписание на конкретный день.

    Args:
        message: Сообщение для ответа
        search_param: Название группы или ФИО преподавателя
        target_date: Целевая дата
        is_teacher: True для преподавателя, False для студента
    """
    parser = get_parser(None, is_teacher=is_teacher)

    # Получаем расписание
    schedule = await parser.get_day_schedule(search_param, target_date)

    # Формируем заголовок
    today = dates.now().date()
    if target_date.date() == today:
        title = f"Расписание на СЕГОДНЯ ({target_date.strftime('%d.%m.%Y')})"
    elif target_date.date() == today + timedelta(days=1):
        title = f"Расписание на ЗАВТРА ({target_date.strftime('%d.%m.%Y')})"
    else:
        weekday = get_weekday_name_russian(target_date)
        title = f"Расписание на {weekday} ({target_date.strftime('%d.%m.%Y')})"

    # Форматируем и отправляем
    formatted = format_day_schedule(schedule, title, is_teacher)

    # Определяем, показывать ли кнопку "Сегодня"
    show_today = target_date.date() != today

    await message.edit_text(
        formatted,
        parse_mode="Markdown",
        reply_markup=get_day_navigation_keyboard(target_date, show_today)
    )


async def show_week_schedule(message: Message, search_param: str, week_type: str, is_teacher: bool):
    """
    Показывает расписание на неделю.

    Args:
        message: Сообщение для ответа
        search_param: Название группы или ФИО преподавателя
        week_type: "current" или "next"
        is_teacher: True для преподавателя, False для студента
    """
    parser = get_parser(None, is_teacher=is_teacher)

    # Получаем расписание
    if week_type == "current":
        schedule = await parser.get_week_schedule(search_param)
        title = f"Расписание на ТЕКУЩУЮ НЕДЕЛЮ"
    else:
        schedule = await parser.get_next_week_schedule(search_param)
        title = f"Расписание на СЛЕДУЮЩУЮ НЕДЕЛЮ"

    # Форматируем и отправляем
    formatted = format_week_schedule(schedule, title, is_teacher)

    await message.edit_text(
        formatted,
        parse_mode="Markdown",
        reply_markup=get_week_navigation_keyboard(week_type)
    )


@router.callback_query(F.data == "main_menu")
async def return_to_main_menu(callback: CallbackQuery):
    """
    Возвращает в главное меню.
    """
    await show_main_menu(callback)
    