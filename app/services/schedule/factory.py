from typing import Dict, Type, Optional
from .base import BaseParser
from .parsers.magpk import MagpkParser
from .parsers.magpk_teacher import MagpkTeacherParser


class ParserFactory:
    """
    Фабрика для создания парсеров.
    """
    _parsers: Dict[str, Type[BaseParser]] = {
        'magpk': MagpkParser,  # Парсер для студентов
        'magpk_teacher': MagpkTeacherParser,  # Парсер для преподавателей
        # 'spbstu': SpbstuParser,  # Пример для другого колледжа
    }

    @classmethod
    def register_parser(cls, college_id: str, parser_class: Type[BaseParser]):
        """Позволяет регистрировать новые парсеры динамически."""
        cls._parsers[college_id] = parser_class

    @classmethod
    def get_parser(cls, college_id: str, teacher_mode: bool = False) -> BaseParser:
        """
        Возвращает экземпляр парсера для указанного колледжа.

        Args:
            college_id: ID колледжа
            teacher_mode: Если True, возвращает парсер для преподавателей

        Returns:
            Экземпляр парсера
        """
        # Если запрошен режим преподавателя для magpk, используем специальный парсер
        if college_id == 'magpk' and teacher_mode:
            parser_id = 'magpk_teacher'
        else:
            parser_id = college_id

        if parser_id not in cls._parsers:
            raise ValueError(f"Парсер для колледжа '{parser_id}' не найден.")

        parser_class = cls._parsers[parser_id]
        return parser_class()
