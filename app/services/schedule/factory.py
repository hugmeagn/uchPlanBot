from typing import Dict, Type, Optional
from .base import BaseParser
from .parsers.magpk import MagpkParser
from .parsers.magpk_teacher import MagpkTeacherParser
from .parsers.magtu import MagtuParser, MagtuTeacherParser


class ParserFactory:
    """
    Фабрика для создания парсеров.
    """
    _parsers: Dict[str, Type[BaseParser]] = {
        'magpk': MagpkParser,
        'magpk_teacher': MagpkTeacherParser,
        'magtu': MagtuParser,
        'magtu_teacher': MagtuTeacherParser,
    }

    @classmethod
    def register_parser(cls, college_id: str, parser_class: Type[BaseParser]):
        """Позволяет регистрировать новые парсеры динамически."""
        cls._parsers[college_id] = parser_class

    @classmethod
    def get_parser(cls, college_id: str, teacher_mode: bool = False) -> BaseParser:
        """
        Возвращает экземпляр парсера для указанного колледжа.
        """
        # Для magtu используем teacher_mode
        if college_id == 'magtu' and teacher_mode:
            parser_id = 'magtu_teacher'
        elif college_id == 'magpk' and teacher_mode:
            parser_id = 'magpk_teacher'
        else:
            parser_id = college_id

        if parser_id not in cls._parsers:
            raise ValueError(f"Парсер для колледжа '{parser_id}' не найден.")

        parser_class = cls._parsers[parser_id]
        return parser_class()
