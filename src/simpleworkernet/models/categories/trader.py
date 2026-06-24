from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, BaseItem, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Trader(BaseCategory):
    """Поставщики"""

    link_cat = 'trader/show?id='

    @api_method(int)
    def add(self, *, name: str) -> ApiRetSData[int]:
        """Добавление 

            Обязательные параметры:
                name - наименование
        """
        ...
    
    @api_method(bool)
    def delete(self, *, id: int) -> ApiRetBool:
        """Удаление 

            Обязательные параметры:
                id - id объекта
        """
        ...
    
    @api_method(bool)
    def edit(self, *, id: int, name: str) -> ApiRetBool:
        """Редактирование 

            Обязательные параметры:
                id - id объекта
                name - наименование
        """
        ...
    
    @smart_model
    class Get(BaseModel):
        id: int
        name: vStr
            
    @api_method(Get)
    def get(self, *, id: int | str = None) -> ApiRetSData[Get]:
        """Список поставщиков

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id объектов (можно через запятую)
        """
        ...
    