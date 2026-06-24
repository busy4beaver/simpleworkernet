from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, BaseItem, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Vlan(BaseCategory):
    """Vlan"""

    link_cat = 'vlan/show?vid='
    
    @api_method(int)
    def add(self, *, vid: int, name: str, comment: str = None) -> ApiRetSData[int]:
        """Добавление vlan

            Обязательные параметры:
                vid - vlan id
                name - наименование
            Необязательные параметры:
                comment - заметки
        """
        ...
    
    @api_method(bool)
    def delete(self, *, vid: int) -> ApiRetBool:
        """Удаление vlan

            Обязательные параметры:
                vid - vlan id
        """
        ...
    
    @api_method(bool)
    def edit(self, *, vid: int, name: str = None, comment: str = None) -> ApiRetBool:
        """Редактирование vlan

            Обязательные параметры:
                vid - vlan id
            Необязательные параметры:
                name - наименование
                comment - заметки
        """
        ...
    
    @smart_model
    class Get_list(BaseModel):
        vid: int
        name: vStr
        comment: vStr
        devices: list = None
            
    @api_method(Get_list)
    def get_list(self, *, vid: int = None) -> ApiRetSData[Get_list]:
        """Получение списка vlan

            Обязательные параметры:
                Нет
            Необязательные параметры:
                vid - VlanID (в этом случае будут указан список устройств и портов с этим Vlan)
        """
        ...
    