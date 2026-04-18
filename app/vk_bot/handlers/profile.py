"""
Хендлеры настройки профиля
"""
import logging
from typing import Optional

from ..vk_api.client import VkMessage
from ..keyboards.profile import (
    get_profile_setup_keyboard,
    get_role_selection_keyboard,
    get_institution_search_keyboard,
    get_skip_keyboard
)
from ..keyboards.base import create_back_keyboard
from ..handlers import router
from models.user import User
from models.institution import Institution
from services.institution_search import (
    find_institution,
    get_all_institutions,
    get_institution_by_id
)
from ..utils.vk_utils import format_message

logger = logging.getLogger(__name__)

# Состояния FSM
STATE_WAITING_ROLE = "profile_waiting_role"
STATE_WAITING_FULL_NAME = "profile_waiting_full_name"
STATE_WAITING_INSTITUTION = "profile_waiting_institution"
STATE_WAITING_GROUP = "profile_waiting_group"


async def start_profile_setup(message: VkMessage, state: Optional[str], data: dict):
    """Начинает настройку профиля"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.clear(user_id)

    text = (
        "👋 Добро пожаловать в UchPlan!\n\n"
        "Я помогу вам:\n"
        "📅 Следить за расписанием занятий\n"
        "✅ Управлять учебными задачами\n"
        "⏰ Получать напоминания о парах и дедлайнах\n\n"
        "Для начала давайте настроим ваш профиль:"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_profile_setup_keyboard()
    )


@router.command("profile")
@router.callback("menu_settings")
@router.callback("profile_set_role")
async def start_role_selection(message: VkMessage, state: Optional[str], data: dict):
    """Начинает выбор роли"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.set_state(user_id, STATE_WAITING_ROLE)

    text = (
        "👤 **Выбор роли**\n\n"
        "Выберите вашу роль в учебном процессе:"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_role_selection_keyboard()
    )


@router.callback("role_student")
@router.callback("role_teacher")
async def handle_role_selection(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает выбор роли"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    callback = message.payload.get("callback")
    role = "student" if callback == "role_student" else "teacher"
    role_name = "студент" if role == "student" else "преподаватель"

    await fsm.update_data(user_id, role=role, role_name=role_name)

    if role == "teacher":
        await fsm.set_state(user_id, STATE_WAITING_FULL_NAME)
        text = (
            "👨‍🏫 **Регистрация преподавателя**\n\n"
            "Введите ваше **ФИО** полностью.\n\n"
            "Это необходимо для корректного отображения ваших пар в расписании.\n\n"
            "**Пример:** Иванов Иван Иванович"
        )
        await vk.send_message(
            peer_id=user_id,
            text=format_message(text),
            keyboard=create_back_keyboard("profile_back")
        )
    else:
        await show_institution_selection(message, state, data)


@router.message(STATE_WAITING_FULL_NAME)
async def handle_full_name(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает ввод ФИО преподавателя"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    full_name = message.text.strip()

    if len(full_name) < 5 or len(full_name.split()) < 2:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Пожалуйста, введите полное ФИО (фамилия и имя).",
            keyboard=create_back_keyboard("profile_back")
        )
        return

    await fsm.update_data(user_id, full_name=full_name)
    await show_institution_selection(message, state, data)


async def show_institution_selection(message: VkMessage, state: Optional[str], data: dict):
    """Показывает меню выбора учебного заведения"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.set_state(user_id, STATE_WAITING_INSTITUTION)

    from services.institution_search import get_institutions_count
    institutions_count = await get_institutions_count()

    fsm_data = await fsm.get_data(user_id)
    role = fsm_data.get('role', 'student')
    role_text = "преподавателя" if role == "teacher" else "студента"

    text = (
        f"🏫 **Настройка учебного заведения**\n\n"
        f"В базе данных: **{institutions_count}** учебных заведений\n\n"
        f"Выберите учебное заведение для {role_text}:"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_institution_search_keyboard()
    )


@router.callback("institution_search")
async def start_institution_search(message: VkMessage, state: Optional[str], data: dict):
    """Начинает поиск заведения по вводу"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.set_state(user_id, STATE_WAITING_INSTITUTION)

    text = (
        "🔍 **Поиск учебного заведения**\n\n"
        "Введите **название** или **веб-сайт** вашего учебного заведения.\n\n"
        "**Примеры:**\n"
        "• Магнитогорский политехнический колледж\n"
        "• magpk.ru\n"
        "• МПК"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=create_back_keyboard("institution_back")
    )


@router.message(STATE_WAITING_INSTITUTION)
async def handle_institution_search(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает поиск учебного заведения"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    search_term = message.text.strip()

    if len(search_term) < 2:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Слишком короткий запрос. Введите минимум 2 символа.",
            keyboard=create_back_keyboard("institution_back")
        )
        return

    institution = await find_institution(search_term)

    if not institution:
        await vk.send_message(
            peer_id=user_id,
            text=f"❌ Заведение '{search_term}' не найдено.\nПопробуйте другой запрос или выберите из списка.",
            keyboard=get_institution_search_keyboard()
        )
        return

    await fsm.update_data(user_id, institution_id=institution.id)
    await show_group_input(message, state, data, institution)


@router.callback("institution_show_all")
async def show_all_institutions(message: VkMessage, state: Optional[str], data: dict):
    """Показывает список всех заведений"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    institutions, total_pages = await get_all_institutions(page=0)

    if not institutions:
        await vk.send_message(
            peer_id=user_id,
            text="📭 Список заведений пуст.",
            keyboard=create_back_keyboard("profile_back")
        )
        return

    # Формируем текст со списком заведений
    text = "📋 **Доступные учебные заведения:**\n\n"

    from ..utils.vk_utils import create_keyboard, create_text_button
    buttons = []

    for i, inst in enumerate(institutions, 1):
        text += f"{i}. {str(inst)}\n"

        # Обрезаем название кнопки до 40 символов
        button_label = str(inst)
        if len(button_label) > 37:
            button_label = button_label[:37] + "..."

        buttons.append([create_text_button(
            button_label,
            {"callback": f"select_institution_{inst.id}"},
            "primary"
        )])

    buttons.append([create_text_button("↩️ Назад", {"callback": "profile_back"}, "secondary")])

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=create_keyboard(buttons)
    )


@router.callback("select_institution_")
async def handle_institution_selection(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает выбор заведения из списка"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    callback = message.payload.get("callback")
    institution_id = int(callback.replace("select_institution_", ""))

    institution = await get_institution_by_id(institution_id)

    if not institution:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Заведение не найдено.",
            keyboard=create_back_keyboard("profile_back")
        )
        return

    await fsm.update_data(user_id, institution_id=institution.id)
    await show_group_input(message, state, data, institution)


async def show_group_input(message: VkMessage, state: Optional[str], data: dict, institution: Institution):
    """Показывает ввод группы/кафедры"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.set_state(user_id, STATE_WAITING_GROUP)

    fsm_data = await fsm.get_data(user_id)
    role = fsm_data.get('role', 'student')

    if role == "teacher":
        full_name = fsm_data.get('full_name', 'Преподаватель')
        text = (
            f"✅ **Заведение выбрано!**\n\n"
            f"**{institution.name}**\n"
            f"📍 {institution.city or 'Город не указан'}\n\n"
            f"👨‍🏫 **Ваше ФИО:** {full_name}\n\n"
            f"🏛️ **Введите название вашей кафедры или факультета**"
        )
    else:
        text = (
            f"✅ **Заведение выбрано!**\n\n"
            f"**{institution.name}**\n"
            f"📍 {institution.city or 'Город не указан'}\n\n"
            f"👥 **Введите название вашей группы**"
        )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=create_back_keyboard("profile_back")
    )


