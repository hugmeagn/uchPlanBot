"""
Утилиты для работы с VK
"""
import json
from typing import Optional, Dict, Any, List, Union


def create_keyboard(buttons: List[List[Dict[str, Any]]], one_time: bool = False, inline: bool = False) -> str:
    """
    Создает клавиатуру для VK в формате JSON

    Args:
        buttons: Список рядов кнопок. Каждый ряд - список кнопок
        one_time: Скрыть клавиатуру после использования
        inline: Инлайн клавиатура (под сообщением)

    Returns:
        JSON строка клавиатуры
    """
    keyboard = {
        "one_time": one_time,
        "inline": inline,
        "buttons": buttons
    }

    return json.dumps(keyboard, ensure_ascii=False)


def create_button(
    label: str,
    payload: Optional[Dict] = None,
    color: str = "primary",
    button_type: str = "text"
) -> Dict[str, Any]:
    """
    Создает кнопку для клавиатуры VK

    Args:
        label: Текст кнопки
        payload: Данные, которые вернутся при нажатии
        color: Цвет кнопки (primary, secondary, negative, positive)
        button_type: Тип кнопки (text, location, vkpay, vkapps, callback)

    Returns:
        Словарь с описанием кнопки
    """
    action = {
        "type": button_type,
        "label": label
    }

    if payload:
        action["payload"] = json.dumps(payload, ensure_ascii=False)

    return {
        "action": action,
        "color": color
    }


def create_text_button(
    label: str,
    payload: Union[str, Dict] = None,
    color: str = "primary"
) -> Dict[str, Any]:
    """
    Создает текстовую кнопку

    Args:
        label: Текст кнопки
        payload: Данные (строка или словарь)
        color: Цвет кнопки
    """
    if isinstance(payload, str):
        payload = {"callback": payload}
    elif payload is None:
        payload = {"callback": label.lower().replace(" ", "_")}

    return create_button(label, payload, color, "text")


def create_callback_button(
    label: str,
    callback_data: str,
    color: str = "primary"
) -> Dict[str, Any]:
    """
    Создает callback кнопку (аналог инлайн кнопки Telegram)
    """
    return create_button(
        label=label,
        payload={"callback": callback_data},
        color=color,
        button_type="callback"
    )


def create_link_button(label: str, link: str) -> Dict[str, Any]:
    """
    Создает кнопку-ссылку
    """
    return {
        "action": {
            "type": "open_link",
            "link": link,
            "label": label
        }
    }


def create_empty_keyboard() -> str:
    """Создает пустую клавиатуру (для скрытия)"""
    return json.dumps({"buttons": [], "one_time": True})


def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы для Markdown VK
    VK поддерживает ограниченный Markdown: *, _, ~, ```
    """
    return text


def format_message(
    text: str,
    parse_mode: str = "Markdown"
) -> str:
    """
    Форматирует сообщение для VK
    """
    return text


def extract_payload(message: Dict) -> Optional[Dict]:
    """
    Извлекает payload из сообщения
    """
    if not message:
        return None

    payload_str = message.get("payload")
    if payload_str:
        try:
            return json.loads(payload_str)
        except json.JSONDecodeError:
            return None
    return None


def extract_callback(payload: Dict) -> Optional[str]:
    """
    Извлекает callback_data из payload
    """
    if not payload:
        return None

    return payload.get("callback") or payload.get("cmd")


def chunk_text(text: str, max_length: int = 4000) -> List[str]:
    """
    Разбивает длинный текст на части для VK (лимит 4096 символов)
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.split('\n')
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 <= max_length:
            if current_chunk:
                current_chunk += '\n' + line
            else:
                current_chunk = line
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def get_priority_color(priority: int) -> str:
    """
    Возвращает цвет кнопки в зависимости от приоритета
    """
    colors = {
        0: "secondary",   # LOW
        1: "primary",     # MEDIUM
        2: "positive",    # HIGH
        3: "negative"     # CRITICAL
    }
    return colors.get(priority, "primary")
