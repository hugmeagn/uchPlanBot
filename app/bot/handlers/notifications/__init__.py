# app/bot/handlers/notifications/__init__.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

"""
Хендлеры для работы с уведомлениями (через инлайн кнопки)
"""
import logging
import math
from aiogram.types import Message, CallbackQuery
from aiogram import Router

from bot_integration.integration import get_integration
from services.notifications.models import NotificationStatus

from .keyboards import (
    get_notifications_main_keyboard,
    get_notifications_list_keyboard,
    get_notification_settings_keyboard
)

logger = logging.getLogger(__name__)

router = Router()


# ==================== ОСНОВНЫЕ ФУНКЦИИ ДЛЯ ОТОБРАЖЕНИЯ ====================

async def show_notifications_menu(callback: CallbackQuery):
    """Показать главное меню уведомлений"""
    await callback.message.edit_text(
        "🔔 **Уведомления**\n\n"
        "Выберите действие:",
        reply_markup=get_notifications_main_keyboard()
    )
    await callback.answer()


async def show_notifications_list(callback: CallbackQuery, page: int = 0):
    """Показать список уведомлений с пагинацией"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        # Получаем уведомления пользователя с пагинацией
        # Используем существующий метод get_user_notifications с offset/limit
        limit = 5
        offset = page * limit
        
        notifications = await integration.notification_service.get_user_notifications(
            user_id=user_id,
            limit=limit,
            offset=offset,
            status=None  # получаем все статусы
        )
        
        # Получаем общее количество уведомлений для пагинации
        # Для этого нужно получить все уведомления (неэффективно) или добавить метод count
        # Временное решение: получаем все уведомления и считаем
        all_notifications = await integration.notification_service.get_user_notifications(
            user_id=user_id,
            limit=1000,  # большой лимит
            offset=0,
            status=None
        )
        total = len(all_notifications)
        
        # Вычисляем общее количество страниц
        page_size = 5
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        if not notifications:
            await callback.message.edit_text(
                "📭 **У вас нет уведомлений**\n\n"
                "Здесь будут появляться напоминания о парах и дедлайнах.",
                reply_markup=get_notifications_main_keyboard(show_back=True)
            )
            await callback.answer()
            return

        text = "🔔 **Последние уведомления:**\n\n"

        for i, notif in enumerate(notifications, 1 + page * page_size):
            status_emoji = {
                NotificationStatus.SENT: "✅",
                NotificationStatus.DELIVERED: "📨",
                NotificationStatus.FAILED: "❌",
                NotificationStatus.PENDING: "⏳"
            }.get(notif.status, "📌")

            time_str = notif.sent_at.strftime("%H:%M %d.%m") if notif.sent_at else "ожидает"

            text += f"{i}. {status_emoji} **{notif.title}**\n"
            text += f"   🕒 {time_str}\n"

            if notif.status == NotificationStatus.FAILED and notif.last_error:
                text += f"   ❗ Ошибка: {notif.last_error[:50]}\n"

            text += "\n"

        # Добавляем клавиатуру с пагинацией
        keyboard = get_notifications_list_keyboard(notifications, page, total_pages)

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error in show_notifications_list: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при получении уведомлений",
            reply_markup=get_notifications_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


async def show_notification_settings(callback: CallbackQuery):
    """Показать настройки уведомлений"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        # Получаем текущие настройки пользователя
        # В вашей модели User есть поле notifications_enabled
        from models.user import User
        user = await User.get_or_none(telegram_id=int(user_id))
        
        if user:
            text = "⚙️ **Настройки уведомлений**\n\n"
            text += f"• Статус: {'🔔 Включены' if user.notifications_enabled else '🔕 Выключены'}\n"
            # Добавьте другие настройки, если они есть в модели User
        else:
            text = "⚙️ **Настройки уведомлений**\n\nПользователь не найден."

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_notification_settings_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in show_notification_settings: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка",
            reply_markup=get_notifications_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


async def mark_notification_read(callback: CallbackQuery, notification_id: str):
    """Отметить уведомление как прочитанное"""
    integration = await get_integration()

    try:
        # Используем существующий метод mark_as_delivered
        await integration.notification_service.mark_as_delivered(notification_id)
        await callback.answer("✅ Уведомление отмечено как прочитанное")

        # Обновляем список
        await show_notifications_list(callback)

    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


async def clear_all_notifications(callback: CallbackQuery):
    """Очистить все уведомления"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        # Получаем все уведомления пользователя
        notifications = await integration.notification_service.get_user_notifications(
            user_id=user_id,
            limit=1000,
            offset=0
        )
        
        # Отменяем каждое уведомление
        for notification in notifications:
            await integration.notification_service.cancel_notification(notification.id)

        await callback.message.edit_text(
            "✅ Все уведомления очищены",
            reply_markup=get_notifications_main_keyboard(show_back=True)
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error clearing notifications: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


async def toggle_notifications(callback: CallbackQuery, enabled: bool):
    """Включить/выключить уведомления"""
    user_id = int(callback.from_user.id)

    try:
        from models.user import User
        user = await User.get_or_none(telegram_id=user_id)
        
        if user:
            user.notifications_enabled = enabled
            await user.save()
            
            status = "включены" if enabled else "выключены"
            await callback.answer(f"🔔 Уведомления {status}")

        # Обновляем настройки
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Error toggling notifications: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


# ==================== CALLBACK ХЕНДЛЕР ====================

@router.callback_query()
async def notification_callback_handler(callback: CallbackQuery):
    """Единый обработчик callback'ов от уведомлений"""
    action = callback.data

    try:
        if action == "notifications_main":
            await show_notifications_menu(callback)

        elif action == "notifications_list":
            await show_notifications_list(callback, page=0)

        elif action.startswith("notifications_page_"):
            page = int(action.replace("notifications_page_", ""))
            await show_notifications_list(callback, page=page)

        elif action.startswith("notif_read_"):
            notification_id = action.replace("notif_read_", "")
            await mark_notification_read(callback, notification_id)

        elif action == "notif_clear_all":
            await clear_all_notifications(callback)

        elif action == "notifications_settings":
            await show_notification_settings(callback)

        elif action == "notif_on":
            await toggle_notifications(callback, True)

        elif action == "notif_off":
            await toggle_notifications(callback, False)

        elif action == "notif_reminders":
            # TODO: Настройка напоминаний
            await callback.answer("⚙️ В разработке", show_alert=True)

        elif action == "notif_stats":
            # TODO: Статистика уведомлений
            await callback.answer("📊 В разработке", show_alert=True)

        else:
            await callback.answer()

    except Exception as e:
        logger.error(f"Error in notification callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
        