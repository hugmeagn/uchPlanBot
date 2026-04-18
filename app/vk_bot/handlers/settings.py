"""
Хендлеры настроек
"""
import logging
from typing import Optional

from ..vk_api.client import VkMessage
from ..keyboards.base import create_back_keyboard, create_confirm_keyboard
from ..keyboards import get_main_menu_keyboard
from ..handlers import router
from models.user import User
from models.task import TaskModel
from models.daily_plan import DailyPlan
from ..utils.vk_utils import format_message, create_keyboard, create_text_button

logger = logging.getLogger(__name__)


def get_settings_keyboard() -> str:
    """Клавиатура настроек"""
    buttons = [
        [create_text_button("🗑️ Удалить данные", {"callback": "settings_delete_data"}, "negative")],
        [create_text_button("↩️ В меню", {"callback": "back_to_menu"}, "secondary")]
    ]
    return create_keyboard(buttons)


def get_delete_confirmation_keyboard() -> str:
    """Клавиатура подтверждения удаления"""
    buttons = [
        [create_text_button("✅ Да, удалить всё", {"callback": "delete_confirm_all"}, "negative")],
        [create_text_button("🗑️ Удалить только задачи", {"callback": "delete_confirm_tasks"}, "secondary")],
        [create_text_button("❌ Отменить", {"callback": "delete_cancel"}, "primary")]
    ]
    return create_keyboard(buttons)


@router.callback("menu_settings")
async def show_settings_menu(message: VkMessage, state: Optional[str], data: dict):
    """Показывает меню настроек"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.clear(user_id)

    user = await User.get_or_none(vk_id=user_id).select_related('institution')

    if not user:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Профиль не найден. Используйте /start.",
            keyboard=create_back_keyboard("back_to_menu")
        )
        return

    institution_name = user.institution.name if user.institution else "Не указано"

    if user.role == "teacher":
        profile_text = (
            f"👨‍🏫 **Роль:** Преподаватель\n"
            f"📇 **ФИО:** {user.full_name or 'Не указано'}\n"
            f"🏫 **Учебное заведение:** {institution_name}\n"
            f"🏛️ **Кафедра:** {user.group or 'Не указана'}\n"
            f"🔔 **Уведомления:** {'✅ Включены' if user.notifications_enabled else '❌ Выключены'}"
        )
    else:
        profile_text = (
            f"👤 **Роль:** Студент\n"
            f"🏫 **Учебное заведение:** {institution_name}\n"
            f"👥 **Группа:** {user.group or 'Не указана'}\n"
            f"🔔 **Уведомления:** {'✅ Включены' if user.notifications_enabled else '❌ Выключены'}"
        )

    text = f"⚙️ **Настройки профиля**\n\n{profile_text}\n\nВыберите действие:"

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_settings_keyboard()
    )


@router.callback("settings_delete_data")
async def settings_delete_data(message: VkMessage, state: Optional[str], data: dict):
    """Показывает подтверждение удаления данных"""
    vk = data['vk']
    user_id = message.from_id

    text = (
        "⚠️ **Удаление данных**\n\n"
        "Вы уверены, что хотите удалить ваши данные?\n\n"
        "**Действие необратимо!**"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_delete_confirmation_keyboard()
    )


@router.callback("delete_cancel")
async def delete_cancel(message: VkMessage, state: Optional[str], data: dict):
    """Отмена удаления"""
    await show_settings_menu(message, state, data)


@router.callback("delete_confirm_all")
async def delete_all_data(message: VkMessage, state: Optional[str], data: dict):
    """Полное удаление всех данных"""
    vk = data['vk']
    user_id = message.from_id

    try:
        user = await User.get_or_none(vk_id=user_id)

        if user:
            # Удаляем daily plans
            await DailyPlan.filter(user=user).delete()

            # Удаляем задачи
            await TaskModel.filter(user_id=str(user_id)).delete()

            # Удаляем пользователя
            await user.delete()

        await vk.send_message(
            peer_id=user_id,
            text="🗑️ **Все данные успешно удалены!**\n\n"
                 "Если захотите использовать бота снова, просто напишите /start."
        )

    except Exception as e:
        logger.error(f"Error deleting user data: {e}", exc_info=True)
        await vk.send_message(
            peer_id=user_id,
            text=f"❌ Ошибка при удалении данных: {str(e)[:200]}"
        )


@router.callback("delete_confirm_tasks")
async def delete_tasks_only(message: VkMessage, state: Optional[str], data: dict):
    """Удаление только задач"""
    vk = data['vk']
    user_id = message.from_id

    try:
        deleted = await TaskModel.filter(user_id=str(user_id)).delete()

        await vk.send_message(
            peer_id=user_id,
            text=f"✅ **Задачи успешно удалены!**\n\nУдалено задач: **{deleted}**"
        )

        await show_settings_menu(message, state, data)

    except Exception as e:
        logger.error(f"Error deleting tasks: {e}")
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при удалении задач."
        )
