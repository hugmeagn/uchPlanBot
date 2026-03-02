import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from bot.handlers.menu.keyboards.common import back_button_kb
from services.institution_search import (
    find_institution,
    get_all_institutions,
    create_institutions_keyboard,
    format_institutions_list,
    get_institutions_count,
    get_institution_by_id
)
from bot.utils.group_input import create_group_input_message, normalize_group_name

from models.user import User
from models.institution import Institution
from ..menu.keyboards.menu import main_menu_kb

from ..menu.menu import show_main_menu

from .keyboards.selection import role_selection_kb
from .keyboards.setup import setup_profile_kb, institution_list_kb

logger = logging.getLogger(__name__)
router = Router()


class ProfileStates(StatesGroup):
    waiting_for_role = State()
    waiting_for_full_name = State()  # Для ввода ФИО преподавателя
    waiting_for_institution_input = State()
    waiting_for_institution_list = State()
    waiting_for_group_input = State()  # Для студентов - группа, для преподавателей - кафедра


@router.callback_query(F.data == "profile_set_role")
async def set_role_start(callback: CallbackQuery, state: FSMContext):
    """
    Начало выбора роли (первичная настройка).
    """
    await callback.message.edit_text(
        "👤 **Выбор роли**\n\n"
        "Выберите вашу роль в учебном процессе:",
        reply_markup=role_selection_kb(),
    )
    await state.set_state(ProfileStates.waiting_for_role)
    await callback.answer()


@router.callback_query(F.data.startswith("role_"), ProfileStates.waiting_for_role)
async def set_role(callback: CallbackQuery, state: FSMContext):
    """
    Выбор роли пользователя (первичная настройка).
    """
    role = callback.data.replace("role_", "")
    role_name = "студент" if role == "student" else "преподаватель"

    # Сохраняем роль в состоянии
    await state.update_data(role=role, role_name=role_name)

    if role == "teacher":
        # Для преподавателя сначала запрашиваем ФИО
        await callback.message.edit_text(
            "👨‍🏫 **Регистрация преподавателя**\n\n"
            "Введите ваше **ФИО** полностью.\n\n"
            "Это необходимо для корректного отображения ваших пар в расписании.\n\n"
            "**Пример:** Иванов Иван Иванович",
            parse_mode="Markdown"
        )
        await state.set_state(ProfileStates.waiting_for_full_name)
    else:
        # Для студента сразу переходим к выбору заведения
        await show_institution_input_menu(callback, state)  # ← Добавлен state
        await state.set_state(ProfileStates.waiting_for_institution_input)

    await callback.answer(f"Роль: {role_name}")


@router.message(ProfileStates.waiting_for_full_name)
async def handle_full_name(message: Message, state: FSMContext):
    """
    Обработка ввода ФИО преподавателя.
    """
    full_name = message.text.strip()

    # Простая валидация
    if len(full_name) < 5:
        await message.answer(
            "❌ ФИО должно содержать минимум 5 символов.\n"
            "Пожалуйста, введите полное ФИО:",
            reply_markup=back_button_kb("profile_back")
        )
        return

    if len(full_name.split()) < 2:
        await message.answer(
            "❌ Пожалуйста, введите хотя бы фамилию и имя.\n"
            "**Пример:** Иванов Иван Иванович",
            parse_mode="Markdown",
            reply_markup=back_button_kb("profile_back")
        )
        return

    # Сохраняем ФИО
    await state.update_data(full_name=full_name)

    # Переходим к выбору заведения
    await show_institution_input_menu_callback(message, state)


async def show_institution_input_menu_callback(message: Message, state: FSMContext):
    """
    Показать меню ввода заведения (из callback).
    """
    # Получаем количество заведений для информации
    institutions_count = await get_institutions_count()
    data = await state.get_data()
    role = data.get('role', 'student')

    role_text = "преподавателя" if role == "teacher" else "студента"

    await message.answer(
        f"🏫 **Настройка учебного заведения**\n\n"
        f"В базе данных: **{institutions_count}** учебных заведений\n\n"
        f"Выберите учебное заведение для {role_text}:",
        reply_markup=institution_list_kb()
    )
    await state.set_state(ProfileStates.waiting_for_institution_input)


