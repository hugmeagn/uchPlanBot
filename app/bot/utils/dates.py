# app/bot/utils/dates.py

"""
Утилиты для работы с датами и часовыми поясами
"""
from datetime import datetime, date, timedelta
from typing import Optional, Union
import pytz

from config import TIMEZONE_OBJ


def now() -> datetime:
    """
    Возвращает текущее время в часовом поясе из конфига
    """
    return datetime.now(TIMEZONE_OBJ)


def today() -> date:
    """
    Возвращает текущую дату в часовом поясе из конфига
    """
    return now().date()


def to_local(dt: datetime) -> datetime:
    """
    Конвертирует datetime в локальный часовой пояс
    """
    if dt.tzinfo is None:
        # Если datetime naive, считаем что это UTC и конвертируем
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(TIMEZONE_OBJ)


def to_utc(dt: datetime) -> datetime:
    """
    Конвертирует datetime в UTC
    """
    if dt.tzinfo is None:
        # Если datetime naive, считаем что это локальное время
        dt = TIMEZONE_OBJ.localize(dt)
    return dt.astimezone(pytz.UTC)


def format_datetime(
        dt: Optional[datetime],
        format: str = "%d.%m.%Y %H:%M",
        default: str = "не указано"
) -> str:
    """
    Форматирует datetime для вывода пользователю
    """
    if not dt:
        return default

    local_dt = to_local(dt)
    return local_dt.strftime(format)


def format_date(
        d: Optional[Union[date, datetime]],
        format: str = "%d.%m.%Y",
        default: str = "не указано"
) -> str:
    """
    Форматирует дату для вывода пользователю
    """
    if not d:
        return default

    if isinstance(d, datetime):
        d = to_local(d).date()

    return d.strftime(format)


def format_time(
        dt: Optional[datetime],
        format: str = "%H:%M",
        default: str = ""
) -> str:
    """
    Форматирует время для вывода пользователю
    """
    if not dt:
        return default

    local_dt = to_local(dt)
    return local_dt.strftime(format)


def parse_user_datetime(date_str: str) -> Optional[datetime]:
    """
    Парсит дату, введенную пользователем, в локальном часовом поясе
    """
    from services.tasks.utils import parse_deadline

    dt = parse_deadline(date_str)
    if dt:
        # Если дата naive, считаем что это локальное время
        if dt.tzinfo is None:
            dt = TIMEZONE_OBJ.localize(dt)
        else:
            dt = to_local(dt)

    return dt


def get_day_start(d: Optional[date] = None) -> datetime:
    """
    Возвращает начало дня в локальном часовом поясе
    """
    if d is None:
        d = today()

    return TIMEZONE_OBJ.localize(
        datetime(d.year, d.month, d.day, 0, 0, 0)
    )


def get_day_end(d: Optional[date] = None) -> datetime:
    """
    Возвращает конец дня в локальном часовом поясе
    """
    if d is None:
        d = today()

    return TIMEZONE_OBJ.localize(
        datetime(d.year, d.month, d.day, 23, 59, 59)
    )


def is_today(dt: datetime) -> bool:
    """
    Проверяет, является ли дата сегодняшней
    """
    local_dt = to_local(dt)
    return local_dt.date() == today()


def is_tomorrow(dt: datetime) -> bool:
    """
    Проверяет, является ли дата завтрашней
    """
    local_dt = to_local(dt)
    return local_dt.date() == today() + timedelta(days=1)


def is_yesterday(dt: datetime) -> bool:
    """
    Проверяет, является ли дата вчерашней
    """
    local_dt = to_local(dt)
    return local_dt.date() == today() - timedelta(days=1)
