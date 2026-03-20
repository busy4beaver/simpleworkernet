from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, CollapsedField, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Setting(BaseCategory):
    """Настройка"""

    @api_method()
    def get(self, *, id: int | str = None):
        """Получение значений параметров настройки

            Необязательные параметры:
                id - ID параметров настройки (через запятую)
        """
        ...
    
    @smart_model
    class Mark_show(BaseModel):
        id: int
        name: vStr
        color: vStr
        onmapdef: int

    @api_method(Mark_show)
    def mark_show(self, *, object_type: Literal['customer'] = None) -> ApiRetSData[Mark_show]:
        """Вывод списка меток/слоёв для объектов

            Необязательные параметры:
                object_type - тип объектов [customer]
        """
        ...

    @api_method(int)
    def mark_add(self, *, name: str, color: str = None, line_type = None, is_on_map_by_default: int = None, type_array = None) -> ApiRetSData[int]:
        """Добавление метки/слоя для оборудования/объектов

            Обязательные параметры:
                name - наименование
            Необязательные параметры:
                color - цвет
                line_type - тип линии
                is_on_map_by_default - флаг отображения на карте по-умолчанию
                type_array - массив с типами объектов для меток
        """
        ...

    @api_method(bool)
    def mark_edit(self, *, id: int, name: str = None, color: str = None, line_type = None, is_on_map_by_default: int = None, type_array = None) -> ApiRetBool:
        """Редактирование метки

            Обязательные параметры:
                id - ID метки
            Необязательные параметры:
                name - наименование
                color - цвет
                line_type - тип линии
                is_on_map_by_default - флаг отображения на карте по-умолчанию
                type_array - массив с типами объектов для меток
        """
        ...
    
    @api_method(bool)
    def mark_delete(self, *, id: int) -> ApiRetBool:
        """Удаление метки

            Обязательные параметры:
                id - ID метки
        """
        ...