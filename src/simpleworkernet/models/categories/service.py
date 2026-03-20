from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Service(BaseCategory):
    """Дополнительные услуги"""

    @smart_model
    class Get(BaseModel):
        id: int
        name: vStr
        cost: int
        billing_id: int

    @api_method(Get)
    def get(self, *, id: int | str = None) -> ApiRetSData[Get]:
        """Список дополнительных услуг

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id услуги (можно через запятую)
        """
        ...