from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Splitter(BaseCategory):
    """Делители/Уплотнители"""

    link_cat = 'splitter'

    @smart_model
    class Get(BaseModel):
        id: int
        node_id: int
        port_count_in: int
        port_count_out: int
        description: vStr
        date_add: vStr
        is_planned: int
        inventory_id: int

    @api_method(Get)
    def get(self, *, id: int | str = None) -> ApiRetSData[Get]:
        """Список объектов

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id объектов (можно через запятую)
        """
        ...
    
    @api_method(int)
    def add(self, *, node_id: int, port_count_in: int, port_count_out: int, description: str = None, is_planned: vFlag = None) -> ApiRetSData[int]:
        """Добавление объекта

            Обязательные параметры:
                node_id - id объекта размещения
                port_count_in - количество входящих портов
                port_count_out - количество исходящих портов
            Дополнительные параметры:
                description - заметки
                is_planned - флаг - объект только запланирован
        """
        ...
    
    @api_method(bool)
    def edit(self, *, id: int, description: str = None, is_planned: vFlag = None) -> ApiRetBool:
        """Редактирование объекта

            Обязательные параметры:
                id - id объекта
            Дополнительные параметры:
                description - заметки
                is_planned - флаг - объект только запланирован
        """
        ...
        
    @api_method(bool)
    def delete(self, *, id: int) -> ApiRetBool:
        """Удаление объекта

            Обязательные параметры:
                id - id объекта
        """
        ...