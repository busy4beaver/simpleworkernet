from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Call(BaseCategory):
    """Звонки"""

    @api_method(int)
    def add(self, *, number: str, date_add: str = None, phone_system_uuid: str = None, answer_number: str = None) -> ApiRetSData[int]:
        """Создание записи о звонке

            Обязательные параметры:
                number - входящий номер вызова
            Необязательные параметры:
                date_add - дата вызова
                phone_system_uuid - ID вызова во внешней системе телефонии
                answer_number - вызываемый номер
        """
        ...

    @smart_model
    class Get(BaseModel):
        id: int
        date_add: vStr
        phone: vStr
        asterisk_id: vStr
        customer_id: int | None
        answer_phone: vStr | None
        additional_data: List

    @api_method(Get)
    def get(self, date_from: str = None, date_to: str = None) -> ApiRetSData[Get]:
        """Список звонков

            Обязательные параметры:
                нет
            Необязательные параметры:
                date_from - дата и время звонка (с)
                date_to - дата и время звонка (до)
        """
        ...

    @overload
    def hangup(self, *, id: int, record_url: str = None) -> ApiRetSData[int]:  ...
    @overload
    def hangup(self, *, phone_system_uuid: str, record_url: str = None) -> ApiRetSData[int]:  ...

    @api_method(int)
    def hangup(self, *, id = None, phone_system_uuid = None, record_url = None) -> ApiRetSData[int]: 
        """Фиксация факта окончания звонка

            Обязательные параметры:
                id - ID вызова
                ЛИБО
                phone_system_uuid - ID вызова во внешней системе телефонии
            Необязательные параметры:
                record_url - ссылка на запись вызова
        """
        ...

    @overload
    def transfer_call(self, *, id: int, answer_number: str) -> ApiRetSData[int]: ...
    @overload
    def transfer_call(self, *, phone_system_uuid: str, answer_number: str) -> ApiRetSData[int]: ...

    @api_method(None)
    def transfer_call(self, *, id = None, phone_system_uuid = None, answer_number = None) -> ApiRetSData[int]:
        """Передача информации и звонке другому сотруднику

            Обязательные параметры:
                id - ID вызова
                ЛИБО
                phone_system_uuid - ID вызова во внешней системе телефонии
            Необязательные параметры:
                answer_number - вызываемый номер
        """
        ...