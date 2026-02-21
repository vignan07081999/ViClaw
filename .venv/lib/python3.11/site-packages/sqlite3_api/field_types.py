"""

Типы данных, которые можно хранить в базе данных.
А так же инструменты для их создания.

"""

from __future__ import annotations

import sqlite3 as sql
from ast import literal_eval


class FieldType:
    """
    Инструмент для создания своих типов данных.
    """

    field_types = []  # Инициализированные типы данных.

    def __init_subclass__(cls, **kwargs):
        """
        Инициализируем тип данных.
        """

        sql.register_adapter(cls, cls.adapter)
        sql.register_converter(cls.__name__.lower(), lambda obj: cls.converter(obj))

    @staticmethod
    def adapter(obj: FieldType) -> bytes:
        """
        Функция, возвращающая строку для записи в бд.
        :param obj: Объект поля.
        """

        return str(obj).encode()

    @classmethod
    def converter(cls, obj: bytes) -> FieldType:
        """
        Функция, возвращающая объект поля.
        :param obj: Строка полученная из бд.
        """

        return cls(obj.decode("utf-8"))


class List(FieldType, list):
    @classmethod
    def converter(cls, obj: bytes) -> List:
        return cls(literal_eval(obj.decode("utf-8")))


class Dict(FieldType, dict):
    @classmethod
    def converter(cls, obj: bytes) -> Dict:
        return cls(literal_eval(obj.decode("utf-8")))