async def show_institution_input_menu(callback: CallbackQuery, state: FSMContext):  # ← Добавлен state
    """
    Показать меню ввода учебного заведения.
    """
    # Получаем количество заведений для информации
    institutions_count = await get_institutions_count()
    data = await state.get_data()  # ← Теперь state доступен
    role = data.get('role', 'student')

    role_text = "преподавателя" if role == "teacher" else "студента"

    await callback.message.edit_text(
        f"🏫 **Настройка учебного заведения**\n\n"
        f"В базе данных: **{institutions_count}** учебных заведений\n\n"
        f"Выберите учебное заведение для {role_text}:",
        reply_markup=institution_list_kb()
    )


@router.callback_query(F.data == "institution_search")
async def search_institution_start(callback: CallbackQuery, state: FSMContext):
    """
    Начало поиска заведения по вводу.
    """
    data = await state.get_data()
    role = data.get('role', 'student')

    role_text = "преподавателя" if role == "teacher" else "студента"

    await callback.message.edit_text(
        f"🔍 **Поиск учебного заведения**\n\n"
        f"Введите **название** или **веб-сайт** вашего учебного заведения.\n\n"
        f"**Примеры:**\n"
        f"• Магнитогорский политехнический колледж\n"
        f"• https://mpk-mgn.ru\n"
        f"• МГУ\n"
        f"• МПК (сокращение)\n\n"
        f"**Важно:** Заведение должно быть уже в базе данных.\n"
        f"Если не нашли своё - выберите из списка или обратитесь к администратору.",
        reply_markup=back_button_kb("institution_back")
    )
    await state.set_state(ProfileStates.waiting_for_institution_input)


@router.message(ProfileStates.waiting_for_institution_input)
async def search_institution(message: Message, state: FSMContext):
    """
    Поиск учебного заведения по введенному тексту.
    """
    search_term = message.text.strip()

    if len(search_term) < 2:
        await message.answer(
            "❌ Слишком короткий запрос. Введите минимум 2 символа:",
            reply_markup=back_button_kb("institution_back")
        )
        return

    # Используем сервис поиска
    institution = await find_institution(search_term)

    if not institution:
        # Заведение не найдено
        await message.answer(
            f"❌ **Заведение не найдено!**\n\n"
            f"По запросу **'{search_term}'** ничего не найдено в базе данных.\n\n"
            f"**Что можно сделать:**\n"
            f"1. 🔍 **Попробуйте другой запрос**\n"
            f"2. 📋 **Выберите из списка** доступных заведений\n"
            f"3. 📞 **Обратитесь к администратору** для добавления заведения\n\n"
            f"Выберите действие:",
            reply_markup=institution_list_kb()
        )
        return

    # Заведение найдено - сохраняем
    await state.update_data(institution_id=institution.id)

    # Переходим к вводу группы/кафедры
    await show_group_input(message, state, institution)


@router.callback_query(F.data == "institution_show_all")
async def show_all_institutions(callback: CallbackQuery, state: FSMContext):
    """
    Показать все доступные учебные заведения в виде клавиатуры.
    """
    # Используем сервис для получения данных
    page_institutions, total_pages = await get_all_institutions(page=0)
    total_items = await get_institutions_count()

    if not page_institutions:
        await callback.message.edit_text(
            "📭 **Список заведений пуст**\n\n"
            "В базе данных пока нет учебных заведений.\n"
            "Обратитесь к администратору для добавления.",
            reply_markup=back_button_kb("institution_back")
        )
        return

    # Форматируем текст
    text = format_institutions_list(page_institutions, 0, total_pages, total_items)

    # Создаем клавиатуру с кнопками заведений
    keyboard = create_institutions_keyboard(page_institutions, 0, total_pages)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )
    await state.set_state(ProfileStates.waiting_for_institution_list)
    await callback.answer()


