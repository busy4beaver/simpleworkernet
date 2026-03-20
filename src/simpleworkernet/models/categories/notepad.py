from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Notepad(BaseCategory):
    """Блокнот"""

    @smart_model
    class Get_chapter(BaseModel):
        id: int
        name: vStr
        @smart_model
        class Item(BaseModel):
            id: int
            name: vStr
        fields: List[Item]

    @api_method(Get_chapter)
    def get_chapter(self) -> ApiRetSData[Get_chapter]:
        """Информация о разделах блокнота"""
        ...
    
    @smart_model
    class Get_note(BaseModel):
        id: int
        chapter_id: int
        date_edit: vStr
        fields: List[vStr]

    @api_method(Get_note)
    def get_note(self, *, id: int = None, chapter_id: int = None) -> ApiRetSData[Get_note]:
        """Информация о записях

            Обязательные параметры:
                нет
            Дополнительные параметры:
                id - id записи
                chapter_id - id раздела
        """
        ...