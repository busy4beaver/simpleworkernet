from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Cross(BaseCategory):
    """ODF/Кроссы"""

    link_cat = 'cross'

    @api_method(str)
    def add(self, *, node_id: int, port_count: int, description: str = None, is_planned: vFlag = None) -> ApiRetSData[int]:
        """Добавление кросса

            Обязательные параметры:
                node_id - id объекта размещения
                port_count - количество портов/адаптеров
            Дополнительные параметры:
                description - заметки
                is_planned - флаг - планируемый объект
        """
        ...
    
    # @api_method(None)
    # def edit_adapter(self, *, id: str, side: int, number: int, signature: str = None):
    #     """Изменение свойств адаптера

    #         Обязательные параметры:
    #             id - id объекта
    #             side - сторона [1|2]
    #             number - номер адаптера
    #         Дополнительные параметры:
    #             signature - текст подписи
    #     """
    #     ...

    @smart_model
    class Get_list(BaseModel):
        id: vStr
        node_id: int
        port_count: int
        comment: vStr
        number: vStr
        is_planned: int

    @api_method(Get_list)
    def get_list(self, *, id: str = None, node_id: int = None) -> ApiRetSData[Get_list]:
        """Список ODF/кроссов
            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id объектов (можно через запятую)
                node_id - id объектов размещения (можно через запятую)
        """
        ...