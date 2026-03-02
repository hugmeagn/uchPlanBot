from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
import calendar
import bot.utils.dates as dates


@dataclass
class Lesson:
    """Структура данных для одной пары."""
    number: int  # Номер пары (1, 2, 3...)
    time_start: str  # Время начала (например, "09:00")
    time_end: str  # Время окончания (например, "10:30")
    name: str  # Название предмета
    teacher: Optional[str]  # Преподаватель
    room: Optional[str]  # Аудитория
    note: Optional[str] = None  # Дополнительная информация (подгруппа и т.д.)


class BaseParser(ABC):
    """
    Абстрактный базовый класс для всех парсеров расписания.
    """

    # Эти атрибуты должны быть определены в классах-наследниках
    base_url: str
    college_id: str

    def __init__(self):
        """
        Базовый инициализатор. Проверяет, что необходимые атрибуты определены.
        """
        if not hasattr(self, 'base_url') or not self.base_url:
            raise NotImplementedError(
                f"Класс {self.__class__.__name__} должен определить атрибут 'base_url'"
            )
        if not hasattr(self, 'college_id') or not self.college_id:
            raise NotImplementedError(
                f"Класс {self.__class__.__name__} должен определить атрибут 'college_id'"
            )
        self.session = None

    @abstractmethod
    async def get_groups(self) -> List[str]:
        """
        Получает список всех доступных учебных групп.
        """
        pass

    @abstractmethod
    async def get_schedule(
            self,
            group: str,
            date: Optional[datetime] = None
    ) -> Dict[str, List[Lesson]]:
        """
        Основной метод для получения расписания.

        :param group: Название группы.
        :param date: Дата, на которую нужно расписание.
                     Если None, парсер сам решает, что отдавать (обычно текущая неделя).
        :return: Словарь, где ключ — это день недели (например, "Понедельник (16.02)").
                 Значение — список объектов Lesson.
        """
        pass

    async def get_today_schedule(self, group: str) -> Dict[str, List[Lesson]]:
        """
        Получает расписание на сегодня.

        Базовая реализация получает расписание на неделю и фильтрует по сегодняшнему дню.

        :param group: Название группы.
        :return: Словарь с расписанием на сегодня (один день).
        """
        # Получаем расписание на текущую неделю
        week_schedule = await self.get_week_schedule(group)

        # Определяем сегодняшнюю дату
        today = dates.now().date()
        today_name = self._get_weekday_name(today)

        # Фильтруем дни, оставляя только сегодняшний
        result = {}
        for day_title, lessons in week_schedule.items():
            # Проверяем, содержит ли заголовок дня сегодняшнюю дату или название дня
            if self._is_day_match(day_title, today, today_name):
                result[day_title] = lessons
                break

        return result

    async def get_tomorrow_schedule(self, group: str) -> Dict[str, List[Lesson]]:
        """
        Получает расписание на завтра.

        Базовая реализация получает расписание на неделю и фильтрует по завтрашнему дню.

        :param group: Название группы.
        :return: Словарь с расписанием на завтра (один день).
        """
        # Получаем расписание на текущую неделю
        week_schedule = await self.get_week_schedule(group)

        # Определяем завтрашнюю дату
        tomorrow = (dates.now() + timedelta(days=1)).date()
        tomorrow_name = self._get_weekday_name(tomorrow)

        # Фильтруем дни, оставляя только завтрашний
        result = {}
        for day_title, lessons in week_schedule.items():
            if self._is_day_match(day_title, tomorrow, tomorrow_name):
                result[day_title] = lessons
                break

        return result

    async def get_week_schedule(self, group: str) -> Dict[str, List[Lesson]]:
        """
        Получает расписание на текущую неделю.

        Базовая реализация вычисляет дату понедельника текущей недели
        и вызывает get_schedule() с этой датой.

        :param group: Название группы.
        :return: Словарь с расписанием на всю неделю.
        """
        # Получаем дату понедельника текущей недели
        today = dates.now()

        # Вычисляем сколько дней нужно вычесть, чтобы получить понедельник
        # weekday(): 0 - понедельник, 1 - вторник, ..., 6 - воскресенье
        days_to_subtract = today.weekday()  # 0 для понедельника, 1 для вторника и т.д.

        # Получаем дату понедельника
        monday_date = today - timedelta(days=days_to_subtract)

        # Устанавливаем время на 00:00:00 для чистоты
        monday = datetime(monday_date.year, monday_date.month, monday_date.day)

        return await self.get_schedule(group, date=monday)

    async def get_next_week_schedule(self, group: str) -> Dict[str, List[Lesson]]:
        """
        Получает расписание на следующую неделю.

        Базовая реализация вычисляет дату следующего понедельника
        и вызывает get_schedule() с этой датой.

        :param group: Название группы.
        :return: Словарь с расписанием на следующую неделю.
        """
        # Вычисляем дату следующего понедельника
        next_monday = self._get_next_weekday(dates.now(), 0)  # 0 = понедельник
        return await self.get_schedule(group, date=next_monday)

    async def get_day_schedule(self, group: str, target_date: datetime) -> Dict[str, List[Lesson]]:
        """
        Получает расписание на конкретную дату.

        Базовая реализация получает расписание на неделю, содержащую target_date,
        и фильтрует по нужному дню.

        :param group: Название группы.
        :param target_date: Дата, на которую нужно расписание.
        :return: Словарь с расписанием на указанную дату.
        """
        # Получаем понедельник недели, содержащей target_date
        week_start = self._get_week_start(target_date)

        # Получаем расписание на эту неделю
        week_schedule = await self.get_schedule(group, date=week_start)

        # Фильтруем по нужному дню
        target_date_str = target_date.date()
        target_weekday_name = self._get_weekday_name(target_date_str)

        result = {}
        for day_title, lessons in week_schedule.items():
            if self._is_day_match(day_title, target_date_str, target_weekday_name):
                result[day_title] = lessons
                break

        return result

    async def get_next_lesson(self, group: str) -> Optional[Lesson]:
        """
        Получает информацию о следующей паре (с учётом текущего времени).

        :param group: Название группы.
        :return: Объект Lesson следующей пары или None, если пар больше нет сегодня.
        """
        today_schedule = await self.get_today_schedule(group)
        if not today_schedule:
            return None

        current_time = dates.now().time()

        # Берём первый (и единственный) день из расписания на сегодня
        for lessons in today_schedule.values():
            # Сортируем пары по номеру
            sorted_lessons = sorted(lessons, key=lambda x: x.number)

            # Ищем первую пару, которая ещё не началась или идёт сейчас
            for lesson in sorted_lessons:
                try:
                    lesson_end = datetime.strptime(lesson.time_end, "%H:%M").time()
                    if current_time < lesson_end:
                        return lesson
                except (ValueError, AttributeError):
                    # Если не удалось распарсить время, пропускаем
                    continue

        return None

    async def is_day_off(self, group: str, target_date: Optional[datetime] = None) -> bool:
        """
        Проверяет, есть ли пары в указанный день.

        :param group: Название группы.
        :param target_date: Дата для проверки. Если None, проверяется сегодня.
        :return: True, если пар нет, иначе False.
        """
        if target_date is None:
            target_date = dates.now()

        day_schedule = await self.get_day_schedule(group, target_date)
        return len(day_schedule) == 0 or all(len(lessons) == 0 for lessons in day_schedule.values())

    # Вспомогательные методы для работы с датами

    def _get_weekday_name(self, target_date: date) -> str:
        """
        Возвращает название дня недели по-русски.
        """
        weekdays = {
            0: "понедельник",
            1: "вторник",
            2: "среда",
            3: "четверг",
            4: "пятница",
            5: "суббота",
            6: "воскресенье"
        }
        return weekdays[target_date.weekday()]

    def _get_week_start(self, target_date: datetime) -> datetime:
        """
        Возвращает дату понедельника недели, содержащей target_date.
        """
        days_to_subtract = target_date.weekday()  # 0 = понедельник
        week_start = target_date - timedelta(days=days_to_subtract)
        return datetime(week_start.year, week_start.month, week_start.day)

    def _get_next_weekday(self, start_date: datetime, target_weekday: int) -> datetime:
        """
        Возвращает дату следующего указанного дня недели.
        target_weekday: 0 = понедельник, 6 = воскресенье
        """
        days_ahead = target_weekday - start_date.weekday()
        if days_ahead <= 0:  # Если сегодня target_weekday или позже
            days_ahead += 7
        return start_date + timedelta(days=days_ahead)

    def _is_day_match(self, day_title: str, target_date: date, target_weekday_name: str) -> bool:
        """
        Проверяет, соответствует ли заголовок дня целевой дате.
        """
        day_title_lower = day_title.lower()

        # Проверяем по названию дня недели
        if target_weekday_name in day_title_lower:
            return True

        # Проверяем по дате в формате DD.MM.YYYY
        date_str = target_date.strftime("%d.%m.%Y")
        if date_str in day_title:
            return True

        # Проверяем по дате в формате DD.MM.YY
        date_str_short = target_date.strftime("%d.%m.%y")
        if date_str_short in day_title:
            return True

        return False

    async def close(self):
        """
        Закрывает сессию, если она была открыта.
        """
        if self.session:
            await self.session.close()
