from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Sms(BaseCategory):
    """SMS-сообщения"""

    @api_method(int)
    def send(self, *, number: str, msg: str, customer_id: int = None) -> ApiRetSData[int]:
        """Отправка сообщения

            Обязательные параметры:
                number - номер телефона
                msg - текст сообщения
            Необязательные параметры:
                customer_id - ID абонента, к которому прикрепить SMS
        """
        ...

    @smart_model
    class Status(BaseModel):
        id: int
        status_name: vStr
        time_add: vStr

    @api_method(Status)
    def status(self, *, id: int | str) -> ApiRetSData[Status]:
        """Информация о сообщения

            Обязательные параметры:
                id - ID сообщения (возможна подача нескольких значений через запятую)
        """
        ...
