from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Tariff(BaseCategory):
    """Тарифы"""

    @api_method(int)
    def add(self, *, name: str, billing_id: int, billing_tariff_id: int) -> ApiRetSData[int]:
        """Добавление тарифа

            Обязательные параметры:
                name - наименование тарифа
                billing_id - id биллинга
                billing_tariff_id - id тарифа в стороннем биллинге
        """
        ...
    
    @api_method(int)
    def add_group(self, *, name: str) -> ApiRetSData[int]:
        """Добавление группы тарифов

            Обязательные параметры:
                name - наименование
        """
        ...
    
    @api_method(bool)
    def add_tariff_in_group(self, *, tariff_id: int, group_id: int) -> ApiRetBool:
        """Добавление тарифа в группу тарифов

            Обязательные параметры:
                tariff_id - id тарифа
                group_id - id группы тарифов
        """
        ...
        
    @api_method(bool)
    def delete_group(self, *, id: int) -> ApiRetBool:
        """Удаление группы тарифов

            Обязательные параметры:
                id - id группы
        """
        ...
    
    @api_method(bool)
    def edit_group(self, *, id: int, name: str) -> ApiRetBool:
        """Редактирование группы тарифов

            Обязательные параметры:
                id - id группы
                name - наименование
        """
        ...
    
    @smart_model
    class Get(BaseModel):
        id: int
        name: vStr
        amount: int
        billing_id: int
        billing_uuid: vStr
        tariff_group_id: List[int]
        service_type: Any

    @api_method(Get)
    def get(self, *, billing_id: int = None, name: str = None) -> ApiRetSData[Get]:
        """Список тарифов

            Дополнительные параметры:
                billing_id - id биллинга
                name - наименование тарифа
        """
        ...

    @smart_model
    class Get_group(BaseModel):
        id: int
        name: vStr
        tariff_id: List[int]
        building_id: List[int]

    @api_method(Get_group)
    def get_group(self, *, id: int = None) -> ApiRetSData[Get_group]:
        """Информация о группах тарифов

            Дополнительные параметры:
                id - id группы (можно через запятую)
        """
        ...

    @api_method(bool)
    def remove_tariff_from_group(self, *, tariff_id: int, group_id: int) -> ApiRetBool:
        """Исключение тарифа из группы тарифов

            Обязательные параметры:
                tariff_id - id тарифа
                group_id - id группы тарифов
        """
        ...
    