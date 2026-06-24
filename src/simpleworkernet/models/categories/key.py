from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method

class Key(BaseCategory):
    """Ключи"""

    link_cat = 'keys'

    @overload
    def add(self, *, name: str, building_id: int = None, comment: str = None): ...
    @overload
    def add(self, *, building_id: int, name: str = None, comment: str = None): ...
    @overload
    def add(self, *, name: str, building_id: int, comment: str = None): ...

    @api_method(int)
    def add(self, *, name: str = None, building_id: int = None, comment: str = None) -> ApiRetSData[int]:
        """Добавление

            Обязательные параметры:
                нет (но должно быть указано либо name либо building_id либо и то и другое)
            Обязательные параметры:
                name - "Название" ключа
                building_id - ID здания
                comment - Заметки
        """
        ...
    
    @smart_model
    class Get_list(BaseModel):
        id: int
        name: vStr
        comment: vStr | None
        building_id: int
        employee_id: int | None

    @api_method(Get_list)
    def get_list(self, *, id: int | str = None, staff_id: int | str = None) -> ApiRetSData[Get_list]:
        """Ключи

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - ID ключа (можно через запятую)
                staff_id - ID сотрудника, на котором учитываются ключи (можно через запятую)
        """
        ...