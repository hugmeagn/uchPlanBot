import re
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin

import bot.utils.dates as dates

from bs4 import BeautifulSoup
import aiohttp

from ..base import BaseParser, Lesson


class MagpkParser(BaseParser):
    """
    Парсер для сайта magpk.ru.
    Сайт возвращает расписание на всю неделю при запросе конкретной даты.
    """
    base_url = "https://magpk.ru/"
    college_id = "magpk"
    schedule_page_path = "/studentu/raspisanie-zanyatij"

    async def _get_page(self, group: str, date: datetime) -> str:
        """
        Выполняет POST-запрос к форме расписания и возвращает HTML.
        """
        full_url = urljoin(self.base_url, self.schedule_page_path)
        date_str = date.strftime("%Y-%m-%d")

        form_data = {
            'uch_gr_html': group,
            'date_sch_html': date_str,
            'btn_schedule_html': 'Расписание'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(full_url, data=form_data) as response:
                response.raise_for_status()
                return await response.text()

    async def get_groups(self) -> List[str]:
        """
        Получает список групп из выпадающего списка.
        """
        full_url = urljoin(self.base_url, self.schedule_page_path)
        groups = []

        async with aiohttp.ClientSession() as session:
            async with session.get(full_url) as response:
                response.raise_for_status()
                html = await response.text()

        soup = BeautifulSoup(html, 'html.parser')
        select_tag = soup.find('select', {'name': 'uch_gr_html'})

        if select_tag:
            options = select_tag.find_all('option')
            for option in options:
                group_name = option.get_text(strip=True)
                if group_name:
                    groups.append(group_name)

        return groups

    async def get_schedule(
        self,
        group: str,
        date: Optional[datetime] = None
    ) -> Dict[str, List[Lesson]]:
        """
        Получает расписание. Сайт всегда возвращает всю неделю.
        """
        if date is None:
            date = dates.now()

        html = await self._get_page(group, date)
        return self._parse_schedule_html(html)

    # Мы НЕ переопределяем get_today_schedule, get_tomorrow_schedule, get_week_schedule,
    # get_next_week_schedule и get_day_schedule, потому что базовая реализация
    # отлично работает с нашим get_schedule, который возвращает всю неделю.
    #
    # Базовая реализация этих методов:
    # - get_week_schedule() вызывает get_schedule() с датой понедельника
    # - get_next_week_schedule() вызывает get_schedule() с датой следующего понедельника
    # - get_today_schedule() получает недельное расписание и фильтрует сегодня
    # - get_tomorrow_schedule() получает недельное расписание и фильтрует завтра
    # - get_day_schedule() получает недельное расписание и фильтрует нужный день

    def _parse_schedule_html(self, html: str) -> Dict[str, List[Lesson]]:
        """
        Парсит HTML и возвращает расписание на неделю.
        """
        soup = BeautifulSoup(html, 'html.parser')
        schedule_dict = {}

        # Находим все блоки с расписанием на день
        day_blocks = soup.find_all('div', class_='timetable timetable--group')

        for day_block in day_blocks:
            # Заголовок дня: например, "Понедельник (16.02.2026)"
            day_header = day_block.find('h4', class_='timetable__dayname')
            if not day_header:
                continue
            day_name = day_header.get_text(strip=True)

            lessons_for_day = []

            # В каждом дне ищем периоды (пары)
            period_blocks = day_block.find_all('ul', class_='timetable__period', recursive=False)

            for period_block in period_blocks:
                # Номер пары
                period_num_tag = period_block.find('li', class_='timetable__item--period-num')
                if not period_num_tag:
                    continue
                period_num_match = re.search(r'\d+', period_num_tag.get_text())
                if not period_num_match:
                    continue
                period_num = int(period_num_match.group())

                # Блок с деталями пары
                period_details_tag = period_block.find('li', class_='timetable__item--periods')
                if not period_details_tag:
                    continue

                period_div = period_details_tag.find('div', class_='period')
                if not period_div:
                    continue

                time_span = period_div.find('span', class_='period__time')
                disciple_span = period_div.find('span', class_='period__disciple')
                teacher_span = period_div.find('span', class_='period__teacher')
                hall_span = period_div.find('span', class_='period__lecturehall')

                # Время
                time_range = time_span.get_text(strip=True) if time_span else ""
                time_parts = time_range.split('-')
                time_start = time_parts[0].strip() if len(time_parts) > 0 else ""
                time_end = time_parts[1].strip() if len(time_parts) > 1 else ""

                # Название предмета
                lesson_name_full = disciple_span.get_text(strip=True) if disciple_span else ""

                # Преподаватель
                teacher_name = teacher_span.get_text(strip=True) if teacher_span else None

                # Аудитория
                room_name = hall_span.get_text(strip=True) if hall_span else None
                if room_name == "":
                    room_name = None

                lesson = Lesson(
                    number=period_num,
                    time_start=time_start,
                    time_end=time_end,
                    name=lesson_name_full,
                    teacher=teacher_name,
                    room=room_name,
                    note=None
                )
                lessons_for_day.append(lesson)

            if lessons_for_day:
                schedule_dict[day_name] = lessons_for_day

        return schedule_dict
