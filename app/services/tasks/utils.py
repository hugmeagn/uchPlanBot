# services/tasks/utils.py

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import re

import pytz

import config
from .models import Task
import bot.utils.dates as dates


def generate_reminder_times(
        deadline: datetime,
        minutes_before: List[int]
) -> List[datetime]:
    """
    Генерирует времена напоминаний на основе дедлайна
    """
    # Убеждаемся, что deadline aware
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    reminders = []
    now = dates.now()

    for minutes in minutes_before:
        reminder_time = deadline - timedelta(minutes=minutes)
        if reminder_time > now:
            reminders.append(reminder_time)
    return reminders


def parse_deadline(text: str) -> Optional[datetime]:
    """
    Пытается распарсить дату из текста
    Поддерживает форматы:
    - завтра 15:00
    - послезавтра 18:30
    - 25.12 14:00
    - 25.12.2024 15:30
    - через 2 часа
    - через 30 минут

    Возвращает datetime в UTC
    """
    text = text.lower().strip()
    now_local = dates.now()  # локальное время с таймзоной

    # Завтра
    if text.startswith('завтра'):
        time_part = text.replace('завтра', '').strip()
        if time_part:
            try:
                hour, minute = map(int, time_part.split(':'))
                # Создаем локальное время на завтра
                result_local = datetime(
                    now_local.year, now_local.month, now_local.day,
                    hour, minute, 0, 0
                ) + timedelta(days=1)
                # Добавляем таймзону
                result_local = config.TIMEZONE_OBJ.localize(result_local)
                # Конвертируем в UTC для хранения
                return result_local.astimezone(pytz.UTC)
            except:
                pass
        # Если время не указано, ставим 00:00
        result_local = datetime(
            now_local.year, now_local.month, now_local.day,
            0, 0, 0, 0
        ) + timedelta(days=1)
        result_local = config.TIMEZONE_OBJ.localize(result_local)
        return result_local.astimezone(pytz.UTC)

    # Послезавтра
    if text.startswith('послезавтра'):
        result_local = datetime(
            now_local.year, now_local.month, now_local.day,
            0, 0, 0, 0
        ) + timedelta(days=2)
        result_local = config.TIMEZONE_OBJ.localize(result_local)
        return result_local.astimezone(pytz.UTC)

    # Через N часов/минут
    match = re.match(r'через\s+(\d+)\s*(часа?|часов|минуты?|минут)', text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)

        if 'час' in unit:
            result_local = now_local + timedelta(hours=amount)
        elif 'минут' in unit:
            result_local = now_local + timedelta(minutes=amount)
        else:
            return None

        # Конвертируем в UTC для хранения
        return result_local.astimezone(pytz.UTC)

    # Дата в формате ДД.ММ [ЧЧ:ММ]
    match = re.match(r'(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*(?:(\d{1,2}):(\d{1,2}))?', text)
    if match:
        day, month, year, hour, minute = match.groups()

        year = int(year) if year else now_local.year
        month = int(month)
        day = int(day)
        hour = int(hour) if hour else 0
        minute = int(minute) if minute else 0

        try:
            # Создаем datetime в локальной таймзоне
            result_local = datetime(year, month, day, hour, minute, 0, 0)
            result_local = config.TIMEZONE_OBJ.localize(result_local)

            # Если дата в прошлом и это не сегодня, возможно пользователь имел в виду следующий год
            if result_local < now_local and result_local.date() != now_local.date():
                result_local = result_local.replace(year=year + 1)

            # Конвертируем в UTC для хранения
            return result_local.astimezone(pytz.UTC)
        except ValueError:
            pass

    return None


def format_time_left(deadline: datetime) -> str:
    """
    Форматирует оставшееся время до дедлайна
    """
    # Убеждаемся, что deadline aware
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    now = dates.now()  # Это уже локальное время с таймзоной

    # Приводим к одному формату для сравнения
    if now.tzinfo != deadline.tzinfo:
        # Если таймзоны разные, конвертируем
        deadline = deadline.astimezone(now.tzinfo)

    if deadline < now:
        return "просрочено"

    delta = deadline - now
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    if days > 0:
        return f"{days}д {hours}ч"
    elif hours > 0:
        return f"{hours}ч {minutes}м"
    else:
        return f"{minutes}м"


def validate_task_title(title: str) -> bool:
    """
    Проверяет корректность заголовка задачи
    """
    if not title or len(title.strip()) == 0:
        return False

    if len(title) > 200:
        return False

    # Запрещаем только пробелы и спецсимволы
    if title.strip() in ['.', ',', '!', '?', '-', '_']:
        return False

    return True


def generate_task_summary(tasks: List[Task]) -> str:
    """
    Генерирует краткое summary по задачам
    """
    if not tasks:
        return "Нет задач"

    total = len(tasks)
    active = sum(1 for t in tasks if t.status == "active")
    overdue = sum(1 for t in tasks if t.status == "overdue")
    completed = sum(1 for t in tasks if t.status == "completed")

    summary = f"📊 Всего задач: {total}\n"
    summary += f"✅ Активных: {active}\n"

    if overdue > 0:
        summary += f"⚠️ Просрочено: {overdue}\n"

    if completed > 0:
        summary += f"✔️ Выполнено: {completed}\n"

    # Ближайшие дедлайны
    now = dates.now()
    upcoming = [t for t in tasks if t.deadline and t.deadline > now and t.status == "active"]
    upcoming.sort(key=lambda x: x.deadline)

    if upcoming:
        summary += "\n📅 Ближайшие:\n"
        for task in upcoming[:3]:
            time_left = format_time_left(task.deadline)
            summary += f"  • {task.title} ({time_left})\n"

    return summary
