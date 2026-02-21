from typing import Dict, Any

from .api import Sqlite3

# Постфиксы для выражения действий при вызове метода `filter`.
# filter(table_name, filed_no=1, filed_2_egt=5)
# Получится запрос “SELECT * FROM table_name WHERE filed != 0 AND field_2 >= 5”
OPT_MAP = {
    "gt": ">",
    "lt": "<",
    "no": "!=",
    "egt": ">=",
    "elt": "<=",
}


class Sqlite3ApiError(Exception):
    """
    Ошибки, которые возникают при работе API.
    """


class API(Sqlite3):
    def __init__(self, db_path: str = None):
        self._active = False

        if db_path:
            Sqlite3.__init__(self, db_path)
            self._active = True

    def save(self, *table_classes) -> str:
        """
        Функция, сохраняющая все изменения.
        :param table_classes: Объекты классов таблиц.
        :type table_classes: Table.
        :return: "Successfully"
        """

        self._check_active()

        if len(table_classes) == 0:
            raise Sqlite3ApiError("Не переданы классы таблиц.")

        for obj in table_classes:
            self.execute(
                "UPDATE %s SET %s WHERE id=?"
                % (
                    obj.table_name,
                    ", ".join(map(lambda x: f"{x}=?", obj.get_fields())),
                ),
                *(
                    obj.__dict__[field_name]
                    for field_name, field_type in obj.get_fields().items()
                ),
                obj.id,
            )
        self.commit()

        return "Successfully"

    def filter(
        self,
        table_name: str,
        table_fields: Dict[str, str] = None,
        **where: Dict[str, Any],
    ):
        """
        Функция, выбирающая данные из таблицы на основе указанных параметров.
        :param table_name: Название таблицы, с которой мы работаем.
        :param table_fields: Поля, присутствующие в таблице, и их типы данных.
        :param where: Параметры сортировки.
        """

        self._check_active()
        conditions = []
        values = []

        # Формирование параметров сортировки
        for key, value in where.items():
            field = key
            opt = "="
            if (index := key.rfind("_")) > 0:
                try:
                    opt = OPT_MAP[key[index + 1 :]]
                    field = key[:index]
                except KeyError:
                    pass

            if table_fields and field not in table_fields and field != "id":
                raise Sqlite3ApiError(
                    f"Поле `{field}` не найдено в таблице `{table_name}`"
                )

            conditions.append(f"{field} {opt} ?")
            values.append(value)

        # Получение данных
        if conditions:
            return self.fetchall(
                "SELECT * FROM '%s' WHERE %s" % (table_name, " and ".join(conditions)),
                *values,
            )
        else:
            return self.fetchall("SELECT * FROM '%s'" % table_name)

    def insert(self, table_name: str, **fields: Dict[str, Any]) -> str:
        """
        Функция, добавляющая данные в таблицу.
        :param table_name: Название таблицы, с которой мы работаем.
        :param fields: {<название поля>: <значение>, ...}.
        :return: "Successfully"
        """

        self._check_active()

        self.execute(
            "INSERT INTO %s (%s) VALUES (%s)"
            % (table_name, ", ".join(fields.keys()), ", ".join(["?"] * len(fields))),
            *fields.values(),
        )

        self.commit()

        return "Successfully"

    def add_field(
        self, table_name: str, field_name: str, field_type: str, start_value: Any
    ) -> str:
        """
        Функция, добавляющая поле в таблицу.
        :param table_name: Название таблицы, с которой мы работаем.
        :param field_name: Название нового поля.
        :param field_type: Тип данных.
        :param start_value: Значение нового поля.
        :return: "Successfully"
        """

        self._check_active()

        self.execute(
            "ALTER TABLE '%s' ADD %s %s" % (table_name, field_name, field_type)
        )  # Добавление нового поля
        self.execute(
            "UPDATE '%s' SET %s=?" % (table_name, field_name), str(start_value)
        )  # Изменение стартового значения
        self.commit()

        return "Successfully"

    def create_table(self, table_name: str, **fields: [str, str]) -> str:
        """
        Функция, создающая таблицу в базе данных.
        :param table_name: Название таблицы.
        :param fields: {<название поля>: <тип данных>, ...}
        :return: "Successfully"
        """

        self._check_active()

        fields = [
            f"{field_name} {field_type}"
            for field_name, field_type in fields.items()
            if not field_name.startswith("_")
        ]

        self.execute(
            "CREATE TABLE IF NOT EXISTS %s "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, %s)"
            % (table_name, ", ".join(fields))
        )

        return "Successfully"

    def _check_active(self):
        if not self._active:
            raise Sqlite3ApiError("Файл базы данных не инициализирован.")

    @property
    def cursor(self):
        """
        Sqlite3 cursor.
        """

        self._check_active()
        return self._cursor

    def __del__(self):
        if self._active:
            self.close()
