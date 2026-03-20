from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Attach(BaseCategory):
    """Действие с прикрепляемыми файлами"""

    @overload
    def add(self, *, object_type: Literal['cable_line','customer','node','task','task_comment','inventory'],
        object_id: int, comment_id: int = None, src: str = None, employee_id: int = None, name: str = None, comment: str = None, src_id: int = None): ...
    @overload
    def add(self, *, object_type: Literal['cable_line','customer','node','task','task_comment','inventory'],
        object_id: int, comment_id: int = None, uuid: str = None, employee_id: int = None, name: str = None, comment: str = None, src_id: int = None): ...

    @api_method()
    def add(self, *, object_type: Literal['cable_line','customer','node','task','task_comment','inventory'],
        object_id: int, comment_id: int = None, src: str = None, uuid: str = None, employee_id: int = None, name: str = None, comment: str = None, src_id: int = None):
        """Добавление файла к объекту

            Обязательные параметры:
                object_type - тип объекта [cable_line|customer|node|task|task_comment|inventory]
                object_id - id объекта, к которому прикреплять файл
                comment_id - id комментария к заданию, к которому прикреплять файл (для типа task_comment)
                ЛИБО src - url к файлу, который требуется загрузить и прикрепить
                ЛИБО uuid - uuid с иным файлом, который уже загружен и который требуется прикрепить к иному объекту
            Необязательные параметры:
                employee_id - id сотрудника, от имени которого добавить файл
                name - имя файла (произвольный текст)
                comment - заметки/описание к файлу
                src_id - id метода/типа загрузки файла (произвольно, на усмотрение клиента)
        """
        ...

    @api_method()
    def delete(self, *, uuid: str, name: str):
        """Удаление файла

            Обязательные параметры:
                uuid - uuid файла
                name - имя файла (без путей)
        """
        ...
    
    @api_method()
    def get(self, *, uuid: str = None, ext_name: str = None, int_name: str = None, object_type: Literal['cable_line','customer','node','task','task_comment','inventory'] = None, object_id: int = None):
        """Получение информации

            Обязательные параметры (что-то одно):
                uuid - uuid файла (можно через запятую)
                ext_name - внешнее имя файла (исходное)
                int_name - внутреннее имя файла (как хранится в системе)
                object_type - тип объекта [cable_line|customer|inventory|node|task|task_comment] (используется совместно с object_id)
                object_id - id объекта, к которому прикреплён файл (используется совместно с object_type)
        """
        ...
    
    @api_method()
    def get_file(self, *, uuid: str):
        """Вывод содержимого файла (в бинарном виде)

            Обязательные параметры:
                uuid - uuid файла
        """
        ...
    
    @api_method()
    def get_file_temporary_link(self, *, uuid: str):
        """Предоставление прямой временной ссылки на загрузку файла

            Обязательные параметры:
                uuid - uuid файла
        """
        ...