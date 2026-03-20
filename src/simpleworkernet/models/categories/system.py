from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class System(BaseCategory):
    """Системная информация и операции"""

    @smart_model
    class Get_system_info(BaseModel):
        erp_version: vStr
        date_time_unix: int
        date_time_string: vStr
        os: vStr
        php_version: vStr

    @api_method(Get_system_info)
    def get_system_info(self) -> ApiRetSData[Get_system_info]:
        """Получение системной информации"""
        ...

    @api_method()
    def send_email(self, *, recipient: str, subject: str, body: str, is_html: vFlag = None):
        """Отправка e-mail

            Обязательные параметры:
                recipient - адрес получателя
                subject - тема
                body - текст
            Необязательные параметры:
                is_html - флаг - тело сообщения в html-формате
        """
        ...
    