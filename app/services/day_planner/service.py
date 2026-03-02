"""
Сервис для планирования дня с использованием GigaChat
"""
import logging
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from models.user import User
from models.daily_plan import DailyPlan
from models.task import TaskModel
from bot.utils import dates
from services.gigachat.client import GigaChatClient
from services.schedule.factory import ParserFactory
import config

logger = logging.getLogger(__name__)


@dataclass
class PlanGenerationResult:
    """Результат генерации плана"""
    success: bool
    plan: Optional[str] = None
    error: Optional[str] = None
    from_cache: bool = False


class DayPlannerService:
    """
    Сервис для генерации ежедневных планов с помощью GigaChat
    """

    def __init__(self):
        self.gigachat = GigaChatClient()
        self._parsers_cache = {}

    async def get_or_generate_plan(
        self,
        user: User,
        target_date: date,
        force_refresh: bool = False
    ) -> PlanGenerationResult:
        """
        Получает существующий план или генерирует новый

        Args:
            user: Пользователь
            target_date: Дата, на которую нужен план
            force_refresh: Принудительно сгенерировать новый план

        Returns:
            Результат с планом или ошибкой
        """
        # Проверяем, есть ли уже план на эту дату (если не force_refresh)
        if not force_refresh:
            existing_plan = await DailyPlan.filter(
                user=user,
                plan_date=target_date
            ).first()

            if existing_plan:
                logger.info(f"Found existing plan for user {user.telegram_id} on {target_date}")
                return PlanGenerationResult(
                    success=True,
                    plan=existing_plan.content,
                    from_cache=True
                )

        # Генерируем новый план
        try:
            # ВАЖНО: Загружаем связанные данные пользователя
            await user.fetch_related('institution')

            # Собираем данные - теперь получаем ВСЕ активные задачи, не только на сегодня
            tasks = await self._get_all_active_tasks(user, target_date)

            # Определяем текущее время для фильтрации прошедших событий
            current_time = dates.now()
            is_today = (target_date == current_time.date())

            # Конвертируем date в datetime для получения расписания
            target_datetime = datetime.combine(target_date, time.min)
            schedule = await self._get_schedule_for_date(user, target_datetime)

            # Фильтруем расписание - убираем прошедшие пары, если это сегодня
            if is_today and schedule and schedule.get('lessons'):
                current_time_str = current_time.strftime("%H:%M")
                future_lessons = []

                for lesson in schedule['lessons']:
                    # Если время окончания пары еще не прошло
                    if lesson['time_end'] > current_time_str:
                        future_lessons.append(lesson)
                    else:
                        logger.info(f"Filtering out past lesson: {lesson['name']} at {lesson['time_end']}")

                schedule['lessons'] = future_lessons
                schedule['filtered'] = True

            # Добавляем информацию о текущем времени в user_info
            user_info = {
                'role': user.role or "студент",
                'group': user.group or "",
                'institution': user.institution.name if user.institution else "Не указано",
                'current_time': current_time.strftime("%H:%M"),
                'is_today': is_today,
                'is_evening': current_time.hour >= 18,
                'is_morning': current_time.hour < 12
            }

            # Генерируем план через GigaChat
            plan_content = await self.gigachat.generate_plan(
                user_info=user_info,
                tasks=tasks,
                schedule=schedule
            )

            # Сохраняем в БД - используем update_or_create чтобы избежать дубликатов
            plan, created = await DailyPlan.update_or_create(
                user=user,
                plan_date=target_date,
                defaults={
                    'content': plan_content,
                    'notification_sent': False,
                    'generated_at': datetime.now()
                }
            )

            if created:
                logger.info(f"Created new plan for user {user.telegram_id} on {target_date}")
            else:
                logger.info(f"Updated existing plan for user {user.telegram_id} on {target_date}")

            return PlanGenerationResult(
                success=True,
                plan=plan_content,
                from_cache=False
            )

        except Exception as e:
            logger.error(f"Failed to generate plan: {e}", exc_info=True)
            return PlanGenerationResult(
                success=False,
                error=str(e)
            )

    async def _get_all_active_tasks(self, user: User, target_date: date) -> List[Dict[str, Any]]:
        """
        Получает ВСЕ активные задачи пользователя с информацией о срочности

        Args:
            user: Пользователь
            target_date: Дата, на которую составляется план

        Returns:
            Список задач с дополнительной информацией
        """
        current_time = dates.now()

        # Получаем все активные задачи пользователя (не завершенные)
        tasks = await TaskModel.filter(
            user_id=str(user.telegram_id),
            status__in=['active', 'overdue']  # Активные и просроченные
        ).order_by('deadline')

        result = []
        urgent_count = 0

        for task in tasks:
            # Определяем приоритет как строку
            priority_map = {0: 'low', 1: 'medium', 2: 'high', 3: 'critical'}
            priority_str = priority_map.get(task.priority, 'medium')

            # Базовая информация о задаче
            task_data = {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'priority': priority_str,
                'deadline': task.deadline,
                'status': task.status,
                'created_at': task.created_at
            }

            # Анализируем срочность задачи
            if task.deadline:
                days_until_deadline = (task.deadline.date() - target_date).days
                hours_until_deadline = (task.deadline - current_time).total_seconds() / 3600

                # Проверяем, просрочена ли задача
                if task.deadline < current_time and task.status != 'completed':
                    task_data['urgency'] = 'overdue'
                    task_data['urgency_description'] = '⚠️ ПРОСРОЧЕНО! Нужно сделать срочно!'
                    urgent_count += 1
                # Критические задачи за 2 дня до дедлайна
                elif priority_str == 'critical' and 0 <= days_until_deadline <= 2:
                    task_data['urgency'] = 'critical_soon'
                    task_data['urgency_description'] = f'🔥 Осталось {days_until_deadline} дн. до дедлайна!'
                    urgent_count += 1
                # Высокий приоритет за день до дедлайна
                elif priority_str == 'high' and days_until_deadline == 1:
                    task_data['urgency'] = 'high_soon'
                    task_data['urgency_description'] = '⚠️ Завтра дедлайн!'
                    urgent_count += 1
                # Средний приоритет за день до дедлайна (невзначай)
                elif priority_str == 'medium' and days_until_deadline == 1:
                    task_data['urgency'] = 'medium_soon'
                    task_data['urgency_description'] = '📅 Завтра дедлайн, если не забыл'
                # Обычные задачи с дедлайном
                elif days_until_deadline > 0:
                    task_data['urgency'] = 'normal'
                    task_data['urgency_description'] = f'📆 Дедлайн через {days_until_deadline} дн.'
            else:
                # Задачи без дедлайна - тоже важны, но не срочные
                task_data['urgency'] = 'no_deadline'
                task_data['urgency_description'] = '📌 Можно сделать, когда будет время'

                # Для задач без дедлайна добавляем информацию о возрасте
                days_since_created = (target_date - task.created_at.date()).days
                if days_since_created > 7:
                    task_data['note'] = f'🗓️ Создано {days_since_created} дн. назад'

            result.append(task_data)

        # Логируем статистику
        logger.info(f"Found {len(result)} active tasks for user {user.telegram_id} ({urgent_count} urgent)")

        return result

    async def _get_tasks_for_date(self, user: User, target_date: date) -> List[Dict[str, Any]]:
        """
        Получает задачи на указанную дату (только с дедлайном в этот день)
        """
        # Определяем начало и конец дня
        day_start = datetime.combine(target_date, time.min)
        day_end = datetime.combine(target_date, time.max)
        current_time = dates.now()
        is_today = (target_date == current_time.date())

        # Ищем задачи с дедлайном в этот день
        tasks = await TaskModel.filter(
            user_id=str(user.telegram_id),
            deadline__gte=day_start,
            deadline__lte=day_end
        ).order_by('deadline')

        result = []
        for task in tasks:
            # Определяем приоритет как строку
            priority_map = {0: 'low', 1: 'medium', 2: 'high', 3: 'critical'}
            priority_str = priority_map.get(task.priority, 'medium')

            # Проверяем, просрочена ли задача
            is_overdue = False
            if task.deadline and task.status != 'completed':
                if task.deadline < current_time:
                    is_overdue = True

            # Проверяем, актуальна ли еще задача по времени (для сегодняшних задач)
            is_past = False
            if is_today and task.deadline and task.status != 'completed':
                if task.deadline < current_time and not is_overdue:
                    is_past = True

            task_data = {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'priority': priority_str,
                'deadline': task.deadline,
                'status': task.status,
                'is_overdue': is_overdue,
                'is_past': is_past
            }

            # Для просроченных задач добавляем пометку
            if is_overdue:
                task_data['note'] = "⚠️ ПРОСРОЧЕНО"

            result.append(task_data)

        return result

    async def _get_schedule_for_date(self, user: User, target_datetime: datetime) -> Optional[Dict]:
        """
        Получает расписание на указанную дату

        Args:
            user: Пользователь
            target_datetime: Дата и время для получения расписания
        """
        if not user.group or not user.institution:
            logger.info(f"No group or institution for user {user.telegram_id}")
            return None

        try:
            # ВАЖНО: Загружаем institution если еще не загружен
            if not hasattr(user, 'institution') or user.institution is None:
                await user.fetch_related('institution')

            institution_name = user.institution.name if user.institution else None

            if not institution_name:
                logger.warning(f"No institution name for user {user.telegram_id}")
                return None

            # Получаем парсер для учебного заведения
            parser = self._get_parser(institution_name)

            # Получаем расписание на день (ожидает datetime)
            schedule_dict = await parser.get_day_schedule(user.group, target_datetime)

            # Преобразуем в удобный формат
            lessons = []
            day_title = None

            for title, day_lessons in schedule_dict.items():
                day_title = title
                for lesson in day_lessons:
                    lessons.append({
                        'number': lesson.number,
                        'time_start': lesson.time_start,
                        'time_end': lesson.time_end,
                        'name': lesson.name,
                        'teacher': lesson.teacher,
                        'room': lesson.room
                    })
                break  # Берем только первый день (должен быть только один)

            return {
                'date': target_datetime.strftime('%d.%m.%Y'),
                'day_title': day_title,
                'lessons': lessons
            }

        except Exception as e:
            logger.error(f"Error getting schedule: {e}", exc_info=True)
            return None

    def _get_parser(self, institution_name: str):
        """
        Получает парсер для учебного заведения
        """
        # TODO: Сделать маппинг institution_name -> college_id
        college_id = "magpk"  # Пока для всех magpk

        if college_id not in self._parsers_cache:
            self._parsers_cache[college_id] = ParserFactory.get_parser(college_id)

        return self._parsers_cache[college_id]

    async def send_daily_plan_notifications(self):
        """
        Отправляет утренние уведомления с планом дня всем пользователям
        """
        from ...bot_integration.integration import get_integration

        integration = await get_integration()
        if not integration or not integration.notification_service:
            logger.error("Notification service not available")
            return

        today = dates.today()

        # Получаем всех пользователей с включенными уведомлениями
        users = await User.filter(notifications_enabled=True)

        for user in users:
            try:
                # Загружаем связанные данные
                await user.fetch_related('institution')

                # Генерируем план на сегодня
                result = await self.get_or_generate_plan(user, today)

                if result.success and result.plan:
                    # Отправляем уведомление
                    await integration.notification_service.send_notification(
                        user_id=str(user.telegram_id),
                        channel="telegram",
                        title="🌅 Доброе утро! Вот ваш план на сегодня:",
                        content=result.plan,
                        notification_type="daily_plan",
                        priority=2  # HIGH
                    )

                    # Отмечаем, что уведомление отправлено
                    await DailyPlan.filter(
                        user=user,
                        plan_date=today
                    ).update(
                        notification_sent=True,
                        sent_at=dates.now()
                    )

                    logger.info(f"Sent daily plan to user {user.telegram_id}")

                else:
                    logger.warning(f"Failed to generate plan for user {user.telegram_id}: {result.error}")

            except Exception as e:
                logger.error(f"Error sending plan to user {user.telegram_id}: {e}", exc_info=True)

    async def mark_plan_as_sent(self, user_id: int, plan_date: date):
        """
        Отмечает план как отправленный (используется после ручной отправки)
        """
        await DailyPlan.filter(
            user_id=user_id,
            plan_date=plan_date
        ).update(
            notification_sent=True,
            sent_at=dates.now()
        )

    async def delete_old_plans(self, days_to_keep: int = 30):
        """
        Удаляет старые планы (для очистки БД)

        Args:
            days_to_keep: Сколько дней хранить планы
        """
        cutoff_date = dates.today() - timedelta(days=days_to_keep)
        deleted = await DailyPlan.filter(plan_date__lt=cutoff_date).delete()
        logger.info(f"Deleted {deleted} old plans (before {cutoff_date})")
        return deleted
