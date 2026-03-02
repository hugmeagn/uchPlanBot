"""
Клиент для работы с GigaChat API с использованием официального пакета gigachat
"""
import logging
import random
from typing import Optional, Dict, Any, List
from datetime import datetime

from gigachat import GigaChat
from gigachat.models import Chat, MessagesRole
from dotenv import load_dotenv

import config

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)


class GigaChatClient:
    """
    Клиент для взаимодействия с GigaChat API через официальный пакет
    """

    def __init__(self):
        self.client: Optional[GigaChat] = None
        self._initialize_client()

    def _initialize_client(self):
        """
        Инициализирует клиент GigaChat
        """
        try:
            # Проверяем наличие учетных данных
            if not config.GIGACHAT_CREDENTIALS:
                logger.warning("GIGACHAT_CREDENTIALS not set, using fallback mode")
                self.client = None
                return

            # Создаем клиента
            self.client = GigaChat(
                credentials=config.GIGACHAT_CREDENTIALS,
                scope=config.GIGACHAT_SCOPE,
                model=config.GIGACHAT_MODEL,
                verify_ssl_certs=False
            )
            logger.info("GigaChat client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize GigaChat client: {e}", exc_info=True)
            self.client = None

    async def generate_plan(
        self,
        user_info: Dict[str, Any],
        tasks: List[Dict],
        schedule: Optional[Dict] = None,
        temperature: float = 0.8
    ) -> str:
        """
        Генерирует план дня на основе данных пользователя
        """
        # Если клиент не инициализирован, используем fallback
        if not self.client:
            logger.warning("GigaChat client not available, using fallback plan")
            return self._get_fallback_plan(user_info, tasks, schedule)

        try:
            # Формируем сообщения для чата
            messages = self._create_messages(user_info, tasks, schedule)

            # Создаем запрос
            chat = Chat(
                messages=messages,
                temperature=temperature,
                max_tokens=2000
            )

            # Отправляем запрос
            import asyncio
            response = await asyncio.to_thread(
                self.client.chat,
                chat
            )

            if response and response.choices:
                content = response.choices[0].message.content
                return content.strip()
            else:
                logger.error("Empty response from GigaChat")
                return self._get_fallback_plan(user_info, tasks, schedule)

        except Exception as e:
            logger.error(f"Error generating plan with GigaChat: {e}", exc_info=True)
            return self._get_fallback_plan(user_info, tasks, schedule)

    def _create_messages(self, user_info: Dict, tasks: List[Dict], schedule: Optional[Dict]) -> List[Dict]:
        """
        Создает сообщения для чата с GigaChat
        """
        messages = []

        # Системное сообщение
        system_content = self._create_system_prompt(user_info)
        messages.append({
            "role": MessagesRole.SYSTEM,
            "content": system_content
        })

        # Пользовательское сообщение с данными
        user_content = self._create_user_prompt(user_info, tasks, schedule)
        messages.append({
            "role": MessagesRole.USER,
            "content": user_content
        })

        return messages

    def _create_system_prompt(self, user_info: Dict[str, Any]) -> str:
        """
        Создает системный промпт с инструкциями для GigaChat
        """
        role = user_info.get('role', 'студент')
        group = user_info.get('group', '')
        institution = user_info.get('institution', '')
        current_time = user_info.get('current_time', '')
        is_today = user_info.get('is_today', True)
        is_evening = user_info.get('is_evening', False)
        is_morning = user_info.get('is_morning', True)

        today = datetime.now().strftime("%d.%m.%Y")
        weekday = self._get_weekday_russian(datetime.now().weekday())

        prompt = f"""Ты — дружелюбный персональный AI-помощник по имени Планик. Твоя задача — помогать {role}у с планированием дня.

Сегодня {weekday}, {today}. Текущее время: {current_time}.

Информация о пользователе:
- Роль: {role}
- Учебное заведение: {institution}
- Группа: {group}

"""
        if is_today:
            if is_evening:
                prompt += """Сейчас вечер. Сфокусируйся на том, что еще можно успеть сделать сегодня.
Будь реалистичным: не предлагай делать дела, которые уже невозможно выполнить сегодня.
"""
            elif is_morning:
                prompt += """Сейчас утро. Отличное время для планирования всего дня!
Помоги пользователю продуктивно начать день.
"""
            else:
                prompt += """Сейчас день. Посмотрим, что еще можно успеть сделать до вечера.
"""
        else:
            prompt += f"""Ты составляешь план на {user_info.get('target_date', 'завтра')}.
Этот день еще не наступил, так что можно планировать его полностью.
"""

        prompt += """
ВАЖНЫЕ ПРАВИЛА РАБОТЫ С ЗАДАЧАМИ:

1. ПРИОРИТЕТЫ ЗАДАЧ:
   - 🔴 Критический приоритет: самые важные задачи
   - 🟠 Высокий приоритет: важные задачи
   - 🟡 Средний приоритет: обычные задачи
   - ⚪ Низкий приоритет: можно отложить

2. СРОЧНОСТЬ (urgency):
   - "overdue" ⚠️ ПРОСРОЧЕНО! - нужно сделать в первую очередь
   - "critical_soon" 🔥 - критическая задача, дедлайн через 1-2 дня
   - "high_soon" ⚠️ - важная задача, дедлайн завтра
   - "medium_soon" 📅 - обычная задача с дедлайном завтра (напомни невзначай)
   - "normal" 📆 - задача с дедлайном в будущем
   - "no_deadline" 📌 - задача без дедлайна (можно сделать когда удобно)

3. ЗАДАЧИ БЕЗ ДЕДЛАЙНА:
   - Не игнорируй их! Они тоже важны
   - Предлагай выделить время на них, если есть свободные окна
   - Если задача давно висит (более недели), мягко напомни о ней

4. УЧЕТ ВРЕМЕНИ:
   - Если сейчас вечер, не предлагай дела на утро
   - Планируй только то, что реально успеть
   - Учитывай время на дорогу и подготовку

5. СТИЛЬ ОБЩЕНИЯ:
   - Будь дружелюбным и поддерживающим
   - Используй эмодзи для эмоций
   - Мотивируй, но будь реалистичным
   - О срочных задачах говори прямо, о несрочных - невзначай

Структура ответа:
1. Приветствие (теплое, с учетом времени)
2. Срочные задачи (⚠️ просроченные и 🔥 критические)
3. План с учетом расписания
4. Напоминания о других задачах (невзначай)
5. Поддерживающее завершение"""

        return prompt

    def _create_user_prompt(self, user_info: Dict, tasks: List[Dict], schedule: Optional[Dict]) -> str:
        """
        Создает промпт с данными пользователя
        """
        current_time = user_info.get('current_time', '')
        is_today = user_info.get('is_today', True)

        prompt_parts = [f"Привет! Сейчас {current_time}. Вот мои задачи и расписание:\n"]

        # Расписание
        if schedule and schedule.get('lessons'):
            prompt_parts.append("📚 РАСПИСАНИЕ:")
            for lesson in schedule['lessons']:
                time_str = f"{lesson.get('time_start', '')}-{lesson.get('time_end', '')}"
                name = lesson.get('name', 'Пара')
                room = lesson.get('room', '')

                line = f"• {lesson.get('number', '?')} пара: {time_str} - {name}"
                if room:
                    line += f" (ауд. {room})"
                prompt_parts.append(line)
            prompt_parts.append("")
        else:
            prompt_parts.append("📚 Сегодня пар нет")
            prompt_parts.append("")

        # Задачи - группируем по срочности
        if tasks:
            prompt_parts.append("✅ ВСЕ ЗАДАЧИ (с указанием срочности):")

            # Сортируем: сначала просроченные, потом по срочности, потом по приоритету
            urgency_order = {
                'overdue': 0,
                'critical_soon': 1,
                'high_soon': 2,
                'medium_soon': 3,
                'normal': 4,
                'no_deadline': 5
            }

            sorted_tasks = sorted(
                tasks,
                key=lambda x: (
                    urgency_order.get(x.get('urgency', 'normal'), 99),
                    - (3 if x.get('priority') == 'critical' else
                       2 if x.get('priority') == 'high' else
                       1 if x.get('priority') == 'medium' else 0)
                )
            )

            for task in sorted_tasks:
                # Эмодзи приоритета
                priority_emoji = {
                    'critical': '🔴', 'high': '🟠',
                    'medium': '🟡', 'low': '⚪'
                }.get(task.get('priority', 'medium'), '⚪')

                # Информация о задаче
                title = task.get('title', 'Без названия')
                deadline_info = ""
                if task.get('deadline'):
                    deadline_info = f" [до {task['deadline'].strftime('%d.%m %H:%M')}]"

                # Добавляем описание срочности
                urgency_desc = task.get('urgency_description', '')
                if urgency_desc:
                    urgency_desc = f" — {urgency_desc}"

                line = f"{priority_emoji} {title}{deadline_info}{urgency_desc}"
                prompt_parts.append(line)

                # Добавляем описание если есть
                if task.get('description'):
                    prompt_parts.append(f"   📝 {task['description'][:100]}")

            prompt_parts.append("")

            # Статистика
            overdue_count = sum(1 for t in tasks if t.get('urgency') == 'overdue')
            if overdue_count > 0:
                prompt_parts.append(f"⚠️ ВНИМАНИЕ: {overdue_count} просроченных задач!")
                prompt_parts.append("")

        else:
            prompt_parts.append("✅ Задач пока нет")
            prompt_parts.append("")

        return "\n".join(prompt_parts)

    def _get_fallback_plan(self, user_info: Dict, tasks: List[Dict], schedule: Optional[Dict]) -> str:
        """
        Возвращает запасной план, если GigaChat недоступен
        """
        current_time = user_info.get('current_time', datetime.now().strftime("%H:%M"))
        is_evening = user_info.get('is_evening', False)
        is_morning = user_info.get('is_morning', True)

        lines = []

        # Приветствие
        if is_morning:
            lines.append("☀️ **Доброе утро!**")
        elif is_evening:
            lines.append("🌆 **Добрый вечер!**")
        else:
            lines.append("👋 **Привет!**")

        lines.append("")
        lines.append(f"Сейчас {current_time}. Давай посмотрим, что у нас по плану:")
        lines.append("")

        # Срочные задачи (просроченные и критические)
        urgent_tasks = [t for t in tasks if t.get('urgency') in ['overdue', 'critical_soon']]
        if urgent_tasks:
            lines.append("⚠️ **Срочные задачи:**")
            for task in urgent_tasks:
                priority_emoji = '🔴' if task.get('priority') == 'critical' else '🟠'
                title = task.get('title')
                desc = task.get('urgency_description', '')
                lines.append(f"{priority_emoji} {title} {desc}")
            lines.append("")

        # Расписание (только будущее)
        if schedule and schedule.get('lessons'):
            lines.append("📚 **Оставшиеся пары:**")
            for lesson in schedule['lessons']:
                time_str = f"{lesson.get('time_start', '')}-{lesson.get('time_end', '')}"
                name = lesson.get('name', 'Пара')
                lines.append(f"• {time_str} - {name}")
            lines.append("")

        # Обычные задачи (невзначай)
        normal_tasks = [t for t in tasks if t.get('urgency') not in ['overdue', 'critical_soon']]
        if normal_tasks:
            lines.append("📋 **Кстати, еще задачи:**")
            for task in normal_tasks[:3]:  # Показываем не больше 3, чтобы не перегружать
                priority_emoji = {
                    'critical': '🔴', 'high': '🟠',
                    'medium': '🟡', 'low': '⚪'
                }.get(task.get('priority', 'medium'), '⚪')
                lines.append(f"{priority_emoji} {task.get('title')}")

            if len(normal_tasks) > 3:
                lines.append(f"... и еще {len(normal_tasks) - 3} задач")
            lines.append("")

        # Советы
        tips = [
            "Начинай с самого важного 💪",
            "Делай перерывы каждые 45 минут ☕",
            "Просроченные задачи - в первую очередь! ⚠️",
            "Даже маленькие шаги ведут к цели 🌈",
            "Не забывай про отдых 😌",
            "Пей воду в течение дня 💧"
        ]

        lines.append("💡 **Совет:**")
        lines.append(f"• {random.choice(tips)}")
        lines.append("")

        lines.append("У тебя всё получится! 🚀")

        return "\n".join(lines)

    def _get_weekday_russian(self, weekday: int) -> str:
        """Возвращает название дня недели по-русски"""
        weekdays = [
            "понедельник", "вторник", "среда",
            "четверг", "пятница", "суббота", "воскресенье"
        ]
        return weekdays[weekday]

    async def close(self):
        """
        Закрывает соединение с GigaChat
        """
        if self.client:
            try:
                import asyncio
                await asyncio.to_thread(self.client.close)
                logger.info("GigaChat client closed")
            except Exception as e:
                logger.error(f"Error closing GigaChat client: {e}")
