"""

Всё что нужно для создания класса таблицы

"""

from __future__ import annotations

import typing as ty
from re import fullmatch

from .main import API, Sqlite3ApiError


class Table(object):
    """
    Родительский класс для создания таблиц
    """

    id: int = None

    def __init__(self, db_path: str = None, _api: API = None, **kwargs: [str, ty.Any]):
        """
        :param db_path: Путь к базе данных.
        :param _api: Sqlite3 Api.
        """

        self.__api = _api or API(db_path)
        self.__dict__.update(**kwargs)

    def save(self) -> str:
        """
        Функция, сохраняющая все изменения.
        :return: "Successfully"
        """

        return self.__api.save(self)

    def update(self, **fields: [str, ty.Any]) -> str:
        """
        Функция, обновляющая значения полей и автоматически сохраняющая изменения.
        :param fields: {<название поля>: <значение>, ...}
        :return: "Successfully"
        """

        self.__dict__.update(**fields)
        return self.save()

    def filter(
        self,
        return_type: ty.Literal["visual", "classes"] = "classes",
        return_list: ty.Literal[True, False] = False,
        **where: [str, ty.Any],
    ):
        """
        Функция, выбирающая данные из таблицы на основе указанных параметров.
        :param return_type:
            Для "classes" - вернёт объект класса таблицы.
            Для "visual" - вернёт данные в том виде,
                в котором они хранятся в базе данных.
        :param return_list:
            Для True - вернёт список объектов независимо от их количества.
        :param where: Параметры сортировки.
        :return: Объект класса таблицы.
        """

        if data := self.__api.filter(
            table_name=self.table_name, table_fields=self.get_fields(), **where
        ):
            if return_type == "visual":
                if return_list:
                    return data

                return data[0] if len(data) == 1 else data

            else:
                data = [self.get_class(obj) for obj in data]
                if return_list:
                    return data

                return data[0] if len(data) == 1 else data

        return [] if return_list else None

    def insert(self, **fields: [str, ty.Any]) -> str:
        """
        Функция, добавляющая данные в таблицу.
        :param fields: {<название поля>: <значение>, ...}.
        :return: "Successfully"
        """

        table_fields = {
            field: getattr(self.__class__, field)
            for field in self.get_fields()
            if hasattr(self.__class__, field)
        }  # Получаем значения по умолчанию
        table_fields.update(**fields)

        if len(_fields := set(table_fields) - set(self.get_fields())):
            raise Sqlite3ApiError(
                f"В таблице `{self.table_name}` не найдены поля: "
                f'{", ".join(_fields)}.'
            )

        if len(_fields := set(self.get_fields()) - set(table_fields)):
            raise Sqlite3ApiError(
                f'Не переданы значения для полей: {", ".join(_fields)}.'
            )

        return self.__api.insert(table_name=self.table_name, **table_fields)

    def create_table(self) -> str:
        """
        Функция, создающая таблицу в базе данных.
        :return: "Successfully"
        """

        return self.__api.create_table(table_name=self.table_name, **self.get_fields())

    def add_field(self, field_name: str, start_value: ty.Any = None) -> str:
        """
        Функция, добавляющая поле в таблицу.
        :param field_name: Название нового поля.
        :param start_value: Значение нового поля.
        :return: "Successfully"
        """

        if not (field_type := self.get_fields().get(field_name)):
            raise Sqlite3ApiError(
                f"Поле `{field_name}` не найдено "
                f"в классе таблицы `{self.table_name}`."
            )

        if start_value is None:
            if (start_value := vars(self.__class__).get(field_name)) is None:
                raise Sqlite3ApiError(
                    f"Не указано значение по умолчанию для поля `{field_name}`."
                )

        return self.__api.add_field(
            table_name=self.table_name,
            field_name=field_name,
            field_type=field_type,
            start_value=start_value,
        )

    def get_class(self, data: ty.Tuple[ty.Any, ...]) -> Table:
        """
        Получаем объект, основываясь на данных, полученных из бд.
        :param data: Данные об объекте.
        :return: Объект класса таблицы.
        """

        fields = dict(id=data[0], **dict(zip(self.get_fields(), data[1:])))
        return self.__class__(**fields, _api=self.__api)

    @classmethod
    def get_fields(cls) -> ty.Dict[str, str]:
        """
        Функция, возвращающая поля и их типы данных.
        """

        types = {
            "str": "TEXT",
            "int": "INTEGER",
            "float": "REAL",
            "dict": "dict",
            "list": "list",
        }
        fields = {}
        for field_name, field_type in ty.get_type_hints(cls).items():
            field_type_name = field_type.__name__.lower()
            fields[field_name] = types.get(field_type_name) or field_type_name
        del fields["id"]
        return fields

    @property
    def table_name(self) -> str:
        """
        Название таблицы.
        """

        return self.__class__.__name__.lower()

    @property
    def api(self) -> API:
        """
        Sqlite3 Api.
        """

        return self.__api

    def __repr__(self):
        return "{table_name} OBJECT\n{fields}".format(
            table_name=self.table_name.upper(),
            fields="\n".join(
                f"{k}={v}"
                for k, v in vars(self).items()
                if not fullmatch(r"_.+__.+", k)
            ),
        )