@router.callback_query(F.data.startswith("inst_page_"), ProfileStates.waiting_for_institution_list)
async def handle_institutions_pagination(callback: CallbackQuery, state: FSMContext):
    """
    Обработка пагинации списка заведений.
    """
    page_str = callback.data.replace("inst_page_", "")

    if page_str == "current":
        await callback.answer()
        return

    try:
        page = int(page_str)
    except ValueError:
        await callback.answer("❌ Неверная страница")
        return

    # Используем сервис для получения данных
    page_institutions, total_pages = await get_all_institutions(page=page)
    total_items = await get_institutions_count()

    # Проверяем корректность номера страницы
    if page < 0 or page >= total_pages:
        await callback.answer("❌ Такой страницы нет")
        return

    # Форматируем текст
    text = format_institutions_list(page_institutions, page, total_pages, total_items)

    # Создаем клавиатуру
    keyboard = create_institutions_keyboard(page_institutions, page, total_pages)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("select_institution_"), ProfileStates.waiting_for_institution_list)
async def handle_institution_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора учебного заведения из списка.
    """
    institution_id = int(callback.data.replace("select_institution_", ""))

    # Получаем заведение по ID
    institution = await get_institution_by_id(institution_id)

    if not institution:
        await callback.answer("❌ Заведение не найдено", show_alert=True)
        return

    # Сохраняем ID заведения
    await state.update_data(institution_id=institution.id)

    # Подтверждаем выбор и переходим к вводу группы/кафедры
    await show_group_input(callback.message, state, institution)

    await callback.answer(f"Выбрано: {institution.name}")


async def show_group_input(message: Message, state: FSMContext, institution: Institution):
    """
    Показать ввод группы (для студента) или кафедры (для преподавателя).
    """
    data = await state.get_data()
    role = data.get('role', 'student')

    if role == "teacher":
        # Для преподавателя - ввод кафедры/факультета
        full_name = data.get('full_name', 'Преподаватель')

        await message.answer(
            f"✅ **Заведение выбрано!**\n\n"
            f"**{institution.name}**\n"
            f"📍 {institution.city or 'Город не указан'}\n"
            f"🌐 {institution.website or 'Сайт не указан'}\n\n"
            f"👨‍🏫 **Ваше ФИО:** {full_name}\n\n"
            f"🏛️ **Введите название вашей кафедры или факультета**\n\n"
            f"Это поможет точнее определять ваши пары в расписании.\n\n"
            f"**Примеры:**\n"
            f"• Кафедра информатики\n"
            f"• Факультет прикладной математики\n"
            f"• ЦМК программирования",
            parse_mode="Markdown"
        )
    else:
        # Для студента - ввод группы
        await message.answer(
            f"✅ **Заведение выбрано!**\n\n"
            f"**{institution.name}**\n"
            f"📍 {institution.city or 'Город не указан'}\n"
            f"🌐 {institution.website or 'Сайт не указан'}\n\n"
            f"👥 **Введите название вашей группы**\n\n"
            f"**Примеры:**\n"
            f"• ИБ-21\n"
            f"• ПКС-20-2\n"
            f"• МОАИС-19",
            parse_mode="Markdown"
        )

    await message.answer(
        "Введите название:",
        reply_markup=back_button_kb("profile_back")
    )
    await state.set_state(ProfileStates.waiting_for_group_input)


@router.message(ProfileStates.waiting_for_group_input)
async def handle_group_input(message: Message, state: FSMContext):
    """
    Обработка ввода группы (для студента) или кафедры (для преподавателя).
    """
    group_or_department = message.text.strip()

    # Простая проверка на пустую строку
    if not group_or_department:
        await message.answer(
            "❌ Название не может быть пустым.\n"
            "Пожалуйста, введите название:",
            reply_markup=back_button_kb("profile_back")
        )
        return

    # Нормализуем название
    group_normalized = normalize_group_name(group_or_department)

    # Сохраняем в состоянии
    await state.update_data(group=group_normalized)

    # Завершаем настройку профиля
    await setup_end(message, state)


async def setup_end(message: Message, state: FSMContext):
    """
    Конец настройки профиля.
    """
    from_user = message.from_user
    data = await state.get_data()

    role = data.get('role')
    full_name = data.get('full_name')  # Для преподавателя
    institution_id = data.get('institution_id')
    institution = await Institution.get_or_none(id=institution_id)
    group = data.get('group')  # Для студента - группа, для преподавателя - кафедра

    if role == "teacher" and not full_name:
        await message.answer(
            "❌ **Ошибка!** Не указано ФИО преподавателя.\n"
            "Пожалуйста, заполните профиль заново",
        )
        await state.set_state("profile_setup")
        return

    if None in [role, institution, group]:
        await message.answer(
            "❌ **Ошибка!** Какое-то из полей не заполнено.\n"
            "Пожалуйста, заполните профиль заново",
        )
        await state.set_state("profile_setup")
        return

    # Проверяем, существует ли уже пользователь
    existing_user = await User.get_or_none(telegram_id=from_user.id)

    if existing_user:
        # Обновляем существующего пользователя
        existing_user.role = role
        existing_user.full_name = full_name if role == "teacher" else None
        existing_user.institution = institution
        existing_user.group = group
        await existing_user.save()
        user = existing_user
    else:
        # Создаем нового пользователя
        user = await User.create(
            telegram_id=from_user.id,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            username=from_user.username,
            role=role,
            full_name=full_name if role == "teacher" else None,
            institution=institution,
            group=group
        )

    # Формируем сообщение об успехе
    if role == "teacher":
        success_text = (
            f"🎉 **Профиль преподавателя успешно сохранен!**\n\n"
            f"👨‍🏫 **ФИО:** {full_name}\n"
            f"🏫 **Учебное заведение:** {institution.name}\n"
            f"🏛️ **Кафедра/факультет:** {group}\n\n"
            f"Теперь вы можете пользоваться всеми функциями бота!"
        )
    else:
        success_text = (
            f"🎉 **Профиль студента успешно сохранен!**\n\n"
            f"👤 **Роль:** {role}\n"
            f"🏫 **Учебное заведение:** {institution.name}\n"
            f"👥 **Группа:** {group}\n\n"
            f"Теперь вы можете пользоваться всеми функциями бота!"
        )

    await message.answer(
        success_text,
        parse_mode="Markdown"
    )

    await state.clear()
    await show_main_menu(message)


@router.callback_query(F.data == "profile_back")
async def profile_back(callback: CallbackQuery, state: FSMContext):
    """
    Возврат на предыдущий шаг настройки профиля.
    """
    current_state = await state.get_state()

    if current_state == ProfileStates.waiting_for_role:
        await callback.message.edit_text(
            "📝 **Настройка профиля**\n\n"
            "Выберите, что хотите настроить:",
            reply_markup=setup_profile_kb(),
        )
        await state.set_state("profile_setup")

    elif current_state == ProfileStates.waiting_for_full_name:
        # Возврат к выбору роли
        await callback.message.edit_text(
            "👤 **Выбор роли**\n\n"
            "Выберите вашу роль в учебном процессе:",
            reply_markup=role_selection_kb(),
        )
        await state.set_state(ProfileStates.waiting_for_role)

    elif current_state == ProfileStates.waiting_for_institution_input:
        # Возврат к вводу ФИО (для преподавателя) или к выбору роли (для студента)
        data = await state.get_data()
        role = data.get('role')

        if role == "teacher":
            await callback.message.edit_text(
                "👨‍🏫 **Регистрация преподавателя**\n\n"
                "Введите ваше **ФИО** полностью:",
                parse_mode="Markdown"
            )
            await state.set_state(ProfileStates.waiting_for_full_name)
        else:
            await callback.message.edit_text(
                "👤 **Выбор роли**\n\n"
                "Выберите вашу роль в учебном процессе:",
                reply_markup=role_selection_kb(),
            )
            await state.set_state(ProfileStates.waiting_for_role)

    elif current_state == ProfileStates.waiting_for_institution_list:
        # Возврат к меню выбора заведения
        await show_institution_input_menu(callback, state)
        await state.set_state(
            ProfileStates.waiting_for_institution_input)  # ← Исправлено: было waiting_for_information_input

    elif current_state == ProfileStates.waiting_for_group_input:
        # Возврат к выбору заведения
        await show_institution_input_menu(callback, state)
        await state.set_state(ProfileStates.waiting_for_institution_input)

    else:
        # Если состояние не определено, просто возвращаем в главное меню
        await callback.message.edit_text(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            reply_markup=main_menu_kb()
        )
        await state.clear()

    await callback.answer()
