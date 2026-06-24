from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, BaseItem, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Vehicle(BaseCategory):
    """Автотранспорт"""
    
    link_cat = 'transport'

    @smart_model
    class Get(BaseModel):
        id: int
        brand: vStr
        model: vStr
        reg_number: vStr
        gps_id: vStr
        @smart_model
        class Gps_activity(BaseModel):
            date: vStr
        gps_activity: Gps_activity
        date_add: dict
            
    @api_method(Get)
    def get(self, *, id: int | str = None) -> ApiRetSData[Get]:
        """Список транспорта

            Необязательные параметры:
                id - ID транспорта (можно через запятую)
        """
        ...
    