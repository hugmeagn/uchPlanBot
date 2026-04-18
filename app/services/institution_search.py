"""
Сервис для поиска учебных заведений.
"""
import logging
from typing import List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from models.institution import Institution

logger = logging.getLogger(__name__)


async def find_institution(search_term: str) -> Optional[Institution]:
    """
    Поиск учебного заведения по названию или веб-сайту.

    Args:
        search_term: Название или URL для поиска

    Returns:
        Institution object или None если не найдено
    """
    # Нормализуем поисковый запрос
    search_term = search_term.strip().lower()

    if len(search_term) < 2:
        return None

    try:
        # 1. Ищем по полному совпадению названия (регистронезависимо)
        institution = await Institution.filter(name__iexact=search_term).first()
        if institution:
            logger.debug(f"Найдено по полному совпадению названия: {institution.name}")
            return institution

        # 2. Ищем по частичному совпадению названия
        institution = await Institution.filter(name__icontains=search_term).first()
        if institution:
            logger.debug(f"Найдено по частичному совпадению названия: {institution.name}")
            return institution

        # 3. Ищем по веб-сайту
        institution = await Institution.filter(website__icontains=search_term).first()
        if institution:
            logger.debug(f"Найдено по веб-сайту: {institution.website}")
            return institution

        logger.debug(f"Заведение не найдено по запросу: '{search_term}'")
        return None

    except Exception as e:
        logger.error(f"Ошибка при поиске заведения '{search_term}': {e}")
        return None


async def get_all_institutions(page: int = 0, items_per_page: int = 5) -> Tuple[List[Institution], int]:
    """
    Получить все учебные заведения с пагинацией.

    Args:
        page: Номер страницы (начиная с 0)
        items_per_page: Количество элементов на странице

    Returns:
        Кортеж (список заведений на странице, общее количество страниц)
    """
    try:
        # Получаем все заведения, отсортированные по названию
        institutions = await Institution.all().order_by('name')

        # Применяем пагинацию
        total_items = len(institutions)
        total_pages = (total_items + items_per_page - 1) // items_per_page

        # Проверяем корректность номера страницы
        if page < 0:
            page = 0
        elif page >= total_pages > 0:
            page = total_pages - 1

        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page

        page_institutions = institutions[start_idx:end_idx]

        logger.debug(f"Получено {len(page_institutions)} заведений на странице {page + 1}/{total_pages}")
        return page_institutions, total_pages

    except Exception as e:
        logger.error(f"Ошибка при получении списка заведений: {e}")
        return [], 0


async def get_institution_by_id(institution_id: int) -> Optional[Institution]:
    """
    Получить учебное заведение по ID.

    Args:
        institution_id: ID заведения в БД

    Returns:
        Institution object или None если не найдено
    """
    try:
        institution = await Institution.get_or_none(id=institution_id)
        if institution:
            logger.debug(f"Found institution by ID {institution_id}: {institution.name}")
        else:
            logger.warning(f"Institution with ID {institution_id} not found")
        return institution
    except Exception as e:
        logger.error(f"Error getting institution by ID {institution_id}: {e}")
        return None


async def get_institutions_count() -> int:
    """
    Получить общее количество учебных заведений.

    Returns:
        Количество заведений
    """
    try:
        count = await Institution.all().count()
        return count
    except Exception as e:
        logger.error(f"Ошибка при получении количества заведений: {e}")
        return 0


def create_institutions_keyboard(
        institutions: List[Institution],
        current_page: int,
        total_pages: int
) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру со списком учебных заведений.

    Args:
        institutions: Список заведений на текущей странице
        current_page: Текущая страница (начиная с 0)
        total_pages: Общее количество страниц

    Returns:
        InlineKeyboardMarkup с кнопками заведений и пагинацией
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для каждого заведения
    for inst in institutions:
        # Обрезаем название, если слишком длинное
        display_name = str(inst)
        if len(display_name) > 40:
            display_name = display_name[:37] + "..."

        builder.row(
            InlineKeyboardButton(
                text=f"🏫 {display_name}",
                callback_data=f"select_institution_{inst.id}"
            )
        )

    # Добавляем кнопки пагинации
    pagination_buttons = []

    if current_page > 0:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"inst_page_{current_page - 1}"
            )
        )

    pagination_buttons.append(
        InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="inst_page_current"
        )
    )

    if current_page < total_pages - 1:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"inst_page_{current_page + 1}"
            )
        )

    if pagination_buttons:
        builder.row(*pagination_buttons)

    # Добавляем кнопки действий
    builder.row(
        InlineKeyboardButton(
            text="🔍 Поиск заведения",
            callback_data="institution_search"
        ),
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="institution_back"
        ),
        width=2
    )

    return builder.as_markup()


def create_institutions_list_kb(
        current_page: int,
        total_pages: int
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для списка заведений с пагинацией (устаревший метод,
    оставлен для обратной совместимости).

    Args:
        current_page: Текущая страница (начиная с 0)
        total_pages: Общее количество страниц

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Кнопки пагинации
    pagination_row = []

    if current_page > 0:
        pagination_row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"institutions_page_{current_page - 1}"
            )
        )

    pagination_row.append(
        InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="institutions_page_current"
        )
    )

    if current_page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=f"institutions_page_{current_page + 1}"
            )
        )

    if pagination_row:
        builder.row(*pagination_row)

    # Кнопки действий
    builder.row(
        InlineKeyboardButton(
            text="🔍 Поиск заведения",
            callback_data="institution_search"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="↩️ Назад в меню",
            callback_data="institution_back"
        )
    )

    return builder.as_markup()


def format_institutions_list(
        institutions: List[Institution],
        current_page: int,
        total_pages: int,
        total_items: int
) -> str:
    """
    Форматировать список заведений в текстовое сообщение.

    Args:
        institutions: Список заведений
        current_page: Текущая страница
        total_pages: Общее количество страниц
        total_items: Общее количество заведений

    Returns:
        Отформатированный текст
    """
    text = f"📋 **Все доступные учебные заведения**\n\n"
    text += f"**Найдено:** {total_items} заведений\n"
    text += f"**Страница:** {current_page + 1}/{total_pages}\n\n"

    if not institutions:
        text += "❌ Нет доступных учебных заведений.\n"
        return text

    text += "👇 **Нажмите на кнопку с нужным заведением:**\n\n"

    return text


def format_institution_info(institution: Institution) -> str:
    """
    Форматировать информацию о заведении.

    Args:
        institution: Объект Institution

    Returns:
        Отформатированный текст
    """
    text = f"🏫 **{institution.name}**\n\n"

    if institution.website:
        text += f"**🌐 Сайт:** {institution.website}\n"

    if institution.city:
        text += f"**🏙️ Город:** {institution.city}\n"

    return text


def format_institution_info_short(institution: Institution) -> str:
    """
    Форматировать информацию о заведении.

    Args:
        institution: Объект Institution

    Returns:
        Отформатированный текст
    """
    return f"🏫 **{institution.name}**, 🏙️ {institution.city} (🌐 {institution.website})"