@router.message(STATE_WAITING_GROUP)
async def handle_group_input(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает ввод группы/кафедры"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    group = message.text.strip()

    if not group:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Название не может быть пустым.",
            keyboard=create_back_keyboard("profile_back")
        )
        return

    await fsm.update_data(user_id, group=group)
    await complete_profile_setup(message, state, data)


async def complete_profile_setup(message: VkMessage, state: Optional[str], data: dict):
    """Завершает настройку профиля"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    fsm_data = await fsm.get_data(user_id)

    role = fsm_data.get('role')
    full_name = fsm_data.get('full_name')
    institution_id = fsm_data.get('institution_id')
    group = fsm_data.get('group')

    institution = await Institution.get_or_none(id=institution_id)

    if not all([role, institution, group]):
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка! Не все поля заполнены. Начните заново.",
            keyboard=get_profile_setup_keyboard()
        )
        await fsm.clear(user_id)
        return

    # Получаем информацию о пользователе из VK
    user_info = await vk.get_user_info([user_id])
    first_name = user_info[0]['first_name'] if user_info else "Пользователь"
    last_name = user_info[0]['last_name'] if user_info else ""

    # Создаем или обновляем пользователя
    existing_user = await User.get_or_none(vk_id=user_id)

    if existing_user:
        existing_user.role = role
        existing_user.full_name = full_name if role == "teacher" else None
        existing_user.institution = institution
        existing_user.group = group
        existing_user.first_name = first_name
        existing_user.last_name = last_name
        await existing_user.save()
        user = existing_user
    else:
        user = await User.create(
            vk_id=user_id,
            first_name=first_name,
            last_name=last_name,
            role=role,
            full_name=full_name if role == "teacher" else None,
            institution=institution,
            group=group
        )

    await fsm.clear(user_id)

    if role == "teacher":
        success_text = (
            f"🎉 **Профиль преподавателя успешно сохранен!**\n\n"
            f"👨‍🏫 **ФИО:** {full_name}\n"
            f"🏫 **Учебное заведение:** {institution.name}\n"
            f"🏛️ **Кафедра/факультет:** {group}"
        )
    else:
        success_text = (
            f"🎉 **Профиль студента успешно сохранен!**\n\n"
            f"👤 **Роль:** студент\n"
            f"🏫 **Учебное заведение:** {institution.name}\n"
            f"👥 **Группа:** {group}"
        )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(success_text)
    )

    # Показываем главное меню
    from .menu import show_main_menu
    await show_main_menu(message, state, data)


@router.callback("profile_back")
async def profile_back(message: VkMessage, state: Optional[str], data: dict):
    """Возврат на предыдущий шаг"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    current_state = await fsm.get_state(user_id)

    if current_state == STATE_WAITING_ROLE:
        await fsm.clear(user_id)
        from .menu import show_main_menu
        await show_main_menu(message, state, data)

    elif current_state == STATE_WAITING_FULL_NAME:
        await start_role_selection(message, state, data)

    elif current_state == STATE_WAITING_INSTITUTION:
        fsm_data = await fsm.get_data(user_id)
        role = fsm_data.get('role')
        if role == "teacher":
            await fsm.set_state(user_id, STATE_WAITING_FULL_NAME)
            await vk.send_message(
                peer_id=user_id,
                text="Введите ваше ФИО:",
                keyboard=create_back_keyboard("profile_back")
            )
        else:
            await start_role_selection(message, state, data)

    elif current_state == STATE_WAITING_GROUP:
        await show_institution_selection(message, state, data)

    else:
        await fsm.clear(user_id)
        from .menu import show_main_menu
        await show_main_menu(message, state, data)
