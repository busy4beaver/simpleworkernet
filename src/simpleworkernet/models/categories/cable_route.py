from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Cable_route(BaseCategory):
    """Кабельные трассы и каналы"""

    link_cat = 'duct'

    class In_type(IntEnum):
        """ID типов начальных и конечных объектов трассы"""
        customer=1
        building=19
        node=22

    @api_method(int)
    def add_route(self, *, object_first_type: In_type, object_first_id: int,
                object_second_type: In_type, object_second_id: int,
                name: str = None, comment: str = None, length: int = None, date_install: str = None) -> ApiRetSData[int]:
        """Добавление кабельной трассы

            Обязательные параметры:
                object_first_type - тип начального объекта
                object_first_id - id начального объекта
                object_second_type - тип конечного объекта
                object_second_id - id конечного объекта
            Дополнительные параметры:
                name - наименование
                comment - заметка
                length - длина
                date_install - дата фактической установки
        """
        ...

    @api_method(int)
    def add_duct(self, *, cable_route_id: int, number: int = None, comment: str = None, diameter: int = None, date_install: str = None) -> ApiRetSData[int]:
        """Добавление кабельного канала

            Обязательные параметры:
                cable_route_id - id кабельной трассы
            Дополнительные параметры:
                number - номер
                comment - заметка
                diameter - диаметр
                date_install - дата фактической установки
        """
        ...

    @smart_model
    class Get_route(BaseModel):
        id: int
        name: vStr
        object_first_type: vStr
        object_first_id: int
        object_second_type: vStr
        object_second_id: int
        comment: vStr | None
        owner_id: int | None
        length: int | None
        date_add: vStr
        date_install: vStr | None

    @api_method(Get_route)
    def get_route(self, *, id: int | str = None) -> ApiRetSData[Get_route]: 
        """Список кабельных трасс

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id объектов (можно через запятую)
        """
        ...

    @smart_model
    class GetDuct(BaseModel):
        id: int
        cable_route_id: int
        number: int
        comment: vStr | None
        diameter: int | None
        date_add: vStr
        date_install: vStr | None
        content: List

    @api_method(GetDuct)
    def get_duct(self, *, id: int | str = None, cable_route_id: int | str = None) -> ApiRetSData[GetDuct]:
        """Список кабельных каналов

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id объектов (можно через запятую)
                cable_route_id - id кабельной трассы (можно через запятую)
        """
        ...
