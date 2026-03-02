"""
Обработчики для подтверждения удаления данных.
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.handlers.menu.menu import show_main_menu
from bot.utils.user_data import format_user

from models.user import User

from bot.handlers.menu.keyboards.common import back_button_kb
from .keyboards.settings import settings_kb, delete_confirmation_kb, notification_settings_kb

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "settings_back")
async def settings_back(callback: CallbackQuery):
    """
    Возврат в меню настроек
    """
    # ВАЖНО: Используем callback.from_user.id
    user_id = callback.from_user.id
    logger.info(f"Settings back from user {user_id}")

    user = await User.get_or_none(telegram_id=user_id)

    if not user:
        await callback.message.edit_text(
            "❌ **Профиль не найден!**\n"
            "Пожалуйста, используйте /start",
            reply_markup=back_button_kb()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"⚙️ **Настройки профиля**\n\n"
        f"Текущие данные:\n" +
        await format_user(user) +
        f"Выберите, что хотите изменить:",
        parse_mode="Markdown",
        reply_markup=settings_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings_profile")
async def settings_profile(callback: CallbackQuery):
    """
    Редактирование профиля из настроек.
    """
    logger.info(f"Settings profile from user {callback.from_user.id}")
    # TODO: edit_fields
    await callback.message.edit_text(
        "✏️ **Редактирование профиля**\n\n"
        "В разработке",
        reply_markup=back_button_kb("settings_back")
    )
    await callback.answer()


@router.callback_query(F.data == "settings_notifications")
async def settings_notifications(callback: CallbackQuery):
    """
    Настройка уведомлений.
    """
    # ВАЖНО: Используем callback.from_user.id
    user_id = callback.from_user.id
    logger.info(f"Settings notifications from user {user_id}")

    user = await User.get_or_none(telegram_id=user_id)

    if not user:
        await callback.message.edit_text(
            "❌ **Профиль не найден!**",
            reply_markup=back_button_kb()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🔔 **Настройка уведомлений**\n\n"
        "Здесь вы можете управлять уведомлениями:\n"
        "• О начале пар\n"
        "• О дедлайнах задач\n"
        "• О изменениях в расписании",
        parse_mode="Markdown",
        reply_markup=notification_settings_kb(user.notifications_enabled),
    )
    await callback.answer()


@router.callback_query(F.data == "settings_delete_data")
async def settings_delete_data(callback: CallbackQuery):
    """
    Удаление данных пользователя.
    """
    logger.info(f"Settings delete data from user {callback.from_user.id}")
    await callback.message.edit_text(
        "⚠️ **Удаление данных**\n\n"
        "Вы уверены, что хотите удалить ваши данные?\n\n"
        "**Действие необратимо!**",
        parse_mode="Markdown",
        reply_markup=delete_confirmation_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_"))
async def handle_delete_confirmation(callback: CallbackQuery):
    """
    Обработка подтверждения удаления данных.
    """
    action = callback.data
    user_id = callback.from_user.id
    logger.info(f"Delete confirmation from user {user_id}: {action}")

    if action == "delete_cancel":
        # Отмена удаления
        await callback.message.edit_text(
            "❌ Удаление отменено.\n\n"
            "Возвращаемся в настройки...",
        )
        # Возвращаемся в настройки
        await settings_back(callback)

    elif action == "delete_confirm_all":
        # Удаление всех данных
        await delete_all_data(callback)

    elif action == "delete_confirm_tasks":
        # Удаление только задач
        await delete_tasks_only(callback)

    elif action == "delete_confirm_schedule":
        # Удаление только расписания
        await delete_schedule_only(callback)

    await callback.answer()


async def delete_all_data(callback: CallbackQuery):
    """
    Полное удаление всех данных пользователя, включая запись из БД.
    """
    try:
        # ВАЖНО: Используем callback.from_user.id
        user = await User.get_or_none(telegram_id=callback.from_user.id)

        if not user:
            await callback.message.edit_text(
                "❌ **Пользователь не найден!**\n\n"
                "Похоже, ваши данные уже были удалены ранее.",
            )
            return

        # Сохраняем информацию для логирования перед удалением
        user_id = user.id
        telegram_id = user.telegram_id
        first_name = user.first_name

        # Удаляем связанные данные
        # 1. Удаляем daily plans если есть
        try:
            from models.daily_plan import DailyPlan
            deleted_plans = await DailyPlan.filter(user=user).delete()
            logger.info(f"Deleted {deleted_plans} daily plans")
        except Exception as e:
            logger.error(f"Error deleting daily plans: {e}")

        # 2. Удаляем задачи
        try:
            from models.task import TaskModel
            deleted_tasks = await TaskModel.filter(user_id=str(telegram_id)).delete()
            logger.info(f"Deleted {deleted_tasks} tasks")
        except Exception as e:
            logger.error(f"Error deleting tasks: {e}")

        # 3. Удаляем пользователя
        await user.delete()

        logger.info(
            f"User fully deleted:\n"
            f"• ID in DB: {user_id}\n"
            f"• Telegram ID: {telegram_id}\n"
            f"• Name: {first_name}"
        )

        await callback.message.edit_text(
            "🗑️ **Все данные успешно удалены!**\n\n"
            "✅ Ваша учетная запись полностью удалена из системы.\n\n"
            "Если вы захотите использовать бота снова, "
            "просто запустите его командой /start.",
        )

    except Exception as e:
        logger.error(f"Critical error deleting user: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ **Ошибка при удалении:**\n{str(e)[:200]}",
        )


async def delete_tasks_only(callback: CallbackQuery):
    """
    Удаление только задач пользователя.
    """
    try:
        from models.task import TaskModel

        telegram_id = callback.from_user.id
        deleted = await TaskModel.filter(user_id=str(telegram_id)).delete()

        await callback.message.edit_text(
            f"✅ **Задачи успешно удалены!**\n\n"
            f"Удалено задач: **{deleted}**",
        )

        # Возвращаемся в настройки
        await settings_back(callback)

    except Exception as e:
        logger.error(f"Error deleting tasks: {e}")
        await callback.message.edit_text(
            "❌ **Ошибка при удалении задач!**",
        )


async def delete_schedule_only(callback: CallbackQuery):
    """
    Удаление только расписания пользователя.
    """
    # В вашей системе расписание не хранится в БД, а парсится с сайта
    # Поэтому просто показываем сообщение
    await callback.message.edit_text(
        "✅ **Расписание сброшено!**\n\n"
        "Будет загружено актуальное расписание при следующем просмотре.",
    )

    # Возвращаемся в настройки
    await settings_back(callback)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_from_delete(callback: CallbackQuery):
    """
    Возврат в главное меню после удаления данных.
    """
    await show_main_menu(callback)
