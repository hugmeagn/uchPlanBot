"""
Парсер для сайта расписания МГТУ им. Носова (xn--80agz0af.xn--p1ai)
"""
import re
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin, quote

import bot.utils.dates as dates

from bs4 import BeautifulSoup
import aiohttp

from ..base import BaseParser, Lesson


def format_teacher_name(full_name: str) -> str:
    """
    Преобразует полное ФИО в формат "Фамилия И.О."

    Примеры:
        "Миронова Ольга Александровна" -> "Миронова О.А."
        "Иванов Иван Иванович" -> "Иванов И.И."
        "Петров Петр" -> "Петров П."
    """
    if not full_name:
        return ""

    parts = full_name.strip().split()

    if len(parts) == 1:
        return parts[0]

    if len(parts) == 2:
        # Только фамилия и имя
        return f"{parts[0]} {parts[1][0]}."

    # Фамилия Имя Отчество
    surname = parts[0]
    initials = f"{parts[1][0]}.{parts[2][0]}." if len(parts) > 2 else f"{parts[1][0]}."

    return f"{surname} {initials}"


class MagtuParser(BaseParser):
    """
    Парсер для сайта расписания МГТУ им. Носова.
    """
    base_url = "http://xn--80agz0af.xn--p1ai/"
    college_id = "magtu"

    async def _get_page(self, group_or_teacher: str) -> str:
        """
        Выполняет GET-запрос к странице группы или преподавателя.
        """
        # Для преподавателей форматируем имя
        formatted_name = group_or_teacher

        # Кодируем URL
        url_path = quote(formatted_name, safe='()/')
        full_url = urljoin(self.base_url, url_path.lstrip('/'))

        print(f"Requesting URL: {full_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(full_url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response.reason}")
                return await response.text()

    async def get_groups(self) -> List[str]:
        """Получает список групп."""
        return []

    async def get_schedule(
        self,
        group: str,
        date: Optional[datetime] = None
    ) -> Dict[str, List[Lesson]]:
        """Получает расписание на неделю."""
        if date is None:
            date = dates.now()

        html = await self._get_page(group)
        return self._parse_schedule_html(html, date)

    async def get_week_schedule(self, group: str) -> Dict[str, List[Lesson]]:
        """Получает расписание на текущую неделю."""
        today = dates.now()
        html = await self._get_page(group)
        soup = BeautifulSoup(html, 'html.parser')

        week1 = soup.find('div', id='week-1')
        week2 = soup.find('div', id='week-2')

        if week1 and self._week_contains_date(week1, today):
            return self._parse_week_html(week1)
        elif week2 and self._week_contains_date(week2, today):
            return self._parse_week_html(week2)

        if week1:
            return self._parse_week_html(week1)

        return {}

    async def get_next_week_schedule(self, group: str) -> Dict[str, List[Lesson]]:
        """Получает расписание на следующую неделю."""
        today = dates.now()
        html = await self._get_page(group)
        soup = BeautifulSoup(html, 'html.parser')

        week1 = soup.find('div', id='week-1')
        week2 = soup.find('div', id='week-2')

        if week1 and self._week_contains_date(week1, today):
            if week2:
                return self._parse_week_html(week2)
        elif week2 and self._week_contains_date(week2, today):
            return {}

        if week2:
            return self._parse_week_html(week2)

        return {}

    def _week_contains_date(self, week_element, target_date: datetime) -> bool:
        """Проверяет, содержит ли неделя указанную дату."""
        target_str = target_date.strftime('%d.%m')

        day_elements = week_element.find_all('div', class_='day')
        for day in day_elements:
            day_name_div = day.find('div', class_='day-name')
            if day_name_div:
                date_divs = day_name_div.find_all('div')
                if len(date_divs) >= 2:
                    date_text = date_divs[1].get_text(strip=True)
                    if target_str in date_text:
                        return True
        return False

    def _parse_schedule_html(self, html: str, target_date: datetime) -> Dict[str, List[Lesson]]:
        """Парсит HTML и возвращает расписание на неделю."""
        soup = BeautifulSoup(html, 'html.parser')

        week1 = soup.find('div', id='week-1')
        week2 = soup.find('div', id='week-2')

        if week1 and self._week_contains_date(week1, target_date):
            return self._parse_week_html(week1)
        elif week2 and self._week_contains_date(week2, target_date):
            return self._parse_week_html(week2)

        if week1:
            return self._parse_week_html(week1)

        return {}

    def _parse_week_html(self, week_element) -> Dict[str, List[Lesson]]:
        """Парсит HTML одной недели."""
        schedule_dict = {}

        day_elements = week_element.find_all('div', class_='day')

        for day_element in day_elements:
            day_name_div = day_element.find('div', class_='day-name')
            if not day_name_div:
                continue

            # Получаем название дня и дату
            day_name_parts = day_name_div.get_text(strip=True, separator='|').split('|')
            if len(day_name_parts) >= 2:
                day_name = f"{day_name_parts[0]} ({day_name_parts[1]})"
            else:
                day_name = day_name_parts[0] if day_name_parts else "Неизвестный день"

            lessons = []

            # Ищем все пары
            lesson_rows = day_element.find_all('tr')

            for row in lesson_rows:
                lesson_cell = row.find('td', class_=lambda x: x and 'less-' in x and 'haveLess' in x)
                if not lesson_cell:
                    continue

                # Номер пары
                classes = lesson_cell.get('class', [])
                lesson_num = None
                for cls in classes:
                    if cls.startswith('less-'):
                        try:
                            parts = cls.split('-')
                            if len(parts) >= 4:
                                lesson_num = int(parts[3])
                        except:
                            pass

                if not lesson_num:
                    continue

                # Все блоки с парами
                less_blocks = lesson_cell.find_all('div', class_='less')

                for less_block in less_blocks:
                    title_elem = less_block.find('div', class_='title')
                    if not title_elem:
                        continue

                    lesson_name = title_elem.get_text(strip=True)

                    if lesson_name == "Занятие отменено":
                        continue

                    # Время
                    time_elem = less_block.find('div', class_='time')
                    time_range = time_elem.get_text(strip=True) if time_elem else ""
                    time_parts = time_range.split('–')
                    time_start = time_parts[0].strip() if len(time_parts) > 0 else ""
                    time_end = time_parts[1].strip() if len(time_parts) > 1 else ""

                    # Преподаватель или группа
                    teacher_elem = less_block.find('div', class_='teacher')
                    teacher = None
                    if teacher_elem:
                        teacher_link = teacher_elem.find('a')
                        if teacher_link:
                            teacher = teacher_link.get_text(strip=True)

                    # Аудитория
                    aud_elem = less_block.find('div', class_='aud')
                    room = None
                    if aud_elem:
                        room_text = aud_elem.get_text(strip=True)
                        link = aud_elem.find('a')
                        if link:
                            room = link.get_text(strip=True)
                        elif room_text:
                            room = room_text

                    # Тип занятия
                    ad_elem = less_block.find('div', class_='ad')
                    note = None
                    if ad_elem:
                        ad_text = ad_elem.get_text(strip=True)
                        if teacher and teacher in ad_text:
                            ad_text = ad_text.replace(teacher, '').strip()
                        if ad_text and ad_text != '-':
                            note = ad_text

                    lesson = Lesson(
                        number=lesson_num,
                        time_start=time_start,
                        time_end=time_end,
                        name=lesson_name,
                        teacher=teacher,
                        room=room,
                        note=note
                    )
                    lessons.append(lesson)

            if lessons:
                schedule_dict[day_name] = lessons

        return schedule_dict

    async def get_teachers(self) -> List[str]:
        """Получает список преподавателей."""
        return []


class MagtuTeacherParser(MagtuParser):
    """
    Парсер для расписания преподавателей МГТУ.
    Автоматически форматирует ФИО в формат "Фамилия И.О."
    """
    college_id = "magtu_teacher"

    async def _get_page(self, teacher_name: str) -> str:
        """
        Форматирует ФИО преподавателя и получает страницу.
        """
        # Форматируем ФИО: "Миронова Ольга Александровна" -> "Миронова О.А."
        formatted_name = format_teacher_name(teacher_name)
        print(f"Teacher name formatted: '{teacher_name}' -> '{formatted_name}'")

        # Используем родительский метод с форматированным именем
        return await super()._get_page(formatted_name)

    async def get_groups(self) -> List[str]:
        return []
