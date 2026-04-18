"""
Хендлеры для работы с уведомлениями
"""
import logging
from typing import Optional

from ..vk_api.client import VkMessage
from ..keyboards.base import create_back_keyboard
from ..handlers import router
from models.user import User
from ..utils.vk_utils import format_message, create_keyboard, create_text_button

logger = logging.getLogger(__name__)


def get_notifications_keyboard(notifications_enabled: bool = True) -> str:
    """Клавиатура для уведомлений"""
    buttons = []

    status_text = "🔔 Уведомления: ВКЛ" if notifications_enabled else "🔕 Уведомления: ВЫКЛ"
    toggle_callback = "notif_disable" if notifications_enabled else "notif_enable"

    buttons.append([create_text_button(
        status_text,
        {"callback": toggle_callback},
        "primary" if notifications_enabled else "secondary"
    )])

    buttons.append([create_text_button(
        "🗑 Очистить все уведомления",
        {"callback": "notif_clear_all"},
        "negative"
    )])

    buttons.append([create_text_button(
        "↩️ Назад",
        {"callback": "back_to_menu"},
        "secondary"
    )])

    return create_keyboard(buttons)


@router.callback("menu_notifications")
async def show_notifications_menu(message: VkMessage, state: Optional[str], data: dict):
    """Показывает меню уведомлений"""
    vk = data['vk']
    user_id = message.from_id

    user = await User.get_or_none(vk_id=user_id)
    notifications_enabled = user.notifications_enabled if user else True

    text = (
        "🔔 **Уведомления**\n\n"
        f"Статус: {'🔔 Включены' if notifications_enabled else '🔕 Выключены'}\n\n"
        "Выберите действие:"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_notifications_keyboard(notifications_enabled)
    )


@router.callback("notif_enable")
async def enable_notifications(message: VkMessage, state: Optional[str], data: dict):
    """Включает уведомления"""
    vk = data['vk']
    user_id = message.from_id

    user = await User.get_or_none(vk_id=user_id)

    if user:
        user.notifications_enabled = True
        await user.save()

    await vk.send_message(
        peer_id=user_id,
        text="✅ Уведомления включены!"
    )

    await show_notifications_menu(message, state, data)


@router.callback("notif_disable")
async def disable_notifications(message: VkMessage, state: Optional[str], data: dict):
    """Выключает уведомления"""
    vk = data['vk']
    user_id = message.from_id

    user = await User.get_or_none(vk_id=user_id)

    if user:
        user.notifications_enabled = False
        await user.save()

    await vk.send_message(
        peer_id=user_id,
        text="🔕 Уведомления выключены!"
    )

    await show_notifications_menu(message, state, data)


@router.callback("notif_clear_all")
async def clear_all_notifications(message: VkMessage, state: Optional[str], data: dict):
    """Очищает все уведомления"""
    vk = data['vk']
    notification_service = data['notification_service']
    user_id = message.from_id

    try:
        notifications = await notification_service.get_user_notifications(
            user_id=str(user_id),
            limit=1000
        )

        for notification in notifications:
            await notification_service.cancel_notification(notification.id)

        await vk.send_message(
            peer_id=user_id,
            text="✅ Все уведомления очищены!"
        )

    except Exception as e:
        logger.error(f"Error clearing notifications: {e}")
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при очистке уведомлений."
        )

    await show_notifications_menu(message, state, data)
