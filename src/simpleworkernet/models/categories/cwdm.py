from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Cwdm(BaseCategory):
    """CWDM"""

    link_cat = 'cwdm'

    @smart_model
    class Get(BaseModel):
        id: int
        name: vStr
        node_id: int
        description: vStr
        date_add: vStr
        is_planned: bool
        inventory_id: int
        location: vStr

    @api_method(Get)
    def get(self, *, id: int | str = None, node_id: int | str = None) -> ApiRetSData[Get]:
        """Список CWDM

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id объектов (можно через запятую)
                node_id - id объектов размещения (можно через запятую)
        """
        ...
